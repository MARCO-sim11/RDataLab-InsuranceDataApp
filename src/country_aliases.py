"""Maps the country names used in Allianz report tables to World Bank
iso3 codes / country names.

Most names match the World Bank list directly or after light normalization
(case, punctuation). This dict covers the ones that don't - built by
running the extraction, diffing against wbgapi's country list, and fixing
what didn't match (see resolve_countries()'s unmatched report to redo this
if a future report introduces a new mismatch).
"""
from __future__ import annotations

import pandas as pd

# Allianz name -> World Bank iso3
ALIASES: dict[str, str] = {
    "Czech Republic": "CZE",
    "Egypt": "EGY",
    "Hong Kong": "HKG",
    "Kenia": "KEN",          # typo for Kenya in the 2022 report edition
    "Laos": "LAO",
    "Russia": "RUS",
    "Slovakia": "SVK",
    "South Korea": "KOR",
    "Turkey": "TUR",
    "Türkiye": "TUR",  # "Türkiye" - the literal ü renders oddly in some terminals/fonts
    "Vietnam": "VNM",
}

# Countries Allianz reports that the World Bank doesn't track at all (no
# iso3 in wbgapi's country list) - kept with a manual iso3 so they still
# show up in the dashboard, just without World Bank region/GDP/population.
MANUAL_COUNTRIES: dict[str, str] = {
    "Taiwan": "TWN",
}


def _norm(name: str) -> str:
    return name.lower().replace(",", "").replace(".", "").replace("-", " ").strip()


def resolve_countries(allianz_df: pd.DataFrame, wb_countries: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Attach iso3/country/region/income_level to a raw Allianz extraction.

    Returns (resolved_df, unmatched_names). Rows whose country name can't be
    resolved at all (not in the World Bank list, no alias, no manual entry)
    are dropped and their raw name is returned in `unmatched_names` so the
    caller can report/log it rather than silently lose data.
    """
    wb_by_name = {row.country: row for row in wb_countries.itertuples()}
    wb_by_norm = {_norm(row.country): row for row in wb_countries.itertuples()}
    wb_by_iso3 = {row.iso3: row for row in wb_countries.itertuples()}

    resolved_rows = []
    unmatched = []

    for _, row in allianz_df.iterrows():
        raw = row["country_raw"]
        wb_row = None

        if raw in wb_by_name:
            wb_row = wb_by_name[raw]
        elif _norm(raw) in wb_by_norm:
            wb_row = wb_by_norm[_norm(raw)]
        elif raw in ALIASES:
            wb_row = wb_by_iso3.get(ALIASES[raw])

        record = row.to_dict()
        if wb_row is not None:
            record.update(iso3=wb_row.iso3, country=wb_row.country,
                          region=wb_row.region, income_level=wb_row.income_level)
        elif raw in MANUAL_COUNTRIES:
            record.update(iso3=MANUAL_COUNTRIES[raw], country=raw, region=None, income_level=None)
        else:
            unmatched.append(raw)
            continue

        resolved_rows.append(record)

    resolved = pd.DataFrame(resolved_rows)
    return resolved, sorted(set(unmatched))
