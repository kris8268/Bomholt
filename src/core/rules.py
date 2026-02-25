from __future__ import annotations
from dataclasses import dataclass
from src.core.parsing import extract_sqm, extract_rooms

@dataclass
class Analysis:
    needs_carpenter: bool
    sqm: float | None
    rooms: int | None
    estimated_minutes: int

# Alle varianter vi har set i PDF'er (med/uden stavefejl, med/uden æøå)
_CARPENTER_KEYWORDS = [
    "tømrerarbejde",
    "toemrerarbejde",
    "tømrer arbejde",
    "tømrer",         # bred match — fanger "tømrer skal", "kræver tømrer" osv.
    "tømrermester",
    # Gamle stavefejl fra tidligere version — beholdes for sikkerhedsskyld
    "tømmerarbejde",
    "toemmerarbejde",
]

def needs_carpenter(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in _CARPENTER_KEYWORDS)


def analyze(text: str, minutes_per_sqm: int, setup_minutes: int, fallback_minutes: int) -> Analysis:
    sqm = extract_sqm(text)
    rooms = extract_rooms(text)

    if sqm is None:
        est = setup_minutes + fallback_minutes
    else:
        est = setup_minutes + int(round(sqm * minutes_per_sqm))

    return Analysis(
        needs_carpenter=needs_carpenter(text),
        sqm=sqm,
        rooms=rooms,
        estimated_minutes=est,
    )
