"""Rows for batch generation from a CSV file or a Google Sheet.

Google Sheets: the sheet must be shared as "Anyone with the link can view". Its CSV export is
fetched without OAuth. Only docs.google.com is contacted, with size and time limits.
"""

from __future__ import annotations

import csv
import io
import re
from typing import Any, Optional

from docgen.field_aliases import CANONICAL_ALIASES

MAX_ROWS = 300
MAX_BYTES = 2 * 1024 * 1024
_SHEET = re.compile(r"^https://docs\.google\.com/spreadsheets/d/([A-Za-z0-9_-]{20,})(?:/[^?#]*)?(?:[?#].*)?$")


def sheet_csv_url(url: str) -> str:
    """Turn a Google Sheets link into its CSV export URL (keeps the selected tab)."""
    url = (url or "").strip()
    m = _SHEET.match(url)
    if not m:
        raise ValueError("Paste a Google Sheets link (https://docs.google.com/spreadsheets/d/...).")
    gid = re.search(r"[#&?]gid=(\d+)", url)
    return f"https://docs.google.com/spreadsheets/d/{m.group(1)}/export?format=csv" + (f"&gid={gid.group(1)}" if gid else "")


def fetch_sheet_csv(url: str) -> bytes:
    import requests

    export = sheet_csv_url(url)
    resp = requests.get(export, timeout=10, allow_redirects=True, stream=True)
    final_host = re.match(r"^https://([^/]+)/", resp.url or "")
    if not final_host or not final_host.group(1).endswith(("google.com", "googleusercontent.com")):
        raise ValueError("Unexpected redirect while reading the sheet.")
    if resp.status_code != 200 or "text/csv" not in resp.headers.get("Content-Type", ""):
        raise ValueError("Could not read the sheet. Share it as “Anyone with the link can view” and try again.")
    data = resp.raw.read(MAX_BYTES + 1, decode_content=True)
    if len(data) > MAX_BYTES:
        raise ValueError("The sheet is too large (limit 2 MB).")
    return data


def parse_csv(data: bytes) -> tuple[list[str], list[dict[str, str]]]:
    text = data.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    headers = [h.strip() for h in (reader.fieldnames or []) if h and h.strip()]
    if not headers:
        raise ValueError("The first row must contain column names.")
    rows: list[dict[str, str]] = []
    for raw in reader:
        row = {h.strip(): (v or "").strip() for h, v in raw.items() if h and h.strip()}
        if any(row.values()):
            rows.append(row)
        if len(rows) > MAX_ROWS:
            raise ValueError(f"At most {MAX_ROWS} rows can be generated at once.")
    return headers, rows


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def suggest_mapping(headers: list[str], fields: list[dict[str, Any]]) -> dict[str, Optional[str]]:
    """Column -> template field key, matching names, labels and common synonyms."""
    synonyms: dict[str, str] = {}
    for canonical, aliases in CANONICAL_ALIASES.items():
        for name in (canonical, *aliases):
            synonyms[name] = canonical
    names = {
        "name": "recipient_name", "full_name": "recipient_name", "participant": "recipient_name",
        "participant_name": "recipient_name", "student_name": "recipient_name", "winner": "recipient_name",
        "rank": "position", "place": "position", "prize": "position",
    }
    field_keys = {f["key"] for f in fields if f.get("key")}
    by_label = {_norm(f.get("label") or ""): f["key"] for f in fields if f.get("key") and f.get("label")}
    mapping: dict[str, Optional[str]] = {}
    for h in headers:
        n = _norm(h)
        candidate = (
            (n if n in field_keys else None)
            or by_label.get(n)
            or (names.get(n) if names.get(n) in field_keys else None)
            or next((k for k in field_keys if synonyms.get(n) and synonyms.get(n) == synonyms.get(k, k)), None)
        )
        mapping[h] = candidate
    return mapping


def apply_mapping(rows: list[dict[str, str]], mapping: dict[str, Optional[str]]) -> list[dict[str, str]]:
    out = []
    for row in rows:
        mapped = {}
        for col, value in row.items():
            key = mapping.get(col)
            if key and value:
                mapped[key] = value
        out.append(mapped)
    return out
