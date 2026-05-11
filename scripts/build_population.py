#!/usr/bin/env python3
"""Emit a country -> population JSON for per-capita visualizations.

Populations are approximate 2023 estimates (millions rounded to 0.1).
The country names match the Nobel API's `countryNow` field exactly.
Sources: World Bank / UN data, manually curated.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOBEL = ROOT / "data" / "processed" / "nobel.json"
PRIZES = ROOT / "data" / "processed" / "prizes.json"
OUT = ROOT / "data" / "processed" / "population.json"

# population in millions (2023 estimates)
POPULATION_M = {
    "USA": 334.9,
    "United Kingdom": 67.6,  # excludes Scotland/NI rolled out below
    "Scotland": 5.5,
    "Northern Ireland": 1.9,
    "Germany": 83.8,
    "France": 68.0,
    "Japan": 124.5,
    "Sweden": 10.5,
    "Russia": 143.4,
    "Poland": 36.7,
    "Switzerland": 8.8,
    "Canada": 40.1,
    "the Netherlands": 17.9,
    "Italy": 58.9,
    "Austria": 9.1,
    "Norway": 5.5,
    "Denmark": 5.9,
    "Hungary": 9.6,
    "China": 1410.7,
    "Australia": 26.6,
    "Belgium": 11.7,
    "India": 1428.6,
    "South Africa": 60.4,
    "Spain": 48.4,
    "Czech Republic": 10.5,
    "Ukraine": 36.7,
    "Egypt": 112.7,
    "Israel": 9.8,
    "Ireland": 5.3,
    "Finland": 5.6,
    "Argentina": 45.8,
    "Turkey": 85.3,
    "Belarus": 9.2,
    "Romania": 19.0,
    "New Zealand": 5.2,
    "Lithuania": 2.9,
    "Pakistan": 240.5,
    "Mexico": 128.5,
    "South Korea": 51.7,
    "Iran": 89.2,
    "Luxembourg": 0.7,
    "Chile": 19.6,
    "Portugal": 10.5,
    "Algeria": 45.6,
    "Bosnia and Herzegovina": 3.2,
    "Guatemala": 17.6,
    "Saint Lucia": 0.18,
    "Venezuela": 28.8,
    "Colombia": 52.1,
    "East Timor": 1.4,
    "Bangladesh": 172.9,
    "Liberia": 5.4,
    "Tunisia": 12.4,
    "Faroe Islands (Denmark)": 0.054,
    "Slovakia": 5.4,
    "Latvia": 1.9,
    "Slovenia": 2.1,
    "Indonesia": 277.5,
    "Croatia": 3.9,
    "Iceland": 0.39,
    "Guadeloupe, France": 0.4,
    "Zimbabwe": 16.7,
    "Brazil": 216.4,
    "Azerbaijan": 10.4,
    "Vietnam": 98.9,
    "Greece": 10.4,
    "North Macedonia": 2.1,
    "Bulgaria": 6.7,
    "Madagascar": 30.3,
    "Taiwan": 23.4,
    "Nigeria": 223.8,
    "Costa Rica": 5.2,
    "Myanmar": 54.6,
    "Trinidad and Tobago": 1.5,
    "Ghana": 33.5,
    "Kenya": 55.1,
    "Cyprus": 1.3,
    "Peru": 34.4,
    "Yemen": 34.4,
    "Morocco": 37.0,
    "Democratic Republic of the Congo": 102.3,
    "Iraq": 45.5,
    "Ethiopia": 126.5,
    "Philippines": 117.3,
    "Lebanon": 5.4,
    "Jordan": 11.3,
    "Estonia": 1.4,
    "Serbia": 6.6,
    "Sri Lanka": 22.0,
    "Uruguay": 3.4,
    "Uzbekistan": 35.6,
    "Dutch East Indies": 277.5,  # → modern Indonesia
}


def main() -> None:
    used: set[str] = set()
    for f in (PRIZES, NOBEL):
        if f.exists():
            for r in json.loads(f.read_text()):
                if r.get("currentCountry"):
                    used.add(r["currentCountry"])
    used = sorted(used)
    missing = [c for c in used if c not in POPULATION_M]
    if missing:
        print(f"WARN: missing population for: {missing}")

    rows = [
        {"country": c, "populationMillions": POPULATION_M[c]}
        for c in used if c in POPULATION_M
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2))
    print(f"wrote {len(rows)} country populations to {OUT}")


if __name__ == "__main__":
    main()
