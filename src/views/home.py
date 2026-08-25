"""Home / cover page: logo, three world KPIs, two headline charts, and
illustrated shortcuts into the analytical pages. Designed to also work as
a single, self-contained screenshot (e.g. for a social post) - see the
App5 conversation history for that requirement.
"""
from __future__ import annotations

import plotly.express as px
import streamlit as st

from src import theme
from src.common import (
    LOGO_PATH, APP_NAME, TAGLINE, REGION_COLORS, NAV_ITEMS, ICON_LIFE_SVG,
    COL_LIFE, ICON_NONLIFE_IMG, COL_NONLIFE,
    aggregate_metric, fmt_metric, fmt_compact_usd, render_kpi_card, render_sub_kpi_card, nav_card_html,
)


def render(ctx: dict) -> None:
    wide_range = ctx["wide_range"]
    year_selected = ctx["year_selected"]
    metric = ctx["metric"]
    metric_label = ctx["metric_label"]
    t = ctx["card_theme"]

    hero_l, hero_r = st.columns([1, 5], vertical_alignment="center")
    with hero_l:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), width=80)
        else:
            st.markdown("<div style='font-size:64px; text-align:center;'>\U0001F6E1️</div>", unsafe_allow_html=True)
    with hero_r:
        st.markdown(f'<div class="imx-hero-title">{APP_NAME}</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="imx-hero-subtitle">Global insurance market intelligence — '
            'World Bank &amp; Allianz data, combined.</div>',
            unsafe_allow_html=True,
        )

    st.write("")
    home_wide = wide_range[wide_range["year"] == year_selected]
    world_kpi = aggregate_metric(home_wide, [], metric)
    total_val = world_kpi["total"].iloc[0] if len(world_kpi) else None
    life_val = world_kpi["life"].iloc[0] if len(world_kpi) else None
    nonlife_val = world_kpi["nonlife"].iloc[0] if len(world_kpi) else None
    value_fmt = (lambda v: fmt_metric(v, metric)) if metric == "penetration" else fmt_compact_usd

    w_col, life_col, nonlife_col = st.columns([2, 1, 1], vertical_alignment="center")
    with w_col:
        render_kpi_card("\U0001F30D", f"World {metric_label}", value_fmt(total_val),
                         f"Year {year_selected}")
    with life_col:
        render_sub_kpi_card(ICON_LIFE_SVG, "\u21b3 Life", value_fmt(life_val), COL_LIFE)
    with nonlife_col:
        render_sub_kpi_card(ICON_NONLIFE_IMG, "\u21b3 Non-life", value_fmt(nonlife_val), COL_NONLIFE)

    st.write("")
    st.write("")
    ts = aggregate_metric(wide_range, ["year"], metric)
    ts_long = ts.melt(id_vars="year", value_vars=["life", "nonlife", "total"], var_name="series", value_name="value")
    ts_long["series"] = ts_long["series"].map({"life": "Life", "nonlife": "Non-life", "total": "Total"})
    fig = px.line(
        ts_long, x="year", y="value", color="series", markers=True,
        color_discrete_map={"Life": COL_LIFE, "Non-life": COL_NONLIFE, "Total": t["text_muted"]},
        labels={"year": "Year", "value": metric_label, "series": ""},
        title=f"Global {metric_label} — over time",
    )
    fig.update_layout(
        height=480,
        title=dict(y=0.98, yanchor="top"),
        legend=dict(orientation="h", y=0.88, x=0.5, xanchor="center", yanchor="bottom"),
        margin=dict(t=100, b=40),
    )
    st.plotly_chart(fig, width="stretch")

    st.write("")
    region_bar = (
        aggregate_metric(home_wide.dropna(subset=["region"]), ["region"], metric)
        .dropna(subset=["total"]).sort_values("total")
    )
    if region_bar.empty:
        st.info("No region data available.")
    else:
        fig = px.bar(
            region_bar, x="total", y="region", orientation="h", color="region",
            color_discrete_map=REGION_COLORS,
            labels={"total": metric_label, "region": ""},
            title=f"By region — {metric_label} — {year_selected}",
        )
        fig.update_layout(height=380, showlegend=False, margin=dict(t=60, b=40))
        st.plotly_chart(fig, width="stretch")


    st.write("")
    st.markdown("#### Explore the data")
    nav_cols = st.columns(4)
    for i, (page_key, icon, title, desc) in enumerate(NAV_ITEMS[1:5]):
        with nav_cols[i]:
            st.markdown(nav_card_html(icon, title, desc), unsafe_allow_html=True)
            if st.button("Explore →", key=f"homenav_{page_key}", width="stretch"):
                st.session_state["page"] = page_key
                st.rerun()
    nav_cols2 = st.columns(4)
    for i, (page_key, icon, title, desc) in enumerate(NAV_ITEMS[5:]):
        with nav_cols2[i]:
            st.markdown(nav_card_html(icon, title, desc), unsafe_allow_html=True)
            if st.button("Explore →", key=f"homenav_{page_key}", width="stretch"):
                st.session_state["page"] = page_key
                st.rerun()

    st.write("")
    st.write("")
    st.markdown(f'<div class="imx-tagline">\U0001F6E1️ {APP_NAME} — {TAGLINE}</div>', unsafe_allow_html=True)
