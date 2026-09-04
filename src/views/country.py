"""Country Explorer: evolution over time, Life/Non-life split, a
World Bank -> Allianz source note, and the Country Scorecard (Section 15) -
market size, development, consumption, growth, ranking and maturity
profile for one country/year in one place.

The generic "Top 5 / Bottom 5" table that used to live here moved to the
Rankings page (Section 18): it doesn't depend on the selected country, so
keeping it here duplicated a view that belongs at the world level. What
stays here is explicitly country-scoped: this country's own rank.
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import analytics as an
from src.common import (
    LOGO_PATH, COL_TOTAL, COL_LIFE, COL_NONLIFE, ICON_LIFE_SVG, ICON_NONLIFE_IMG, fmt_metric, fmt_compact_usd, fmt_pp_signed, fmt_pct_signed,
    page_header_html, render_kpi_card, render_sub_kpi_card, source_transition_note, sync_selector, country_flag, aggregate_metric, 
)


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
    metric = ctx["metric"]
    cols = ctx["cols"]
    metric_label = ctx["metric_label"]
    year_selected = ctx["year_selected"]
    year_range = ctx["year_range"]
    country = ctx["country"]

    st.subheader(f"{country} — {metric_label}")

    row_cy = wide_range[(wide_range["country"] == country) & (wide_range["year"] == year_selected)]
    iso3 = row_cy["iso3"].iloc[0] if len(row_cy) else long_range.loc[long_range["country"] == country, "iso3"].iloc[0]

    value_fmt = (lambda v: fmt_metric(v, metric)) if metric == "penetration" else fmt_compact_usd
    ck_col, cl_col, cnl_col = st.columns([2, 1, 1], vertical_alignment="center")
    with ck_col:
        render_kpi_card(country_flag(iso3), f"{country} — {metric_label}",
                         value_fmt(row_cy[cols["total"]].iloc[0] if len(row_cy) else None),
                         f"Year {year_selected}")
    with cl_col:
        render_sub_kpi_card(ICON_LIFE_SVG, "↳ Life",
                             value_fmt(row_cy[cols["life"]].iloc[0] if len(row_cy) else None), COL_LIFE)
    with cnl_col:
        render_sub_kpi_card(ICON_NONLIFE_IMG, "↳ Non-life",
                             value_fmt(row_cy[cols["nonlife"]].iloc[0] if len(row_cy) else None), COL_NONLIFE)


    show_world = st.session_state.get("show_world_avg", False) #controls world average showing

    c1, c2 = st.columns([2, 1])

    with c1:
        country_long = long_range[long_range["country"] == country].dropna(subset=[metric])
        if country_long.empty:
            st.info("No data available for this selection.")
        else:
            fig = px.line(
                country_long.sort_values("year"), x="year", y=metric, color="type",
                color_discrete_map={"Life": COL_LIFE, "Non-life": COL_NONLIFE},
                markers=True, labels={"year": "Year", metric: metric_label, "type": ""},
                title=f"{metric_label} over time — {country}",
            )

            total_series = wide_range[wide_range["country"] == country].sort_values("year").dropna(subset=[cols["total"]])
            if not total_series.empty:
                fig.add_trace(go.Scatter(
                    x=total_series["year"], y=total_series[cols["total"]],
                    mode="lines+markers", name="Total",
                    line=dict(color=COL_TOTAL),
                ))

            # Adding the world view if necessary
            if show_world:
                world_ts = aggregate_metric(wide_range, ["year"], metric)
                for series_key, series_name, color in (
                    ("life", "World life", COL_LIFE),
                    ("nonlife", "World non-life", COL_NONLIFE),
                    ("total", "World total", COL_TOTAL),
                ):
                    fig.add_trace(go.Scatter(
                        x=world_ts["year"], y=world_ts[series_key],
                        mode="lines", name=series_name,
                        line=dict(color=color, dash="dash", width=1),
                    ))

            iso3 = row_cy["iso3"].iloc[0] if len(row_cy) else long_range.loc[long_range["country"] == country, "iso3"].iloc[0]
            transition_year = an.source_transition_year(long_df, iso3)
            if transition_year and year_range[0] <= transition_year <= year_range[1]:
                fig.add_vline(x=transition_year, line_dash="dash", line_color="gray",
                               annotation_text="World Bank → Allianz", annotation_position="top")
            fig.update_layout(legend=dict(orientation="h", y=1.1), margin=dict(t=60))
            st.plotly_chart(fig, width='stretch')
            note = source_transition_note(long_df, transition_year)
            if note and year_range[0] <= (transition_year or 0) <= year_range[1]:
                st.caption(note)

    with c2:
        life_v = row_cy["primes_life"].iloc[0] if len(row_cy) else None
        nonlife_v = row_cy["primes_nonlife"].iloc[0] if len(row_cy) else None
        pie_df = pd.DataFrame({"type": ["Life", "Non-life"], "primes": [life_v, nonlife_v]}).dropna()
        if pie_df.empty:
            st.info("No premium split available.")
        else:
            fig = px.pie(
                pie_df, names="type", values="primes", hole=0.45,
                color="type", color_discrete_map={"Life": COL_LIFE, "Non-life": COL_NONLIFE},
                title=f"Life / Non-life — {country} — {year_selected}",
            )
            fig.update_traces(textinfo="label+percent", pull=0.03)
            st.plotly_chart(fig, width='stretch')

    st.write("")
    pc1, pc2, pc3, pc4 = st.columns(4)
    with pc1:
        st.selectbox("Country", ctx["countries_sorted"], key="sel_country_page",
                     on_change=sync_selector, args=("sel_country_page", "sel_country", "sel_country_sb"))
    with pc2:
        st.selectbox("Year for split / ranking", ctx["years_desc"], key="sel_year_page",
                     on_change=sync_selector, args=("sel_year_page", "sel_year", "sel_year_sb"))
    with pc3:
        st.slider("Time range", ctx["year_min"], ctx["year_max"], key="sel_year_range_page",
                   on_change=sync_selector, args=("sel_year_range_page", "sel_year_range", "sel_year_range_sb"))
    with pc4:
        st.toggle("Compare to world average", key="show_world_avg")

    st.divider()
    _render_scorecard(wide_df, long_df, country, year_selected, year_range, metric, cols, metric_label)


def _render_scorecard(wide_df: pd.DataFrame, long_df: pd.DataFrame, country: str, year_selected: int,
                       year_range: tuple[int, int], metric: str, cols: dict, metric_label: str) -> None:
    """Country Scorecard (Section 15): market size, development,
    consumption, growth, ranking, and maturity profile for one
    country/year, in one place instead of scattered across tabs.
    """
    st.markdown("### \U0001F4CB Country scorecard")

    row = wide_df[(wide_df["country"] == country) & (wide_df["year"] == year_selected)]
    if row.empty:
        st.info(f"No data for {country} in {year_selected}.")
        return
    r = row.iloc[0]
    iso3 = r["iso3"]

    st.caption(f"**Observed / derived indicators** for {country}, {year_selected}. "
               f"Premium volume and premium per capita are *derived* from penetration × GDP "
               f"(and ÷ population) — not a separately-reported figure.")

    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        st.markdown("**Market size** (premium volume)")
        st.dataframe(pd.DataFrame({
            "": ["Life", "Non-life", "Total"],
            "Premium": [fmt_compact_usd(r["primes_life"]), fmt_compact_usd(r["primes_nonlife"]), fmt_compact_usd(r["primes_total"])],
        }), hide_index=True, width="stretch")
    with sc2:
        st.markdown("**Market development** (penetration)")
        st.dataframe(pd.DataFrame({
            "": ["Life", "Non-life", "Total"],
            "% of GDP": [fmt_metric(r["life"], "penetration"), fmt_metric(r["nonlife"], "penetration"), fmt_metric(r["total"], "penetration")],
        }), hide_index=True, width="stretch")
    with sc3:
        st.markdown("**Consumption** (premium per capita)")
        st.dataframe(pd.DataFrame({
            "": ["Life", "Non-life", "Total"],
            "Per capita": [fmt_metric(r["prime_par_tete_life"], "primes"), fmt_metric(r["prime_par_tete_nonlife"], "primes"), fmt_metric(r["prime_par_tete_total"], "primes")],
        }), hide_index=True, width="stretch")

    sc4, sc5 = st.columns(2)
    with sc4:
        st.markdown(f"**Growth** ({year_range[0]}–{year_range[1]}, derived)")
        growth = an.compute_growth_metrics(wide_df, year_range[0], year_range[1], "total")
        g = growth[growth["iso3"] == iso3]
        if g.empty:
            st.caption("Not enough data over this period.")
        else:
            g = g.iloc[0]
            st.dataframe(pd.DataFrame({
                "Indicator": ["Δ penetration", "Premium CAGR", "Premium/capita CAGR"],
                "Value": [fmt_pp_signed(g["delta_penetration"]), fmt_pct_signed(g["cagr_primes"]), fmt_pct_signed(g["cagr_per_capita"])],
            }), hide_index=True, width="stretch")
            st.caption("A rising premium volume with flat penetration usually reflects GDP growth, "
                       "not more insurance uptake — read Δ penetration as the real development signal.")

    with sc5:
        st.markdown(f"**Ranking** ({metric_label}, {year_selected})")
        rank = an.rank_country(wide_df, year_selected, cols["total"], iso3)
        if rank["global_rank"] is None:
            st.caption("No rank available for this metric/year.")
        else:
            st.dataframe(pd.DataFrame({
                "Scope": [f"Global (of {rank['n_global']})", f"{rank['region']} (of {rank['n_regional']})"],
                "Rank": [f"#{rank['global_rank']}", f"#{rank['regional_rank']}" if rank["regional_rank"] else "NA"],
            }), hide_index=True, width="stretch")

    st.markdown("**Profile** (analytical, Section 8)")
    pen_bench = an.quadrant_benchmark(wide_df.loc[wide_df["year"] == year_selected, "total"])
    cap_bench = an.quadrant_benchmark(wide_df.loc[wide_df["year"] == year_selected, "prime_par_tete_total"])
    profile = an.maturity_profile(r["prime_par_tete_total"], r["total"], cap_bench, pen_bench)
    st.info(f"**{profile}** — {an.MATURITY_DISCLAIMER}")

    mix = an.source_mix(long_df, iso3, year_range[0], year_range[1])
    if mix:
        mix_str = ", ".join(f"{k}: {v * 100:.0f}%" for k, v in mix.items())
        st.caption(f"Data sources over {year_range[0]}–{year_range[1]}: {mix_str}.")
