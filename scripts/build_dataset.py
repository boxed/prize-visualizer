#!/usr/bin/env python3
"""Normalize the raw Nobel API dump into a flat per-prize record list."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "laureates.json"
ENRICHMENT = ROOT / "data" / "raw" / "wikidata_enrichment.json"
OUT = ROOT / "data" / "processed" / "nobel.json"


def en(field) -> str | None:
    if field is None:
        return None
    if isinstance(field, str):
        return field
    if isinstance(field, dict):
        return field.get("en")
    return None


def country_pair(place: dict | None) -> tuple[str | None, str | None]:
    if not place:
        return None, None
    return en(place.get("country")), en(place.get("countryNow"))


def load_enrichment() -> dict[str, dict]:
    if not ENRICHMENT.exists():
        return {}
    return json.loads(ENRICHMENT.read_text())


def normalize(laureates: list[dict], enrichment: dict[str, dict]) -> list[dict]:
    records = []
    for l in laureates:
        is_person = "gender" in l
        if is_person:
            name = en(l.get("knownName")) or en(l.get("fullName"))
            gender = l.get("gender")
            birth = l.get("birth") or {}
            birth_year = birth.get("year")
            birth_country, current_country = country_pair(birth.get("place"))
        else:
            name = en(l.get("orgName"))
            gender = None
            birth_year = (l.get("founded") or {}).get("year")
            birth_country, current_country = country_pair((l.get("founded") or {}).get("place"))
            # fallback flat fields
            if current_country is None:
                current_country = en(l.get("foundedCountryNow")) or en(l.get("foundedCountry"))
            if birth_country is None:
                birth_country = en(l.get("foundedCountry"))

        wiki = l.get("wikipedia") or {}
        wikidata = l.get("wikidata") or {}
        wd_id = wikidata.get("id")
        enrich = enrichment.get(wd_id, {}) if wd_id else {}

        for prize in l.get("nobelPrizes", []):
            records.append({
                "id": l.get("id"),
                "name": name,
                "kind": "person" if is_person else "organization",
                "year": int(prize["awardYear"]),
                "category": en(prize.get("category")),
                "gender": gender,
                "birthCountry": birth_country,
                "currentCountry": current_country,
                "birthYear": int(birth_year) if birth_year and birth_year.isdigit() else None,
                "wikipediaSlug": wiki.get("slug"),
                "wikidataId": wd_id,
                "portion": prize.get("portion"),
                "motivation": en(prize.get("motivation")),
                "religions": enrich.get("religions", []),
                "ethnicGroups": enrich.get("ethnicGroups", []),
            })
    return records


def main() -> None:
    laureates = json.loads(RAW.read_text())
    enrichment = load_enrichment()
    records = normalize(laureates, enrichment)
    records.sort(key=lambda r: (r["year"], r["category"] or "", r["name"] or ""))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(records, ensure_ascii=False, indent=2))
    print(f"wrote {len(records)} prize-records to {OUT} (enrichment entries: {len(enrichment)})")

    from collections import Counter
    by_cat = Counter(r["category"] for r in records)
    by_country = Counter(r["currentCountry"] for r in records)
    by_gender = Counter(r["gender"] for r in records)
    with_rel = sum(1 for r in records if r["religions"])
    with_eth = sum(1 for r in records if r["ethnicGroups"])
    print("categories:", dict(by_cat))
    print("genders:", dict(by_gender))
    print("top countries:", by_country.most_common(10))
    print(f"enrichment coverage: {with_rel}/{len(records)} religion ({with_rel*100/len(records):.1f}%), {with_eth}/{len(records)} ethnicity ({with_eth*100/len(records):.1f}%)")


if __name__ == "__main__":
    main()
