#!/usr/bin/env python3
"""Pull heritage signals from Wikipedia (categories + curated lists).

Two passes:
1. **Wikipedia categories** — for every laureate with a Wikipedia slug, fetch the
   page's categories via the MediaWiki API in batches of 50. Categories like
   "American Jewish physicists" or "Catholic priests" are the data source.
2. **Curated lists** — pages like "List of Jewish Nobel laureates" contain
   editor-vetted membership. We pull the outbound article links from each list
   page and treat any laureate slug that appears as a member.

Output: data/raw/wikipedia_heritage.json — keyed by Wikipedia slug:
    { "Albert_Einstein": {
        "categories": [...],
        "lists": ["Jewish"]
      }, ... }

The downstream `extract_heritage.py` (or build_combined.py) does the keyword
matching.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRIZES = ROOT / "data" / "processed" / "prizes.json"
OUT = ROOT / "data" / "raw" / "wikipedia_heritage.json"
API_URL = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "prize-visualizer/0.1 (+https://github.com/local; heritage)"
BATCH = 10

# Curated list pages — title : tag we'd record if a laureate appears in it
# Pages with actual outbound article links to laureates. The Muslim / African-
# American / atheist lists return 0 because Wikipedia doesn't have dedicated
# laureate pages with that title — keep curating as standalone pages appear.
CURATED_LISTS = {
    "List_of_Jewish_Nobel_laureates": "Jewish",
    "List_of_Christian_Nobel_laureates": "Christian",
    "List_of_Latin_American_Nobel_laureates": "Latin American",
    "List_of_Indian_Nobel_laureates": "Indian",
    "List_of_Chinese_Nobel_laureates": "Chinese",
}


def http_get(params: dict) -> dict:
    params = {**params, "format": "json", "formatversion": "2"}
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(1, 5):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (TimeoutError, urllib.error.URLError, urllib.error.HTTPError) as e:
            if attempt == 4:
                raise
            wait = 2 * attempt
            print(f"    retry {attempt} after {e}, sleep {wait}s", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError("unreachable")


def decode_slug(slug: str) -> str:
    """Percent-decode the Nobel-API slugs so MediaWiki finds the page."""
    return urllib.parse.unquote(slug)


def fetch_categories_for(slugs: list[str], cache: dict) -> None:
    """Fill cache[slug]['categories'] for the given slugs (force refetch if empty)."""
    todo = [s for s in slugs if not cache.get(s, {}).get("categories")]
    print(f"categories: {len(todo)} laureates to fetch (cached: {len(slugs) - len(todo)})", file=sys.stderr)
    for i in range(0, len(todo), BATCH):
        batch = todo[i : i + BATCH]
        # MediaWiki accepts either underscore or space; we send decoded titles
        # so non-ASCII slugs (%C3%89lie_…) actually resolve.
        decoded = [decode_slug(s) for s in batch]
        params = {
            "action": "query",
            "prop": "categories",
            "titles": "|".join(decoded),
            "clshow": "!hidden",
            "cllimit": "max",
        }
        try:
            res = http_get(params)
        except Exception as e:
            print(f"  batch {i // BATCH + 1} failed permanently: {e}", file=sys.stderr)
            continue
        # Continue tokens may be present if any page has >500 cats; usually not
        cont = res.get("continue", {})
        all_pages = list(res.get("query", {}).get("pages", []))
        # Handle pagination for very long category lists
        while "clcontinue" in cont:
            try:
                more = http_get({**params, **cont})
            except Exception as e:
                print(f"    continuation failed: {e}", file=sys.stderr)
                break
            for p in more.get("query", {}).get("pages", []):
                # Merge into all_pages
                existing = next((q for q in all_pages if q.get("title") == p.get("title")), None)
                if existing:
                    existing.setdefault("categories", []).extend(p.get("categories", []))
                else:
                    all_pages.append(p)
            cont = more.get("continue", {})

        # MediaWiki may normalize titles (e.g. percent-encoded → readable). Track
        # the mapping so we hit the right cache key.
        norm_map = {n["from"]: n["to"] for n in res.get("query", {}).get("normalized", [])}
        slug_from_title = {p["title"]: p for p in all_pages}

        for slug in batch:
            display = decode_slug(slug).replace("_", " ")
            normalized = norm_map.get(display, display)
            page = slug_from_title.get(normalized)
            cats = []
            if page and "categories" in page:
                cats = [c["title"].removeprefix("Category:") for c in page["categories"]]
            entry = cache.setdefault(slug, {})
            entry["categories"] = cats

        write_cache(cache)
        print(f"  cats batch {i // BATCH + 1}/{(len(todo) + BATCH - 1) // BATCH} done", file=sys.stderr)
        time.sleep(0.5)


def fetch_list_members(list_title: str) -> set[str]:
    """Outbound article links from a list page → set of slugs."""
    members: set[str] = set()
    params = {
        "action": "query",
        "prop": "links",
        "titles": list_title,
        "plnamespace": "0",  # main namespace only
        "pllimit": "max",
    }
    cont: dict = {}
    while True:
        try:
            res = http_get({**params, **cont})
        except Exception as e:
            print(f"  list {list_title} failed: {e}", file=sys.stderr)
            return members
        for page in res.get("query", {}).get("pages", []):
            for link in page.get("links", []):
                title = link.get("title")
                if title:
                    members.add(title.replace(" ", "_"))
        if "continue" in res and "plcontinue" in res["continue"]:
            cont = res["continue"]
        else:
            break
    return members


def fetch_lists_for(slugs: set[str], cache: dict) -> None:
    print(f"curated lists: {len(CURATED_LISTS)} pages", file=sys.stderr)
    for title, tag in CURATED_LISTS.items():
        print(f"  fetching {title} …", file=sys.stderr)
        members = fetch_list_members(title)
        hits = members & slugs
        print(f"    {len(members)} links, {len(hits)} match a laureate", file=sys.stderr)
        for s in hits:
            entry = cache.setdefault(s, {})
            entry.setdefault("lists", []).append(tag)
        time.sleep(0.5)


def write_cache(cache: dict) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(cache, ensure_ascii=False, indent=2))


def load_cache() -> dict:
    if OUT.exists():
        return json.loads(OUT.read_text())
    return {}


def main() -> None:
    prizes = json.loads(PRIZES.read_text())
    slugs = sorted({p["wikipediaSlug"] for p in prizes if p.get("wikipediaSlug")})
    print(f"unique laureate Wikipedia slugs: {len(slugs)}", file=sys.stderr)

    cache = load_cache()
    fetch_categories_for(slugs, cache)
    fetch_lists_for(set(slugs), cache)

    # Dedupe list tags
    for entry in cache.values():
        if "lists" in entry:
            entry["lists"] = sorted(set(entry["lists"]))

    write_cache(cache)

    with_cats = sum(1 for v in cache.values() if v.get("categories"))
    with_lists = sum(1 for v in cache.values() if v.get("lists"))
    print(f"\ncached entries: {len(cache)}", file=sys.stderr)
    print(f"  with categories: {with_cats}", file=sys.stderr)
    print(f"  with curated list memberships: {with_lists}", file=sys.stderr)


if __name__ == "__main__":
    main()
