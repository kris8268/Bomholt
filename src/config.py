from __future__ import annotations
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

def _get(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name)
    if v is None or v.strip() == "":
        return default
    return v

def _must(name: str) -> str:
    v = _get(name)
    if not v:
        raise RuntimeError(f"Missing env var: {name}")
    return v

@dataclass(frozen=True)
class Settings:
    # Graph (OPTIONAL hvis du kører Outlook lokalt)
    tenant_id: str | None
    client_id: str | None
    client_secret: str | None
    mailbox_upn: str | None

    # Mail filter / pipeline
    sender_domain: str
    processed_folder_name: str | None
    carpenter_emails: list[str]

    window_start_day: int
    window_end_day: int

    minutes_per_sqm: int
    setup_minutes: int
    fallback_minutes: int

    workday_start: str
    workday_end: str
    num_painters: int

def get_settings() -> Settings:
    processed = _get("PROCESSED_FOLDER_NAME")

    carpenters = (_get("CARPENTER_EMAILS", "") or "").strip()
    carpenter_emails = [x.strip() for x in carpenters.split(",") if x.strip()]

    return Settings(
        # Graph OPTIONAL
        tenant_id=_get("TENANT_ID"),
        client_id=_get("CLIENT_ID"),
        client_secret=_get("CLIENT_SECRET"),
        mailbox_upn=_get("MAILBOX_UPN"),

        # Required for Outlook/Graph both
        sender_domain=(_must("SENDER_DOMAIN")).lower(),
        processed_folder_name=processed,
        carpenter_emails=carpenter_emails,

        window_start_day=int(_get("WINDOW_START_DAY", "15") or "15"),
        window_end_day=int(_get("WINDOW_END_DAY", "18") or "18"),

        minutes_per_sqm=int(_get("MINUTES_PER_SQM", "12") or "12"),
        setup_minutes=int(_get("SETUP_MINUTES", "60") or "60"),
        fallback_minutes=int(_get("FALLBACK_MINUTES", "240") or "240"),

        workday_start=_get("WORKDAY_START", "07:00") or "07:00",
        workday_end=_get("WORKDAY_END", "15:00") or "15:00",
        num_painters=int(_get("NUM_PAINTERS", "6") or "6"),
    )
