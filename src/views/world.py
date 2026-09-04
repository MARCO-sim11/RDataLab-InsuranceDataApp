"""World Overview: global KPIs, world evolution over time, Life/Non-life
split, evolution by region, the world choropleth, and region ranking.
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from src import analytics as an
from src.common import (LOGO_PATH, COL_LIFE, COL_NONLIFE, COL_TOTAL, REGION_COLORS, ICON_LIFE_SVG, ICON_NONLIFE_IMG, 
                    aggregate_metric, fmt_metric, page_header_html, source_transition_note, sync_selector, render_kpi_card, render_sub_kpi_card, fmt_compact_usd,)


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
    metric = ctx["metric"]
    cols = ctx["cols"]
    metric_label = ctx["metric_label"]
    year_selected = ctx["year_selected"]
    year_range = ctx["year_range"]

    st.subheader(f"World — {metric_label}")

    world_year = wide_range[wide_range["year"] == year_selected]
    world_kpi_df = aggregate_metric(world_year, [], metric)
    world_kpi = world_kpi_df.iloc[0] if len(world_kpi_df) else pd.Series({"total": None, "life": None, "nonlife": None})

    value_fmt = (lambda v: fmt_metric(v, metric)) if metric == "penetration" else fmt_compact_usd
    wk_col, wl_col, wnl_col, wc_col = st.columns([2, 1, 1, 1], vertical_alignment="center")
    with wk_col:
        render_kpi_card("\U0001F30D", f"World {metric_label}", value_fmt(world_kpi["total"]),
                         f"Year {year_selected}")
    with wl_col:
        render_sub_kpi_card(ICON_LIFE_SVG, "↳ Life", value_fmt(world_kpi["life"]), COL_LIFE)
    with wnl_col:
        render_sub_kpi_card(ICON_NONLIFE_IMG, "↳ Non-life", value_fmt(world_kpi["nonlife"]), COL_NONLIFE)
    with wc_col:
        st.metric(f"Countries covered — {year_selected}", int(world_year[cols["total"]].notna().sum()))

    c1, c2 = st.columns([2, 1])
    with c1:
        world_ts = aggregate_metric(wide_range, ["year"], metric)
        world_ts_long = world_ts.melt(
            id_vars="year", value_vars=["life", "nonlife", "total"], var_name="series", value_name="value"
        )
        world_ts_long["series"] = world_ts_long["series"].map({"life": "Life", "nonlife": "Non-life", "total": "Total"})
        fig = px.line(
            world_ts_long, x="year", y="value", color="series", markers=True,
            color_discrete_map={"Life": COL_LIFE, "Non-life": COL_NONLIFE, "Total": COL_TOTAL},
            labels={"year": "Year", "value": metric_label, "series": ""},
            title=f"World — {metric_label}",
        )
        transition_year = an.source_transition_year(long_df)
        if transition_year and year_range[0] <= transition_year <= year_range[1]:
            fig.add_vline(x=transition_year, line_dash="dash", line_color="gray",
                           annotation_text="World Bank → Allianz", annotation_position="top")
        fig.update_layout(legend=dict(orientation="h", y=1.1), margin=dict(t=60))
        st.plotly_chart(fig, width='stretch')
        note = source_transition_note(long_df, transition_year)
        if note and year_range[0] <= (transition_year or 0) <= year_range[1]:
            st.caption(note)

    with c2:
        pie_df = pd.DataFrame({
            "type": ["Life", "Non-life"],
            "primes": [world_year["primes_life"].sum(), world_year["primes_nonlife"].sum()],
        })
        pie_df = pie_df[pie_df["primes"] > 0]
        if pie_df.empty:
            st.info("No data.")
        else:
            fig = px.pie(
                pie_df, names="type", values="primes", color="type", hole=0.45,
                color_discrete_map={"Life": COL_LIFE, "Non-life": COL_NONLIFE},
                title=f"World Life / Non-life — {year_selected}",
            )
            fig.update_traces(textinfo="label+percent", pull=0.03)
            st.plotly_chart(fig, width='stretch')

    st.write("")
    st.slider("Time range", ctx["year_min"], ctx["year_max"], key="sel_year_range_page",
              on_change=sync_selector, args=("sel_year_range_page", "sel_year_range", "sel_year_range_sb"))

    st.divider()
    series_choice = st.radio("Series", ["total", "life", "nonlife"], horizontal=True, index=0, key="region_series")
    region_ts = aggregate_metric(wide_range.dropna(subset=["region"]), ["region", "year"], metric).dropna(subset=[series_choice])
    if region_ts.empty:
        st.info("No data.")
    else:
        fig = px.line(
            region_ts, x="year", y=series_choice, color="region", markers=True,
            color_discrete_map=REGION_COLORS,
            labels={"year": "Year", series_choice: metric_label, "region": "Region"},
            title=f"By region — {metric_label} — {series_choice.title()}",
        )
        fig.update_layout(margin=dict(t=60))
        st.plotly_chart(fig, width='stretch')

    st.divider()
    st.markdown(f"**World map — {metric_label} — {year_selected}**")
    map_series = st.radio("Insurance type", ["total", "life", "nonlife"], horizontal=True, index=0, key="map_series")
    map_col = cols[map_series]
    map_df = wide_df[wide_df["year"] == year_selected][["iso3", "country", map_col]].dropna(subset=[map_col])
    if map_df.empty:
        st.info("No data available for this selection.")
    else:
        fig = px.choropleth(
            map_df, locations="iso3", color=map_col, hover_name="country",
            color_continuous_scale="YlOrRd",
            labels={map_col: metric_label},
        )
        fig.update_layout(margin=dict(t=10, b=10, l=0, r=0), geo=dict(showframe=False))
        st.plotly_chart(fig, width='stretch')

    st.divider()
    st.markdown(f"**Region ranking — {year_selected}**")
    region_bar = aggregate_metric(
        wide_df[(wide_df["year"] == year_selected)].dropna(subset=["region"]), ["region"], metric
    ).dropna(subset=["total"]).sort_values("total")
    if region_bar.empty:
        st.info("No region data available.")
    else:
        fig = px.bar(
            region_bar, x="total", y="region", orientation="h", color="region",
            color_discrete_map=REGION_COLORS,
            labels={"total": metric_label, "region": ""},
        )
        fig.update_layout(showlegend=False, margin=dict(t=10))
        st.plotly_chart(fig, width='stretch')
