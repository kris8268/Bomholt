from __future__ import annotations
from src.graph.client import GraphClient

def create_calendar_event(
    gc: GraphClient,
    mailbox_upn: str,
    subject: str,
    start_iso: str,
    end_iso: str,
    body: str | None = None,
    location: str | None = None,
    timezone: str = "Europe/Copenhagen",
) -> dict:
    """
    Klar til senere: opret et Outlook kalender-event via Graph.
    (Ikke brugt i MVP endnu.)
    """
    payload = {
        "subject": subject,
        "start": {"dateTime": start_iso, "timeZone": timezone},
        "end": {"dateTime": end_iso, "timeZone": timezone},
    }
    if body:
        payload["body"] = {"contentType": "Text", "content": body}
    if location:
        payload["location"] = {"displayName": location}

    return gc.post(f"/users/{mailbox_upn}/events", json=payload)

def list_calendar_events(
    gc: GraphClient,
    mailbox_upn: str,
    start_iso: str,
    end_iso: str,
    top: int = 50,
) -> list[dict]:
    """
    Klar til senere: hent events i et interval.
    God til at undgå overlap når vi begynder at skrive til kalender.
    """
    params = {
        "$top": str(top),
        "$orderby": "start/dateTime asc",
        "$filter": f"start/dateTime ge '{start_iso}' and end/dateTime le '{end_iso}'",
    }
    data = gc.get(f"/users/{mailbox_upn}/events", params=params)
    return data.get("value", [])
