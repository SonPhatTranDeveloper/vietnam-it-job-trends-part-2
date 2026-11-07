"""Paths, constants and small helpers shared by every step of the pipeline."""

from __future__ import annotations

from pathlib import Path

import duckdb

DATA_DIR = Path("data")
SOURCE_DIR = DATA_DIR / "job-dataset"  # symlink to the Techmap JSONL feed
STAGING_DIR = DATA_DIR / "staging"
DEDUP_DIR = DATA_DIR / "step-02-dedup"
FINGERPRINT_DIR = DATA_DIR / "step-03-fp"
TITLES_PATH = DATA_DIR / "step-04-titles.parquet"
JEV_CACHE_PATH = DATA_DIR / "step-04-jev-cache.jsonl"
IT_DIR = DATA_DIR / "step-04-it"
AMBIGUOUS_DIR = DATA_DIR / "step-04-ambiguous"
FEATURES_DIR = DATA_DIR / "step-05-features"
ROLE_CACHE_PATH = DATA_DIR / "step-06-role-cache.jsonl"
DUCKDB_TEMP_DIR = DATA_DIR / ".duckdb-tmp"  # spill space, kept inside the git-ignored data/

# Strips "(...)" / "[...]" groups and a trailing " - <city>" from a title. The same
# expression keys the fingerprint (step 3) and the Jev cache (step 4), so a cached
# answer always matches the title it was asked about.
_CLEAN_TITLE_TEMPLATE = (
    r"trim(regexp_replace(regexp_replace(regexp_replace({col}, "
    r"'\s*[\(\[][^\)\]]*[\)\]]', '', 'g'), "
    r"'(?i)\s*[-|\x{{2013}},]\s*(hà nội|hồ chí minh|hcm|tp\.? ?hcm|đà nẵng|hn|remote)\b.*$', "
    r"'', 'g'), "
    r"'\s+', ' ', 'g'))"
)


def clean_title_sql(column: str = "title") -> str:
    """Build the DuckDB expression that cleans a job title.

    Args:
        column: Name (optionally table-qualified) of the column holding the raw title.

    Returns:
        A SQL expression that evaluates to the title without brackets or trailing city.
    """
    return _CLEAN_TITLE_TEMPLATE.format(col=column)


def connect() -> duckdb.DuckDBPyConnection:
    """Open an in-memory DuckDB connection configured for these scripts.

    Returns:
        A connection using 8 threads whose scratch files stay under ``data/``.
    """
    DUCKDB_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("PRAGMA threads=8")
    con.execute(f"SET temp_directory='{DUCKDB_TEMP_DIR}'")
    return con


def month_of(path: Path) -> str:
    """Extract the ``YYYY-MM`` month from a staged ``jobs_YYYY-MM.parquet`` file name.

    Args:
        path: Path of a monthly Parquet file.

    Returns:
        The month as a ``YYYY-MM`` string.
    """
    return path.stem.split("_")[-1][:7]
