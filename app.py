"""InsurAtlas - global insurance market analytics.

Data comes from data/insurance_long.csv and data/insurance_wide.csv, built
by combining two independent sources - see the "Data Sources" page or, from
the command line: refresh_data.py (World Bank) and
src/build_allianz_dataset.py (Allianz PDF reports), then
src/combine_sources.py to merge them. Run at least once before this app if
the files don't exist yet.

This file is intentionally a thin router: sidebar filters, then dispatch
to one page module per nav item (see src/views/). Each page module owns
its own layout and docstrings describing the business question, formula,
and limitations of what it shows - see src/analytics.py for the
market-structure calculations (positioning quadrants, CAGR, Life/Non-Life
structure, concentration) shared across pages.
"""
from __future__ import annotations

import streamlit as st

from src import data_quality as dq
from src import theme
from src.common import (
    APP_NAME, DATA_DIR, LOGO_PATH, METRIC_LABELS, METRIC_COLS, NAV_ITEMS, load_data,sync_selector,
)
from src.views import country, dynamics, home, positioning, quality, rankings, sources, world

PAGES = {
    "Home": home.render,
    "World": world.render,
    "Country": country.render,
    "Dynamics": dynamics.render,
    "Positioning": positioning.render,
    "Rankings": rankings.render,
    "Data Quality": quality.render,
    "Data Sources": sources.render,
}

st.set_page_config(page_title=APP_NAME, page_icon="\U0001F6E1️", layout="wide")

if not (DATA_DIR / "insurance_long.csv").exists():
    st.error(
        "Consolidated data not found in `data/`. Run `python refresh_data.py` first "
        "to fetch data from the World Bank API and build the CSVs."
    )
    st.stop()

long_df, wide_df = load_data()

year_min, year_max = int(wide_df["year"].min()), int(wide_df["year"].max())
default_year = dq.latest_reliable_year(wide_df)
years_desc = sorted(wide_df["year"].dropna().unique().astype(int), reverse=True)
countries_sorted = sorted(wide_df["country"].dropna().unique())
sources_list = sorted(long_df["source"].dropna().unique()) if "source" in long_df else ["World Bank"]

st.session_state.setdefault("page", "Home")
card_theme = theme.inject_card_css()

# ---------------------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------------------
if LOGO_PATH.exists():
    sb_l, sb_r = st.sidebar.columns([1, 2], vertical_alignment="center")
    with sb_l:
        st.image(str(LOGO_PATH), width=50)
    with sb_r:
        st.markdown(f'<div class="imx-sidebar-title">{APP_NAME}</div>', unsafe_allow_html=True)
else:
    st.sidebar.markdown(f"### \U0001F6E1️ {APP_NAME}")
    st.sidebar.caption(f"(drop a logo at `assets/logo.png` to brand this)")

st.sidebar.markdown(
    '<div class="imx-hero-subtitle"> Mapping the Global Insurance Market</div>',
    unsafe_allow_html=True,
)

#st.sidebar.caption("\U0001F3A8 Theme: use the ⋮ menu (top-right) → Settings → Choose app theme "
                    #"to switch light/dark.")

st.sidebar.divider()

for page_key, icon, label, _desc in NAV_ITEMS:
    active = st.session_state["page"] == page_key
    if st.sidebar.button(f"{icon} {label}", width="stretch", type="primary" if active else "secondary", key=f"navbtn_{page_key}"):
        st.session_state["page"] = page_key
        st.rerun()

st.sidebar.divider()
st.sidebar.caption(
    f"Data: {' + '.join(sources_list)}  \n"
    f"Coverage: {year_min}–{year_max}  \n"
    f"Default year (≥ 30% country coverage): **{default_year}**"
)

metric = st.sidebar.radio(
    "Metric", list(METRIC_LABELS.keys()), format_func=lambda k: METRIC_LABELS[k], index=0
)

st.session_state.setdefault("sel_year_range", (year_min, year_max))
st.session_state.setdefault("sel_year_range_sb", st.session_state["sel_year_range"])
st.session_state.setdefault("sel_year_range_page", st.session_state["sel_year_range"])

st.session_state.setdefault("sel_year", default_year)
st.session_state.setdefault("sel_year_sb", st.session_state["sel_year"])
st.session_state.setdefault("sel_year_page", st.session_state["sel_year"])

st.session_state.setdefault("sel_country", "France" if "France" in countries_sorted else countries_sorted[0])
st.session_state.setdefault("sel_country_sb", st.session_state["sel_country"])
st.session_state.setdefault("sel_country_page", st.session_state["sel_country"])

year_range = st.sidebar.slider(
    "Time range", year_min, year_max, key="sel_year_range_sb",
    on_change=sync_selector, args=("sel_year_range_sb", "sel_year_range", "sel_year_range_page"),
)
year_selected = st.sidebar.selectbox(
    "Year for split / ranking", years_desc, key="sel_year_sb",
    on_change=sync_selector, args=("sel_year_sb", "sel_year", "sel_year_page"),
)
country_selected = st.sidebar.selectbox(
    "Country", countries_sorted, key="sel_country_sb",
    on_change=sync_selector, args=("sel_country_sb", "sel_country", "sel_country_page"),
)

metric_label = METRIC_LABELS[metric]
cols = METRIC_COLS[metric]

wide_range = wide_df[(wide_df["year"] >= year_range[0]) & (wide_df["year"] <= year_range[1])]
long_range = long_df[(long_df["year"] >= year_range[0]) & (long_df["year"] <= year_range[1])]

ctx = dict(
    long_df=long_df, wide_df=wide_df,
    wide_range=wide_range, long_range=long_range,
    metric=metric, cols=cols, metric_label=metric_label,
    year_selected=year_selected, year_range=year_range, country=country_selected,
    default_year=default_year, year_min=year_min, year_max=year_max,
    years_desc=years_desc, countries_sorted=countries_sorted, sources=sources_list,
    card_theme=card_theme,
)

PAGES[st.session_state["page"]](ctx)
