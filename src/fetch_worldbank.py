"""World Bank data client built on wbgapi.

Two World Bank databases are involved:
  - db=2  (World Development Indicators)      -> GDP, population
  - db=32 (Global Financial Development)       -> life / non-life insurance
    premium volume to GDP (%)

wbgapi talks to the official World Bank API directly - no HTML scraping,
no manual CSV export.
"""
from __future__ import annotations

import pandas as pd
import wbgapi as wb

WDI_DB = 2
GFD_DB = 32

# name -> (indicator code, database id)
INDICATORS = {
    "life_penetration": ("GFDD.DI.09", GFD_DB),
    "nonlife_penetration": ("GFDD.DI.10", GFD_DB),
    "gdp": ("NY.GDP.MKTP.CD", WDI_DB),
    "population": ("SP.POP.TOTL", WDI_DB),
    # Official exchange rate, period average (LCU per US$) - used for a
    # Eurozone country in src/fx_rates.py to convert Allianz's
    # EUR-denominated density figures into USD.
    "fx_rate": ("PA.NUS.FCRF", WDI_DB),
}

# World Bank's 7 standard operational regions (the ones with a numeric
# region id in wb.region.list()) - used instead of a hand-maintained
# UN sub-region table.
REGION_NAMES = {
    "EAS": "East Asia & Pacific",
    "ECS": "Europe & Central Asia",
    "LCN": "Latin America & Caribbean",
    "MEA": "Middle East, North Africa, Afghanistan & Pakistan",
    "NAC": "North America",
    "SAS": "South Asia",
    "SSF": "Sub-Saharan Africa",
}


def get_countries() -> pd.DataFrame:
    """Real countries known to the World Bank.

    Aggregates ("World", income groups, regional blocs, etc.) are excluded
    via wbgapi's own `aggregate` flag - no name-based guessing needed.
    """
    rows = [
        {
            "iso3": e["id"],
            "country": e["value"],
            "region": REGION_NAMES.get(e.get("region"), e.get("region")),
            "income_level": e.get("incomeLevel"),
        }
        for e in wb.economy.list()
        if not e.get("aggregate")
    ]
    return pd.DataFrame(rows)


def get_indicator(code: str, db: int, iso3_list: list[str],
                   start_year: int, end_year: int) -> pd.DataFrame:
    """Fetch one indicator for a list of countries over a year range.

    Returns a tidy long dataframe: iso3, year, value.
    """
    wide = wb.data.DataFrame(
        code,
        economy=iso3_list,
        db=db,
        time=range(start_year, end_year + 1),
        numericTimeKeys=True,
    )

    long = (
        wide.reset_index()
        .rename(columns={"economy": "iso3"})
        .melt(id_vars="iso3", var_name="year", value_name="value")
    )
    long["year"] = long["year"].astype(int)
    return long
