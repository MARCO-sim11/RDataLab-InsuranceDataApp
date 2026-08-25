"""Data-quality diagnostics for the consolidated insurance dataset.

Feeds the dashboard's "Data Quality" tab: coverage/missingness by year and
by country, and a handful of coherence checks that flag rows worth a second
look rather than silently trusting every number pulled from the API.
"""
from __future__ import annotations

import pandas as pd

COVERAGE_METRICS = {
    "Life penetration": "life",
    "Non-life penetration": "nonlife",
    "GDP": "gdp",
    "Population": "population",
}


def latest_reliable_year(wide: pd.DataFrame, min_coverage: float = 0.3) -> int:
    """Most recent year where at least `min_coverage` of countries report a
    total penetration figure.

    The World Bank / Allianz-supplemented panel always stretches to the
    current year even though most countries only report with a 1-2 year
    lag - using plain max(year) as a default selection lands on a mostly
    empty year. This picks the latest year that's actually usable instead.
    """
    coverage = wide.groupby("year")["total"].apply(lambda s: s.notna().mean()).sort_index()
    reliable = coverage[coverage >= min_coverage]
    if reliable.empty:
        return int(coverage.index.max())
    return int(reliable.index.max())


def completeness_by_year(wide: pd.DataFrame) -> pd.DataFrame:
    """Long dataframe: year, metric, coverage (share of countries with a value)."""
    rows = []
    for label, col in COVERAGE_METRICS.items():
        s = wide.groupby("year")[col].apply(lambda x: x.notna().mean())
        for year, pct in s.items():
            rows.append({"year": int(year), "metric": label, "coverage": pct})
    return pd.DataFrame(rows)


def completeness_by_country(wide: pd.DataFrame, start_year: int, end_year: int) -> pd.DataFrame:
    """Per-country completeness over the selected year range."""
    sub = wide[(wide["year"] >= start_year) & (wide["year"] <= end_year)]
    grouped = sub.groupby("country").agg(
        n_years=("year", "nunique"),
        n_with_total=("total", lambda s: s.notna().sum()),
        n_with_gdp=("gdp", lambda s: s.notna().sum()),
        n_with_population=("population", lambda s: s.notna().sum()),
    )
    grouped["completeness_pct"] = (100 * grouped["n_with_total"] / grouped["n_years"]).round(1)
    return grouped.reset_index().sort_values("completeness_pct")


def coherence_flags(wide: pd.DataFrame, penetration_outlier_pct: float = 40.0,
                     yoy_jump_pp: float = 5.0) -> pd.DataFrame:
    """Rows worth a manual check: missing macro data, extreme penetration
    values, or abrupt year-over-year swings."""
    flags = []

    missing_macro = wide[wide["total"].notna() & (wide["gdp"].isna() | wide["population"].isna())]
    for _, r in missing_macro.iterrows():
        missing = []
        if pd.isna(r["gdp"]):
            missing.append("GDP")
        if pd.isna(r["population"]):
            missing.append("population")
        flags.append({
            "country": r["country"], "year": int(r["year"]), "issue": "Missing GDP/population",
            "detail": f"penetration reported but {' & '.join(missing)} missing "
                      f"-> premium volume / per-capita cannot be derived",
        })

    outliers = wide[wide["total"] > penetration_outlier_pct]
    for _, r in outliers.iterrows():
        flags.append({
            "country": r["country"], "year": int(r["year"]), "issue": "Very high penetration",
            "detail": f"total penetration = {r['total']:.1f}% of GDP - worth double-checking "
                      f"(can be genuine for reinsurance/offshore hubs)",
        })

    sorted_wide = wide.sort_values(["iso3", "year"]).copy()
    sorted_wide["prev_total"] = sorted_wide.groupby("iso3")["total"].shift(1)
    sorted_wide["jump"] = (sorted_wide["total"] - sorted_wide["prev_total"]).abs()
    jumps = sorted_wide[sorted_wide["jump"] >= yoy_jump_pp]
    for _, r in jumps.iterrows():
        flags.append({
            "country": r["country"], "year": int(r["year"]), "issue": "Large year-over-year jump",
            "detail": f"{r['prev_total']:.2f}% -> {r['total']:.2f}% ({r['jump']:.2f} pp change)",
        })

    if not flags:
        return pd.DataFrame(columns=["country", "year", "issue", "detail"])
    return pd.DataFrame(flags).sort_values(["issue", "country", "year"]).reset_index(drop=True)


def country_source_breakdown(long: pd.DataFrame) -> pd.DataFrame:
    """Per-country count of rows by source (World Bank vs Allianz supplement)."""
    has_value = long[long["penetration"].notna()]
    return (
        has_value.groupby(["country", "source"]).size().reset_index(name="n_rows")
        .pivot(index="country", columns="source", values="n_rows")
        .fillna(0)
        .astype(int)
        .reset_index()
    )
