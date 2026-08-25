"""Shared constants, data loading, and small formatting/aggregation
helpers used by every page module in src/views/.

Kept separate from app.py so each page can be its own file (see
src/views/) without a tangle of circular imports back into the app
entrypoint.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
LOGO_PATH = ASSETS_DIR / "logo.png"

APP_NAME = "InsurAtlas"
TAGLINE = "Exploring Risks through data"
ICON_LIFE_SVG = """<svg width="40" height="40" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" style="vertical-align:-6px">
  <defs>
    <linearGradient id="lifeGrad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#f9a825"/>
      <stop offset="100%" stop-color="#e8402c"/>
    </linearGradient>
  </defs>
  <g fill="none" stroke="url(#lifeGrad)" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
    <line x1="32" y1="4" x2="32" y2="60"/>
    <path d="M4 32 C4 17 16 6 32 6 C48 6 60 17 60 32"/>
    <path d="M4 32 C4 26 9 21 15 21 C21 21 26 26 26 32"/>
    <path d="M26 32 C26 26 27 21 32 21"/>
    <path d="M38 32 C38 26 39 21 32 21"/>
    <path d="M38 32 C38 26 43 21 49 21 C55 21 60 26 60 32"/>
    <circle cx="15" cy="42" r="4.2"/>
    <path d="M8 58 C8 51 11 46 15 46 C19 46 22 51 22 58"/>
    <circle cx="49" cy="42" r="4.2"/>
    <path d="M42 58 C42 51 45 46 49 46 C53 46 56 51 56 58"/>
  </g>
</svg>"""


ICON_NONLIFE_IMG = """<img src="data:image/png;base64,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" width="35" style="vertical-align:-7px">"""


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

ICON_NONLIFE_SVG = f"""<svg width="35" height="35" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" style="vertical-align:-7px">
  <circle cx="32" cy="24" r="18" fill="{COL_NONLIFE}"/>
  <path d="M32 12 L42 16 V26 C42 33 37 38 32 41 C27 38 22 33 22 26 V16 Z" fill="#ffffff"/>
  <path d="M27 25 L31 30 L38 19" fill="none" stroke="{COL_NONLIFE}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M6 48 Q6 60 22 60" fill="none" stroke="#2b2b2b" stroke-width="7" stroke-linecap="round"/>
  <path d="M42 60 Q58 60 58 48" fill="none" stroke="#2b2b2b" stroke-width="7" stroke-linecap="round"/>
</svg>"""

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


# World/Life/Non-life KPI cards are rendered through an iframe
# (components.html) instead of st.markdown so the JS below can detect the
# theme directly from the parent document's own background color and
# restyle the card live. Plain st.markdown HTML can't do this: its color
# values are baked in by Python at script-run time, and toggling the theme
# in the Settings menu does not by itself trigger a script rerun, so those
# cards would keep the old theme's colors until some unrelated widget
# interaction happened to rerun the script. This card is its own tiny
# same-origin document (a components.html iframe is same-origin with the
# main app by default), so it can read the live theme with no round trip
# to Python at all, and re-checks it every 400ms.
_CARD_PALETTE = {
    "dark": {"bg": "#161f33", "border": "#26314a", "muted": "#9aa7bd", "text": "#eef2f7",
             "shadow": "0 6px 20px rgba(0,0,0,0.35)"},
    "light": {"bg": "#fbf6ec", "border": "#ddcdac", "muted": "#5b6b7f", "text": "#122436",
              "shadow": "0 6px 20px rgba(15,45,75,0.08)"},
}

_CARD_THEME_WATCHER_JS = f"""
<script>
(function() {{
  var palette = {json.dumps(_CARD_PALETTE)};
  function luminance(rgb) {{
    var m = rgb.match(/\\d+/g);
    if (!m) return 255;
    return (parseInt(m[0]) * 299 + parseInt(m[1]) * 587 + parseInt(m[2]) * 114) / 1000;
  }}
  function apply() {{
    try {{
      var bg = getComputedStyle(window.parent.document.body).backgroundColor;
      var c = luminance(bg) < 128 ? palette.dark : palette.light;
      var root = document.documentElement.style;
      root.setProperty('--imx-bg', c.bg);
      root.setProperty('--imx-border', c.border);
      root.setProperty('--imx-muted', c.muted);
      root.setProperty('--imx-text', c.text);
      root.setProperty('--imx-shadow', c.shadow);
    }} catch (e) {{}}
  }}
  apply();
  setInterval(apply, 400);
}})();
</script>
"""


def render_kpi_card(icon: str, label: str, value: str, sub: str = "", height: int = 175) -> None:
    sub_html = f'<div class="imx-sub">{sub}</div>' if sub else ""
    components.html(
        f"""
        <div class="imx-card">
          <div class="imx-icon">{icon}</div>
          <div class="imx-label">{label}</div>
          <div class="imx-value">{value}</div>
          {sub_html}
        </div>
        <style>
          html, body {{ margin: 0; padding: 0; background: transparent; }}
          .imx-card {{
            font-family: "Source Sans Pro", sans-serif;
            background: var(--imx-bg, #fbf6ec);
            border: 1px solid var(--imx-border, #ddcdac);
            border-radius: 16px;
            padding: 22px 20px;
            box-shadow: var(--imx-shadow, 0 6px 20px rgba(15,45,75,0.08));
            text-align: center;
            box-sizing: border-box;
          }}
          .imx-card .imx-icon {{ font-size: 30px; line-height: 1; }}
          .imx-card .imx-label {{
            font-size: 12px; text-transform: uppercase; letter-spacing: .08em;
            color: var(--imx-muted, #5b6b7f); margin-top: 10px; font-weight: 600;
          }}
          .imx-card .imx-value {{
            font-size: 28px; font-weight: 800; margin-top: 4px; color: var(--imx-text, #122436);
          }}
          .imx-card .imx-sub {{ font-size: 12px; color: var(--imx-muted, #5b6b7f); margin-top: 2px; }}
        </style>
        {_CARD_THEME_WATCHER_JS}
        """,
        height=height,
    )


def render_sub_kpi_card(icon: str, label: str, value: str, accent: str, height: int = 130) -> None:
    components.html(
        f"""
        <div class="imx-subcard" style="border-left-color:{accent}">
          <div class="imx-sub-icon">{icon}</div>
          <div class="imx-sub-label">{label}</div>
          <div class="imx-sub-value">{value}</div>
        </div>
        <style>
          html, body {{ margin: 0; padding: 0; background: transparent; }}
          .imx-subcard {{
            font-family: "Source Sans Pro", sans-serif;
            background: var(--imx-bg, #fbf6ec);
            border: 1px solid var(--imx-border, #ddcdac);
            border-left: 4px solid {accent};
            border-radius: 12px;
            padding: 14px 16px;
            box-shadow: var(--imx-shadow, 0 6px 20px rgba(15,45,75,0.08));
            text-align: center;
            box-sizing: border-box;
          }}
          .imx-subcard .imx-sub-icon {{ font-size: 22px; line-height: 1; }}
          .imx-subcard .imx-sub-label {{
            font-size: 11px; text-transform: uppercase; letter-spacing: .06em;
            color: var(--imx-muted, #5b6b7f); margin-top: 6px; font-weight: 600;
          }}
          .imx-subcard .imx-sub-value {{
            font-size: 20px; font-weight: 700; margin-top: 2px; color: var(--imx-text, #122436);
          }}
        </style>
        {_CARD_THEME_WATCHER_JS}
        """,
        height=height,
    )


def page_header_html() -> str:
    return f'<div class="imx-page-title">{APP_NAME}</div>'


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
