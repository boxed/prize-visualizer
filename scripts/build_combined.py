#!/usr/bin/env python3
"""Combine Nobel + other prizes into a single per-prize record list.

Output: data/processed/prizes.json — same flat schema as nobel.json plus a
`prize` field naming the award. The Elm frontend loads this instead of (or
alongside) nobel.json.
"""

from __future__ import annotations

import json
from pathlib import Path

import re

ROOT = Path(__file__).resolve().parent.parent
NOBEL = ROOT / "data" / "processed" / "nobel.json"
PRIZES_DIR = ROOT / "data" / "raw" / "prizes"
HERITAGE = ROOT / "data" / "raw" / "wikipedia_heritage.json"
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


def merge_heritage(rec: dict, heritage: dict) -> dict:
    slug = rec.get("wikipediaSlug")
    existing_rels = set(rec.get("religions") or [])
    existing_eths = set(rec.get("ethnicGroups") or [])
    rels: set[str] = set(existing_rels)
    eths: set[str] = set(existing_eths)
    if slug:
        entry = heritage.get(slug)
        if entry:
            r2, e2 = extract_tags(entry.get("categories", []), entry.get("lists", []))
            rels |= r2
            eths |= e2
    rec["religions"] = sorted({canonical_religion(x) for x in rels})
    rec["ethnicGroups"] = sorted({canonical_ethnicity(x) for x in eths})
    return rec


def load_nobel(heritage: dict) -> list[dict]:
    if not NOBEL.exists():
        return []
    out = []
    for r in json.loads(NOBEL.read_text()):
        rec = dict(r)
        rec["prize"] = "Nobel Prize"
        out.append(merge_heritage(rec, heritage))
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


# ---------- heritage extraction from Wikipedia categories + curated lists ----------

# (category-name substring → canonical religion). Word-boundary matched.
RELIGION_PATTERNS: list[tuple[str, str]] = [
    (r"\bJewish\b", "Judaism"),
    (r"\bJews\b", "Judaism"),
    (r"\bRoman Catholic\b", "Catholicism"),
    (r"\bCatholic\b", "Catholicism"),
    (r"\bProtestant\b", "Protestantism"),
    (r"\bLutheran\b", "Lutheranism"),
    (r"\bAnglican\b", "Anglicanism"),
    (r"\bMethodist\b", "Methodism"),
    (r"\b(Mormon|Latter[- ]day Saints?)\b", "Mormonism"),
    (r"\bQuaker\b", "Quaker"),
    (r"\bPresbyterian\b", "Presbyterianism"),
    (r"\b(Episcopalian|Episcopal Church)\b", "Episcopal Church"),
    (r"\bBaptist\b", "Baptist"),
    (r"\b(Eastern Orthodox|Russian Orthodox|Greek Orthodox)\b", "Eastern Orthodoxy"),
    (r"\b(Muslim|Islamic|Sunni|Shia|Shi'a)\b", "Islam"),
    (r"\bHindu\b", "Hinduism"),
    (r"\bBuddhist\b", "Buddhism"),
    (r"\bSikh\b", "Sikhism"),
    (r"\b(Atheist|Atheism)\b", "Atheism"),
    (r"\b(Agnostic|Agnosticism)\b", "Agnosticism"),
    (r"\b(Bahá'í|Baha'i|Bahai)\b", "Bahá'í"),
    (r"\bChristian\b", "Christianity"),  # last so more-specific denominations win
]

# Patterns that should NOT trigger a religion match — proper-noun prizes,
# institutions, etc.
RELIGION_FALSE_POSITIVE = re.compile(
    r"Christian Doppler|Christian Democratic|Christian Aid|Saint [A-Z]|St\. [A-Z]"
)

# Ethnic / heritage patterns (substring → canonical tag).
ETHNICITY_PATTERNS: list[tuple[str, str]] = [
    (r"\bAfrican[- ]American\b", "African American"),
    (r"\bAsian[- ]American\b", "Asian American"),
    (r"\bHispanic\b", "Hispanic/Latino"),
    (r"\bLatino\b", "Hispanic/Latino"),
    (r"\bNative American\b", "Native American"),
    (r"\bTibetan people\b", "Tibetan"),
    (r"\bAshkenazi Jews?\b", "Ashkenazi Jews"),
    (r"\bSephardi(c)? Jews?\b", "Sephardi Jews"),
    (r"\bRoma people\b", "Roma"),
    # "Jewish people" or any "Jewish" mention → also ethnic Jewish (we tag both
    # religion=Judaism above and ethnicity=Jewish here, since Wikipedia
    # categories conflate them and the user can pick which view to use).
    (r"\bJewish\b", "Jewish people"),
    (r"\bJews\b", "Jewish people"),
    # Diaspora ethnicity patterns: "Polish American", "Russian-Jewish descent",
    # etc. We capture the prefix nationality.
]

# "<Adjective> American" diaspora pattern — extract the heritage prefix.
DIASPORA = re.compile(r"\b([A-Z][a-z]+(?:-[A-Z][a-z]+)?)[- ]American\b")

# Exclude generic prefixes that aren't really heritages.
NOT_HERITAGES = {
    "African",  # noise; we already catch "African American" separately
    "Asian",
    "Native",
    "North",
    "South",
    "Latin",
    "Anglo",
    "Pan",
    "Pre",
    "New",
    "Old",
    "Modern",
    "Contemporary",
    "Scientific",  # "Scientific American" magazine, not a heritage
    "Central",
    "Eastern",
    "Western",
    "Northern",
    "Southern",
    "American",  # "American American" garbage
    "Christian",  # "Christian American" rarely intended as ethnicity
    "Roman",
    "Living",
    "United",
    "Foreign",
    "Member",
}

# Require a "people-noun" suffix elsewhere in the category for the diaspora
# match to count. Otherwise we pick up magazine/institution names.
DIASPORA_VALID_SUFFIX = re.compile(
    r"\b(people|men|women|scientists|physicists|chemists|biologists|mathematicians|"
    r"economists|writers|poets|novelists|playwrights|laureates|winners|recipients|"
    r"academics|professors|engineers|computer scientists|astronomers|physicians|"
    r"researchers|inventors|activists|politicians|diplomats|philosophers|"
    r"descent|ancestry|heritage|origin|emigrants|immigrants|expatriates|"
    r"Jews|Christians|Muslims|Hindus|Buddhists|Sikhs|"
    r"births|deaths)\b",
    re.IGNORECASE,
)


def _word_search(rx_or_pat, cat: str) -> bool:
    if isinstance(rx_or_pat, re.Pattern):
        return bool(rx_or_pat.search(cat))
    return bool(re.search(rx_or_pat, cat, flags=re.IGNORECASE))


def extract_tags(categories: list[str], list_tags: list[str]) -> tuple[set[str], set[str]]:
    """Return (religions, ethnicGroups) sets derived from category names + lists."""
    religions: set[str] = set()
    ethnicities: set[str] = set()

    for cat in categories:
        if RELIGION_FALSE_POSITIVE.search(cat):
            # don't run religion patterns on this category, but still allow
            # ethnicity matching
            religion_match = False
        else:
            religion_match = True

        for pat, canonical in RELIGION_PATTERNS:
            if religion_match and re.search(pat, cat):
                religions.add(canonical)
                break

        for pat, canonical in ETHNICITY_PATTERNS:
            if re.search(pat, cat):
                ethnicities.add(canonical)

        # diaspora "X American" / "X-American" — only count when the category
        # also contains a person-noun suffix (avoids "Scientific American people"
        # being read as a heritage).
        if DIASPORA_VALID_SUFFIX.search(cat):
            for m in DIASPORA.finditer(cat):
                prefix = m.group(1)
                if prefix not in NOT_HERITAGES:
                    ethnicities.add(f"{prefix} American")

    # curated list tags: editor-vetted, treat as high-confidence
    for tag in list_tags:
        if tag == "Jewish":
            religions.add("Judaism")
            ethnicities.add("Jewish people")
        elif tag == "Christian":
            religions.add("Christianity")
        elif tag == "Latin American":
            ethnicities.add("Hispanic/Latino")
        elif tag == "Indian":
            ethnicities.add("Indian")
        elif tag == "Chinese":
            ethnicities.add("Chinese")

    return religions, ethnicities


def load_heritage() -> dict:
    if not HERITAGE.exists():
        return {}
    return json.loads(HERITAGE.read_text())


# Canonicalize religion labels coming from different sources (Wikidata uses
# lowercase "atheism", Wikipedia categories use "Atheism", etc.)
RELIGION_CANONICAL = {
    "atheism": "Atheism",
    "agnosticism": "Agnosticism",
    "agnostic atheism": "Atheism",
    "reformed": "Reformed Church",
    "Reformed Church": "Reformed Church",
    "Catholic Church": "Catholicism",
    "Catholic": "Catholicism",
    "Roman Catholic Church": "Catholicism",
    "Russian Orthodox Church": "Eastern Orthodoxy",
    "Greek Orthodox Church": "Eastern Orthodoxy",
    "Eastern Orthodox Church": "Eastern Orthodoxy",
    "Sunni Islam": "Islam",
    "Shia Islam": "Islam",
    "Hinduism": "Hinduism",
    "Lutheran": "Lutheranism",
}

ETHNICITY_CANONICAL = {
    "African Americans": "African American",
    "Jewish": "Jewish people",
    "Jews": "Jewish people",
    "Tibetan people": "Tibetan",
    "Tibetans": "Tibetan",
    "Roma people": "Roma",
}


def canonical_religion(s: str) -> str:
    if s in RELIGION_CANONICAL:
        return RELIGION_CANONICAL[s]
    # Title-case fallback so "atheism" / "Atheism" merge
    return s[:1].upper() + s[1:] if s else s


def canonical_ethnicity(s: str) -> str:
    return ETHNICITY_CANONICAL.get(s, s)


def load_prize(slug: str, name: str, default_category: str, heritage: dict) -> list[dict]:
    path = PRIZES_DIR / f"{slug}.json"
    if not path.exists():
        return []
    out = []
    for r in json.loads(path.read_text()):
        if r.get("year") is None:
            # skip winners without a year - the time-series view needs it
            continue
        rec = {
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
            "religions": list(r.get("religions", [])),
            "ethnicGroups": list(r.get("ethnicGroups", [])),
            "prize": name,
        }
        out.append(merge_heritage(rec, heritage))
    return out


def main() -> None:
    heritage = load_heritage()
    print(f"Wikipedia heritage entries: {len(heritage)}")

    records: list[dict] = []
    nobel = load_nobel(heritage)
    print(f"Nobel: {len(nobel)} records")
    records.extend(nobel)

    for slug, (name, default_cat) in PRIZE_META.items():
        recs = load_prize(slug, name, default_cat, heritage)
        print(f"{name}: {len(recs)} records")
        records.extend(recs)

    records.sort(key=lambda r: (r["year"], r["prize"], r["name"] or ""))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(records, ensure_ascii=False, indent=2))
    print(f"\nwrote {len(records)} total prize-records to {OUT}")

    from collections import Counter
    by_prize = Counter(r["prize"] for r in records)
    print("by prize:", dict(by_prize))

    with_rel = sum(1 for r in records if r["religions"])
    with_eth = sum(1 for r in records if r["ethnicGroups"])
    print(f"religion coverage: {with_rel}/{len(records)} = {with_rel * 100 / len(records):.1f}%")
    print(f"ethnicity coverage: {with_eth}/{len(records)} = {with_eth * 100 / len(records):.1f}%")
    rels = Counter()
    eths = Counter()
    for r in records:
        for x in r["religions"]:
            rels[x] += 1
        for x in r["ethnicGroups"]:
            eths[x] += 1
    print("top religions:", rels.most_common(10))
    print("top ethnicities:", eths.most_common(10))


if __name__ == "__main__":
    main()
