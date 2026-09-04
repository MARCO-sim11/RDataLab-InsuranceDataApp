"""Extracts the country-level appendix table (premium income, penetration,
and density i.e. premium per capita) from Allianz Global Insurance Report
PDFs.

Penetration and density are taken *directly* from Allianz - they're
reported figures, not something this project needs to compute. Premium
volume is extracted too but only used as a raw EUR reference (see
build_allianz_dataset.py): the USD premium volume used throughout the app
is still derived as penetration x World Bank GDP, the same formula used
for World Bank-sourced years, so premium volume stays comparable across
the whole 2000-2025 series. Density is reported in EUR - see
src/fx_rates.py for the EUR->USD conversion applied downstream.

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
    "Global-Insurance-Report-2021.pdf": None,
    "Global-Insurance-Report-2022.pdf": (2021, "2segment"),
    "Global-Insurance-Report-2023.pdf": (2022, "3segment"),
    "Global-Insurance-Report-2024.pdf": (2023, "3segment"),
    "Global-insurance-Report-2025.pdf": (2024, "3segment"),
    "Global-Insurance-Report-2026.pdf": (2025, "3segment"),
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
    single, unbroken tokens in every report inspected. Used as-is for the
    "2segment" layout, where density is also always a single token (no
    thousands-separator space observed in that report edition); the
    "3segment" layout needs `_merge_density_tokens` on top of this for its
    density columns - see `_parse_3segment`.
    """
    tokens = line.split()
    start = _find_value_start(tokens)
    if start is None or start == 0 or len(tokens) - start < n_values:
        return None
    return " ".join(tokens[:start]), tokens[start:start + n_values]


# A bare 1- or 2-digit token, e.g. the "1" in "1 500" (-> 1500), or the
# "10" in "10 411" (-> 10411). Every grouped density value observed across
# report editions has exactly this shape: a short leading group (1 or 2
# digits), a space (i.e. a token break), then a 3-digit group.
_LONE_DIGIT_RE = re.compile(r"^\d{1,2}$")
# A continuation group: exactly 3 digits, optionally with a European-style
# comma-decimal suffix (e.g. "500", or "362,1" for a value like "3362.1").
_CONTINUATION_RE = re.compile(r"^\d{3}(,\d{1,2})?$")


def _merge_density_tokens(tokens: list[str]) -> list[str]:
    """Re-joins a thousands-separator space back into one token (e.g.
    ["1", "500"] -> ["1500"]) for the density columns specifically - the
    only columns observed to be split this way (see module docstring for
    why premium/penetration never need this).

    Best-effort heuristic, not a guaranteed-correct parse:a merge fires 
    when the current token is a bare 1- or 2-digit group and the next token is a
    3-digit group. A genuine standalone single-digit density value
    immediately followed by a genuine standalone 3-digit value would be
    mis-merged into one - no such case has been observed across the 5
    report editions with a usable appendix table, but it's a real
    limitation of parsing text layout rather than a structured table.
    """
    merged: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if _LONE_DIGIT_RE.match(tok) and i + 1 < len(tokens) and _CONTINUATION_RE.match(tokens[i + 1]):
            tok = tok + tokens[i + 1]
            i += 2
        else:
            i += 1
        merged.append(tok)
    return merged


def _parse_3segment(text: str, data_year: int, report_file: str) -> pd.DataFrame:
    rows = []
    for line in text.split("\n"):
        tokens = line.split()
        start = _find_value_start(tokens)
        if start is None or start == 0 or len(tokens) - start < 6:
            continue
        country = " ".join(tokens[:start])
        sextet = tokens[start:start + 6]
        remainder = tokens[start + 6:]

        floats = [_to_float(v) for v in sextet]
        if all(v is None for v in floats):
            continue
        pc_prem, life_prem, health_prem, pc_pen, life_pen, health_pen = floats

        density_tokens = _merge_density_tokens(remainder)[:3]
        if len(density_tokens) == 3:
            pc_den, life_den, health_den = [_to_float(v) for v in density_tokens]
        else:
            pc_den = life_den = health_den = None

        rows.append({
            "country_raw": country, "year": data_year,
            "pc_penetration": pc_pen, "life_penetration": life_pen, "health_penetration": health_pen,
            "pc_premium_eur_bn": pc_prem, "life_premium_eur_bn": life_prem, "health_premium_eur_bn": health_prem,
            "pc_density_eur": pc_den, "life_density_eur": life_den, "health_density_eur": health_den,
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
        (pc_prem, _pc_yoy, pc_den, pc_pen,
         life_prem, _life_yoy, life_den, life_pen) = floats
        rows.append({
            "country_raw": country, "year": data_year,
            "pc_penetration": pc_pen, "life_penetration": life_pen, "health_penetration": None,
            "pc_premium_eur_bn": pc_prem, "life_premium_eur_bn": life_prem, "health_premium_eur_bn": None,
            "pc_density_eur": pc_den, "life_density_eur": life_den, "health_density_eur": None,
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
    return df, meta


def extract_all(reports_dir: Path) -> tuple[pd.DataFrame, list[dict]]:
    """Extract every report listed in REPORT_CONFIG found in `reports_dir`.

    Returns (raw_dataframe, per_report_meta_list). The raw dataframe has one
    row per country per data_year with pc/life/health penetration, premium
    (EUR bn), and density (EUR per capita) - it still needs country-name
    resolution (see resolve_countries) before use.
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
