from __future__ import annotations

import copy
import math
import re
from datetime import datetime, timedelta, date, time
from pathlib import Path

from src.config import get_settings
from src.core.storage import load_tasks, save_tasks, OUT_DIR
from src.core.routing import route_bucket
from src.core.ics import write_ics
from src.core.parsing import extract_deadline


# =========================
# QUICK TWEAK VARIABLES
# =========================
MAX_TASKS_PER_DAY_PER_PAINTER = 2
PAINTERS_PER_JOB = 1
CARPENTER_RATIO_OF_PAINTER = 0.33
PLAN_START_OFFSET_DAYS = 1
# =========================

POSTCODE_RE = re.compile(r"\b(\d{4})\b")


def parse_hhmm(s: str) -> tuple[int, int]:
    hh, mm = s.split(":")
    return int(hh), int(mm)


def iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def extract_zone(address: str | None) -> str:
    if not address:
        return "UNKNOWN"
    m = POSTCODE_RE.search(address)
    if m:
        return m.group(1)
    return route_bucket(address)


class Resource:
    """
    En ressource (maler/tømrer) med daglig arbejdstid.
    
    VIGTIGT: next_slots() er nu ikke-destruktiv (bruger ikke self.day/used direkte).
    Brug commit_slots() for at bekræfte en allokering.
    """
    def __init__(self, name: str, start_date: date, work_start: str, work_end: str):
        self.name = name
        self.start_date = start_date
        self.work_start_h, self.work_start_m = parse_hhmm(work_start)
        self.work_end_h, self.work_end_m = parse_hhmm(work_end)
        self.day_minutes = (
            (self.work_end_h * 60 + self.work_end_m)
            - (self.work_start_h * 60 + self.work_start_m)
        )
        self.day = 0
        self.used = 0

    def _base_dt(self, d: date) -> datetime:
        return datetime(d.year, d.month, d.day, self.work_start_h, self.work_start_m)

    def _compute_slots(
        self,
        minutes: int,
        earliest: datetime | None,
        day_offset: int,
        used_offset: int,
    ) -> tuple[list[tuple[datetime, datetime]], int, int]:
        """
        Beregner blokke uden at ændre self.
        Returnerer (blocks, final_day, final_used).
        """
        remaining = max(15, int(minutes))
        blocks: list[tuple[datetime, datetime]] = []
        cur_day = day_offset
        cur_used = used_offset

        while remaining > 0:
            d = self.start_date + timedelta(days=cur_day)
            base = self._base_dt(d)

            if earliest and earliest.date() == d:
                earliest_min = int((earliest - base).total_seconds() // 60)
                if earliest_min > cur_used:
                    cur_used = max(0, earliest_min)

            available = self.day_minutes - cur_used
            if available <= 0:
                cur_day += 1
                cur_used = 0
                continue

            chunk = min(remaining, available)
            start_dt = base + timedelta(minutes=cur_used)
            end_dt = start_dt + timedelta(minutes=chunk)

            blocks.append((start_dt, end_dt))
            cur_used += chunk
            remaining -= chunk

            if cur_used >= self.day_minutes and remaining > 0:
                cur_day += 1
                cur_used = 0

        return blocks, cur_day, cur_used

    def peek_slots(
        self,
        minutes: int,
        earliest: datetime | None = None,
        extra_day_offset: int = 0,
    ) -> list[tuple[datetime, datetime]]:
        """
        Beregn blokke UDEN at committe. Sikker at kalde flere gange.
        extra_day_offset: bruges til at skubbe fremad for MAX-check.
        """
        blocks, _, _ = self._compute_slots(
            minutes, earliest, self.day + extra_day_offset, self.used if extra_day_offset == 0 else 0
        )
        return blocks

    def commit_slots(
        self,
        minutes: int,
        earliest: datetime | None = None,
    ) -> list[tuple[datetime, datetime]]:
        """
        Beregn OG committe blokke. Kun kald denne når du er sikker på valget.
        """
        blocks, new_day, new_used = self._compute_slots(minutes, earliest, self.day, self.used)
        self.day = new_day
        self.used = new_used
        return blocks

    def advance_to_next_day(self) -> None:
        self.day += 1
        self.used = 0


def _get_deadline_dt(task: dict, workday_end: str) -> datetime | None:
    """
    Returner deadline som datetime (slutningen af dagen), eller None.
    """
    raw = task.get("deadline") or extract_deadline(task.get("text_raw", "") or "")
    if not raw:
        return None
    try:
        d = date.fromisoformat(raw)
        h, m = parse_hhmm(workday_end)
        return datetime(d.year, d.month, d.day, h, m)
    except Exception:
        return None


def run():
    s = get_settings()
    tasks = load_tasks()

    pool = [t for t in tasks if t.get("status") in ("ANALYZED", "CARPENTER_REQUESTED")]
    if not pool:
        out_txt = OUT_DIR / "plan_preview.txt"
        out_txt.write_text("Ingen tasks klar til plan.\n", encoding="utf-8")
        print(f"[C] Wrote plan preview: {out_txt}")
        print("[C] Planned tasks: 0")
        write_ics([], Path("data/out/plan_preview.ics"))
        return

    pool.sort(key=lambda t: (extract_zone(t.get("address")), t.get("received_at", "")))

    start_date = datetime.now().date() + timedelta(days=PLAN_START_OFFSET_DAYS)

    carpenter = Resource("CARPENTER", start_date, s.workday_start, s.workday_end)
    painters = [
        Resource(f"PAINTER_{i+1}", start_date, s.workday_start, s.workday_end)
        for i in range(s.num_painters)
    ]

    tasks_per_day: dict[tuple[str, date], int] = {}

    def painter_day_count(p: Resource, d: date) -> int:
        return tasks_per_day.get((p.name, d), 0)

    def bump_painter_day(p: Resource, d: date) -> None:
        tasks_per_day[(p.name, d)] = painter_day_count(p, d) + 1

    # --------------------------
    # GROUP + ZONE ASSIGNMENT
    # --------------------------
    zone_tasks: dict[str, list[dict]] = {}
    zone_minutes: dict[str, int] = {}

    for t in pool:
        zone = extract_zone(t.get("address"))
        zone_tasks.setdefault(zone, []).append(t)
        an = t.get("analysis", {}) or {}
        est = max(60, int(an.get("estimated_minutes") or 0))
        zone_minutes[zone] = zone_minutes.get(zone, 0) + est

    zones_sorted = sorted(zone_tasks.keys(), key=lambda z: zone_minutes.get(z, 0), reverse=True)

    painter_load: dict[str, int] = {p.name: 0 for p in painters}
    zone_assignment: dict[str, str] = {}

    for z in zones_sorted:
        best = min(painters, key=lambda p: painter_load[p.name])
        zone_assignment[z] = best.name
        painter_load[best.name] += zone_minutes.get(z, 0)

    # --------------------------
    # PLAN
    # --------------------------
    plan_lines = []
    plan_lines.append("PLAN — zone-batching + max tasks/day + tømrer->maler")
    plan_lines.append(f"Startdato: {start_date.isoformat()}")
    plan_lines.append(f"Arbejdstid: {s.workday_start}-{s.workday_end} | Malere: {s.num_painters}")
    plan_lines.append(f"MAX_TASKS_PER_DAY_PER_PAINTER={MAX_TASKS_PER_DAY_PER_PAINTER}")
    plan_lines.append("")
    plan_lines.append("Zone assignment:")
    for z in zones_sorted:
        plan_lines.append(f"  - zone {z}: {zone_assignment[z]} (min={zone_minutes.get(z, 0)})")
    plan_lines.append("")

    events = []
    scheduled = 0
    # Denne liste bruges til at bygge tømrermail-tillæg med tidspunkter
    carpenter_schedule_lines: list[str] = []

    for zone in zones_sorted:
        zone_tasks[zone].sort(key=lambda t: t.get("received_at", ""))

        for t in zone_tasks[zone]:
            an = t.get("analysis", {}) or {}
            est_maler = max(60, int(an.get("estimated_minutes") or 0))
            needs_carp = bool(an.get("needs_carpenter"))
            addr = t.get("address", "(ukendt)")

            # Respekter deadline hvis den er sat
            deadline_dt = _get_deadline_dt(t, s.workday_end)

            blocks = []
            carp_end = None

            # -------------------
            # TØMRER først
            # -------------------
            if needs_carp:
                est_carp = max(60, int(round(est_maler * CARPENTER_RATIO_OF_PAINTER)))
                carp_blocks = carpenter.commit_slots(est_carp)
                carp_end = carp_blocks[-1][1]

                for cs, ce in carp_blocks:
                    blocks.append(("TØMRER", cs, ce, "carpenter"))

                # Gem til tømrermail
                carp_start_str = carp_blocks[0][0].strftime("%A d. %d/%m/%Y kl. %H:%M")
                carp_end_str = carp_blocks[-1][1].strftime("%H:%M")
                carpenter_schedule_lines.append(
                    f"  → {addr}: {carp_start_str}–{carp_end_str}  (~{est_carp} min)"
                )

            # -------------------
            # MALER — find rigtig maler for zone
            # -------------------
            primary_name = zone_assignment.get(zone)
            chosen_painters: list[Resource] = []

            primary = next((p for p in painters if p.name == primary_name), None)
            if primary:
                chosen_painters.append(primary)
            else:
                chosen_painters.append(min(painters, key=lambda r: (r.day, r.used)))

            if PAINTERS_PER_JOB > 1:
                others = sorted(
                    [p for p in painters if p not in chosen_painters],
                    key=lambda r: (r.day, r.used),
                )
                chosen_painters.extend(others[: PAINTERS_PER_JOB - 1])

            per_painter_minutes = int(math.ceil(est_maler / max(1, len(chosen_painters))))

            for p in chosen_painters:
                # FIX: brug peek_slots til at finde første dag, commit kun når dag er godkendt
                extra_offset = 0
                MAX_ATTEMPTS = 30  # sikkerhedsventil
                attempts = 0

                while attempts < MAX_ATTEMPTS:
                    tentative = p.peek_slots(
                        per_painter_minutes,
                        earliest=carp_end,
                        extra_day_offset=extra_offset,
                    )
                    if not tentative:
                        break

                    first_day = tentative[0][0].date()

                    # Deadline-check: starter maler-blokken inden deadline?
                    if deadline_dt and tentative[0][0] > deadline_dt:
                        plan_lines.append(
                            f"  [ADVARSEL] Task {t['task_id']} kan ikke planlægges inden deadline {deadline_dt.date()}!"
                        )
                        break

                    if painter_day_count(p, first_day) < MAX_TASKS_PER_DAY_PER_PAINTER:
                        # Godkendt — committe nu
                        # Vi er nødt til at sætte painter til den rigtige position
                        # ekstra_offset er antal ekstra dage fra nuværende position
                        if extra_offset > 0:
                            p.advance_to_next_day()
                            # Gentag til vi er på den rigtige dag
                            for _ in range(extra_offset - 1):
                                p.advance_to_next_day()

                        actual_blocks = p.commit_slots(per_painter_minutes, earliest=carp_end)
                        bump_painter_day(p, actual_blocks[0][0].date())

                        label = f"MALER ({p.name})"
                        for ps, pe in actual_blocks:
                            blocks.append((label, ps, pe, "painter"))
                        break
                    else:
                        extra_offset += 1
                        attempts += 1

            # -------------------
            # Output
            # -------------------
            plan_lines.append(f"- Task: {t['task_id']} | zone={zone} | adresse={addr}")
            plan_lines.append(f"  Fra: {t.get('from')} | Emne: {t.get('subject')}")
            if deadline_dt:
                plan_lines.append(f"  Deadline: {deadline_dt.date()}")
            for label, sdt, edt, _kind in blocks:
                plan_lines.append(
                    f"    [{label}] {sdt.strftime('%Y-%m-%d %H:%M')} -> {edt.strftime('%H:%M')}"
                )
            plan_lines.append("")

            t["plan"] = {
                "zone": zone,
                "blocks": [
                    {"label": label, "start": iso(sdt), "end": iso(edt), "kind": kind}
                    for label, sdt, edt, kind in blocks
                ],
            }
            t["status"] = "PLANNED"
            scheduled += 1

            for label, sdt, edt, _kind in blocks:
                events.append({
                    "title": label,
                    "start": iso(sdt),
                    "end": iso(edt),
                    "location": addr,
                    "description": (
                        f"Task: {t.get('task_id')}\n"
                        f"Zone: {zone}\n"
                        f"Fra: {t.get('from')}\n"
                        f"Emne: {t.get('subject')}"
                    ),
                })

    # Gem tømrer-tidspunkter til b_analyze_and_notify.py
    if carpenter_schedule_lines:
        sched_path = OUT_DIR / "carpenter_schedule.txt"
        sched_path.write_text(
            "TØMRER-TIDSPUNKTER (genereret af planlægger):\n\n"
            + "\n".join(carpenter_schedule_lines),
            encoding="utf-8",
        )
        print(f"[C] Wrote carpenter schedule: {sched_path}")

    out_txt = OUT_DIR / "plan_preview.txt"
    out_txt.write_text("\n".join(plan_lines), encoding="utf-8")
    print(f"[C] Wrote plan preview: {out_txt}")
    print(f"[C] Planned tasks: {scheduled}")

    write_ics(events, Path("data/out/plan_preview.ics"))
    print("[C] Wrote calendar ICS: data/out/plan_preview.ics")

    save_tasks(tasks)


if __name__ == "__main__":
    run()
