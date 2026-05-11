#!/usr/bin/env python3
"""Fetch all Nobel laureates from the official API and cache to disk.

Output: data/raw/laureates.json (a single JSON array of laureate records).
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

API_URL = "https://api.nobelprize.org/2.1/laureates"
PAGE_SIZE = 100
ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / "data" / "raw" / "laureates.json"


USER_AGENT = "prize-visualizer/0.1 (+https://github.com/local)"


def fetch_page(offset: int, limit: int) -> dict:
    url = f"{API_URL}?offset={offset}&limit={limit}&format=json"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_all() -> list[dict]:
    first = fetch_page(0, PAGE_SIZE)
    total = int(first["meta"]["count"])
    laureates = list(first["laureates"])
    print(f"total laureates: {total}; fetched {len(laureates)}", file=sys.stderr)

    offset = PAGE_SIZE
    while offset < total:
        page = fetch_page(offset, PAGE_SIZE)
        laureates.extend(page["laureates"])
        print(f"fetched {len(laureates)}/{total}", file=sys.stderr)
        offset += PAGE_SIZE
        time.sleep(0.2)

    return laureates


def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    laureates = fetch_all()
    OUT_PATH.write_text(json.dumps(laureates, ensure_ascii=False, indent=2))
    print(f"wrote {len(laureates)} laureates to {OUT_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()
