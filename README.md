# Prize Visualizer

Interactive visualizer for prize statistics. Currently covers ~1,970 prize records:

- **Nobel Prize** (1901–present, official Nobel API)
- **Fields Medal** (math, since 1936)
- **Abel Prize** (math, since 2003)
- **Turing Award** (computer science, since 1966)
- **Wolf Prize** in Math, Physics, Chemistry, Medicine (since 1978)
- **Crafoord Prize** (rotating: math/astronomy/geosciences/biosciences)
- **Breakthrough Prize** in Life Sciences, Fundamental Physics, Mathematics
- **Kavli Prize** in Astrophysics, Nanoscience, Neuroscience
- **Copley Medal** (Royal Society, since 1731 — oldest in the dataset)
- **Lasker Award** (medicine — only the umbrella QID; sub-prizes are tagged separately on Wikidata so coverage is limited)

Olympic Medals etc. can be added by mirroring the same pipeline.

## What it shows

- **By country** — absolute prize counts per laureate's birthplace mapped to its modern country
- **Per capita** — prizes per million people (~2023 populations)
- **Over time** — prizes per year line chart
- **Gender over time** — male / female / org breakdown by decade
- **By category** — Physics, Chemistry, Medicine, Literature, Peace, Economic Sciences

Filterable by category and year range.

## Data sources

| Field | Source | Notes |
|-------|--------|-------|
| Year, category, gender, birth country, name | Nobel API v2.1 | Authoritative; complete |
| Modern country mapping | Nobel API `countryNow` | Handles dissolved states (Prussia → Germany) |
| Population | Hardcoded 2023 estimates | Manually curated; see `scripts/build_population.py` |
| Religion, ethnicity | (planned) Wikidata P140 / P172 | Coverage will be partial; not yet wired up |

The Nobel API does **not** track religion or ethnicity. Those would come from a separate Wikidata SPARQL pass against each laureate's `wikidata.id`. Both fields are inherently messy — many laureates have neither set on Wikidata, and "Jewish" mixes religion and ethnicity. Any UI exposing them needs explicit caveats.

## Building & running

```sh
# 1. Fetch and normalize data (one-time, or whenever you want to refresh)
python3 scripts/fetch_nobel.py            # → data/raw/laureates.json
python3 scripts/fetch_wikidata.py         # → data/raw/wikidata_enrichment.json (religion/ethnicity)
python3 scripts/build_dataset.py          # → data/processed/nobel.json
python3 scripts/fetch_wikidata_prizes.py  # → data/raw/prizes/<slug>.json (Fields, Turing, etc.)
python3 scripts/build_combined.py         # → data/processed/prizes.json (Elm reads this)
python3 scripts/build_population.py       # → data/processed/population.json

# 2. Compile the frontend
cd frontend
elm make src/Main.elm --output=main.js

# 3. Serve from the project root (so /data/processed/*.json resolves)
cd ..
python3 -m http.server 8765 --bind 127.0.0.1
# open http://127.0.0.1:8765/frontend/
```

## Layout

```
.
├── scripts/
│   ├── fetch_nobel.py        # downloads raw API responses
│   ├── build_dataset.py      # normalizes to one record per laureate-prize
│   └── build_population.py   # emits country -> population map
├── data/
│   ├── raw/laureates.json
│   └── processed/
│       ├── nobel.json
│       └── population.json
└── frontend/
    ├── index.html
    ├── elm.json
    ├── main.js               # compiled, gitignored in real projects
    └── src/Main.elm
```

## Adding a new prize

1. Write a fetcher in `scripts/` that produces the same flat schema as `nobel.json`:
   ```
   { id, name, kind, year, category, gender, birthCountry, currentCountry, birthYear,
     wikipediaSlug, wikidataId, portion, motivation }
   ```
2. Update the Elm app to load and tag the new dataset (e.g. add a "Prize" filter alongside category).
