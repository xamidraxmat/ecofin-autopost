"""Sozlamalarni yuklash va umumiy yordamchi funksiyalar."""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
STATE_DIR = ROOT / "state"
DRAFTS_DIR = ROOT / "drafts"


def load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def common() -> dict:
    return load_yaml(CONFIG_DIR / "common.yaml")


def channel(name: str) -> dict:
    cfg = load_yaml(CONFIG_DIR / f"{name}.yaml")
    cfg["id"] = name
    return cfg


def all_channels() -> list[str]:
    skip = {"common", "curriculum"}
    return sorted(p.stem for p in CONFIG_DIR.glob("*.yaml") if p.stem not in skip)


def curriculum() -> dict:
    return load_yaml(CONFIG_DIR / "curriculum.yaml")


def env(name: str, required: bool = True) -> str | None:
    val = os.environ.get(name, "").strip()
    if required and not val:
        raise SystemExit(f"[XATO] '{name}' maxfiy kaliti topilmadi (GitHub Secrets'ga qo'shing).")
    return val or None


def now_local(tz: str) -> datetime:
    return datetime.now(ZoneInfo(tz))


# ---------- holat (state) ----------

def read_state(name: str) -> dict:
    p = STATE_DIR / f"{name}.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"next_topic": 0, "history": [], "extra_topics": [], "tg_offset": 0}


def write_state(name: str, state: dict) -> None:
    STATE_DIR.mkdir(exist_ok=True)
    (STATE_DIR / f"{name}.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)
