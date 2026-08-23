"""Annual average EUR/USD exchange rate, for converting Allianz's
EUR-denominated density (premium per capita) figures into USD.

Source: the World Bank's PA.NUS.FCRF indicator ("Official exchange rate,
LCU per US$, period average"), read for a single Eurozone member country.
Every Eurozone country reports the identical rate for a given year (LCU =
EUR for all of them since 1999), so any member works; France is used here
since it's already tracked by this project.

Fetching requires network (same World Bank API as everything else in
fetch_worldbank.py) and is done once, in refresh_data.py, alongside the
GDP/population fetch - not from build_allianz_dataset.py, which is meant
to stay fast/local/offline (see its module docstring). The rates are
cached to data/fx_rates.csv; if that cache doesn't exist yet (refresh
hasn't been re-run since this feature was added), density-based
conversion is skipped for the affected years and prime_par_tete falls
back to being derived from primes/population instead, exactly as before -
see combine_sources.py's `_attach_macro`.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import fetch_worldbank as wbfetch

CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "fx_rates.csv"
FX_REFERENCE_COUNTRY = "FRA"


def fetch_eur_usd_rates(start_year: int, end_year: int) -> pd.DataFrame:
    """Fetches EUR/USD (USD per 1 EUR) for each year in range from the
    World Bank API. Returns DataFrame(year, eur_usd) - multiply a EUR
    amount by `eur_usd` to get USD.

    PA.NUS.FCRF reports LCU per US$ (i.e. EUR per USD for a Eurozone
    country), so USD per EUR is its reciprocal.
    """
    raw = wbfetch.get_indicator(*wbfetch.INDICATORS["fx_rate"], [FX_REFERENCE_COUNTRY], start_year, end_year)
    raw = raw.dropna(subset=["value"])
    raw = raw[raw["value"] > 0]
    return pd.DataFrame({"year": raw["year"], "eur_usd": 1.0 / raw["value"]}).sort_values("year").reset_index(drop=True)


def write_fx_cache(start_year: int, end_year: int, path: Path = CACHE_PATH) -> pd.DataFrame:
    rates = fetch_eur_usd_rates(start_year, end_year)
    path.parent.mkdir(parents=True, exist_ok=True)
    rates.to_csv(path, index=False)
    return rates


def load_eur_usd_rates(path: Path = CACHE_PATH) -> pd.DataFrame:
    """Reads the cached rates written by write_fx_cache(). Returns an
    empty DataFrame(year, eur_usd) - not an error - if the cache doesn't
    exist yet, so callers can treat "no FX data available" as a normal,
    gracefully-degradable case rather than a crash.
    """
    if not path.exists():
        return pd.DataFrame(columns=["year", "eur_usd"])
    return pd.read_csv(path)
