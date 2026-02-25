from __future__ import annotations

from pathlib import Path
import shutil
import time
import win32com.client


def _shorten_attachment_path(src: Path, spool_dir: Path) -> Path:
    """
    Copy attachment to a short path to avoid Outlook/Windows long-path issues.
    Returns the new path (or original if already short enough).
    """
    spool_dir.mkdir(parents=True, exist_ok=True)

    # Outlook/COM kan fejle ved lange stier. Vi copier altid til spool med kort navn.
    # Brug timestamp + original filnavn, så vi undgår collisions.
    ts = int(time.time() * 1000)
    safe_name = f"{ts}_{src.name}".replace(" ", "_")
    dst = spool_dir / safe_name

    shutil.copy2(src, dst)
    return dst


def send_mail_outlook(
    to_emails: list[str],
    subject: str,
    body: str,
    attachment_paths: list[str] | None = None,
    cc_emails: list[str] | None = None,
    spool_dir: str = "data/out/_mail_attachments",
) -> None:
    """
    Sender en mail via lokal Outlook (COM) med vedhæftninger.
    Løser typiske issues:
      - relative paths -> absolut
      - long path / OneDrive path issues -> copy til kort spool path
    """
    outlook = win32com.client.Dispatch("Outlook.Application")
    mail = outlook.CreateItem(0)  # 0 = MailItem

    mail.To = ";".join([x.strip() for x in to_emails if x.strip()])
    if cc_emails:
        mail.CC = ";".join([x.strip() for x in cc_emails if x.strip()])

    mail.Subject = subject
    mail.Body = body

    attached_count = 0
    errors = 0

    if attachment_paths:
        spool = Path(spool_dir).resolve()

        for raw in attachment_paths:
            try:
                src = Path(raw).expanduser()
                # gør absolut (relativ til current working dir)
                if not src.is_absolute():
                    src = (Path.cwd() / src).resolve()
                else:
                    src = src.resolve()

                if not src.exists():
                    print(f"[OUTLOOK SEND] Attachment missing on disk: {src}")
                    errors += 1
                    continue

                # copy til kort spool path (meget vigtig ved lange stier)
                dst = _shorten_attachment_path(src, spool)

                mail.Attachments.Add(str(dst))
                attached_count += 1
                print(f"[OUTLOOK SEND] Attached: {dst}")

            except Exception as e:
                print(f"[OUTLOOK SEND] Attachment error for {raw}: {e}")
                errors += 1

    print(f"[OUTLOOK SEND] Attach summary: attached={attached_count}, errors={errors}")

    # Send
    mail.Send()
