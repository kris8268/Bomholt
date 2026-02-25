from __future__ import annotations
from datetime import datetime, timezone
from src.config import get_settings
from src.graph.auth import acquire_token
from src.graph.client import GraphClient
from src.graph.mail import list_messages_in_date_range, download_file_attachments
from src.core.storage import load_seen, save_seen, load_tasks, save_tasks, save_attachment, sha256_bytes
from src.core.pdf_extract import extract_text_from_pdf
from src.core.parsing import extract_address_from_text

def _month_window_iso(now_utc: datetime, day_start: int, day_end: int) -> tuple[str, str]:
    # Vindue i indeværende måned (UTC). Godt nok for MVP.
    y, m = now_utc.year, now_utc.month
    start = datetime(y, m, day_start, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(y, m, day_end + 1, 0, 0, 0, tzinfo=timezone.utc)
    return start.isoformat(), end.isoformat()

def run():
    s = get_settings()
    token = acquire_token(s)
    gc = GraphClient(token)

    now = datetime.now(timezone.utc)
    start_iso, end_iso = _month_window_iso(now, s.window_start_day, s.window_end_day)

    msgs = list_messages_in_date_range(gc, s.mailbox_upn, start_iso, end_iso, top=200)

    seen = load_seen()
    tasks = load_tasks()

    added = 0
    for m in msgs:
        # filter på afsender-domæne i kode
        frm = (m.from_address or "").lower()
        if "@" not in frm or not frm.endswith("@" + s.sender_domain):
            continue

        if not m.has_attachments:
            continue

        # dedupe pr message
        if m.id in seen:
            continue

        atts = download_file_attachments(gc, s.mailbox_upn, m.id)
        pdf_paths = []
        full_text_parts = []
        address = None

        for a in atts:
            # kun pdf i MVP
            if not a.filename.lower().endswith(".pdf"):
                continue
            h = sha256_bytes(a.content)
            # dedupe pr attachment-hash
            if seen.get("attachment_hashes", {}).get(h):
                continue

            p = save_attachment(m.id, a.filename, a.content)
            pdf_paths.append(str(p))

            text = extract_text_from_pdf(p)
            if text:
                full_text_parts.append(text)
                if address is None:
                    address = extract_address_from_text(text)

            seen.setdefault("attachment_hashes", {})[h] = {"message_id": m.id, "file": a.filename}

        full_text = "\n\n".join(full_text_parts).strip()
        if not full_text and not pdf_paths:
            continue

        task = {
            "task_id": f"{m.id}",
            "source_message_id": m.id,
            "received_at": m.received_datetime,
            "from": m.from_address,
            "subject": m.subject,
            "address": address or "(ukendt adresse endnu)",
            "pdf_paths": pdf_paths,
            "text_raw": full_text,  # MVP: dump alt her
            "status": "NEW",
        }
        tasks.append(task)
        seen[m.id] = {"received_at": m.received_datetime}
        added += 1

        # Flyt mail (KLAR, men udkommenteret i MVP)
        # if s.processed_folder_name:
        #     dest_id = find_folder_id_by_name(gc, s.mailbox_upn, s.processed_folder_name)
        #     if dest_id:
        #         move_message_to_folder(gc, s.mailbox_upn, m.id, dest_id)

    save_seen(seen)
    save_tasks(tasks)

    print(f"[A] Done. Added tasks: {added}. Total tasks in state: {len(tasks)}")

if __name__ == "__main__":
    run()
