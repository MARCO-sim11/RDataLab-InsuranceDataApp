# InsuranceR (Python: wbgapi + Streamlit)

Python write of the dashboard, built from two sources
that only ever get combined through one auditable step:

1. **World Bank** (`` + ``) — pulls insurance penetration, GDP and
   population from the World Bank API via
   [`wbgapi`](https://pypi.org/project/wbgapi/).
2. **Allianz** (``) —
   extracts the country appendix table from the Allianz Global Insurance
   Report PDFs (2022–2026 editions, covering 2021–2025 data).
3. **Combine** (``) — merges the two into the CSVs
   the app actually reads, validates the result, and only replaces the
   live files if every check passes. Every attempt is logged, successful
   or not, so the dashboard never breaks silently.
4. **Dashboard** (``, Streamlit): Country view, World view, a
   **Data Quality** tab, and a **Data Sources** tab to re-run steps 2–3
   from the UI.
