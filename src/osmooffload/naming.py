"""Filename parsing, folder layout, and naming templates.

DJI Osmo names look like `DJI_<YYYYMMDDHHMMSS>_<NNNN>_D.MP4` inside
`DCIM/DJI_001/`. The timestamp in the name is the capture time and is what we
sort into dated folders. Custom Folder/File prefixes on the camera are handled
by falling back to any embedded 14-digit timestamp, then to "undated".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

_TS_RE = re.compile(r"(\d{14})")  # YYYYMMDDHHMMSS anywhere in the name
_SEQ_RE = re.compile(r"_(\d{4})(?:_|\.|$)")

DEFAULT_FOLDER_TEMPLATE = "{camera}/{date}/{kind}"

PHOTO_EXTS = {"JPG", "JPEG", "DNG", "RAW", "HEIF", "HEIC"}
VIDEO_EXTS = {"MP4", "MOV"}


@dataclass
class ParsedName:
    base: str  # filename without extension
    ext: str  # upper, no dot
    timestamp: datetime | None
    seq: str | None

    @property
    def is_video(self) -> bool:
        return self.ext in VIDEO_EXTS

    @property
    def is_photo(self) -> bool:
        return self.ext in PHOTO_EXTS

    @property
    def kind(self) -> str:
        if self.is_video:
            return "video"
        if self.is_photo:
            return "photo"
        return "other"


def parse_name(name: str) -> ParsedName:
    base, _, ext = name.rpartition(".")
    if not base:  # no extension
        base, ext = name, ""
    ts = None
    m = _TS_RE.search(name)
    if m:
        try:
            ts = datetime.strptime(m.group(1), "%Y%m%d%H%M%S")
        except ValueError:
            ts = None
    sm = _SEQ_RE.search(name)
    return ParsedName(base=base, ext=ext.upper(), timestamp=ts, seq=sm.group(1) if sm else None)


def date_folder(parsed: ParsedName) -> str:
    return parsed.timestamp.strftime("%Y-%m-%d") if parsed.timestamp else "undated"


def _render(template: str, parsed: ParsedName, camera: str, original: str) -> str:
    ts = parsed.timestamp
    values = {
        "date": ts.strftime("%Y-%m-%d") if ts else "undated",
        "year": ts.strftime("%Y") if ts else "undated",
        "month": ts.strftime("%m") if ts else "undated",
        "day": ts.strftime("%d") if ts else "undated",
        "kind": parsed.kind,
        "time": ts.strftime("%H%M%S") if ts else "000000",
        "datetime": ts.strftime("%Y-%m-%d_%H%M%S") if ts else "undated",
        "camera": _sanitize(camera),
        "seq": parsed.seq or "0000",
        "ext": parsed.ext.lower(),
        "original": original,
        "base": parsed.base,
    }
    out = template
    for k, v in values.items():
        out = out.replace("{" + k + "}", str(v))
    return out


def apply_template(template: str, parsed: ParsedName, camera: str, original: str) -> str:
    """Render an output filename from a token template.

    Tokens: {date} {year} {month} {day} {time} {datetime} {camera} {kind} {seq}
    {ext} {original} {base}. Unknown tokens are left as-is. The extension is
    always appended if the template doesn't already end with it.
    """
    out = _sanitize(_render(template, parsed, camera, original), keep_seps=True)
    if parsed.ext and not out.lower().endswith("." + parsed.ext.lower()):
        out = f"{out}.{parsed.ext.lower()}"
    return out


def folder_parts(template: str, parsed: ParsedName, camera: str, original: str) -> list[str]:
    """Render the folder layout template into sanitized path segments."""
    rendered = _render(template, parsed, camera, original)
    return [_sanitize(p) for p in re.split(r"[\\/]+", rendered) if p.strip(" .")]


_BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_BAD_KEEP = re.compile(r'[<>:"|?*\x00-\x1f]')


def _sanitize(s: str, keep_seps: bool = False) -> str:
    s = (_BAD_KEEP if keep_seps else _BAD).sub("_", s).strip(" .")
    return s or "_"
