from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from src.config import get_settings
from src.core.storage import load_tasks, save_tasks, OUT_DIR
from src.core.rules import analyze
from src.core.outlook_send import send_mail_outlook


def run():
    s = get_settings()
    tasks = load_tasks()

    analyzed = 0
    carpenter_tasks = []

    # 1) Analyze NEW tasks
    for t in tasks:
        if t.get("status") != "NEW":
            continue

        text = t.get("text_raw", "") or ""
        a = analyze(text, s.minutes_per_sqm, s.setup_minutes, s.fallback_minutes)

        t["analysis"] = {
            "needs_carpenter": bool(a.needs_carpenter),
            "sqm": a.sqm,
            "rooms": a.rooms,
            "estimated_minutes": a.estimated_minutes,
        }
        t["status"] = "ANALYZED"
        analyzed += 1

        if a.needs_carpenter:
            carpenter_tasks.append(t)

    # 2) Build one carpenter email
    if carpenter_tasks:
        lines = []
        lines.append(f"Hej,")
        lines.append(f"")
        lines.append(
            f"Der er {len(carpenter_tasks)} opgave(r) denne periode der kræver tømrerarbejde."
        )
        lines.append("Se detaljer og jeres planlagte tidspunkter nedenfor.")
        lines.append("")
        lines.append("=" * 60)
        lines.append("")

        attach = []
        seen_attach: set[str] = set()

        for i, t in enumerate(carpenter_tasks, 1):
            an = t.get("analysis", {}) or {}
            addr = t.get("address") or "(ukendt adresse)"

            lines.append(f"{i}) {addr}")
            lines.append(f"   Modtaget:         {t.get('received_at')}")
            lines.append(f"   m²:               {an.get('sqm')} | Værelser: {an.get('rooms')}")
            lines.append(f"   Maler-estimat:    {an.get('estimated_minutes')} min")

            # Tilføj planlagte tømrer-blokke hvis planen allerede er kørt
            plan = t.get("plan", {}) or {}
            carp_blocks = [b for b in plan.get("blocks", []) if b.get("kind") == "carpenter"]
            if carp_blocks:
                lines.append(f"   Jeres tidspunkt(er):")
                for b in carp_blocks:
                    try:
                        sdt = datetime.fromisoformat(b["start"])
                        edt = datetime.fromisoformat(b["end"])
                        lines.append(
                            f"     • {sdt.strftime('%A d. %d/%m/%Y kl. %H:%M')} – {edt.strftime('%H:%M')}"
                        )
                    except Exception:
                        lines.append(f"     • {b.get('start')} – {b.get('end')}")
            else:
                # Plan ikke kørt endnu — lad vide at tidspunkt følger
                lines.append("   Tidspunkt:        Planlægges – du modtager besked.")

            pdfs = t.get("pdf_paths", []) or []
            for p in pdfs:
                if p and p not in seen_attach:
                    attach.append(p)
                    seen_attach.add(p)

            excerpt = (t.get("text_raw", "") or "").replace("\n", " ")
            lines.append(f"   Uddrag fra PDF:   {excerpt[:250]}...")
            lines.append("")

        lines.append("=" * 60)
        lines.append("PDF-bilag er vedhæftet denne mail.")
        lines.append("")
        lines.append("Med venlig hilsen")
        lines.append("Job Mail Planner")

        out_path = OUT_DIR / "carpenter_email_preview.txt"
        out_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"[B] Wrote carpenter mail preview: {out_path}")
        print(f"[B] Attachments collected: {len(attach)}")

        SEND = os.getenv("SEND_CARPENTER_MAIL", "1") == "1"

        if SEND:
            if not s.carpenter_emails:
                print("[B] CARPENTER_EMAILS er tom. Sender ikke.")
            else:
                subject = f"Tømreropgaver denne periode ({len(carpenter_tasks)} stk) — tidspunkter vedhæftet"
                body = "\n".join(lines)

                send_mail_outlook(
                    to_emails=s.carpenter_emails,
                    subject=subject,
                    body=body,
                    attachment_paths=attach,
                )

                now = datetime.now().isoformat(timespec="seconds")
                for t in carpenter_tasks:
                    t["status"] = "CARPENTER_REQUESTED"
                    t["carpenter_notified"] = True
                    t["carpenter_notified_at"] = now

                print("[B] Sent carpenter email via Outlook (with PDFs).")
        else:
            print("[B] SEND_CARPENTER_MAIL=0 → preview only (no send).")
    else:
        print("[B] No carpenter tasks found in analyzed batch.")

    save_tasks(tasks)
    print(f"[B] Done. Analyzed: {analyzed}")


if __name__ == "__main__":
    run()
