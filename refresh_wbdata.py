"""World Bank data refresh pipeline.

Pulls insurance penetration, GDP and population directly from the World
Bank API (via wbgapi) and writes the standalone World Bank long/wide CSVs.
Also fetches and caches the EUR/USD exchange rate (see src/fx_rates.py) -
grouped here rather than in build_allianz_dataset.py because both this
and the FX rate need network access, and build_allianz_dataset.py is
meant to stay fast/local/offline.

This is one of two independent sources (the other is the Allianz report
extraction - see build_allianz_dataset.py). Combining the two into the
CSVs the app actually reads (insurance_long.csv / insurance_wide.csv) is a
separate step - see combine_sources.py / the "Update data sources" section
in the app - so a bad combine never corrupts this source data.

Usage (from this directory, App4/):
    python refresh_data.py

Re-run whenever you want fresher World Bank data - safe to run repeatedly.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from src.build_wb_datasets import build_wb_dataset, to_wide
from src.fx_rates import write_fx_cache

DATA_DIR = Path(__file__).resolve().parent / "data"
START_YEAR = 2000
END_YEAR = dt.date.today().year


def main() -> None:
    print(f"=== Fetching World Bank data ({START_YEAR}-{END_YEAR}) ===")
    long, macro = build_wb_dataset(START_YEAR, END_YEAR)

    print("=== Pivoting to wide format ===")
    wide = to_wide(long)

    DATA_DIR.mkdir(exist_ok=True)
    long.to_csv(DATA_DIR / "worldbank_long.csv", index=False)
    wide.to_csv(DATA_DIR / "worldbank_wide.csv", index=False)
    macro.to_csv(DATA_DIR / "worldbank_macro.csv", index=False)

    print("=== Fetching EUR/USD exchange rate ===")
    fx = write_fx_cache(START_YEAR, END_YEAR)
    print(f"Cached {len(fx)} year(s) of EUR/USD rates to data/fx_rates.csv.")

    print(
        f"Done. {len(long)} rows (long), {len(wide)} rows (wide). "
        f"Years covered: {int(wide['year'].min())}-{int(wide['year'].max())}. "
        f"Macro (GDP/population) covers {int(macro['year'].min())}-{int(macro['year'].max())}. "
        f"Run the 'Update data sources' step (combine_sources.py or the app button) "
        f"to rebuild insurance_long.csv / insurance_wide.csv from this."
    )


if __name__ == "__main__":
    main()
