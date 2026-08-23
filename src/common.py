"""Shared constants, data loading, and small formatting/aggregation
helpers used by every page module in src/views/.

Kept separate from app.py so each page can be its own file (see
src/views/) without a tangle of circular imports back into the app
entrypoint.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
LOGO_PATH = ASSETS_DIR / "logo.png"

APP_NAME = "InsurMarketExplorer"
TAGLINE = "Exploring Risks through data"

COL_LIFE = "#1f77b4"
COL_NONLIFE = "#d1351b"
COL_TOTAL = "#616365"
REGION_COLORS = {
    "East Asia & Pacific": "#d95f02",
    "Europe & Central Asia": "#7570b3",
    "Latin America & Caribbean": "#1b9e77",
    "Middle East, North Africa, Afghanistan & Pakistan": "#e6ab02",
    "North America": "#66a61e",
    "South Asia": "#e7298a",
    "Sub-Saharan Africa": "#a6761d",
}

METRIC_LABELS = {
    "penetration": "Penetration (% of GDP)",
    "primes": "Premium volume (USD)",
    "prime_par_tete": "Premium per capita (USD)",
}
METRIC_COLS = {
    "penetration": {"life": "life", "nonlife": "nonlife", "total": "total"},
    "primes": {"life": "primes_life", "nonlife": "primes_nonlife", "total": "primes_total"},
    "prime_par_tete": {"life": "prime_par_tete_life", "nonlife": "prime_par_tete_nonlife", "total": "prime_par_tete_total"},
}

# The six analytical tabs (Section 18) plus Home (cover page) and Data
# Sources (data-ops tooling) - not part of the analytical six, but needed
# operationally, so kept as extra nav entries rather than folded in.
NAV_ITEMS = [
    ("Home", "\U0001F3E0", "Home", ""),
    ("World", "\U0001F30D", "World Overview", "Global trends, regions and the world map"),
    ("Country", "\U0001F3F3️", "Country Explorer", "Deep-dive into any country's scorecard & trends"),
    ("Dynamics", "\U0001F4C8", "Market Dynamics", "Growth, CAGR, and the Life/Non-life mix over time"),
    ("Positioning", "\U0001F3AF", "Market Positioning", "Penetration vs premium per capita, by market size"),
    ("Rankings", "\U0001F3C6", "Rankings", "Full country rankings & market concentration"),
    ("Data Quality", "\U0001F50D", "Data Quality", "Coverage, completeness and coherence checks"),
    ("Data Sources", "\U0001F504", "Data Sources", "Refresh and combine the data feeds"),
]


@st.cache_data
def load_data():
    """Loads the combined long/wide tables written by combine_sources.py.
    Cached for the session; the Data Sources page clears this cache after
    a successful combine so the rest of the app picks up fresh data.
    """
    long_df = pd.read_csv(DATA_DIR / "insurance_long.csv")
    wide_df = pd.read_csv(DATA_DIR / "insurance_wide.csv")
    return long_df, wide_df


def aggregate_metric(df: pd.DataFrame, group_cols: list[str], metric: str) -> pd.DataFrame:
    """Aggregate life/nonlife/total for the selected metric, grouped by
    `group_cols` (e.g. ["year"] or ["region", "year"]).

    - penetration: 100 * sum(primes) / sum(gdp) within each group
    - prime_par_tete: sum(primes) / sum(population) within each group
    - primes: sum(primes) within each group

    Pass an empty `group_cols` to aggregate the whole dataframe into one row.
    """
    if not group_cols:
        df = df.assign(_all="all")
        group_cols = ["_all"]
        drop_index = True
    else:
        drop_index = False

    if metric == "penetration":
        d = df.dropna(subset=["gdp"])
        agg = d.groupby(group_cols).agg(
            _life=("primes_life", "sum"), _nonlife=("primes_nonlife", "sum"), _gdp=("gdp", "sum"),
        )
        out = pd.DataFrame({
            "life": 100 * agg["_life"] / agg["_gdp"],
            "nonlife": 100 * agg["_nonlife"] / agg["_gdp"],
            "total": 100 * (agg["_life"] + agg["_nonlife"]) / agg["_gdp"],
        })
    elif metric == "prime_par_tete":
        d = df.dropna(subset=["population"])
        agg = d.groupby(group_cols).agg(
            _life=("primes_life", "sum"), _nonlife=("primes_nonlife", "sum"), _pop=("population", "sum"),
        )
        out = pd.DataFrame({
            "life": agg["_life"] / agg["_pop"],
            "nonlife": agg["_nonlife"] / agg["_pop"],
            "total": (agg["_life"] + agg["_nonlife"]) / agg["_pop"],
        })
    else:
        agg = df.groupby(group_cols).agg(
            life=("primes_life", "sum"), nonlife=("primes_nonlife", "sum"), total=("primes_total", "sum"),
        )
        out = agg[["life", "nonlife", "total"]]
    out = out.reset_index()
    if drop_index:
        out = out.drop(columns="_all")
    return out


def fmt_metric(value, metric: str, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "NA"
    if metric == "penetration":
        return f"{value:,.{digits}f}%"
    return f"${value:,.{digits}f}"


def fmt_compact_usd(value) -> str:
    if value is None or pd.isna(value):
        return "NA"
    abs_v = abs(value)
    if abs_v >= 1e12:
        return f"${value / 1e12:,.2f}T"
    if abs_v >= 1e9:
        return f"${value / 1e9:,.2f}B"
    if abs_v >= 1e6:
        return f"${value / 1e6:,.2f}M"
    return f"${value:,.0f}"


def fmt_pct_signed(value, digits: int = 1) -> str:
    """Signed percentage, e.g. '+2.3%' / '-1.1%' - for growth deltas
    where the sign itself is the point."""
    if value is None or pd.isna(value):
        return "NA"
    return f"{value * 100:+.{digits}f}%"


def fmt_pp_signed(value, digits: int = 2) -> str:
    """Signed percentage-point change, e.g. '+1.20pp' - for penetration
    deltas, which are differences of percentages (not a percentage of a
    percentage, so not expressed as a compounding rate)."""
    if value is None or pd.isna(value):
        return "NA"
    return f"{value:+.{digits}f}pp"


def kpi_card_html(icon: str, label: str, value: str, sub: str = "") -> str:
    sub_html = f'<div class="imx-sub">{sub}</div>' if sub else ""
    return (
        f'<div class="imx-card"><div class="imx-icon">{icon}</div>'
        f'<div class="imx-label">{label}</div>'
        f'<div class="imx-value">{value}</div>{sub_html}</div>'
    )


def nav_card_html(icon: str, title: str, desc: str) -> str:
    return (
        f'<div class="imx-nav-card"><div class="imx-nav-icon">{icon}</div>'
        f'<div class="imx-nav-title">{title}</div>'
        f'<div class="imx-nav-desc">{desc}</div></div>'
    )


def source_transition_note(long_df: pd.DataFrame, transition_year: int | None) -> str | None:
    """Short caption explaining a World Bank -> Allianz handover on a
    chart, or None if the series doesn't cross one (Section 17)."""
    if transition_year is None:
        return None
    return (
        f"⚠️ From {transition_year} onward this series is sourced from the Allianz Global "
        f"Insurance Report rather than the World Bank - methodologies aren't guaranteed to match "
        f"exactly (see the Data Quality page), so treat the {transition_year} handover as a possible "
        f"break in the series, not necessarily a real market shift."
    )
