from __future__ import annotations
import re

def postal_code(address: str | None) -> str | None:
    if not address:
        return None
    m = re.search(r"\b(\d{4})\b", address)
    return m.group(1) if m else None

def route_bucket(address: str | None) -> str:
    # Ultra MVP: bucket på første 1-2 cifre i postnr (giver “nord/syd-ish” i DK)
    pc = postal_code(address)
    if not pc:
        return "UNK"
    return pc[:2]
