"""Step 3 - a fingerprint duplicate mark that works for EVERY month.

Techmap's isDuplicate flag only exists from May 2025, so the 16 months before it are
not deduplicated by step 2. This step marks postings that repeat the same
(company, cleaned title, city, month), across sources, keeping the earliest one.

Reads ``data/step-02-dedup/jobs_*.parquet``.
Writes ``data/step-03-fp/jobs_YYYY-MM.parquet`` (all rows plus ``fp_dup``) and
``data/step-03-fp-report.csv`` (per-month repeat rate).

Nothing is dropped here: analyses use ``fp_dup = false`` for the headline number and
``fp_dup = true`` as the sensitivity check ("does the claim survive without it?").
Postings with no company name are never marked: without a company the fingerprint is
just a title, which would delete real separate openings. Some repeats are genuinely
separate openings with the same title, so the rate is an upper bound on true duplicates.

    uv run python 03-fingerprint.py
"""

from __future__ import annotations

import duckdb

from common import DATA_DIR, DEDUP_DIR, FINGERPRINT_DIR, clean_title_sql, connect, month_of

REPORT_PATH = DATA_DIR / "step-03-fp-report.csv"
FLAG_ERA_START = "2025-05"  # first month in which Techmap's own duplicate flag exists


def fingerprint_sql() -> str:
    """Build the expression that fingerprints a posting.

    Returns:
        A SQL expression over company, cleaned title, city and month (all lower-cased).
        The month is part of the fingerprint, so repeats never span two months.
    """
    return (
        f"lower(coalesce(company_name, '')) || '|' || lower({clean_title_sql()})"
        " || '|' || lower(coalesce(city, '')) || '|' || month"
    )


def write_month(con: duckdb.DuckDBPyConnection, month: str) -> tuple[str, int, int]:
    """Write one month with its ``fp_dup`` column and count the repeats.

    Because the fingerprint contains the month, each month is independent: no join, and the
    long description text just streams through.

    Args:
        con: Open DuckDB connection.
        month: The month to write, as ``YYYY-MM``.

    Returns:
        ``(month, rows, fingerprint_repeats)``.
    """
    source = DEDUP_DIR / f"jobs_{month}.parquet"
    destination = FINGERPRINT_DIR / f"jobs_{month}.parquet"
    # Keep the earliest posting of each fingerprint; a blank company is never a repeat.
    con.execute(
        f"""COPY (
          SELECT *,
                 (company_name IS NOT NULL AND company_name <> ''
                  AND row_number() OVER (
                      PARTITION BY {fingerprint_sql()}
                      ORDER BY date_created, source, idInSource) > 1) AS fp_dup
          FROM read_parquet('{source}')
        ) TO '{destination}' (FORMAT parquet, COMPRESSION zstd)"""
    )
    rows, repeats = con.execute(
        f"SELECT count(*), sum(fp_dup::int) FROM read_parquet('{destination}')"
    ).fetchone()
    return month, rows, repeats


def write_report(counts: list[tuple[str, int, int]]) -> None:
    """Save the per-month repeat counts as CSV.

    Args:
        counts: ``(month, rows, repeats)`` for each month.
    """
    lines = ["month,rows,fp_duplicates"] + [f"{m},{n},{d}" for m, n, d in counts]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def summarise(counts: list[tuple[str, int, int]]) -> None:
    """Print the repeat rate before and after Techmap's flag existed.

    Args:
        counts: ``(month, rows, repeats)`` for each month.
    """
    eras = {
        "before the flag": [c for c in counts if c[0] < FLAG_ERA_START],
        "flag exists": [c for c in counts if c[0] >= FLAG_ERA_START],
    }
    for label, months in eras.items():
        rows = sum(c[1] for c in months)
        repeats = sum(c[2] for c in months)
        rate = 100 * repeats / rows
        print(f"{label:16s} {rows:8d} rows, {repeats:7d} fingerprint repeats ({rate:.1f}%)")
    worst = sorted(((round(100 * d / n, 1), m) for m, n, d in counts), reverse=True)[:4]
    print("worst months:", worst)


def main() -> None:
    """Mark fingerprint repeats for every month, then write and print the report."""
    FINGERPRINT_DIR.mkdir(parents=True, exist_ok=True)
    con = connect()
    months = [month_of(p) for p in sorted(DEDUP_DIR.glob("jobs_*.parquet"))]
    counts = [write_month(con, month) for month in months]
    write_report(counts)
    summarise(counts)


if __name__ == "__main__":
    main()
