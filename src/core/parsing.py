from __future__ import annotations
import re

# ---------------------------------------------------------------------------
# Adresse-parsing
# ---------------------------------------------------------------------------
# Dansk adresse-mønster: "Nørregade 5", "Vestervej 12B", "Markvej 3, 3. tv"
# Postnummer: 4 cifre (1000-9999 DK)
# By: ét eller flere ord med æøåÆØÅ og bindestreg
# ---------------------------------------------------------------------------

_POSTCODE_RE = re.compile(
    r"""
    (?P<street>[A-Za-zÆØÅæøå][A-Za-zÆØÅæøå\s\-\.]+?)   # vejnavn
    \s+
    (?P<num>\d+\s*[A-Za-z]?)                              # husnummer (+ evt. bogstav)
    [,\s]*
    (?:(?P<floor>\d+)\.\s*(?P<door>[a-zA-Z0-9\.]+)\s*)?  # etage + dør (valgfrit)
    [,\s]*
    (?P<postcode>\d{4})                                   # postnummer
    \s+
    (?P<city>[A-Za-zÆØÅæøå][A-Za-zÆØÅæøå\s\-]{1,40})   # by
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Alternativ: linje der begynder med "Adresse:", "Adress:", "Address:" osv.
_LABEL_RE = re.compile(
    r"(?:adresse|adress|address|ejendom|placering)\s*[:\-]\s*(.+)",
    re.IGNORECASE,
)

# Bare postnummer + by (fallback hvis fuld adresse mangler)
_POSTCODE_CITY_RE = re.compile(
    r"\b(\d{4})\s+([A-Za-zÆØÅæøå][A-Za-zÆØÅæøå\s\-]{1,40})\b"
)


def extract_address_from_text(text: str) -> str | None:
    """
    Forsøger 3 strategier i prioriteret rækkefølge:
    1) Fuld adresse: vejnavn + husnr + postnr + by
    2) Labelbaseret: "Adresse: ..."
    3) Bare postnr + by (zonebrug stadig mulig)
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    # Strategi 1: fuld adresse
    for line in lines:
        m = _POSTCODE_RE.search(line)
        if m:
            return line  # returner hele linjen (inkl. etage/dør info)

    # Strategi 2: label-baseret
    for line in lines:
        m = _LABEL_RE.match(line)
        if m:
            candidate = m.group(1).strip()
            # Validér at der er et postnummer i kandidaten
            if _POSTCODE_CITY_RE.search(candidate):
                return candidate
            # Ellers er det nok ikke en adresse
            # Men check næste linje — PDF'er splitter tit "Adresse:\nVej 5\n8000 By"
            idx = lines.index(line)
            if idx + 1 < len(lines):
                next_line = lines[idx + 1].strip()
                combined = candidate + " " + next_line
                if _POSTCODE_CITY_RE.search(combined):
                    return combined

    # Strategi 3: bare postnr + by (brugbar til zone-batching)
    for line in lines:
        m = _POSTCODE_CITY_RE.search(line)
        if m:
            return line

    return None


# ---------------------------------------------------------------------------
# m² parsing
# ---------------------------------------------------------------------------
_SQM_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(?:m2|m²|kvm|kvadratmeter)",
    re.IGNORECASE,
)

def extract_sqm(text: str) -> float | None:
    m = _SQM_RE.search(text)
    if not m:
        return None
    val = float(m.group(1).replace(",", "."))
    # Sanity check: 5-500 m² er realistisk for en lejlighed
    if 5 <= val <= 500:
        return val
    return None


# ---------------------------------------------------------------------------
# Rum/værelser parsing
# ---------------------------------------------------------------------------
_ROOMS_RE = re.compile(
    r"\b(\d+)\s*(?:værelses?|vær\.?|rum|rums?|rooms?)\b",
    re.IGNORECASE,
)

def extract_rooms(text: str) -> int | None:
    m = _ROOMS_RE.search(text)
    if not m:
        return None
    val = int(m.group(1))
    if 1 <= val <= 20:  # sanity
        return val
    return None


# ---------------------------------------------------------------------------
# Deadline parsing (P1 feature — bruges i c_plan_schedule.py)
# ---------------------------------------------------------------------------
_DEADLINE_RE = re.compile(
    r"""
    (?:senest|deadline|klar\s+(?:inden|til)|aflevering)\s*[:\-]?\s*
    (?:
        (?P<day>\d{1,2})[.\-/](?P<month>\d{1,2})(?:[.\-/](?P<year>\d{2,4}))?  # dd.mm.yyyy
        |
        uge\s*(?P<week>\d{1,2})                                                  # uge 12
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)

def extract_deadline(text: str) -> str | None:
    """
    Returnerer deadline som 'YYYY-MM-DD' streng hvis fundet, ellers None.
    """
    from datetime import datetime, date
    import isoweek  # pip install isoweek -- valgfri; graceful fallback

    m = _DEADLINE_RE.search(text)
    if not m:
        return None

    try:
        if m.group("week"):
            try:
                week = int(m.group("week"))
                year = date.today().year
                d = isoweek.Week(year, week).monday()
                return d.isoformat()
            except Exception:
                return None
        else:
            day = int(m.group("day"))
            month = int(m.group("month"))
            year_raw = m.group("year")
            year = int(year_raw) if year_raw else date.today().year
            if year < 100:
                year += 2000
            return date(year, month, day).isoformat()
    except Exception:
        return None
