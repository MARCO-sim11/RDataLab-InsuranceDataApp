"""Market Positioning (Section 4) — Priority 1.

Business question: how do countries compare on *how much* insurance
people consume (premium per capita) versus *how central* insurance is to
the economy (penetration, % of GDP), and how big is the market in
absolute terms? A single scatter answers "biggest", "most developed", and
"under/over-consuming relative to penetration" at once - the reason this
was flagged as the highest-value, lowest-complexity addition: every input
already exists in the wide table, nothing new to compute.

Indicator / formula: x = premium per capita (USD), y = penetration (% of
GDP), bubble size = total premium volume (USD), color = World Bank
region. Quadrant split lines are the median x/y among currently-filtered
countries (see analytics.quadrant_benchmark) - median, not mean, because
premium data is heavily right-skewed by a handful of very large markets.

Filters: year, business line (Life / Non-Life / Total - which set of
penetration/premium/per-capita columns feed the fixed x/y/size axes),
region, and an optional country highlight.

Interpretation: the four zones are purely descriptive (Section 4) - e.g.
"Low penetration / High premium per capita" usually means a wealthy,
small-population market where insurance is a minor share of a large GDP,
not necessarily an underdeveloped one.

Limitation: a bubble only appears if penetration, premium per capita, and
premium volume are all non-missing for that country/year - so a lower
apparent count for early or very recent years can be a coverage gap, not
"fewer insurance markets existed". Check the Data Quality page for that.
"""
from __future__ import annotations

import plotly.express as px
import streamlit as st

from src import analytics as an
from src.common import LOGO_PATH, REGION_COLORS, fmt_metric, fmt_compact_usd, page_header_html


def render(ctx: dict) -> None:

    hdr_l, hdr_r = st.columns([1, 10], vertical_alignment="center")
    with hdr_l:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), width=42)
    with hdr_r:
        st.markdown(page_header_html(), unsafe_allow_html=True)

    wide_df = ctx["wide_df"]
    years_desc = ctx["years_desc"]
    default_year = ctx["default_year"]
    countries_sorted = ctx["countries_sorted"]

    st.subheader("\U0001F3AF Market positioning")
    st.caption(
        "Penetration × premium per capita × market size, in one view. Quadrant lines are the median "
        "of the currently-filtered countries - a descriptive split, not a fixed threshold."
    )

    f1, f2, f3, f4 = st.columns([1, 1, 1.4, 1.4])
    with f1:
        year = st.selectbox("Year", years_desc, index=years_desc.index(default_year), key="pos_year")
    with f2:
        business_line = st.radio("Business line", ["total", "life", "nonlife"],
                                  format_func=lambda v: {"total": "Total", "life": "Life", "nonlife": "Non-life"}[v],
                                  key="pos_line")
    with f3:
        all_regions = sorted(wide_df["region"].dropna().unique())
        regions = st.multiselect("Region", all_regions, default=all_regions, key="pos_regions")
    with f4:
        highlight = st.selectbox("Highlight a country (optional)", ["(none)"] + countries_sorted, key="pos_highlight")

    log_x = st.checkbox("Log scale for premium per capita", value=True, key="pos_logx",
                         help="Premium per capita spans several orders of magnitude across countries; "
                              "log scale keeps low-value markets from being crushed against the axis.")

    df = an.positioning_frame(wide_df, year, business_line)
    df = df[df["region"].isin(regions)] if regions else df.iloc[0:0]

    if df.empty:
        st.info("No countries match this selection (check the year/region/business line filters).")
        return

    x_bench = an.quadrant_benchmark(df["x"])
    y_bench = an.quadrant_benchmark(df["y"])
    df["zone"] = [an.classify_quadrant(x, y, x_bench, y_bench) for x, y in zip(df["x"], df["y"])]

    line_label = {"total": "Total", "life": "Life", "nonlife": "Non-life"}[business_line]
    fig = px.scatter(
        df, x="x", y="y", size="size", color="region", hover_name="country",
        color_discrete_map=REGION_COLORS, log_x=log_x, size_max=55,
        labels={"x": f"{line_label} premium per capita (USD)", "y": f"{line_label} penetration (% of GDP)", "region": "Region"},
        title=f"{line_label} market positioning — {year}",
        hover_data={"size": ":$,.0f", "x": ":$,.0f", "y": ":.2f"},
    )
    fig.add_hline(y=y_bench, line_dash="dot", line_color="gray")
    fig.add_vline(x=x_bench, line_dash="dot", line_color="gray")

    if highlight != "(none)":
        hi = df[df["country"] == highlight]
        if not hi.empty:
            fig.add_scatter(
                x=hi["x"], y=hi["y"], mode="markers+text", text=hi["country"], textposition="top center",
                marker=dict(size=hi["size"] / df["size"].max() * 55 + 10, color="rgba(0,0,0,0)",
                            line=dict(color="black", width=3)),
                showlegend=False, hoverinfo="skip",
            )

    fig.update_layout(margin=dict(t=60), legend=dict(orientation="h", y=-0.15))
    st.plotly_chart(fig, width="stretch")

    st.caption(
        f"Dashed lines: median premium per capita (${x_bench:,.0f}) and median penetration ({y_bench:.2f}%) "
        f"among the {len(df)} countries shown."
    )

    st.markdown("#### Zone breakdown")
    zone_counts = df["zone"].value_counts()
    zc1, zc2, zc3, zc4 = st.columns(4)
    for col, zone in zip((zc1, zc2, zc3, zc4), [
        "High penetration / High premium per capita", "High penetration / Low premium per capita",
        "Low penetration / High premium per capita", "Low penetration / Low premium per capita",
    ]):
        col.metric(zone, int(zone_counts.get(zone, 0)))

    st.markdown("**Countries in each zone**")
    zone_pick = st.selectbox("Zone", sorted(df["zone"].unique()), key="pos_zone_pick")
    zone_df = df[df["zone"] == zone_pick][["country", "region", "x", "y", "size"]].sort_values("size", ascending=False)
    zone_df = zone_df.assign(
        **{
            f"{line_label} premium/capita": zone_df["x"].map(lambda v: fmt_metric(v, "primes")),
            f"{line_label} penetration": zone_df["y"].map(lambda v: fmt_metric(v, "penetration")),
            f"{line_label} premium volume": zone_df["size"].map(fmt_compact_usd),
        }
    )[["country", "region", f"{line_label} premium/capita", f"{line_label} penetration", f"{line_label} premium volume"]]
    st.dataframe(zone_df, hide_index=True, width="stretch")
