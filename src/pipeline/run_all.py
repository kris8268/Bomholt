from __future__ import annotations

from pathlib import Path
from datetime import datetime

from src.logging_setup import setup_logging

#from src.pipeline.a_ingest_mail import run as run_a
from src.pipeline.a_ingest_mail_outlook import run as run_a
from src.pipeline.b_analyze_and_notify import run as run_b
from src.pipeline.c_plan_schedule import run as run_c


def _assert_exists(path: Path, logger, label: str) -> None:
    if path.exists():
        logger.info(f"[OK] {label}: {path}")
    else:
        logger.warning(f"[WARN] {label} was not created: {path}")


def run_all():
    logger = setup_logging("run_all")

    logger.info("=== job_mail_planner: RUN ALL (A -> B -> C) ===")
    logger.info(f"Started at: {datetime.now().isoformat(timespec='seconds')}")

    # A) ingest
    logger.info("=== Running A: ingest mails + pdf + text ===")
    run_a()

    # B) analyze + carpenter preview
    logger.info("=== Running B: analyze + carpenter preview ===")
    run_b()

    # C) plan schedule preview
    logger.info("=== Running C: plan schedule preview ===")
    run_c()

    # Expected outputs
    tasks_path = Path("data/state/tasks.json")
    carpenter_preview = Path("data/out/carpenter_email_preview.txt")
    plan_preview = Path("data/out/plan_preview.txt")

    logger.info("=== Output checks ===")
    _assert_exists(tasks_path, logger, "tasks.json")
    _assert_exists(carpenter_preview, logger, "carpenter_email_preview.txt")
    _assert_exists(plan_preview, logger, "plan_preview.txt")

    logger.info("=== DONE ===")


if __name__ == "__main__":
    run_all()
