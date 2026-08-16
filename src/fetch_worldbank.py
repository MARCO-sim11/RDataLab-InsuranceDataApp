"""
    Some basic functions to interact with the World bank data API

    Two World bank data are involved : 
        - db = 2 : World Development Indicators  (Population / GDP)
        - db = 32 : Global Financial Development (Life/non life Insurance premia/GDP)
"""

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


def get_counties() -> pd.DataFrame:
    """
      Provides the countries known by the World Bank
      
      Aggregates (income groups, "World", regional blocks) are exluded
    """
    rows = [
        {
            "iso3": e["id"],
            "country": e["value"],
            "region": REGION_NAMES.get(e.get("region"), e.get("region")),
            "income_level": e.get("incomeLevel")
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
