"""Market-structure analytics: positioning, growth/CAGR, Life/Non-Life
structure, and market concentration.

Every classification built here (quadrant zone, maturity profile,
Life/Non-Life dominance) is a **descriptive analytical label defined by
this application**, not an official industry, regulatory, or World
Bank/Allianz standard. Thresholds are documented in each function's
docstring so they can be audited or tuned.

Data caveat that applies to every function below: World Bank coverage runs
through ~2019-2021 depending on the indicator, and Allianz fills in more
recent years (see combine_sources.py). The two sources are not guaranteed
to use identical methodology (e.g. how health insurance is classified -
see the App4/App5 conversation history). Any growth/CAGR figure computed
across a start/end year that straddles the World Bank -> Allianz handover
should be read with that in mind; callers should surface the source(s)
involved (see `source_mix`) rather than presenting 2000-2025 as one
homogeneous series.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Market Positioning
# ---------------------------------------------------------------------------

POSITIONING_COLS = {
    "life": {"penetration": "life", "primes": "primes_life", "per_capita": "prime_par_tete_life"},
    "nonlife": {"penetration": "nonlife", "primes": "primes_nonlife", "per_capita": "prime_par_tete_nonlife"},
    "total": {"penetration": "total", "primes": "primes_total", "per_capita": "prime_par_tete_total"},
}


def positioning_frame(wide_df: pd.DataFrame, year: int, business_line: str) -> pd.DataFrame:
    """Data for the Market Positioning scatter (Section 4).

    Business question: how do countries compare on *how much* insurance
    they consume per person (premium per capita) versus *how central*
    insurance is to their economy (penetration, % of GDP), and how big is
    each market in absolute terms?

    Indicator / formula: three World Bank/Allianz-derived indicators read
    together - premium per capita (USD), penetration (% of GDP), and total
    premium volume (USD, used as bubble size). No new calculation beyond
    what's already in the wide table; this just selects and renames the
    columns for the chosen business line and year.

    Returns columns: country, iso3, region, income_level, x (premium per
    capita), y (penetration), size (premium volume). Rows with a missing
    x, y, or size are dropped - a bubble can't be plotted without all three.
    """
    cols = POSITIONING_COLS[business_line]
    d = wide_df[wide_df["year"] == year][
        ["country", "iso3", "region", "income_level", cols["per_capita"], cols["penetration"], cols["primes"]]
    ].rename(columns={cols["per_capita"]: "x", cols["penetration"]: "y", cols["primes"]: "size"})
    return d.dropna(subset=["x", "y", "size"])


def quadrant_benchmark(series: pd.Series) -> float:
    """The split line for one axis of the positioning quadrant.

    Formula: median of the series (robust to the extreme skew typical of
    premium/penetration data - a few very large or very small markets
    would distort a mean-based split). Callers may override with a fixed
    benchmark instead (e.g. a prior year's median, for a stable reference
    line across years).
    """
    return float(series.median())


def classify_quadrant(x: float, y: float, x_bench: float, y_bench: float) -> str:
    """Which of the four positioning zones (x, y) falls into.

    Business question: is this market penetration-led, consumption-led,
    both, or neither, relative to the peer set's median?

    Zones (Section 4): named literally (not "mature"/"emerging" - see
    `maturity_profile` for that friendlier, more opinionated label built
    on the exact same split).
    """
    if pd.isna(x) or pd.isna(y):
        return "Unknown"
    if y >= y_bench and x >= x_bench:
        return "High penetration / High premium per capita"
    if y >= y_bench and x < x_bench:
        return "High penetration / Low premium per capita"
    if y < y_bench and x >= x_bench:
        return "Low penetration / High premium per capita"
    return "Low penetration / Low premium per capita"


# ---------------------------------------------------------------------------
# Maturity profile (Section 8) - reuses the positioning quadrant
# ---------------------------------------------------------------------------

MATURITY_PROFILES = {
    "High penetration / High premium per capita": "Mature market",
    "High penetration / Low premium per capita": "Developing market",
    "Low penetration / High premium per capita": "Emerging market",
    "Low penetration / Low premium per capita": "Underinsured market",
    "Unknown": "Not enough data",
}

MATURITY_DISCLAIMER = (
    "Descriptive classification defined by this application (median "
    "penetration/premium-per-capita split for the selected year and "
    "business line), not an official industry or regulatory standard."
)


def maturity_profile(x: float, y: float, x_bench: float, y_bench: float) -> str:
    """Country's market-maturity label (Section 8), built from the exact
    same quadrant split as `classify_quadrant` - a "Mature market" is
    literally a "High penetration / High premium per capita" country. See
    MATURITY_DISCLAIMER: this is this application's own descriptive
    classification, not an official standard, and must be labeled as such
    wherever it's displayed.
    """
    return MATURITY_PROFILES[classify_quadrant(x, y, x_bench, y_bench)]


# ---------------------------------------------------------------------------
# Market Dynamics: growth / CAGR / delta penetration
# ---------------------------------------------------------------------------

def compute_growth_metrics(wide_df: pd.DataFrame, start_year: int, end_year: int,
                            business_line: str = "total") -> pd.DataFrame:
    """Per-country growth between two years (Section 5).

    Business question: where is insurance *developing* (penetration
    rising - insurance becoming more central to the economy) versus where
    is the premium volume merely *growing* (which can just track GDP or
    currency effects with penetration flat)? The two are deliberately
    reported side by side so one is never read as a proxy for the other.

    Formulas (n = end_year - start_year, in years):
    - delta_penetration = penetration[end] - penetration[start]  (in
      percentage points of GDP - the real "is insurance developing" signal)
    - cagr_primes = (primes[end] / primes[start]) ** (1/n) - 1
    - cagr_per_capita = (per_capita[end] / per_capita[start]) ** (1/n) - 1

    CAGR is undefined (returned as NaN) when the start value is missing,
    zero, or negative, or when n <= 0 - no sign-flipping or clipping is
    applied, so a genuine collapse or missing base year shows up as NaN
    rather than a misleading number.

    Limitation: a start/end pair that straddles the World Bank -> Allianz
    handover mixes two source methodologies into one growth figure -
    callers should check `source_mix` for the countries involved.
    """
    cols = POSITIONING_COLS[business_line]
    n_years = end_year - start_year
    base = wide_df[["country", "iso3", "region", "income_level"]].drop_duplicates("iso3")

    start = wide_df[wide_df["year"] == start_year][
        ["iso3", cols["penetration"], cols["primes"], cols["per_capita"]]
    ].rename(columns={cols["penetration"]: "penetration_start", cols["primes"]: "primes_start",
                       cols["per_capita"]: "per_capita_start"})
    end = wide_df[wide_df["year"] == end_year][
        ["iso3", cols["penetration"], cols["primes"], cols["per_capita"]]
    ].rename(columns={cols["penetration"]: "penetration_end", cols["primes"]: "primes_end",
                       cols["per_capita"]: "per_capita_end"})

    d = base.merge(start, on="iso3", how="inner").merge(end, on="iso3", how="inner")
    d["delta_penetration"] = d["penetration_end"] - d["penetration_start"]

    def _cagr(start_val, end_val):
        if n_years <= 0:
            return np.nan
        if pd.isna(start_val) or pd.isna(end_val) or start_val <= 0:
            return np.nan
        return (end_val / start_val) ** (1 / n_years) - 1

    d["cagr_primes"] = [
        _cagr(s, e) for s, e in zip(d["primes_start"], d["primes_end"])
    ]
    d["cagr_per_capita"] = [
        _cagr(s, e) for s, e in zip(d["per_capita_start"], d["per_capita_end"])
    ]
    return d


def top_bottom(df: pd.DataFrame, col: str, n: int = 10) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Top-n and bottom-n rows by `col`, dropping missing values first.
    Generic helper reused across Market Dynamics and Rankings."""
    ranked = df.dropna(subset=[col]).sort_values(col, ascending=False)
    return ranked.head(n), ranked.tail(n).sort_values(col, ascending=True)


# ---------------------------------------------------------------------------
# Life / Non-Life structure (Section 6)
# ---------------------------------------------------------------------------

DOMINANCE_THRESHOLD = 0.6


def classify_dominance(share_life: float, threshold: float = DOMINANCE_THRESHOLD) -> str:
    """Life vs Non-Life dominance label for one country-year.

    Business question: is this market's premium base concentrated in Life
    or Non-Life products?

    Formula: Life Share = Life Premium / Total Premium (already computed
    as `share_life` in the wide table). Labeled "Life-dominated" above
    `threshold`, "Non-life-dominated" below `1 - threshold`, else
    "Balanced". Default threshold 0.6 is this application's own cutoff,
    not an industry definition.
    """
    if pd.isna(share_life):
        return "Unknown"
    if share_life >= threshold:
        return "Life-dominated"
    if share_life <= 1 - threshold:
        return "Non-life-dominated"
    return "Balanced"


def structure_shift(wide_df: pd.DataFrame, start_year: int, end_year: int) -> pd.DataFrame:
    """Countries with the largest change in Life Share between two years
    (Section 6's "changements importants de structure").

    Formula: delta_share_life = share_life[end] - share_life[start].
    A large positive value means the market shifted toward Life over the
    period; a large negative value means it shifted toward Non-Life.
    Sorted by |delta_share_life| descending.
    """
    base = wide_df[["country", "iso3", "region"]].drop_duplicates("iso3")
    start = wide_df[wide_df["year"] == start_year][["iso3", "share_life"]].rename(
        columns={"share_life": "share_life_start"})
    end = wide_df[wide_df["year"] == end_year][["iso3", "share_life"]].rename(
        columns={"share_life": "share_life_end"})
    d = base.merge(start, on="iso3", how="inner").merge(end, on="iso3", how="inner")
    d = d.dropna(subset=["share_life_start", "share_life_end"])
    d["delta_share_life"] = d["share_life_end"] - d["share_life_start"]
    return d.reindex(d["delta_share_life"].abs().sort_values(ascending=False).index)


# ---------------------------------------------------------------------------
# Market concentration (Section 10)
# ---------------------------------------------------------------------------

def market_concentration(wide_df: pd.DataFrame) -> pd.DataFrame:

    """World premium concentration, one row per year (Section 10).

    Business question: "Is the global insurance market becoming more or
    less concentrated?" - i.e. is total premium volume spread across many
    countries, or dominated by a handful?

    Formulas, computed each year over every country with a non-missing
    total premium volume that year:
    - topN_share = sum(primes_total of the N largest markets) / sum(primes_total, all markets)
    - HHI (Herfindahl-Hirschman Index) = sum(market_share_i^2) * 10000,
      where market_share_i = primes_total_i / sum(primes_total). Ranges
      from ~0 (many equal-sized markets) to 10000 (one market has 100%).
      Conventionally: <1500 unconcentrated, 1500-2500 moderately
      concentrated, >2500 highly concentrated - these thresholds are a
      common antitrust-analysis convention, not specific to insurance.

    Limitation: country coverage changes over time (more countries report
    in recent years), which can mechanically move these figures even if
    underlying market structure hasn't changed - see the Data Quality tab
    for coverage by year before reading a trend as a real structural shift.
    """
    
    rows = []
    for year, d in wide_df.dropna(subset=["primes_total"]).groupby("year"):
        d = d[d["primes_total"] > 0]
        total = d["primes_total"].sum()
        if total <= 0 or len(d) == 0:
            continue
        shares = (d["primes_total"] / total).sort_values(ascending=False)
        rows.append({
            "year": int(year),
            "n_countries": len(d),
            "top5_share": shares.head(5).sum(),
            "top10_share": shares.head(10).sum(),
            "top20_share": shares.head(20).sum(),
            "hhi": float((shares ** 2).sum() * 10000),
        })
    return pd.DataFrame(rows).sort_values("year")


def concentration_snapshot(wide_df: pd.DataFrame, year: int, top_n: int = 10) -> pd.DataFrame:

    """Ranked country table for one year: premium volume, market share,
    and cumulative share - the detail behind one point of
    `market_concentration`'s topN_share line.
    """

    d = wide_df[(wide_df["year"] == year) & (wide_df["primes_total"] > 0)].dropna(subset=["primes_total"])
    total = d["primes_total"].sum()
    if total <= 0:
        return pd.DataFrame(columns=["country", "primes_total", "share", "cumulative_share"])
    d = d[["country", "primes_total"]].sort_values("primes_total", ascending=False).head(top_n).copy()
    d["share"] = d["primes_total"] / total
    d["cumulative_share"] = d["share"].cumsum()
    return d


# ---------------------------------------------------------------------------
# Ranking (global + regional) - used by the Country Scorecard
# ---------------------------------------------------------------------------

def rank_country(wide_df: pd.DataFrame, year: int, metric_col: str, iso3: str) -> dict:

    """A country's global and regional rank on one metric/year (feeds the
    "Ranking" block of the Country Scorecard, Section 15).

    Formula: simple descending rank (rank 1 = highest value) among all
    countries with a non-missing value for `metric_col` in `year`;
    regional rank is the same, restricted to the country's own World Bank
    region. Returns a dict with global_rank, n_global, regional_rank,
    n_regional, region - any of the rank fields is None if the country
    itself has no value that year.
    """
    d = wide_df[wide_df["year"] == year].dropna(subset=[metric_col])
    if d.empty or iso3 not in set(d["iso3"]):
        region = wide_df.loc[wide_df["iso3"] == iso3, "region"].dropna()
        return {"global_rank": None, "n_global": len(d), "regional_rank": None, "n_regional": 0,
                "region": region.iloc[0] if len(region) else None}

    ranked = d.sort_values(metric_col, ascending=False).reset_index(drop=True)
    global_rank = int(ranked.index[ranked["iso3"] == iso3][0]) + 1

    region = ranked.loc[ranked["iso3"] == iso3, "region"].iloc[0]
    regional = ranked[ranked["region"] == region].reset_index(drop=True)
    regional_rank = int(regional.index[regional["iso3"] == iso3][0]) + 1 if len(regional) else None

    return {"global_rank": global_rank, "n_global": len(ranked), "regional_rank": regional_rank,
            "n_regional": len(regional), "region": region}


# ---------------------------------------------------------------------------
# Source transparency (Section 17)
# ---------------------------------------------------------------------------

def source_transition_year(long_df: pd.DataFrame, iso3: str | None = None) -> int | None:

    """First year covered by a non-"World Bank" source (i.e. the Allianz
    supplement), for the given country (or globally if iso3 is None).

    Used to annotate time-series charts with a "World Bank -> Allianz"
    marker, per Section 17: a chart spanning 2000-2025 should not imply a
    single homogeneous methodology across the whole period.
    """
    d = long_df if iso3 is None else long_df[long_df["iso3"] == iso3]
    other_source = d[d["source"] != "World Bank"]
    if other_source.empty:
        return None
    return int(other_source["year"].min())


def source_mix(long_df: pd.DataFrame, iso3: str | None = None,
                start_year: int | None = None, end_year: int | None = None) -> dict:

    """Share of observed (non-missing-penetration) rows coming from each
    source, optionally scoped to one country and/or year range. Used to
    flag when a computation (e.g. a CAGR) blends multiple sources."""

    d = long_df[long_df["penetration"].notna()]
    if iso3 is not None:
        d = d[d["iso3"] == iso3]
    if start_year is not None:
        d = d[d["year"] >= start_year]
    if end_year is not None:
        d = d[d["year"] <= end_year]
    if d.empty:
        return {}
    return (d["source"].value_counts(normalize=True)).to_dict()
 