# InsurAtlas

A Streamlit dashboard for exploring the global insurance market — penetration
(% of GDP), premium volume, and premium per capita, by country, region, and
time — built from two **independent** sources that only ever meet through
one auditable combine step. See `CHANGELOG.md` for a detailed history of
changes and `ROADMAP.md` for what's prioritized next.

## Data pipeline

```
worldbank_long.csv  ─┐                         ┌─→ insurance_long.csv
worldbank_wide.csv   ├─ combine_sources.py ────┤   (what the app reads)
worldbank_macro.csv  │  (validate, log,        │
allianz_long.csv     │   atomic write)         └─→ insurance_wide.csv
allianz_wide.csv    ─┘
fx_rates.csv         (EUR/USD, used by step 2 only)
```

1. **World Bank** (`refresh_data.py` + `src/fetch_worldbank.py` +
   `src/build_dataset.py`) — pulls insurance penetration, GDP, and
   population from the World Bank API via
   [`wbgapi`](https://pypi.org/project/wbgapi/), plus the EUR/USD exchange
   rate (`src/fx_rates.py`) used to convert Allianz's EUR figures.
2. **Allianz** (`src/extract_allianz.py` + `src/build_allianz_dataset.py`) —
   extracts penetration, premium volume, and density (premium per capita)
   directly from the Allianz Global Insurance Report PDFs (2022–2026
   editions, covering 2021–2025 data), converting EUR → USD with the
   matching year's exchange rate.
3. **Combine** (`src/combine_sources.py`) — merges the two into the CSVs
   the dashboard actually reads, validates the result (no duplicate rows,
   no unexplained row-count drop, plausible penetration values), and
   **only then** overwrites `insurance_long.csv` / `insurance_wide.csv`.
   World Bank always wins where it has data; Allianz only fills gaps and
   only ever fills `primes`/`prime_par_tete` where they're still missing
   after that. Every attempt is logged to `data/combine_log.csv`
   (success or failure), so a bad combine never takes the dashboard down.
4. **Dashboard** (`app.py` + `src/views/*.py`) — see "Pages" below.

## Setup

```bash
pip install -r requirements.txt
```

## 1. Refresh the World Bank data

```bash
python refresh_data.py
```

Fetches, for every real country (aggregates excluded via `wbgapi`'s own
`aggregate` flag) and years 2000 → current year:

| indicator | database | meaning |
|---|---|---|
| `GFDD.DI.09` | Global Financial Development (db 32) | Life insurance premium volume to GDP (%) |
| `GFDD.DI.10` | Global Financial Development (db 32) | Non-life insurance premium volume to GDP (%) |
| `NY.GDP.MKTP.CD` | World Development Indicators (db 2) | GDP (current US$) |
| `SP.POP.TOTL` | World Development Indicators (db 2) | Population, total |
| `PA.NUS.FCRF` | World Development Indicators (db 2) | LCU per US$ (France, period average) — used to derive the EUR/USD rate |

Writes `data/worldbank_long.csv`, `data/worldbank_wide.csv`,
`data/worldbank_macro.csv` (GDP/population over the full year range, needed
to price any Allianz-only year that still lacks a directly-reported
figure), and `data/fx_rates.csv`. Slow (a couple of minutes, needs
network) — the only step not exposed as a button in the app.

## 2. Extract the Allianz reports

```bash
python -m src.build_allianz_dataset
```

or the **Extract Allianz reports** button on the **Data Sources** page.
Fast (a few seconds), local, no network — it parses the PDFs already
sitting in `../Allianz-Insurance Reports/`.

Reads the country appendix table from each report edition and writes
`data/allianz/allianz_long.csv` / `allianz_wide.csv`, with penetration,
premium volume, and premium per capita taken **directly from Allianz's own
figures** (converted EUR → USD) rather than re-derived — primes/per-capita
are only computed from World Bank GDP/population as a fallback, for the
rare row missing a directly-reported value or a cached FX rate. Every run
prints a per-report status (`ok` / `warning` / `failed` / `missing` /
`skipped`) plus a country-name-resolution report — **always check this**,
it's the only way to know if a report's layout changed and broke the
parser.

Report editions 2022–2026 (2021–2025 data) use two slightly different
table layouts, both handled (`src/extract_allianz.py`). The 2021 edition
(2020 data) has no extractable appendix table — 2020 stays uncovered by
Allianz unless filled in by hand (see below). The 2022 edition (2021 data)
only publishes a p&c/life split with no separate health line — see
"Known limitations" below for what that means for that one year.

Allianz's own p&c / life / health split is folded into this project's
Life / Non-life schema as `Non-life = p&c + health`.

**Country name mismatches** ("South Korea" vs "Korea, Rep.", "Czech
Republic" vs "Czechia", etc.) are handled in `src/country_aliases.py` — an
unresolved name is reported in the extraction log and the row is dropped,
never silently mis-attributed.

## 3. Combine

```bash
python -m src.combine_sources
```

or the **Combine sources** button on the **Data Sources** page. Needs
steps 1 and 2 to have run at least once.

### Optional manual supplement

`data/allianz_recent.csv` is a small hand-editable CSV that
`combine_sources.py` also folds in, on top of the PDF extraction — useful
for filling 2020 (not extractable, see above) or correcting a specific
figure. Same rule: it only fills gaps, never overwrites World Bank or the
PDF extraction.

## 4. Run the dashboard

```bash
streamlit run app.py
```

## Pages

- **Home** — cover page: World/Life/Non-life KPI cards, global evolution
  and by-region charts, shortcuts into every other page.
- **World Overview** — world KPIs, evolution over time (Life/Non-life/
  Total), Life/Non-life split, evolution by region, a choropleth map, and
  a region ranking.
- **Country Explorer** — the selected country's KPIs (flag, Life/Non-life/
  Total), its evolution over time with an optional dashed overlay
  comparing it to the world average, a Life/Non-life split, and the
  **Country Scorecard** (market size, development, consumption, growth,
  global/regional ranking, and a maturity profile).
- **Market Dynamics** — growth/CAGR over a chosen period and how the
  Life/Non-life structure has shifted.
- **Market Positioning** — penetration vs. premium per capita, bubble size
  = market volume, by region, with quadrant benchmarks.
- **Rankings** — the full country ranking table plus market concentration
  (HHI, top 5/10/20 share).
- **Data Quality** — overall completeness, coverage by year (shows the
  World Bank reporting lag directly), completeness by country, coherence
  flags (missing GDP/population despite a reported penetration,
  implausibly high penetration, large year-over-year jumps), and a
  per-country detail table with the source of every figure.
- **Data Sources** — re-run steps 2 and 3 from the browser, see current
  row counts per source, and the combine history log.

The metric (penetration / premium volume / premium per capita), time
range, year, and country filters live in the sidebar and are also
replicated inline on World Overview and Country Explorer — either copy
stays in sync with the other.

## Known limitations

- **World Bank ↔ Allianz definitional seam**: World Bank's "non-life
  insurance" indicator and Allianz's "p&c + health" aren't guaranteed to
  be defined identically (how health insurance is classified varies by
  country and source). Since Allianz only fills years World Bank doesn't
  cover, this shows up as a possible level shift right at the handoff
  year, not a discontinuity within either source's own run. The Data
  Quality page's coherence flags and the "World Bank → Allianz" markers
  on the evolution charts point at exactly where this could matter.
- **2021 data, specifically**: the Allianz report edition covering 2021
  only publishes a p&c/life split, no separate health line — so that one
  year's Non-life figure may understate health-heavy markets relative to
  2020 (World Bank) and 2022+ (Allianz, p&c+health). Treat a sharp
  2021 ↔ 2022 move as a possible artifact of this gap, not necessarily a
  real market shift, until cross-checked against another source.

## Project layout

```
App6/
├── app.py                        Streamlit entrypoint - sidebar filters, dispatch to src/views/
├── refresh_data.py                World Bank refresh entry point
├── requirements.txt
├── .streamlit/config.toml         native light/dark theme definitions
├── src/
│   ├── common.py                  constants, load_data(), aggregate_metric(), formatting helpers
│   ├── theme.py                   brand colors, card CSS
│   ├── analytics.py               market-structure calculations (positioning, CAGR, concentration, ranking...)
│   ├── data_quality.py            coverage & coherence diagnostics
│   ├── fetch_worldbank.py         wbgapi client (countries, indicators)
│   ├── build_dataset.py           World Bank long/wide/macro assembly
│   ├── fx_rates.py                EUR/USD rate fetch + cache
│   ├── extract_allianz.py         Allianz PDF appendix-table parser
│   ├── country_aliases.py         Allianz name -> World Bank iso3 mapping
│   ├── build_allianz_dataset.py   Allianz long/wide assembly
│   ├── combine_sources.py         merge, validation, atomic write, log
│   └── views/                     one file per page, each exporting render(ctx)
│       ├── home.py, world.py, country.py, dynamics.py, positioning.py,
│       └── rankings.py, quality.py, sources.py
└── data/
    ├── worldbank_long/wide/macro.csv   generated (step 1)
    ├── fx_rates.csv                    generated (step 1)
    ├── allianz/allianz_long/wide.csv   generated (step 2)
    ├── allianz_recent.csv              optional manual supplement (edit this)
    ├── combine_log.csv                 generated (step 3) - history of every attempt
    └── insurance_long/wide.csv         generated (step 3) - what the app reads
```
