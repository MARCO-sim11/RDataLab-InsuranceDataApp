"""Rankings — full country ranking table plus Priority 5, Global Market
Concentration (Section 10).

The country-specific "where does my selected country rank" callout lives
on the Country Explorer scorecard instead (it needs a selected country to
mean anything); this page is the exhaustive, country-independent view -
keeping the two separate avoids showing the same ranking twice.
"""
from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import analytics as an
from src.common import LOGO_PATH, fmt_metric, fmt_compact_usd, page_header_html


def render(ctx: dict) -> None:

    hdr_l, hdr_r = st.columns([1, 10], vertical_alignment="center")
    with hdr_l:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), width=42)
    with hdr_r:
        st.markdown(page_header_html(), unsafe_allow_html=True)

    wide_df = ctx["wide_df"]
    metric = ctx["metric"]
    cols = ctx["cols"]
    metric_label = ctx["metric_label"]
    year_selected = ctx["year_selected"]

    st.subheader("\U0001F3C6 Rankings")

    _render_full_ranking(wide_df, metric, cols, metric_label, year_selected)
    st.divider()
    _render_concentration(wide_df, year_selected)


def _render_full_ranking(wide_df, metric: str, cols: dict, metric_label: str, year_selected: int) -> None:
    st.markdown(f"#### Full country ranking — {metric_label}, {year_selected}")

    all_regions = sorted(wide_df["region"].dropna().unique())
    regions = st.multiselect("Region filter", all_regions, default=all_regions, key="rank_regions")

    d = wide_df[(wide_df["year"] == year_selected) & (wide_df["region"].isin(regions))].dropna(subset=[cols["total"]])
    d = d.sort_values(cols["total"], ascending=False).reset_index(drop=True)
    d.insert(0, "Rank", d.index + 1)
    display = d[["Rank", "country", "region", cols["total"], cols["life"], cols["nonlife"]]].copy()
    for c, name in [(cols["total"], "Total"), (cols["life"], "Life"), (cols["nonlife"], "Non-life")]:
        display[name] = display[c].map(lambda v: fmt_metric(v, metric))
    display = display[["Rank", "country", "region", "Total", "Life", "Non-life"]]
    display.columns = ["Rank", "Country", "Region", "Total", "Life", "Non-life"]
    st.dataframe(display, hide_index=True, width="stretch", height=420)
    st.caption(f"{len(display)} countries with data for {year_selected}. Click a column header to sort.")


def _render_concentration(wide_df, year_selected: int) -> None:
    """Global Market Concentration (Section 10).

    Business question: "Is the global insurance market becoming more or
    less concentrated?" See analytics.market_concentration for the
    topN-share and HHI formulas.
    """
    st.markdown("#### Global market concentration")
    st.caption(
        "Country coverage changes year to year (see Data Quality), which can mechanically move these "
        "figures even without a real change in market structure - read the trend together with coverage."
    )

    conc = an.market_concentration(wide_df)
    if conc.empty:
        st.info("Not enough data to compute concentration.")
        return

    row = conc[conc["year"] == year_selected]
    if row.empty:
        row = conc.iloc[[-1]]
        st.caption(f"No concentration data for {year_selected}; showing {int(row['year'].iloc[0])} instead.")
    row = row.iloc[0]

    hhi = row["hhi"]
    hhi_label = "Unconcentrated" if hhi < 1500 else ("Moderately concentrated" if hhi < 2500 else "Highly concentrated")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Top 5 share", f"{row['top5_share']:.1%}")
    c2.metric("Top 10 share", f"{row['top10_share']:.1%}")
    c3.metric("Top 20 share", f"{row['top20_share']:.1%}")
    c4.metric("HHI", f"{hhi:,.0f}", help="Herfindahl-Hirschman Index (0-10000). "
                                          "<1500 unconcentrated, 1500-2500 moderately, >2500 highly - "
                                          "a common antitrust-analysis convention, not insurance-specific.")
    st.caption(f"{hhi_label} market as of {int(row['year'])} ({int(row['n_countries'])} countries with data).")

    t1, t2 = st.columns(2)
    with t1:
        share_long = conc.melt(id_vars="year", value_vars=["top5_share", "top10_share", "top20_share"],
                                var_name="series", value_name="share")
        share_long["series"] = share_long["series"].map({"top5_share": "Top 5", "top10_share": "Top 10", "top20_share": "Top 20"})
        fig = px.line(share_long, x="year", y="share", color="series", markers=True,
                      labels={"year": "Year", "share": "Share of world premium", "series": ""},
                      title="Concentration over time")
        fig.update_layout(yaxis_tickformat=".0%", legend=dict(orientation="h", y=1.12), margin=dict(t=60))
        st.plotly_chart(fig, width="stretch")
    with t2:
        fig = go.Figure(go.Scatter(x=conc["year"], y=conc["hhi"], mode="lines+markers"))
        fig.add_hrect(y0=0, y1=1500, fillcolor="green", opacity=0.06, line_width=0)
        fig.add_hrect(y0=1500, y1=2500, fillcolor="orange", opacity=0.06, line_width=0)
        fig.add_hrect(y0=2500, y1=10000, fillcolor="red", opacity=0.06, line_width=0)
        fig.update_layout(title="HHI over time", xaxis_title="Year", yaxis_title="HHI", margin=dict(t=60))
        st.plotly_chart(fig, width="stretch")

    st.markdown(f"**Top markets — {int(row['year'])}**")
    top_n = st.slider("Show top N", 5, 30, 10, key="conc_topn")
    snap = an.concentration_snapshot(wide_df, int(row["year"]), top_n)
    snap_display = snap.copy()
    snap_display["primes_total"] = snap_display["primes_total"].map(fmt_compact_usd)
    snap_display["share"] = snap_display["share"].map(lambda v: f"{v:.1%}")
    snap_display["cumulative_share"] = snap_display["cumulative_share"].map(lambda v: f"{v:.1%}")
    snap_display.columns = ["Country", "Premium volume", "Share of world", "Cumulative share"]
    st.dataframe(snap_display, hide_index=True, width="stretch")
