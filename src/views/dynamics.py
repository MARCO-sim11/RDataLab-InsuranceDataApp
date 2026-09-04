"""Market Dynamics — Priority 2 (growth/CAGR) + Priority 3 (Life/Non-Life
structure), Sections 5 and 6.

Two sub-sections on one page because both are fundamentally about how a
market *changes* over a period, as opposed to Market Positioning's
single-year snapshot or Rankings' cross-section - keeping them together
avoids a near-duplicate "pick two years" filter pattern on two separate
pages.
"""
from __future__ import annotations

import plotly.express as px
import streamlit as st

from src import analytics as an
from src.common import LOGO_PATH, COL_LIFE, COL_NONLIFE, fmt_metric, fmt_compact_usd, fmt_pct_signed, fmt_pp_signed, page_header_html


def render(ctx: dict) -> None:

    hdr_l, hdr_r = st.columns([1, 10], vertical_alignment="center")
    with hdr_l:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), width=42)
    with hdr_r:
        st.markdown(page_header_html(), unsafe_allow_html=True)

    wide_df = ctx["wide_df"]
    years_desc = ctx["years_desc"]
    year_min = ctx["year_min"]
    year_max = ctx["year_max"]
    default_year = ctx["default_year"]
    countries_sorted = ctx["countries_sorted"]

    st.subheader("\U0001F4C8 Market dynamics")

    _render_growth_section(wide_df, year_min, year_max, default_year)
    st.divider()
    _render_structure_section(wide_df, years_desc, default_year, countries_sorted)


def _render_growth_section(wide_df, year_min: int, year_max: int, default_year: int) -> None:
    """Growth & CAGR (Section 5).

    Business question: where is insurance *developing* (rising
    penetration) versus where is premium volume merely *growing* (which
    can just track GDP)? See analytics.compute_growth_metrics for the
    exact CAGR / delta-penetration formulas.
    """
    st.markdown("#### Growth & CAGR")
    st.caption(
        "A high premium CAGR with flat Δ penetration usually means the market grew with the economy, "
        "not that insurance became more central to it. Read both columns together, not the CAGR alone."
    )

    f1, f2, f3 = st.columns(3)
    with f1:
        start_year = st.selectbox("Start year", list(range(year_min, year_max + 1)), index=0, key="dyn_start")
    with f2:
        end_default = default_year if default_year > start_year else year_max
        end_options = [y for y in range(year_min, year_max + 1) if y > start_year]
        end_year = st.selectbox("End year", end_options,
                                 index=end_options.index(end_default) if end_default in end_options else len(end_options) - 1,
                                 key="dyn_end")
    with f3:
        business_line = st.radio("Business line", ["total", "life", "nonlife"],
                                  format_func=lambda v: {"total": "Total", "life": "Life", "nonlife": "Non-life"}[v],
                                  horizontal=True, key="dyn_line")

    growth = an.compute_growth_metrics(wide_df, start_year, end_year, business_line)

    rc1, rc2 = st.columns([2, 1])
    with rc1:
        rank_by = st.selectbox(
            "Rank by", ["cagr_primes", "cagr_per_capita", "delta_penetration"],
            format_func=lambda c: {"cagr_primes": "Premium volume CAGR", "cagr_per_capita": "Premium per capita CAGR",
                                    "delta_penetration": "Change in penetration (pp)"}[c],
            key="dyn_rankby",
        )
    with rc2:
        top_n = st.selectbox("Top N", list(range(5, 31, 5)), index=1, key="dyn_topn")
        
    fmt_fn = fmt_pp_signed if rank_by == "delta_penetration" else fmt_pct_signed
    label = {"cagr_primes": "Premium CAGR", "cagr_per_capita": "Premium/capita CAGR", "delta_penetration": "Δ Penetration"}[rank_by]

    top, bottom = an.top_bottom(growth, rank_by, top_n)

    tcol, bcol = st.columns(2)
    with tcol:
        st.markdown(f"**Top {top_n} — {label}**")
        t = top[["country", rank_by]].copy()
        t[label] = t[rank_by].map(fmt_fn)
        st.dataframe(t[["country", label]], hide_index=True, width="stretch")
    with bcol:
        st.markdown(f"**Bottom {top_n} — {label}**")
        b = bottom[["country", rank_by]].copy()
        b[label] = b[rank_by].map(fmt_fn)
        st.dataframe(b[["country", label]], hide_index=True, width="stretch")

    fig = px.bar(
        top.sort_values(rank_by), x=rank_by, y="country", orientation="h",
        labels={rank_by: label, "country": ""},
        title=f"Top {top_n} by {label.lower()} ({start_year}–{end_year})",
    )
    fig.update_layout(margin=dict(t=50))
    st.plotly_chart(fig, width="stretch")

def _render_structure_section(wide_df, years_desc, default_year: int, countries_sorted) -> None:
    """Life / Non-Life structure (Section 6).

    Business question: is a market's premium base concentrated in Life or
    Non-Life, and is that mix shifting over time? Life Share is already
    computed in the wide table (`share_life` = Life premium / Total
    premium); dominance labels and structural-shift ranking are new (see
    analytics.classify_dominance / structure_shift).
    """
    st.markdown("#### Life / Non-Life structure")

    year = st.selectbox("Year", years_desc, index=years_desc.index(default_year), key="struct_year")
    year_df = wide_df[wide_df["year"] == year].dropna(subset=["share_life"]).copy()
    year_df["dominance"] = year_df["share_life"].map(an.classify_dominance)

    d1, d2, d3 = st.columns(3)
    counts = year_df["dominance"].value_counts()
    d1.metric("Life-dominated", int(counts.get("Life-dominated", 0)))
    d2.metric("Balanced", int(counts.get("Balanced", 0)))
    d3.metric("Non-life-dominated", int(counts.get("Non-life-dominated", 0)))
    st.caption(f"Dominance threshold: Life Share ≥ {an.DOMINANCE_THRESHOLD:.0%} = Life-dominated, "
               f"≤ {1 - an.DOMINANCE_THRESHOLD:.0%} = Non-life-dominated - this application's own cutoff.")

    top20 = year_df.dropna(subset=["primes_total"]).sort_values("primes_total", ascending=False).head(20)
    top20_long = top20.melt(id_vars=["country"], value_vars=["share_life", "share_nonlife"],
                             var_name="line", value_name="share")
    top20_long["line"] = top20_long["line"].map({"share_life": "Life", "share_nonlife": "Non-life"})
    fig = px.bar(
        top20_long, x="share", y="country", color="line", orientation="h",
        color_discrete_map={"Life": COL_LIFE, "Non-life": COL_NONLIFE},
        labels={"share": "Share of total premium", "country": "", "line": ""},
        title=f"Life / Non-life mix — 20 largest markets, {year}",
    )
    fig.update_layout(barmode="stack", xaxis_tickformat=".0%", legend=dict(orientation="h", y=1.08), margin=dict(t=60))
    st.plotly_chart(fig, width="stretch")

    st.markdown("**Life Share trajectory**")
    traj_countries = st.multiselect("Countries to compare", countries_sorted,
                                     default=[c for c in ["France", "United States", "China"] if c in countries_sorted],
                                     key="struct_traj")
    if traj_countries:
        traj = wide_df[wide_df["country"].isin(traj_countries)].dropna(subset=["share_life"])
        fig = px.line(
            traj.sort_values("year"), x="year", y="share_life", color="country", markers=True,
            labels={"year": "Year", "share_life": "Life Share", "country": ""},
            title="Life Share over time",
        )
        fig.update_layout(yaxis_tickformat=".0%", legend=dict(orientation="h", y=1.1), margin=dict(t=60))
        st.plotly_chart(fig, width="stretch")
    else:
        st.caption("Pick at least one country to see its Life Share trajectory.")

    st.markdown("**Biggest structural shifts**")
    shift_start, shift_end = st.select_slider(
        "Period", options=sorted(wide_df["year"].unique()),
        value=(int(wide_df["year"].min()), int(wide_df["year"].max())), key="struct_shift_period",
    )
    shifts = an.structure_shift(wide_df, shift_start, shift_end).head(10)
    if shifts.empty:
        st.caption("Not enough data for this period.")
    else:
        shifts_display = shifts[["country", "region", "share_life_start", "share_life_end", "delta_share_life"]].copy()
        for c in ["share_life_start", "share_life_end", "delta_share_life"]:
            shifts_display[c] = shifts_display[c].map(lambda v: f"{v:+.1%}" if c == "delta_share_life" else f"{v:.1%}")
        shifts_display.columns = ["Country", "Region", f"Life Share {shift_start}", f"Life Share {shift_end}", "Change"]
        st.dataframe(shifts_display, hide_index=True, width="stretch")
