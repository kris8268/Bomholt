from __future__ import annotations
from datetime import datetime
from pathlib import Path
import uuid

def _dt_to_ics(dt_iso: str) -> str:
    # dt_iso: "2026-02-19T08:00:00"
    dt = datetime.fromisoformat(dt_iso)
    return dt.strftime("%Y%m%dT%H%M%S")

def write_ics(events: list[dict], out_path: Path) -> None:
    """
    events: [{ "title": str, "start": iso, "end": iso, "description": str, "location": str }]
    """
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//job_mail_planner//EN",
        "CALSCALE:GREGORIAN",
    ]

    now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    for e in events:
        uid = str(uuid.uuid4())
        dtstart = _dt_to_ics(e["start"])
        dtend = _dt_to_ics(e["end"])
        title = (e.get("title") or "Opgave").replace("\n", " ")
        desc = (e.get("description") or "").replace("\n", "\\n")
        loc = (e.get("location") or "").replace("\n", " ")

        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{now}",
            f"DTSTART:{dtstart}",
            f"DTEND:{dtend}",
            f"SUMMARY:{title}",
            f"DESCRIPTION:{desc}",
            f"LOCATION:{loc}",
            "END:VEVENT",
        ]

    lines.append("END:VCALENDAR")
    out_path.write_text("\n".join(lines), encoding="utf-8")
