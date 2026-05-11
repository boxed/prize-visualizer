#!/usr/bin/env python3
"""Enrich laureates with Wikidata religion (P140) and ethnic group (P172).

Coverage is intentionally partial — many laureates have neither property set on
Wikidata, and the values that do exist mix religion and ethnicity in messy ways
(e.g. "Jewish people" appears under both P140 and P172 depending on the editor).
Output is labeled clearly so the frontend can show provenance.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOBEL = ROOT / "data" / "processed" / "nobel.json"
OUT = ROOT / "data" / "raw" / "wikidata_enrichment.json"
SPARQL_URL = "https://query.wikidata.org/sparql"
USER_AGENT = "prize-visualizer/0.1 (+https://github.com/local; enrichment script)"
BATCH_SIZE = 25
INTER_BATCH_SLEEP = 2.0


def query_batch(ids: list[str], attempt: int = 1) -> list[dict]:
    values_clause = " ".join(f"wd:{i}" for i in ids)
    query = f"""
    SELECT ?laureate ?religion ?religionLabel ?ethnicGroup ?ethnicGroupLabel WHERE {{
      VALUES ?laureate {{ {values_clause} }}
      OPTIONAL {{ ?laureate wdt:P140 ?religion. }}
      OPTIONAL {{ ?laureate wdt:P172 ?ethnicGroup. }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    """
    data = urllib.parse.urlencode({"query": query, "format": "json"}).encode()
    req = urllib.request.Request(
        SPARQL_URL,
        data=data,
        headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.loads(resp.read().decode("utf-8"))["results"]["bindings"]
    except (TimeoutError, urllib.error.URLError, urllib.error.HTTPError) as e:
        if attempt >= 4:
            raise
        wait = 5 * attempt
        print(f"  retry {attempt} after error {e}, sleeping {wait}s", file=sys.stderr)
        time.sleep(wait)
        return query_batch(ids, attempt + 1)


def load_existing() -> dict[str, dict]:
    if not OUT.exists():
        return {}
    raw = json.loads(OUT.read_text())
    return {qid: {"religions": set(v["religions"]), "ethnicGroups": set(v["ethnicGroups"])} for qid, v in raw.items()}


def write(by_id: dict[str, dict]) -> None:
    serializable = {
        qid: {
            "religions": sorted(v["religions"]),
            "ethnicGroups": sorted(v["ethnicGroups"]),
        }
        for qid, v in by_id.items()
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(serializable, ensure_ascii=False, indent=2))


def main() -> None:
    nobel = json.loads(NOBEL.read_text())
    ids = sorted({r["wikidataId"] for r in nobel if r["wikidataId"]})
    by_id: dict[str, dict] = load_existing()
    by_id_dd = defaultdict(lambda: {"religions": set(), "ethnicGroups": set()})
    by_id_dd.update(by_id)
    pending = [i for i in ids if i not in by_id_dd]
    print(f"laureates total: {len(ids)}; already cached: {len(by_id_dd)}; pending: {len(pending)}", file=sys.stderr)

    failed_batches = 0
    for i in range(0, len(pending), BATCH_SIZE):
        batch = pending[i : i + BATCH_SIZE]
        try:
            rows = query_batch(batch)
        except Exception as e:
            failed_batches += 1
            print(f"  batch {i // BATCH_SIZE + 1} failed permanently: {e}; will retry on next run", file=sys.stderr)
            # do NOT mark as queried; next run will retry these IDs.
            time.sleep(INTER_BATCH_SLEEP * 2)
            continue
        for row in rows:
            qid = row["laureate"]["value"].rsplit("/", 1)[-1]
            if "religionLabel" in row and "religion" in row:
                by_id_dd[qid]["religions"].add(row["religionLabel"]["value"])
            if "ethnicGroupLabel" in row and "ethnicGroup" in row:
                by_id_dd[qid]["ethnicGroups"].add(row["ethnicGroupLabel"]["value"])
        # ensure every queried id is present, even with no hits
        for qid in batch:
            by_id_dd[qid]
        print(f"  batch {i // BATCH_SIZE + 1}/{(len(pending) + BATCH_SIZE - 1) // BATCH_SIZE}: {len(batch)} ids → {len(rows)} rows", file=sys.stderr)
        write(by_id_dd)
        time.sleep(INTER_BATCH_SLEEP)

    if failed_batches:
        print(f"WARNING: {failed_batches} batches failed; rerun the script to retry just those.", file=sys.stderr)

    serializable = by_id_dd

    with_rel = sum(1 for v in serializable.values() if v["religions"])
    with_eth = sum(1 for v in serializable.values() if v["ethnicGroups"])
    print(f"wrote {len(serializable)} entries to {OUT}", file=sys.stderr)
    print(f"  laureates with religion (P140): {with_rel}/{len(ids)} = {with_rel * 100 / len(ids):.1f}%", file=sys.stderr)
    print(f"  laureates with ethnic group (P172): {with_eth}/{len(ids)} = {with_eth * 100 / len(ids):.1f}%", file=sys.stderr)


if __name__ == "__main__":
    main()
