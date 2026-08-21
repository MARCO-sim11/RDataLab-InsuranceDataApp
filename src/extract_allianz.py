"""Extracts the country-level appendix table (premium income, penetration)
from Allianz Global Insurance Report PDFs. Density (premium per capita) is
deliberately not extracted - it's reported in EUR while the rest of this
project works in USD, so premium volume / per-capita get recomputed from
World Bank GDP and population instead, once merged (see combine_sources.py).

Each report edition covers the *previous* year's KPIs (the report published
in May 2025 covers 2024 data, etc). Two table layouts are known:

  - "3segment" (p&c / life / health, each with premium+penetration+density):
    report editions 2023 onward.
  - "2segment" (p&c / life only, no health): report edition 2022.

The 2021 report edition (which would cover 2020 data) does not contain an
extractable country-level appendix table in this PDF - it's recorded as
"missing" rather than silently dropped, see extract_all()'s per-report
report.

This is a best-effort text-layout parser, not a general PDF table reader:
Allianz doesn't publish a machine-readable format, and each report's layout
has to be mapped by hand once (see REPORT_CONFIG). Always check the
per-report status/message before trusting the output.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pdfplumber

# A token that looks like a value: a number (either "1234.5" / "1,234.5"
# American style, or "1234,5" European style), a bare "n/a"/"n.a.", or a
# footnote marker like "1)".
_VALUE_TOKEN_RE = re.compile(r"^-?[\d.,]+\)?$|^n[/.]?a\.?$", re.IGNORECASE)

# filename -> (data_year, layout) | None if no usable appendix table exists
REPORT_CONFIG: dict[str, tuple[int, str] | None] = {
    "Global-Insurance-report-2021.pdf": None,
    "Global-Insurance-Report-2022.pdf": (2021, "2segment"),
    "Global-Insurance-Report-2023.pdf": (2022, "3segment"),
    "Global-Insurance-Report-2024.pdf": (2023, "3segment"),
    "Global-insurance-report-2025.pdf": (2024, "3segment"),
    "Global-Insurance-report-2026.pdf": (2025, "3segment"),
}


def _to_float(token: str) -> float | None:
    """Parse a single numeric token, disambiguating comma usage.

    A comma is either a thousands separator (American-formatted reports,
    e.g. "2,058" -> 2058) or a decimal separator (European-formatted
    reports, e.g. "11,8" -> 11.8). Since real thousands groups are always
    exactly 3 digits and these reports' decimal parts are always 1-2
    digits, the digit count after the last comma disambiguates the two
    reliably.
    """
    token = token.strip()
    if token.endswith(")"):  # footnote markers like "1)"
        return None
    if token.lower() in {"n/a", "n.a.", "na", "-"}:
        return None
    if "," in token and "." in token:
        token = token.replace(",", "")  # comma=thousands, period=decimal
    elif "," in token:
        frac = token.rsplit(",", 1)[-1]
        token = token.replace(",", "") if len(frac) == 3 and frac.isdigit() else token.replace(",", ".")
    try:
        return float(token)
    except ValueError:
        return None


def _find_value_start(tokens: list[str]) -> int | None:
    for i, tok in enumerate(tokens):
        if _VALUE_TOKEN_RE.match(tok):
            return i
    return None


def _split_row_left(line: str, n_values: int) -> tuple[str, list[str]] | None:
    """Split a table line into (country_name, value_tokens) by finding where
    the numeric columns start and taking the next `n_values` tokens.

    Left-anchored on purpose: the premium+penetration columns are always
    single, unbroken tokens in every report inspected, but the trailing
    density columns can be split across two tokens by a thousands-separator
    space in at least one report edition. Anchoring from the country name
    and only reading the columns we actually need sidesteps that entirely -
    density isn't parsed here (premium volume / per-capita get recomputed
    from World Bank GDP and population later instead, to stay in one
    currency).
    """
    tokens = line.split()
    start = _find_value_start(tokens)
    if start is None or start == 0 or len(tokens) - start < n_values:
        return None
    return " ".join(tokens[:start]), tokens[start:start + n_values]


def _parse_3segment(text: str, data_year: int, report_file: str) -> pd.DataFrame:
    rows = []
    for line in text.split("\n"):
        parsed = _split_row_left(line, 6)
        if not parsed:
            continue
        country, vals = parsed
        floats = [_to_float(v) for v in vals]
        if all(v is None for v in floats):
            continue
        pc_prem, life_prem, health_prem, pc_pen, life_pen, health_pen = floats
        rows.append({
            "country_raw": country, "year": data_year,
            "pc_penetration": pc_pen, "life_penetration": life_pen, "health_penetration": health_pen,
            "pc_premium_eur_bn": pc_prem, "life_premium_eur_bn": life_prem, "health_premium_eur_bn": health_prem,
            "source_file": report_file,
        })
    return pd.DataFrame(rows)


def _parse_2segment(text: str, data_year: int, report_file: str) -> pd.DataFrame:
    rows = []
    for line in text.split("\n"):
        parsed = _split_row_left(line, 8)
        if not parsed:
            continue
        country, vals = parsed
        floats = [_to_float(v) for v in vals]
        if all(v is None for v in floats):
            continue
        (pc_prem, _pc_yoy, _pc_den, pc_pen,
         life_prem, _life_yoy, _life_den, life_pen) = floats
        rows.append({
            "country_raw": country, "year": data_year,
            "pc_penetration": pc_pen, "life_penetration": life_pen, "health_penetration": None,
            "pc_premium_eur_bn": pc_prem, "life_premium_eur_bn": life_prem, "health_premium_eur_bn": None,
            "source_file": report_file,
        })
    return pd.DataFrame(rows)


def extract_report(path: Path) -> tuple[pd.DataFrame, dict]:
    """Extract one report's appendix table.

    Returns (dataframe, meta). meta always has keys: filename, data_year,
    layout, n_rows, status ("ok" | "warning" | "failed" | "missing" | "skipped"),
    message.
    """
    filename = path.name
    config = REPORT_CONFIG.get(filename)
    meta = {"filename": filename, "data_year": None, "layout": None, "n_rows": 0,
            "status": "skipped", "message": "No known appendix layout for this report."}

    if config is None:
        return pd.DataFrame(), meta

    data_year, layout = config
    meta.update(data_year=data_year, layout=layout)

    if not path.exists():
        meta.update(status="missing", message="File not found.")
        return pd.DataFrame(), meta

    text = None
    page_index = None
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            page_text = page.extract_text() or ""
            if "Appendix A" in page_text and (
                "Total premium income" in page_text or "P&C insurance market" in page_text
            ):
                text, page_index = page_text, i
                break

    if text is None:
        meta.update(status="failed", message="Appendix A page not found in PDF text.")
        return pd.DataFrame(), meta

    df = _parse_3segment(text, data_year, filename) if layout == "3segment" else _parse_2segment(text, data_year, filename)

    meta["n_rows"] = len(df)
    if len(df) < 10:
        meta.update(status="warning", message=f"Only {len(df)} rows extracted from page {page_index + 1} - layout may have changed.")
    else:
        meta.update(status="ok", message=f"Extracted {len(df)} country rows from page {page_index + 1}.")
    return df, meta, text


def extract_all(reports_dir: Path) -> tuple[pd.DataFrame, list[dict]]:
    """Extract every report listed in REPORT_CONFIG found in `reports_dir`.

    Returns (raw_dataframe, per_report_meta_list). The raw dataframe has one
    row per country per data_year with pc/life/health penetration - it still
    needs country-name resolution (see resolve_countries) before use.
    """
    frames = []
    metas = []
    for filename, config in REPORT_CONFIG.items():
        path = reports_dir / filename
        if config is None:
            metas.append({"filename": filename, "data_year": None, "layout": None,
                          "n_rows": 0, "status": "skipped",
                          "message": "No known appendix layout for this report edition."})
            continue
        df, meta = extract_report(path)
        metas.append(meta)
        if len(df):
            frames.append(df)

    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return combined, metas
