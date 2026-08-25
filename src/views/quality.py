"""Data Quality: coverage over time, completeness by country, coherence
flags, and a per-country detail table with the underlying source of every
row.
"""
from __future__ import annotations

import plotly.express as px
import streamlit as st

from src import data_quality as dq
from src.common import LOGO_PATH, page_header_html


def render(ctx: dict) -> None:

    hdr_l, hdr_r = st.columns([1, 10], vertical_alignment="center")
    with hdr_l:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), width=42)
    with hdr_r:
        st.markdown(page_header_html(), unsafe_allow_html=True)

    wide_df = ctx["wide_df"]
    long_df = ctx["long_df"]
    wide_range = ctx["wide_range"]
    long_range = ctx["long_range"]
    year_range = ctx["year_range"]
    default_year = ctx["default_year"]
    country = ctx["country"]
    countries_sorted = ctx["countries_sorted"]

    st.subheader("Data quality")

    q1, q2, q3 = st.columns(3)
    overall_completeness = 100 * wide_range["total"].notna().mean()
    q1.metric("Overall completeness (total penetration)", f"{overall_completeness:.1f}%")
    q2.metric("Latest year with ≥ 30% coverage", default_year)
    n_allianz = (
        long_df[long_df["source"].str.startswith("Allianz", na=False)]["country"].nunique()
        if "source" in long_df else 0
    )
    q3.metric("Countries with an Allianz-supplement row", n_allianz)

    st.markdown("**Coverage by year** — share of countries with a value, per indicator")
    cov_year = dq.completeness_by_year(wide_df)
    fig = px.line(
        cov_year, x="year", y="coverage", color="metric", markers=True,
        labels={"year": "Year", "coverage": "Share of countries with data", "metric": ""},
    )
    fig.update_layout(yaxis_tickformat=".0%", legend=dict(orientation="h", y=1.15), margin=dict(t=40))
    st.plotly_chart(fig, width='stretch')

    st.markdown(f"**Completeness by country** — total penetration, {year_range[0]}–{year_range[1]}")
    comp_country = dq.completeness_by_country(wide_df, year_range[0], year_range[1])
    slider_max = max(10, min(100, len(comp_country)))
    n_show = st.slider("Countries to show (worst first)", 10, slider_max, min(25, slider_max))
    fig = px.bar(
        comp_country.head(n_show), x="completeness_pct", y="country", orientation="h",
        labels={"completeness_pct": "Completeness (%)", "country": ""},
        color="completeness_pct", color_continuous_scale="RdYlGn", range_color=[0, 100],
    )
    fig.update_layout(height=max(300, 22 * n_show), coloraxis_showscale=False, margin=dict(t=10))
    st.plotly_chart(fig, width='stretch')

    st.markdown("**Coherence checks**")
    flags = dq.coherence_flags(wide_range)
    if flags.empty:
        st.success("No coherence issues flagged over this range.")
    else:
        issue_filter = st.multiselect("Filter by issue type", sorted(flags["issue"].unique()), default=list(flags["issue"].unique()))
        st.dataframe(flags[flags["issue"].isin(issue_filter)], hide_index=True, width='stretch')

    st.markdown("**Per-country detail**")
    dq_country = st.selectbox("Country", countries_sorted, index=countries_sorted.index(country) if country in countries_sorted else 0, key="dq_country")
    detail = long_range[long_range["country"] == dq_country][
        ["year", "type", "penetration", "gdp", "population", "primes", "prime_par_tete", "source"]
    ].sort_values(["year", "type"])
    st.dataframe(detail, hide_index=True, width='stretch')
