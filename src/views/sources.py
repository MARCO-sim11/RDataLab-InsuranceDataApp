"""Data Sources: re-run the Allianz PDF extraction and the World Bank +
Allianz combine step from the browser, with a full history of every
attempt (see src/combine_sources.py for the atomic-write/validation
safety net that keeps the app usable even if a combine fails).
"""
from __future__ import annotations

import streamlit as st

from src import combine_sources as combine
from src.build_allianz_dataset import DEFAULT_REPORTS_DIR, write_allianz_dataset
from src.common import LOGO_PATH, load_data, page_header_html


def render(ctx: dict) -> None:

    hdr_l, hdr_r = st.columns([1, 10], vertical_alignment="center")
    with hdr_l:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), width=42)
    with hdr_r:
        st.markdown(page_header_html(), unsafe_allow_html=True)

    long_df = ctx["long_df"]

    st.subheader("Update data sources")
    st.caption(
        "Two independent sources feed this dashboard: the World Bank API (refreshed offline via "
        "`python refresh_data.py` - slow, needs network) and the Allianz Global Insurance Report PDFs "
        "(extracted below - fast, local, no network). Combining never touches the live data unless "
        "every check below passes, so the app keeps working even if a combine attempt fails."
    )

    src_col1, src_col2 = st.columns(2)
    with src_col1:
        st.metric("World Bank rows", f"{len(long_df[long_df['source'] == 'World Bank']):,}")
    with src_col2:
        n_allianz_rows = int(long_df["source"].str.startswith("Allianz", na=False).sum()) if "source" in long_df else 0
        st.metric("Allianz rows in current data", f"{n_allianz_rows:,}")

    st.divider()
    st.markdown("**1. Extract the Allianz PDF reports**")
    st.caption(f"Reads every report in `{DEFAULT_REPORTS_DIR}` and rebuilds `data/allianz/allianz_long.csv` / "
               f"`allianz_wide.csv`. Doesn't touch the live dashboard data - see step 2 for that.")
    if st.button("Extract Allianz reports", icon="\U0001F4C4"):
        with st.spinner("Parsing PDF reports..."):
            try:
                extraction_log = write_allianz_dataset()
                st.session_state["allianz_extraction_log"] = extraction_log
            except Exception as exc:  # noqa: BLE001
                st.session_state["allianz_extraction_log"] = [
                    {"filename": "(error)", "status": "failed", "message": str(exc)}
                ]

    if "allianz_extraction_log" in st.session_state:
        for m in st.session_state["allianz_extraction_log"]:
            icon = {"ok": "✅", "warning": "⚠️", "failed": "❌", "missing": "❌", "skipped": "⏭️"}.get(m["status"], "•")
            st.text(f"{icon} {m['filename']}: {m['message']}")

    st.divider()
    st.markdown("**2. Combine World Bank + Allianz**")
    st.caption(
        "Merges `worldbank_long/wide.csv` with `allianz_long/wide.csv` (World Bank never gets "
        "overwritten by Allianz for a country/year/type it already covers), validates the result, "
        "and only then replaces `insurance_long/wide.csv`."
    )
    if st.button("Combine sources", type="primary", icon="\U0001F504"):
        with st.spinner("Combining and validating..."):
            result = combine.run_combine()
        if result.status == "success":
            st.success(result.message)
            load_data.clear()
            for d in result.details:
                st.caption(d)
            st.rerun()
        else:
            st.error(result.message)
        for d in result.details:
            st.caption(d)

    st.divider()
    st.markdown("**Combine history**")
    log_df = combine.read_log(20)
    if log_df.empty:
        st.caption("No combine attempts logged yet.")
    else:
        st.dataframe(log_df, hide_index=True, width='stretch')
