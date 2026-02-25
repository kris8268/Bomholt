from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import win32com.client

from src.config import get_settings
from src.core.storage import (
    load_seen,
    save_seen,
    load_tasks,
    save_tasks,
    save_attachment,
    sha256_bytes,
)
from src.core.pdf_extract import extract_text_from_pdf
from src.core.parsing import extract_address_from_text


DEBUG = True  # sæt til False når det virker


def _get_inbox_for_mailbox(namespace, mailbox_upn: str | None):
    """
    Forsøger at finde Inbox for den konto/store der matcher mailbox_upn.
    Fallback: default Inbox.
    """
    target = (mailbox_upn or "").strip().lower()
    if target:
        for store in namespace.Stores:
            try:
                name = (store.DisplayName or "").strip().lower()
            except Exception:
                name = ""
            if target in name:
                if DEBUG:
                    print(f"[OUTLOOK] Using store: {store.DisplayName}")
                return store.GetDefaultFolder(6)  # 6 = Inbox

    if DEBUG:
        print("[OUTLOOK] Using default Inbox (no matching store found)")
    return namespace.GetDefaultFolder(6)


def _restrict_messages_to_window(messages, start_day: int, end_day: int):
    """
    Restrict på indeværende måned og WINDOW_START_DAY..WINDOW_END_DAY.
    Outlook håndterer filtrering -> så vi undgår at samle gamle mails op.
    """
    now = datetime.now()
    start_dt = datetime(now.year, now.month, start_day, 0, 0, 0)
    end_dt = datetime(now.year, now.month, end_day, 23, 59, 59)

    # Outlook Restrict fungerer typisk bedst med dd/mm/yyyy HH:MM
    start_str = start_dt.strftime("%d/%m/%Y %H:%M")
    end_str = end_dt.strftime("%d/%m/%Y %H:%M")

    restriction = f"[ReceivedTime] >= '{start_str}' AND [ReceivedTime] <= '{end_str}'"
    if DEBUG:
        print(f"[OUTLOOK] Restrict: {restriction}")

    return messages.Restrict(restriction)


def _get_sender_smtp(msg) -> str:
    """
    Outlook COM kan give SenderEmailAddress i underlige formater (Exchange).
    Vi prøver derfor fallback til ExchangeUser.PrimarySmtpAddress hvis nødvendigt.
    """
    sender = str(getattr(msg, "SenderEmailAddress", "") or "").strip().lower()

    if "@" in sender:
        return sender

    # Fallback: Exchange
    try:
        exch = msg.Sender.GetExchangeUser()
        if exch:
            smtp = str(exch.PrimarySmtpAddress or "").strip().lower()
            if "@" in smtp:
                return smtp
    except Exception:
        pass

    return sender


def _has_pdf_attachment(attachments) -> bool:
    try:
        count = int(attachments.Count)
    except Exception:
        return False

    for i in range(1, count + 1):
        try:
            name = attachments.Item(i).FileName
            if name and str(name).lower().endswith(".pdf"):
                return True
        except Exception:
            continue
    return False


def run():
    s = get_settings()

    # Outlook COM
    outlook = win32com.client.Dispatch("Outlook.Application")
    namespace = outlook.GetNamespace("MAPI")
    inbox = _get_inbox_for_mailbox(namespace, getattr(s, "mailbox_upn", None))

    messages = inbox.Items
    messages.Sort("[ReceivedTime]", True)

    # KUN mails i indeværende måneds window
    restricted = _restrict_messages_to_window(messages, s.window_start_day, s.window_end_day)

    seen = load_seen()
    tasks = load_tasks()

    added = 0
    scanned = 0

    # Vi looper kun restricted set
    for msg in restricted:
        scanned += 1

        # ReceivedTime
        try:
            received = msg.ReceivedTime  # COM datetime
        except Exception:
            continue

        sender = _get_sender_smtp(msg)
        subject = str(getattr(msg, "Subject", "") or "")

        if DEBUG:
            print(f"DEBUG: {received} | sender_raw: {sender} | subject: {subject}")

        # domænefilter (kræver SENDER_DOMAIN)
        if s.sender_domain:
            if "@" not in sender or not sender.endswith("@" + s.sender_domain):
                continue

        # dedupe pr mail
        entry_id = str(getattr(msg, "EntryID", "") or "")
        if not entry_id:
            continue
        if entry_id in seen:
            continue

        attachments = msg.Attachments
        if not attachments or int(attachments.Count) == 0:
            continue

        # kun mails med mindst én pdf
        if not _has_pdf_attachment(attachments):
            continue

        full_text_parts: list[str] = []
        pdf_paths: list[str] = []
        address: str | None = None

        # Gem og parse alle PDF attachments
        for i in range(1, int(attachments.Count) + 1):
            try:
                att = attachments.Item(i)
                filename = str(att.FileName or "")
            except Exception:
                continue

            if not filename.lower().endswith(".pdf"):
                continue

            # SaveAsFile kræver en sti på disk først.
            # Vi gemmer i en midlertidig fil i current working dir, læser bytes, og gemmer i data-folder.
            tmp_name = filename.replace("/", "_").replace("\\", "_")
            tmp_path = os.path.join(os.getcwd(), tmp_name)

            try:
                att.SaveAsFile(tmp_path)
                content = Path(tmp_path).read_bytes()
            finally:
                # ryd temp
                try:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                except Exception:
                    pass

            h = sha256_bytes(content)

            # dedupe attachment
            if seen.get("attachment_hashes", {}).get(h):
                continue

            saved_path = save_attachment(entry_id, filename, content)
            pdf_paths.append(str(saved_path))

            text = extract_text_from_pdf(saved_path)
            if text:
                full_text_parts.append(text)
                if address is None:
                    address = extract_address_from_text(text)

            seen.setdefault("attachment_hashes", {})[h] = {"message_id": entry_id, "file": filename}

        full_text = "\n\n".join(full_text_parts).strip()

        # Hvis vi af en eller anden grund ikke fik PDF ud, så skip
        if not pdf_paths:
            continue

        task = {
            "task_id": entry_id,
            "source_message_id": entry_id,
            "received_at": received.strftime("%Y-%m-%dT%H:%M:%S"),
            "from": sender,
            "subject": subject,
            "address": address or "(ukendt adresse)",
            "pdf_paths": pdf_paths,
            "text_raw": full_text,  # MVP: dump alt her
            "status": "NEW",
        }

        tasks.append(task)
        seen[entry_id] = {"received_at": task["received_at"]}
        added += 1

        # Flyt mail (klar – udkommenteret indtil du vil bruge det)
        # NOTE: Outlook COM flyt kræver at vi finder/har en folder reference.
        # msg.Move(dest_folder)

    save_seen(seen)
    save_tasks(tasks)

    print(f"[OUTLOOK A] Scanned messages in window: {scanned}")
    print(f"[OUTLOOK A] Added tasks: {added}")
    print(f"[OUTLOOK A] Total tasks: {len(tasks)}")


if __name__ == "__main__":
    run()
