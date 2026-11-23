"""App state persistence.

For now everything lives in ./config/appstate.json next to the repo (gitignored).
Will move to %APPDATA%/OsmoOffload when the app is packaged.

The pairing `identifier` is minted once per install and NEVER rotated — the
camera stores its approval under it (rotating forces a new approval and burns
a remembered slot; retries with a different identifier read as a second app).
"""

from __future__ import annotations

import json
import os
import secrets
import sys
import threading
from pathlib import Path
from typing import Any


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):  # packaged exe: per-user app data
        return Path(os.environ.get("APPDATA", Path.home())) / "OsmoOffload"
    return Path(__file__).resolve().parents[2]


CONFIG_DIR = _base_dir() / "config"
STATE_FILE = CONFIG_DIR / "appstate.json"
LOG_DIR = _base_dir() / "logs"


# The UI thread and the camera worker both read and write the state file.
_lock = threading.RLock()


def load_state() -> dict[str, Any]:
    with _lock:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return {}


def save_state(state: dict[str, Any]) -> None:
    with _lock:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
        os.replace(tmp, STATE_FILE)


def update_state(**fields: Any) -> dict[str, Any]:
    """Merge fields into the file as it is now. The UI and the camera worker
    both write state, so never save a copy loaded earlier."""
    with _lock:
        state = load_state()
        state.update(fields)
        save_state(state)
        return state


def get_identifier(state: dict[str, Any]) -> str:
    ident = state.get("identifier")
    if not ident:
        ident = f"{secrets.randbelow(10**15):015d}"  # 15 digits, the shape Mimo sends
        state["identifier"] = ident
        update_state(identifier=ident)
    return ident


def remember_camera(state: dict[str, Any], address: str, **fields: Any) -> None:
    with _lock:
        cams = load_state().get("cameras", {})
        cams.setdefault(address, {}).update({k: v for k, v in fields.items() if v is not None})
        state["cameras"] = cams
        update_state(cameras=cams)
