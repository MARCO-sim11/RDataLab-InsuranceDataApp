"""Combines the World Bank and Allianz sources into the CSVs the app reads
(data/insurance_long.csv, data/insurance_wide.csv), with a paper trail and
a safety net: a combine attempt that fails, or produces something that
doesn't pass basic sanity checks, never touches the live files - the app
keeps serving whatever the last successful combine produced.

Four "bases" go in, pairwise:
    worldbank_long  + allianz_long  -> combined_long
    worldbank_wide  + allianz_wide  -> combined_wide   (derived from combined_long)

Every attempt - successful or not - appends one row to data/combine_log.csv.
"""
from __future__ import annotations

import os
import tempfile
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .build_wb_datasets import ID_COLS, to_wide

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LOG_PATH = DATA_DIR / "combine_log.csv"
LOG_COLS = ["timestamp", "status", "duration_sec", "n_wb_rows", "n_allianz_rows_available",
            "n_allianz_rows_added", "n_combined_long_rows", "n_combined_wide_rows", "message"]


@dataclass
class CombineResult:
    status: str  # "success" | "failed"
    message: str
    details: list[str] = field(default_factory=list)
    n_wb_rows: int = 0
    n_allianz_rows_available: int = 0
    n_allianz_rows_added: int = 0
    n_combined_long_rows: int = 0
    n_combined_wide_rows: int = 0
    duration_sec: float = 0.0


def _read_csv_or_none(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path)
    except Exception:
        return None
    return df


def _attach_macro(allianz_long: pd.DataFrame, macro: pd.DataFrame) -> pd.DataFrame:
    """Fills in population/gdp for Allianz rows by joining on World Bank's
    macro table (GDP/population, which covers a wider year range than the
    insurance indicators - see build_dataset.py), then fills any gaps in
    `primes`/`prime_par_tete` by deriving them the same way World
    Bank-sourced rows are (penetration x GDP, and primes/population).

    build_allianz_dataset.py already sets both directly from Allianz's own
    reported premium/density (converted EUR->USD) wherever available, and
    this function must not clobber that - it only fills gaps (missing FX
    rate for that year, or a row that predates this feature). That's the
    "calculate only where necessary" behavior requested: World Bank-sourced
    rows always need the derivation (World Bank never reports premium/
    density directly); Allianz-sourced rows only need it as a fallback.
    """
    out = allianz_long.merge(
        macro[["iso3", "year", "gdp", "population"]], on=["iso3", "year"], how="left"
    )

    if "primes" not in out.columns:
        out["primes"] = pd.NA
    out["primes"] = pd.to_numeric(out["primes"])
    needs_primes = out["primes"].isna()
    has_pen_gdp = needs_primes & out["penetration"].notna() & out["gdp"].notna()
    out.loc[has_pen_gdp, "primes"] = (out.loc[has_pen_gdp, "penetration"] / 100) * out.loc[has_pen_gdp, "gdp"]

    if "prime_par_tete" not in out.columns:
        out["prime_par_tete"] = pd.NA
    out["prime_par_tete"] = pd.to_numeric(out["prime_par_tete"])
    needs_derivation = out["prime_par_tete"].isna()
    has_primes_pop = needs_derivation & out["primes"].notna() & out["population"].notna() & (out["population"] > 0)
    out.loc[has_primes_pop, "prime_par_tete"] = out.loc[has_primes_pop, "primes"] / out.loc[has_primes_pop, "population"]

    return out[ID_COLS]


def _merge_long(wb_long: pd.DataFrame, allianz_long: pd.DataFrame, macro: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """World Bank rows always win. Allianz only fills (iso3, year, type)
    combinations the World Bank doesn't already have a value for."""
    if allianz_long.empty:
        return wb_long, 0

    covered = (
        wb_long.loc[wb_long["penetration"].notna(), ["iso3", "year", "type"]]
        .drop_duplicates()
    )
    check = allianz_long.merge(covered, on=["iso3", "year", "type"], how="left", indicator=True)
    allianz_new = allianz_long[(check["_merge"] == "left_only").values].copy()

    if allianz_new.empty:
        return wb_long, 0

    allianz_new = _attach_macro(allianz_new, macro)
    combined = pd.concat([wb_long, allianz_new], ignore_index=True)
    combined = combined.sort_values(["iso3", "year", "type"]).reset_index(drop=True)
    return combined, len(allianz_new)


def _validate(wb_wide: pd.DataFrame, combined_long: pd.DataFrame, combined_wide: pd.DataFrame) -> list[str]:
    """Sanity checks. Returns a list of problems; empty means OK to publish."""
    problems = []
    if combined_long.empty or combined_wide.empty:
        problems.append("Combined output is empty.")
        return problems
    if combined_wide.duplicated(subset=["iso3", "year"]).any():
        problems.append("Combined wide table has duplicate (country, year) rows.")
    if len(combined_wide) < len(wb_wide):
        problems.append(
            f"Combined wide table has fewer rows ({len(combined_wide)}) than the World Bank "
            f"table alone ({len(wb_wide)}) - combining should never lose rows."
        )
    missing_cols = set(ID_COLS) - set(combined_long.columns)
    if missing_cols:
        problems.append(f"Combined long table is missing expected columns: {sorted(missing_cols)}.")
    out_of_range = combined_long["penetration"].dropna()
    out_of_range = out_of_range[(out_of_range < 0) | (out_of_range > 100)]
    if len(out_of_range):
        problems.append(f"{len(out_of_range)} penetration value(s) outside the plausible 0-100% range.")
    return problems


def _append_log(row: dict) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    entry = pd.DataFrame([{c: row.get(c) for c in LOG_COLS}])
    if LOG_PATH.exists():
        entry.to_csv(LOG_PATH, mode="a", header=False, index=False)
    else:
        entry.to_csv(LOG_PATH, mode="w", header=True, index=False)


def read_log(n: int = 20) -> pd.DataFrame:
    if not LOG_PATH.exists():
        return pd.DataFrame(columns=LOG_COLS)
    return pd.read_csv(LOG_PATH).tail(n).iloc[::-1].reset_index(drop=True)


def run_combine(data_dir: Path = DATA_DIR) -> CombineResult:
    """Combine worldbank_{long,wide,macro}.csv with allianz_{long,wide}.csv
    into insurance_{long,wide}.csv. Always logs the attempt. Only replaces
    the live files if every validation check passes - a failed or
    suspicious combine leaves the previous insurance_long/wide.csv
    untouched, so the app keeps working off the last good result.
    """
    t0 = time.time()
    details: list[str] = []

    try:
        wb_long = _read_csv_or_none(data_dir / "worldbank_long.csv")
        wb_macro = _read_csv_or_none(data_dir / "worldbank_macro.csv")
        if wb_long is None or wb_macro is None:
            result = CombineResult(
                status="failed",
                message="World Bank source files not found. Run refresh_data.py first.",
                duration_sec=time.time() - t0,
            )
            _log(result)
            return result

        allianz_long = _read_csv_or_none(data_dir / "allianz" / "allianz_long.csv")
        if allianz_long is None or allianz_long.empty:
            details.append("No Allianz data found (data/allianz/allianz_long.csv missing or empty) - "
                            "combining World Bank data alone.")
            allianz_long = pd.DataFrame(columns=ID_COLS)
        n_allianz_available = len(allianz_long)

        # Optional small manual supplement (e.g. hand-entered figures for a
        # year/country the PDF extraction doesn't cover), same schema.
        manual_path = data_dir / "allianz_recent.csv"
        manual = _read_csv_or_none(manual_path)
        if manual is not None:
            manual = manual.dropna(subset=["iso3", "year", "type"]) if len(manual) else manual
            if len(manual):
                manual = manual.copy()
                manual["year"] = manual["year"].astype(int)
                manual["source"] = "Allianz Global Insurance Report (manual)"
                for col in ID_COLS:
                    if col not in manual.columns:
                        manual[col] = pd.NA
                allianz_long = pd.concat([allianz_long, manual[ID_COLS]], ignore_index=True)
                details.append(f"Included {len(manual)} row(s) from the manual supplement (allianz_recent.csv).")
                n_allianz_available += len(manual)

        combined_long, n_added = _merge_long(wb_long, allianz_long, wb_macro)
        combined_wide = to_wide(combined_long)

        wb_wide = _read_csv_or_none(data_dir / "worldbank_wide.csv")
        wb_wide = wb_wide if wb_wide is not None else to_wide(wb_long)

        problems = _validate(wb_wide, combined_long, combined_wide)
        if problems:
            result = CombineResult(
                status="failed",
                message="Validation failed - live data left untouched. " + " | ".join(problems),
                details=details,
                n_wb_rows=len(wb_long),
                n_allianz_rows_available=n_allianz_available,
                n_allianz_rows_added=n_added,
                n_combined_long_rows=len(combined_long),
                n_combined_wide_rows=len(combined_wide),
                duration_sec=time.time() - t0,
            )
            _log(result)
            return result

        _atomic_write_csv(combined_long, data_dir / "insurance_long.csv")
        _atomic_write_csv(combined_wide, data_dir / "insurance_wide.csv")

        result = CombineResult(
            status="success",
            message=f"Combined successfully: {n_added} Allianz row(s) added to {len(wb_long)} World Bank rows.",
            details=details,
            n_wb_rows=len(wb_long),
            n_allianz_rows_available=n_allianz_available,
            n_allianz_rows_added=n_added,
            n_combined_long_rows=len(combined_long),
            n_combined_wide_rows=len(combined_wide),
            duration_sec=time.time() - t0,
        )
        _log(result)
        return result

    except Exception as exc:  # noqa: BLE001 - deliberately broad: this must never crash the app
        result = CombineResult(
            status="failed",
            message=f"Unexpected error - live data left untouched: {exc}",
            details=details + [traceback.format_exc()],
            duration_sec=time.time() - t0,
        )
        _log(result)
        return result


def _atomic_write_csv(df: pd.DataFrame, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
    os.close(fd)
    try:
        df.to_csv(tmp_path, index=False)
        os.replace(tmp_path, target)  # atomic on both POSIX and Windows
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def _log(result: CombineResult) -> None:
    _append_log({
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": result.status,
        "duration_sec": round(result.duration_sec, 2),
        "n_wb_rows": result.n_wb_rows,
        "n_allianz_rows_available": result.n_allianz_rows_available,
        "n_allianz_rows_added": result.n_allianz_rows_added,
        "n_combined_long_rows": result.n_combined_long_rows,
        "n_combined_wide_rows": result.n_combined_wide_rows,
        "message": result.message,
    })


if __name__ == "__main__":
    res = run_combine()
    print(f"[{res.status}] {res.message}")
    for d in res.details:
        print(" -", d)
