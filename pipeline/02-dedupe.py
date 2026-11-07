"""Step 2 - drop the postings Techmap itself flags as duplicates.

Reads ``data/staging/jobs_YYYY-MM.parquet``.
Writes ``data/step-02-dedup/jobs_YYYY-MM.parquet`` (``is_duplicate = false`` only) and
``data/step-02-dedup-report.csv`` (per-month counts).

Non-destructive: staging is kept, and nothing but ``is_duplicate`` decides what is
dropped. IMPORTANT LIMIT: the flag only exists from May 2025 (``has_dup_flag`` is false
for earlier rows), so for the first 16 months this step removes nothing. The report
shows the flag coverage per month so no chart can quietly treat 2024 as "clean".

    uv run python pipeline/02-dedupe.py
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import duckdb

from vnjobs.common import DATA_DIR, DEDUP_DIR, STAGING_DIR, connect, month_of

REPORT_PATH = DATA_DIR / "step-02-dedup-report.csv"


class MonthCounts(NamedTuple):
    """Row counts for one staged month."""

    month: str
    rows: int
    with_flag_field: int
    flagged: int

    @property
    def kept(self) -> int:
        """Rows left after dropping the flagged duplicates."""
        return self.rows - self.flagged


def dedupe_month(con: duckdb.DuckDBPyConnection, staged: Path) -> MonthCounts:
    """Write one month without its flagged duplicates and count what was dropped.

    Args:
        con: Open DuckDB connection.
        staged: The month's staged Parquet file.

    Returns:
        The month's row, flag-coverage and flagged-duplicate counts.
    """
    month = month_of(staged)
    destination = DEDUP_DIR / f"jobs_{month}.parquet"
    con.execute(
        f"COPY (SELECT * FROM read_parquet('{staged}') WHERE NOT is_duplicate) "
        f"TO '{destination}' (FORMAT parquet, COMPRESSION zstd)"
    )
    rows, flagged, covered = con.execute(
        f"SELECT count(*), sum(is_duplicate::int), sum(has_dup_flag::int) "
        f"FROM read_parquet('{staged}')"
    ).fetchone()
    return MonthCounts(month, rows, covered, flagged)


def write_report(counts: list[MonthCounts]) -> None:
    """Save the per-month counts as CSV.

    Args:
        counts: One entry per staged month.
    """
    lines = ["month,rows,rows_with_flag_field,flagged_duplicates,kept"]
    lines += [f"{c.month},{c.rows},{c.with_flag_field},{c.flagged},{c.kept}" for c in counts]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_report(counts: list[MonthCounts]) -> None:
    """Print the per-month table and the grand total.

    Args:
        counts: One entry per staged month.
    """
    header = f"{'month':8s} {'rows':>8s} {'flag_coverage':>13s} {'flagged':>8s}"
    print(f"{header} {'dup%':>5s} {'kept':>8s}")
    for c in counts:
        coverage = 100 * c.with_flag_field // c.rows
        print(
            f"{c.month:8s} {c.rows:8d} {coverage:12d}% {c.flagged:8d} "
            f"{100 * c.flagged / c.rows:4.0f}% {c.kept:8d}"
        )
    total_rows = sum(c.rows for c in counts)
    total_flagged = sum(c.flagged for c in counts)
    print(f"TOTAL    {total_rows:8d} {total_flagged:21d} {total_rows - total_flagged:>15d}")


def main() -> None:
    """Dedupe every staged month, then write and print the report."""
    DEDUP_DIR.mkdir(parents=True, exist_ok=True)
    con = connect()
    counts = [dedupe_month(con, path) for path in sorted(STAGING_DIR.glob("jobs_*.parquet"))]
    write_report(counts)
    print_report(counts)


if __name__ == "__main__":
    main()
