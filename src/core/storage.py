from __future__ import annotations
import json
import hashlib
from pathlib import Path
from typing import Any

STATE_DIR = Path("data/state")
ATT_DIR = Path("data/inbox_attachments")
OUT_DIR = Path("data/out")

STATE_DIR.mkdir(parents=True, exist_ok=True)
ATT_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR.mkdir(parents=True, exist_ok=True)

TASKS_PATH = STATE_DIR / "tasks.json"
SEEN_PATH = STATE_DIR / "seen.json"

def _load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))

def _save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def load_seen() -> dict[str, Any]:
    return _load_json(SEEN_PATH, default={})

def save_seen(seen: dict[str, Any]) -> None:
    _save_json(SEEN_PATH, seen)

def load_tasks() -> list[dict[str, Any]]:
    return _load_json(TASKS_PATH, default=[])

def save_tasks(tasks: list[dict[str, Any]]) -> None:
    _save_json(TASKS_PATH, tasks)

def save_attachment(message_id: str, filename: str, content: bytes) -> Path:
    safe = filename.replace("/", "_").replace("\\", "_")
    folder = ATT_DIR / message_id
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / safe
    p.write_bytes(content)
    return p
