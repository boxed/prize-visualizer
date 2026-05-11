#!/usr/bin/env python3
"""Combine Nobel + other prizes into a single per-prize record list.

Output: data/processed/prizes.json — same flat schema as nobel.json plus a
`prize` field naming the award. The Elm frontend loads this instead of (or
alongside) nobel.json.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOBEL = ROOT / "data" / "processed" / "nobel.json"
PRIZES_DIR = ROOT / "data" / "raw" / "prizes"
OUT = ROOT / "data" / "processed" / "prizes.json"

# slug -> (display name, default category if record has none)
PRIZE_META = {
    "fields_medal": ("Fields Medal", "Mathematics"),
    "abel_prize": ("Abel Prize", "Mathematics"),
    "turing_award": ("Turing Award", "Computer Science"),
    "wolf_math": ("Wolf Prize in Mathematics", "Mathematics"),
    "wolf_physics": ("Wolf Prize in Physics", "Physics"),
    "wolf_chemistry": ("Wolf Prize in Chemistry", "Chemistry"),
    "wolf_medicine": ("Wolf Prize in Medicine", "Physiology or Medicine"),
    "crafoord_prize": ("Crafoord Prize", "Crafoord (mixed)"),
    "breakthrough_life_sciences": ("Breakthrough Prize in Life Sciences", "Life Sciences"),
    "breakthrough_physics": ("Breakthrough Prize in Fundamental Physics", "Physics"),
    "breakthrough_mathematics": ("Breakthrough Prize in Mathematics", "Mathematics"),
    "kavli_astrophysics": ("Kavli Prize in Astrophysics", "Astrophysics"),
    "kavli_nanoscience": ("Kavli Prize in Nanoscience", "Nanoscience"),
    "kavli_neuroscience": ("Kavli Prize in Neuroscience", "Neuroscience"),
    "copley_medal": ("Copley Medal", "Science (general)"),
    "lasker_award": ("Lasker Award", "Physiology or Medicine"),
}


def load_nobel() -> list[dict]:
    if not NOBEL.exists():
        return []
    out = []
    for r in json.loads(NOBEL.read_text()):
        rec = dict(r)
        rec["prize"] = "Nobel Prize"
        out.append(rec)
    return out


# Map Wikidata country labels to Nobel API conventions so the same country
# rolls up correctly across data sources.
COUNTRY_ALIASES = {
    "United States": "USA",
    "United States of America": "USA",
    "Netherlands": "the Netherlands",
    "People's Republic of China": "China",
    "Russian Empire": "Russia",
    "Soviet Union": "Russia",
    "Kingdom of England": "United Kingdom",
    "Kingdom of Great Britain": "United Kingdom",
    "Kingdom of the Netherlands": "the Netherlands",
    "Republic of Ireland": "Ireland",
    "Hong Kong": "China",
    "Czechoslovakia": "Czech Republic",
    "Yugoslavia": "Bosnia and Herzegovina",  # heuristic; usually Serbian-born laureates
    "West Germany": "Germany",
    "East Germany": "Germany",
    "German Empire": "Germany",
    "Weimar Republic": "Germany",
    "Nazi Germany": "Germany",
    "Empire of Japan": "Japan",
    "Republic of China": "Taiwan",
    "Austria-Hungary": "Austria",
    "British Raj": "India",
    "British India": "India",
    "Mandatory Palestine": "Israel",
    "Palestine": "Israel",
    "Russian SFSR": "Russia",
    "Ottoman Empire": "Turkey",
    "Kingdom of Italy": "Italy",
    "Kingdom of Hungary": "Hungary",
    "Kingdom of Romania": "Romania",
    "French Third Republic": "France",
    "Vichy France": "France",
    "Spanish Empire": "Spain",
    "First French Empire": "France",
    "Second French Empire": "France",
}


def normalize_country(c: str | None) -> str | None:
    if c is None:
        return None
    return COUNTRY_ALIASES.get(c, c)


def load_prize(slug: str, name: str, default_category: str) -> list[dict]:
    path = PRIZES_DIR / f"{slug}.json"
    if not path.exists():
        return []
    out = []
    for r in json.loads(path.read_text()):
        if r.get("year") is None:
            # skip winners without a year - the time-series view needs it
            continue
        out.append({
            "id": r["wikidataId"],
            "name": r["name"],
            "kind": "person",
            "year": r["year"],
            "category": default_category,
            "gender": r.get("gender"),
            "birthCountry": normalize_country(r.get("birthCountry")),
            "currentCountry": normalize_country(r.get("currentCountry")),
            "birthYear": r.get("birthYear"),
            "wikipediaSlug": r.get("wikipediaSlug"),
            "wikidataId": r["wikidataId"],
            "portion": None,
            "motivation": None,
            "religions": r.get("religions", []),
            "ethnicGroups": r.get("ethnicGroups", []),
            "prize": name,
        })
    return out


def main() -> None:
    records: list[dict] = []
    nobel = load_nobel()
    print(f"Nobel: {len(nobel)} records")
    records.extend(nobel)

    for slug, (name, default_cat) in PRIZE_META.items():
        recs = load_prize(slug, name, default_cat)
        print(f"{name}: {len(recs)} records")
        records.extend(recs)

    records.sort(key=lambda r: (r["year"], r["prize"], r["name"] or ""))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(records, ensure_ascii=False, indent=2))
    print(f"\nwrote {len(records)} total prize-records to {OUT}")

    from collections import Counter
    by_prize = Counter(r["prize"] for r in records)
    print("by prize:", dict(by_prize))


if __name__ == "__main__":
    main()
