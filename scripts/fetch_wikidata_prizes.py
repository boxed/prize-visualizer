#!/usr/bin/env python3
"""Fetch laureates of additional high-prestige scientific prizes from Wikidata.

Each prize is identified by its Wikidata QID. We query for all (P166 = QID)
statements, the year qualifier (P585), birth country / gender / wikipedia slug.

Output: data/raw/prizes/<slug>.json — one file per prize, schema:
    [
      { "wikidataId": "Q...", "name": "...", "year": 2020,
        "gender": "male|female|null",
        "currentCountry": "USA|null",
        "birthCountry": "USA|null",
        "birthYear": 1965,
        "wikipediaSlug": "Foo_Bar",
        "religions": [], "ethnicGroups": [] }
    ]

Religion/ethnicity are pulled in the same query when available.
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
OUT_DIR = ROOT / "data" / "raw" / "prizes"
SPARQL_URL = "https://query.wikidata.org/sparql"
USER_AGENT = "prize-visualizer/0.1 (+https://github.com/local; prizes script)"

# slug -> (display name, wikidata QID, category label, prize-domain notes)
PRIZES = {
    "fields_medal": ("Fields Medal", "Q28835", "Mathematics"),
    "abel_prize": ("Abel Prize", "Q188184", "Mathematics"),
    "turing_award": ("Turing Award", "Q185667", "Computer Science"),
    "wolf_math": ("Wolf Prize in Mathematics", "Q915604", "Mathematics"),
    "wolf_physics": ("Wolf Prize in Physics", "Q845333", "Physics"),
    "wolf_chemistry": ("Wolf Prize in Chemistry", "Q968876", "Chemistry"),
    "wolf_medicine": ("Wolf Prize in Medicine", "Q540561", "Physiology or Medicine"),
    "crafoord_prize": ("Crafoord Prize", "Q583069", "Crafoord (mixed)"),
    "breakthrough_life_sciences": ("Breakthrough Prize in Life Sciences", "Q5019489", "Life Sciences"),
    "breakthrough_physics": ("Breakthrough Prize in Fundamental Physics", "Q1314470", "Physics"),
    "breakthrough_mathematics": ("Breakthrough Prize in Mathematics", "Q17278380", "Mathematics"),
    "kavli_astrophysics": ("Kavli Prize in Astrophysics", "Q18889778", "Astrophysics"),
    "kavli_nanoscience": ("Kavli Prize in Nanoscience", "Q18889779", "Nanoscience"),
    "kavli_neuroscience": ("Kavli Prize in Neuroscience", "Q18889781", "Neuroscience"),
    "copley_medal": ("Copley Medal", "Q28003", "Science (general)"),
    "lasker_award": ("Lasker Award", "Q921415", "Physiology or Medicine"),
}


def sparql_query(query: str, attempt: int = 1) -> dict:
    data = urllib.parse.urlencode({"query": query, "format": "json"}).encode()
    req = urllib.request.Request(
        SPARQL_URL,
        data=data,
        headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (TimeoutError, urllib.error.URLError, urllib.error.HTTPError) as e:
        if attempt >= 5:
            raise
        wait = 5 * attempt
        print(f"    retry {attempt} after {e}; sleep {wait}s", file=sys.stderr)
        time.sleep(wait)
        return sparql_query(query, attempt + 1)


def query_award(qid: str) -> list[dict]:
    """Return one row per winner (a person can win twice → multiple rows)."""
    query = f"""
    SELECT DISTINCT ?person ?personLabel ?awardDate ?genderLabel ?countryLabel
                    ?birthDate ?article ?religionLabel ?ethnicGroupLabel WHERE {{
      ?person p:P166 ?awardStmt.
      ?awardStmt ps:P166 wd:{qid}.
      OPTIONAL {{ ?awardStmt pq:P585 ?awardDate. }}
      OPTIONAL {{ ?person wdt:P21 ?gender. }}
      OPTIONAL {{ ?person wdt:P19 ?birthplace. ?birthplace wdt:P17 ?country. }}
      OPTIONAL {{ ?person wdt:P569 ?birthDate. }}
      OPTIONAL {{ ?person wdt:P140 ?religion. }}
      OPTIONAL {{ ?person wdt:P172 ?ethnicGroup. }}
      OPTIONAL {{
        ?article schema:about ?person ;
                 schema:isPartOf <https://en.wikipedia.org/> .
      }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    """
    res = sparql_query(query)
    return res["results"]["bindings"]


def slugify_wiki(article_url: str | None) -> str | None:
    if not article_url:
        return None
    # https://en.wikipedia.org/wiki/Foo_Bar  →  Foo_Bar
    if "/wiki/" not in article_url:
        return None
    return article_url.rsplit("/wiki/", 1)[-1]


def normalize(rows: list[dict]) -> list[dict]:
    """Group raw rows by (person, awardYear), since OPTIONAL crosses produce
    duplicates. Religion / ethnicity get aggregated into lists."""
    by_key: dict[tuple, dict] = {}
    for r in rows:
        person = r["person"]["value"]
        qid = person.rsplit("/", 1)[-1]
        award_date = r.get("awardDate", {}).get("value")
        year = int(award_date[:4]) if award_date and len(award_date) >= 4 else None
        key = (qid, year)

        if key not in by_key:
            birth_date = r.get("birthDate", {}).get("value")
            birth_year = int(birth_date[:4]) if birth_date and len(birth_date) >= 4 else None
            country = r.get("countryLabel", {}).get("value")
            by_key[key] = {
                "wikidataId": qid,
                "name": r.get("personLabel", {}).get("value", qid),
                "year": year,
                "gender": r.get("genderLabel", {}).get("value"),
                "birthCountry": country,
                "currentCountry": country,
                "birthYear": birth_year,
                "wikipediaSlug": slugify_wiki(r.get("article", {}).get("value")),
                "religions": set(),
                "ethnicGroups": set(),
            }
        rec = by_key[key]
        rel = r.get("religionLabel", {}).get("value")
        eth = r.get("ethnicGroupLabel", {}).get("value")
        if rel:
            rec["religions"].add(rel)
        if eth:
            rec["ethnicGroups"].add(eth)

    out = []
    for rec in by_key.values():
        rec["religions"] = sorted(rec["religions"])
        rec["ethnicGroups"] = sorted(rec["ethnicGroups"])
        out.append(rec)
    out.sort(key=lambda r: (r["year"] or 0, r["name"]))
    return out


def gender_normalize(g: str | None) -> str | None:
    """SPARQL returns 'male', 'female', sometimes 'transgender female' etc."""
    if not g:
        return None
    g = g.lower()
    if "female" in g:
        return "female"
    if "male" in g:
        return "male"
    return g  # leave as-is for nonbinary/transgender label


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for slug, (name, qid, _category) in PRIZES.items():
        out_path = OUT_DIR / f"{slug}.json"
        if out_path.exists():
            print(f"  {slug}: already cached, skip (delete file to re-fetch)", file=sys.stderr)
            continue
        print(f"  {slug} ({qid}): fetching …", file=sys.stderr)
        try:
            rows = query_award(qid)
        except Exception as e:
            print(f"    FAILED: {e}", file=sys.stderr)
            continue
        records = normalize(rows)
        for r in records:
            r["gender"] = gender_normalize(r["gender"])
        out_path.write_text(json.dumps(records, ensure_ascii=False, indent=2))
        with_year = sum(1 for r in records if r["year"])
        print(f"    {len(records)} winners ({with_year} with year) → {out_path.name}", file=sys.stderr)
        time.sleep(2.0)


if __name__ == "__main__":
    main()
