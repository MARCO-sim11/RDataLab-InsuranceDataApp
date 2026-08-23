"""Builds the standalone Allianz long/wide dataset from the PDF report
extraction, in the same long/wide schema as the World Bank dataset.

Penetration, premium volume, and premium-per-capita (density) are all
taken *directly* from Allianz reports - they're numbers the report already
publishes, not something this project needs to derive. 

Premium and density are reported in EUR; converting to USD needs an
exchange rate, which needs network access (src/fx_rates.py, cached by
refresh_data.py). Deriving primes/prime_par_tete from World Bank
GDP/population is still the fallback wherever a country/year is missing
an Allianz table or the FX cache doesn't cover that year - see
combine_sources.py's `_attach_macro`, which only fills gaps rather than
overwriting whatever's already set here.

Allianz's own segments (p&c / life / health) get folded into this project's
two-way Life / Non-life split: Non-life = p&c + health, matching how the
World Bank's own "non-life insurance" indicator is defined. The same sum
rule applies to density, since premium-per-capita is additive across
segments for a fixed population (p&c premium/pop + health premium/pop =
(p&c premium + health premium)/pop).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .country_aliases import resolve_countries
from .extract_allianz import extract_all
from .fetch_worldbank import get_countries
from .fx_rates import load_eur_usd_rates

LONG_COLS = ["country", "iso3", "region", "income_level", "year", "type", "penetration", "primes", "prime_par_tete", "source"]
ALLIANZ_SOURCE = "Allianz Global Insurance Report"

# App6/src/build_allianz_dataset.py -> App6 -> Insurance-penetration -> reports
DEFAULT_REPORTS_DIR = Path(__file__).resolve().parent.parent / "Allianz-Insurance Reports"


def _eur_to_usd(resolved: pd.DataFrame, eur_col: str, fx: pd.DataFrame, scale: float = 1.0) -> pd.Series:
    """Converts one EUR-denominated column to USD using the per-year
    EUR/USD rate, optionally rescaled (e.g. `scale=1e9` for a column
    reported in EUR billions, like the premium columns). Rows for a year
    missing from the FX cache come back as NaN (not an error) - see
    module docstring for the fallback.
    """
    if fx.empty:
        return pd.Series(pd.NA, index=resolved.index, dtype="float64")
    merged = resolved[["year"]].merge(fx, on="year", how="left")
    return resolved[eur_col] * merged["eur_usd"].values * scale


def build_allianz_dataset(reports_dir: Path = DEFAULT_REPORTS_DIR) -> tuple[pd.DataFrame, pd.DataFrame, list[dict]]:
    """Returns (allianz_long, allianz_wide, extraction_report).

    extraction_report is the list of per-PDF status dicts from
    extract_all(), plus trailing entries for country-name resolution and
    FX conversion coverage - this is the traceability the pipeline leans
    on, always surface it to the user rather than only the final row
    counts.
    """
    raw, metas = extract_all(reports_dir)
    if raw.empty:
        return pd.DataFrame(columns=LONG_COLS), pd.DataFrame(), metas

    wb_countries = get_countries()
    resolved, unmatched = resolve_countries(raw, wb_countries)

    if unmatched:
        metas.append({
            "filename": "(country resolution)", "data_year": None, "layout": None,
            "n_rows": len(unmatched), "status": "warning",
            "message": f"{len(unmatched)} country name(s) could not be resolved and were dropped: "
                       f"{', '.join(unmatched)}",
        })

    fx = load_eur_usd_rates()
    years_needed = sorted(resolved["year"].unique())
    years_covered = sorted(set(years_needed) & set(fx["year"])) if not fx.empty else []
    years_missing = sorted(set(years_needed) - set(years_covered))
    if fx.empty:
        metas.append({
            "filename": "(FX conversion)", "data_year": None, "layout": None, "n_rows": 0,
            "status": "warning",
            "message": "No cached EUR/USD rate found (data/fx_rates.csv) - run refresh_data.py to fetch it. "
                       "Premium volume and premium per capita will fall back to being derived from World "
                       "Bank GDP/population for every Allianz row until then.",
        })
    elif years_missing:
        metas.append({
            "filename": "(FX conversion)", "data_year": None, "layout": None, "n_rows": len(years_missing),
            "status": "warning",
            "message": f"No EUR/USD rate cached for {years_missing} - premium volume and premium per capita "
                       f"for those years will fall back to being derived from World Bank GDP/population.",
        })
    else:
        metas.append({
            "filename": "(FX conversion)", "data_year": None, "layout": None, "n_rows": len(years_covered),
            "status": "ok",
            "message": f"EUR/USD rate available for all {len(years_covered)} year(s) in this extraction "
                       f"(reference country: France).",
        })

    resolved = resolved.assign(
        nonlife_density_eur=resolved[["pc_density_eur", "health_density_eur"]].sum(axis=1, min_count=1),
        nonlife_premium_eur_bn=resolved[["pc_premium_eur_bn", "health_premium_eur_bn"]].sum(axis=1, min_count=1),
    )
    resolved["life_ppc_usd"] = _eur_to_usd(resolved, "life_density_eur", fx)
    resolved["nonlife_ppc_usd"] = _eur_to_usd(resolved, "nonlife_density_eur", fx)
    resolved["life_primes_usd"] = _eur_to_usd(resolved, "life_premium_eur_bn", fx, scale=1e9)
    resolved["nonlife_primes_usd"] = _eur_to_usd(resolved, "nonlife_premium_eur_bn", fx, scale=1e9)

    life = resolved.assign(type="Life", penetration=resolved["life_penetration"],
                            primes=resolved["life_primes_usd"], prime_par_tete=resolved["life_ppc_usd"])
    nonlife = resolved.assign(
        type="Non-life",
        penetration=resolved[["pc_penetration", "health_penetration"]].sum(axis=1, min_count=1),
        primes=resolved["nonlife_primes_usd"], prime_par_tete=resolved["nonlife_ppc_usd"],
    )

    long_df = pd.concat([life, nonlife], ignore_index=True)
    long_df["source"] = ALLIANZ_SOURCE
    long_df = long_df[LONG_COLS].dropna(subset=["penetration"])
    long_df = long_df.sort_values(["iso3", "year", "type"]).reset_index(drop=True)

    wide_df = long_df.pivot_table(
        index=["iso3", "year"], columns="type", values=["penetration", "primes", "prime_par_tete"], aggfunc="mean"
    )
    wide_df.columns = [f"{val}_{typ}" for val, typ in wide_df.columns]
    wide_df = wide_df.rename(columns={
        "penetration_Life": "life", "penetration_Non-life": "nonlife",
        "primes_Life": "primes_life", "primes_Non-life": "primes_nonlife",
        "prime_par_tete_Life": "prime_par_tete_life", "prime_par_tete_Non-life": "prime_par_tete_nonlife",
    })
    for col in ("life", "nonlife", "primes_life", "primes_nonlife", "prime_par_tete_life", "prime_par_tete_nonlife"):
        if col not in wide_df.columns:
            wide_df[col] = pd.NA
    wide_df["total"] = wide_df[["life", "nonlife"]].sum(axis=1, min_count=1)
    wide_df["primes_total"] = wide_df[["primes_life", "primes_nonlife"]].sum(axis=1, min_count=1)
    wide_df["prime_par_tete_total"] = wide_df[["prime_par_tete_life", "prime_par_tete_nonlife"]].sum(axis=1, min_count=1)
    wide_df = wide_df.reset_index()

    meta_cols = resolved[["iso3", "country", "region", "income_level"]].drop_duplicates("iso3")
    wide_df = wide_df.merge(meta_cols, on="iso3", how="left")
    wide_df = wide_df[["country", "iso3", "region", "income_level", "year", "life", "nonlife", "total",
                        "primes_life", "primes_nonlife", "primes_total",
                        "prime_par_tete_life", "prime_par_tete_nonlife", "prime_par_tete_total"]]
    wide_df = wide_df.sort_values(["country", "year"]).reset_index(drop=True)

    metas.append({
        "filename": "(summary)", "data_year": None, "layout": None,
        "n_rows": len(wide_df), "status": "ok",
        "message": f"Built {len(long_df)} long rows / {len(wide_df)} wide rows across "
                   f"{wide_df['year'].nunique()} year(s) for {wide_df['iso3'].nunique()} countries. "
                   f"{int(long_df['primes'].notna().sum())} row(s) carry a directly-reported premium volume "
                   f"and {int(long_df['prime_par_tete'].notna().sum())} a directly-reported premium per "
                   f"capita (both converted from EUR); the rest will be derived from World Bank GDP/"
                   f"population when combined.",
    })

    return long_df, wide_df, metas


def write_allianz_dataset(reports_dir: Path = DEFAULT_REPORTS_DIR,
                           out_dir: Path = Path(__file__).resolve().parent.parent / "data" / "allianz") -> list[dict]:
    long_df, wide_df, metas = build_allianz_dataset(reports_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    long_df.to_csv(out_dir / "allianz_long.csv", index=False)
    wide_df.to_csv(out_dir / "allianz_wide.csv", index=False)
    return metas


if __name__ == "__main__":
    for m in write_allianz_dataset():
        print(f"[{m['status']:>8}] {m['filename']}: {m['message']}")
