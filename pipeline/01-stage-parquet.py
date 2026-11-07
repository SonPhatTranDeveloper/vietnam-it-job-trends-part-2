"""Stage the Techmap Vietnam job feed as Parquet, one file per month.

Reads ``data/job-dataset/techmap_jobs_vn_YYYY-MM-DD.jsonl`` (symlinked, 26 GB for
2020-2026) and writes ``data/staging/jobs_YYYY-MM.parquet`` for the chosen window.

* Drops the heavy raw columns (``html``, ``rawPage``) and the schema.org blob
  (``json``); keeps ``text`` (the description) for later steps.
* Keeps the nested objects as JSON so nothing is lost, and flattens only the
  handful of fields every later step needs.
* The dataset's schema drifts: before 2025 there is no isDuplicate / isRecruiter /
  isDirect / portal column at all. They come through as NULL, and ``has_dup_flag``
  records which rows could have been flagged in the first place.
* Skips months that are already staged, so a re-run only fills the gaps.

    uv run python pipeline/01-stage-parquet.py                      # all years, 2020-01 to 2026-11
    uv run python pipeline/01-stage-parquet.py --from 2024-01       # or a narrower window
"""

from __future__ import annotations

import argparse
import time
from collections.abc import Iterator
from pathlib import Path

import duckdb

from vnjobs.common import SOURCE_DIR, STAGING_DIR, connect

# Explicit column types make DuckDB skip the raw html and return NULL for any key an
# older file does not have, instead of failing on the schema drift.
READ_COLUMNS = """{
  'idInSource':'VARCHAR','portal':'VARCHAR','source':'VARCHAR','sourceCC':'VARCHAR',
  'locale':'VARCHAR','name':'VARCHAR','url':'VARCHAR','text':'VARCHAR',
  'dateScraped':'VARCHAR','dateCreated':'VARCHAR',
  'isDuplicate':'BOOLEAN','isDuplicateOf':'JSON','isRecruiter':'BOOLEAN','isDirect':'BOOLEAN',
  'position':'JSON','salary':'JSON','orgTags':'JSON','location':'JSON','company':'JSON'
}"""
MAX_OBJECT_BYTES = 134_217_728  # a single job line carries its full html; allow 128 MB
LAST_MONTH_OF_YEAR = 12


def month_range(start: str, end: str) -> Iterator[str]:
    """Yield every ``YYYY-MM`` month from ``start`` to ``end`` inclusive.

    Args:
        start: First month, as ``YYYY-MM``.
        end: Last month, as ``YYYY-MM``.

    Yields:
        Each month in order.
    """
    year, month = map(int, start.split("-"))
    last_year, last_month = map(int, end.split("-"))
    while (year, month) <= (last_year, last_month):
        yield f"{year:04d}-{month:02d}"
        year, month = (year + 1, 1) if month == LAST_MONTH_OF_YEAR else (year, month + 1)


def staging_sql(month: str, files: list[Path], destination: Path) -> str:
    """Build the COPY statement that stages one month.

    Args:
        month: The month being staged, as ``YYYY-MM``.
        files: The month's daily JSONL files.
        destination: Parquet file to write.

    Returns:
        A DuckDB ``COPY ... TO`` statement.
    """
    file_list = "[" + ",".join(f"'{f}'" for f in files) + "]"
    return f"""
    COPY (
      SELECT
        idInSource, portal, source, sourceCC, locale, name AS title, url, text,
        strptime(left(dateCreated, 10), '%Y-%m-%d')::DATE AS date_created,
        left(dateScraped, 19) AS date_scraped,
        '{month}' AS month,
        isDuplicate IS NOT NULL AS has_dup_flag,
        COALESCE(isDuplicate, false) AS is_duplicate,
        COALESCE(isRecruiter, false) AS is_recruiter,
        isDirect AS is_direct,
        json_extract_string(company, '$.nameOrg') AS company_name,
        json_extract_string(location, '$.orgAddress.city') AS city,
        json_extract_string(position, '$.careerLevel') AS career_level,
        json_extract_string(position, '$.workPlace') AS work_place,
        json_extract_string(salary, '$.text') AS salary_text,
        TRY_CAST(json_extract(salary, '$.value') AS DOUBLE) AS salary_value,
        json_extract_string(salary, '$.period') AS salary_period,
        position, salary, orgTags AS org_tags, location, company
      FROM read_json({file_list}, format='newline_delimited', columns={READ_COLUMNS},
                     maximum_object_size={MAX_OBJECT_BYTES}, ignore_errors=true)
    ) TO '{destination}' (FORMAT parquet, COMPRESSION zstd)
    """


def stage_month(con: duckdb.DuckDBPyConnection, month: str) -> int | None:
    """Stage one month unless it is already staged or has no source files.

    Args:
        con: Open DuckDB connection.
        month: The month to stage, as ``YYYY-MM``.

    Returns:
        The number of rows written, or ``None`` when the month was skipped.
    """
    destination = STAGING_DIR / f"jobs_{month}.parquet"
    files = sorted(SOURCE_DIR.glob(f"techmap_jobs_vn_{month}-*.jsonl"))
    if destination.exists():
        print(f"{month} skip (staged)")
        return None
    if not files:
        print(f"{month} no files")
        return None
    started = time.time()
    con.execute(staging_sql(month, files, destination))
    rows = con.execute(f"SELECT count(*) FROM read_parquet('{destination}')").fetchone()[0]
    size_mb = destination.stat().st_size / 1e6
    print(f"{month} {rows:7d} rows  {size_mb:7.1f} MB  {time.time() - started:5.1f}s", flush=True)
    return rows


def parse_args() -> argparse.Namespace:
    """Parse the command line.

    Returns:
        The parsed ``--from`` / ``--to`` month window.
    """
    parser = argparse.ArgumentParser(description="Stage the Techmap feed as monthly Parquet")
    parser.add_argument("--from", dest="start", default="2020-01")
    parser.add_argument("--to", dest="end", default="2026-11")
    return parser.parse_args()


def main() -> None:
    """Stage every month in the requested window and print the row total."""
    args = parse_args()
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    con = connect()
    total = 0
    for month in month_range(args.start, args.end):
        total += stage_month(con, month) or 0
    print("staged rows this run:", total)


if __name__ == "__main__":
    main()
