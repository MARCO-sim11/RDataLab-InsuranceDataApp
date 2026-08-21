"""Assembles the World Bank long/wide insurance dataset.

Combining this with the Allianz dataset (built by build_allianz_dataset.py)
into the CSVs the app reads is a separate, later step - see
combine_sources.py - so this module only ever deals with one source.
"""
from __future__ import annotations

import pandas as pd

from . import fetch_worldbank as wbfetch

ID_COLS = ["country", "iso3", "region", "income_level", "year", "type",
           "penetration", "population", "gdp", "primes", "prime_par_tete", "source"]
MACRO_COLS = ["country", "iso3", "region", "income_level", "year", "gdp", "population"]


def build_wb_dataset(start_year: int, end_year: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (long, macro).

    `long` is the insurance long table (one row per country/year/type),
    bounded to the years the GFDD insurance indicators actually cover.
    `macro` is GDP/population for every country/year in the requested
    range regardless of insurance coverage - the World Bank publishes GDP
    and population well past the insurance indicators' cutoff, and
    combine_sources.py needs that wider range to derive premium volume for
    years only the Allianz supplement covers.
    """
    print("Fetching World Bank country list...")
    countries = wbfetch.get_countries()
    iso3_list = countries["iso3"].tolist()

    print("Fetching GFDD.DI.09 (Life insurance premium / GDP)...")
    life = wbfetch.get_indicator(*wbfetch.INDICATORS["life_penetration"], iso3_list, start_year, end_year)
    life = life.rename(columns={"value": "penetration"})
    life["type"] = "Life"

    print("Fetching GFDD.DI.10 (Non-life insurance premium / GDP)...")
    nonlife = wbfetch.get_indicator(*wbfetch.INDICATORS["nonlife_penetration"], iso3_list, start_year, end_year)
    nonlife = nonlife.rename(columns={"value": "penetration"})
    nonlife["type"] = "Non-life"

    print("Fetching NY.GDP.MKTP.CD (GDP, current US$)...")
    gdp = wbfetch.get_indicator(*wbfetch.INDICATORS["gdp"], iso3_list, start_year, end_year)
    gdp = gdp.rename(columns={"value": "gdp"})

    print("Fetching SP.POP.TOTL (Population, total)...")
    population = wbfetch.get_indicator(*wbfetch.INDICATORS["population"], iso3_list, start_year, end_year)
    population = population.rename(columns={"value": "population"})

    macro = (
        gdp[["iso3", "year", "gdp"]]
        .merge(population[["iso3", "year", "population"]], on=["iso3", "year"], how="outer")
        .merge(countries, on="iso3", how="inner")
    )[MACRO_COLS]

    long = pd.concat([life, nonlife], ignore_index=True)
    long = long.merge(countries, on="iso3", how="inner")
    long = long.merge(population[["iso3", "year", "population"]], on=["iso3", "year"], how="left")
    long = long.merge(gdp[["iso3", "year", "gdp"]], on=["iso3", "year"], how="left")

    has_pen_gdp = long["penetration"].notna() & long["gdp"].notna()
    long["primes"] = pd.NA
    long.loc[has_pen_gdp, "primes"] = (long.loc[has_pen_gdp, "penetration"] / 100) * long.loc[has_pen_gdp, "gdp"]
    long["primes"] = pd.to_numeric(long["primes"])

    has_primes_pop = long["primes"].notna() & long["population"].notna() & (long["population"] > 0)
    long["prime_par_tete"] = pd.NA
    long.loc[has_primes_pop, "prime_par_tete"] = long.loc[has_primes_pop, "primes"] / long.loc[has_primes_pop, "population"]
    long["prime_par_tete"] = pd.to_numeric(long["prime_par_tete"])

    long["source"] = "World Bank"

    return long[ID_COLS], macro


def to_wide(long: pd.DataFrame) -> pd.DataFrame:
    base = (
        long.groupby(["iso3", "year"], as_index=False)
        .agg(
            country=("country", "first"),
            region=("region", "first"),
            income_level=("income_level", "first"),
            population=("population", "first"),
            gdp=("gdp", "first"),
        )
    )

    pivoted = long.pivot_table(
        index=["iso3", "year"],
        columns="type",
        values=["penetration", "primes", "prime_par_tete"],
        aggfunc="mean",
    )
    pivoted.columns = [f"{val}_{typ}" for val, typ in pivoted.columns]
    pivoted = pivoted.reset_index()

    wide = base.merge(pivoted, on=["iso3", "year"], how="left")

    rename_map = {
        "penetration_Life": "life",
        "penetration_Non-life": "nonlife",
        "primes_Life": "primes_life",
        "primes_Non-life": "primes_nonlife",
        "prime_par_tete_Life": "prime_par_tete_life",
        "prime_par_tete_Non-life": "prime_par_tete_nonlife",
    }
    wide = wide.rename(columns=rename_map)

    for col in rename_map.values():
        if col not in wide.columns:
            wide[col] = pd.NA

    wide["total"] = wide[["life", "nonlife"]].sum(axis=1, min_count=1)
    wide["primes_total"] = wide[["primes_life", "primes_nonlife"]].sum(axis=1, min_count=1)
    wide["prime_par_tete_total"] = wide[["prime_par_tete_life", "prime_par_tete_nonlife"]].sum(axis=1, min_count=1)

    wide["share_life"] = wide["primes_life"] / wide["primes_total"]
    wide["share_nonlife"] = wide["primes_nonlife"] / wide["primes_total"]
    bad_total = wide["primes_total"].isna() | (wide["primes_total"] <= 0)
    wide.loc[bad_total, ["share_life", "share_nonlife"]] = pd.NA

    return wide.sort_values(["country", "year"]).reset_index(drop=True)
