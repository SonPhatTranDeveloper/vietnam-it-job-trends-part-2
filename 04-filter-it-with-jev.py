"""Step 4 - keep the IT postings, using Jev on the TITLE ONLY.

Jev (TypeSafe, ``jev-latest``) answers one choice question, ``is_tech``, from the posting
title alone. Because only the title is sent, identical titles get identical answers, so
the job is done once per DISTINCT cleaned title and joined back to every posting.
Cleaning drops "(...)", "[...]" and a trailing city, keeps the original casing ("QA",
".NET"), and compares case-insensitively.

Reads ``data/step-03-fp/jobs_*.parquet`` (every posting, with its ``fp_dup`` mark carried through).
Writes ``data/step-04-titles.parquet`` (distinct titles + posting counts),
``data/step-04-jev-cache.jsonl`` (resumable: one line per answered title),
``data/step-04-it/`` (IT postings), ``data/step-04-ambiguous/`` (the rest) and
``data/step-04-report.csv`` (counts per month).

IT = Jev says ``tech`` with confidence >= 0.6. Confident non-tech is dropped; everything
else (low confidence either way, or no label) is ``ambiguous``: written apart and
counted, never silently folded into IT.

SPENDING. A Jev call costs about $0.000022 (part 1's own estimate). Nothing is sent
unless you pass ``--yes``. Needs TYPESAFE_API_KEY in the environment or in ``.env.local``
(git-ignored).

    uv run python 04-filter-it-with-jev.py --dry-run
    uv run python 04-filter-it-with-jev.py --limit 1000 --yes      # pilot
    uv run python 04-filter-it-with-jev.py --yes                   # everything
    uv run python 04-filter-it-with-jev.py --yes --workers 64      # parallel requests
    uv run python 04-filter-it-with-jev.py --write-only            # rebuild from the cache
"""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb

import jev
from common import (
    AMBIGUOUS_DIR,
    DATA_DIR,
    FINGERPRINT_DIR,
    IT_DIR,
    JEV_CACHE_PATH,
    TITLES_PATH,
    clean_title_sql,
    connect,
    month_of,
)

IT_CONFIDENCE = 0.6  # `tech` at or above this is IT; `non_tech` at or above is dropped
DEFAULT_WORKERS = 64  # parallel requests; raise or lower with --workers
MIN_TITLE_LENGTH = 3
REPORT_PATH = DATA_DIR / "step-04-report.csv"

QUESTION = {
    "is_tech": {
        "type": "choice",
        "instructions": "Is this a hands-on technical (tech) job?",
        "criteria": {
            "tech": (
                "Technical role: developer/engineer (backend, frontend, fullstack, mobile, "
                "embedded, game), data engineer, data scientist, data analyst, ML/AI engineer, "
                "DevOps/SRE/Cloud/Platform, QA/automation tester, security engineer, "
                "solution architect, system/network admin, IT support/helpdesk."
            ),
            "non_tech": (
                "Non-technical role: product owner/manager, project manager, scrum master, "
                "business analyst, UI/UX designer, graphic designer, and any non-IT role "
                "(sales, marketing, accounting, HR, admin, driver, retail, manufacturing, "
                "hospitality, etc.)."
            ),
        },
    }
}


# --- titles to ask about ---------------------------------------------------------------


def build_titles(con: duckdb.DuckDBPyConnection) -> None:
    """Write the distinct cleaned titles, with how many postings use each.

    Args:
        con: Open DuckDB connection.
    """
    clean = clean_title_sql()
    con.execute(
        f"""COPY (
          SELECT lower({clean}) AS title_key, any_value({clean}) AS title, count(*) AS postings
          FROM read_parquet('{FINGERPRINT_DIR}/*.parquet')
          WHERE length({clean}) >= {MIN_TITLE_LENGTH}
          GROUP BY 1
        ) TO '{TITLES_PATH}' (FORMAT parquet, COMPRESSION zstd)"""
    )


def pending_titles(
    con: duckdb.DuckDBPyConnection, limit: int
) -> tuple[list[tuple[str, str]], int, int]:
    """List the titles Jev has not answered yet, most frequent first.

    Args:
        con: Open DuckDB connection.
        limit: Maximum number of titles to return; 0 means no limit.

    Returns:
        ``(titles_to_ask, total_distinct_titles, already_cached)``.
    """
    cache = jev.read_cache(JEV_CACHE_PATH)
    rows = con.execute(
        f"SELECT title_key, title FROM read_parquet('{TITLES_PATH}') ORDER BY postings DESC"
    ).fetchall()
    todo = [(key, title) for key, title in rows if key not in cache]
    return (todo[:limit] if limit else todo), len(rows), len(cache)


# --- outputs ---------------------------------------------------------------------------


def load_cache_table(con: duckdb.DuckDBPyConnection) -> None:
    """Load the cached answers into a DuckDB table named ``jev``.

    Args:
        con: Open DuckDB connection.
    """
    con.execute(
        "CREATE OR REPLACE TABLE jev(title_key VARCHAR, jev_label VARCHAR, jev_conf DOUBLE)"
    )
    rows = [(k, v["label"], v["conf"]) for k, v in jev.read_cache(JEV_CACHE_PATH).items()]
    con.executemany("INSERT INTO jev VALUES (?, ?, ?)", rows)


def write_month(con: duckdb.DuckDBPyConnection, staged: Path) -> tuple[str, ...]:
    """Split one month into IT / ambiguous / non-tech and write the first two.

    Args:
        con: Open DuckDB connection holding the ``jev`` table.
        staged: The month's fingerprinted Parquet file.

    Returns:
        ``(month, rows, it, ambiguous, non_tech, unlabelled)`` as strings for the report.
    """
    month = month_of(staged)
    con.execute(
        f"""CREATE OR REPLACE TEMP TABLE m AS
        SELECT p.*, j.jev_label, j.jev_conf,
               CASE WHEN j.jev_label = 'tech' AND j.jev_conf >= {IT_CONFIDENCE} THEN 'it'
                    WHEN j.jev_label = 'non_tech' AND j.jev_conf >= {IT_CONFIDENCE} THEN 'non_tech'
                    ELSE 'ambiguous' END AS jev_class
        FROM read_parquet('{staged}') p
        LEFT JOIN jev j ON j.title_key = lower({clean_title_sql("p.title")})"""
    )
    for jev_class, folder in (("it", IT_DIR), ("ambiguous", AMBIGUOUS_DIR)):
        con.execute(
            f"COPY (SELECT * FROM m WHERE jev_class = '{jev_class}') "
            f"TO '{folder}/jobs_{month}.parquet' (FORMAT parquet, COMPRESSION zstd)"
        )
    counts = con.execute(
        """SELECT count(*), sum((jev_class = 'it')::int), sum((jev_class = 'ambiguous')::int),
                  sum((jev_class = 'non_tech')::int), sum((jev_label IS NULL)::int) FROM m"""
    ).fetchone()
    return (month, *map(str, counts))


def write_outputs(con: duckdb.DuckDBPyConnection) -> None:
    """Rebuild the IT and ambiguous sets from the cache and print the totals.

    Args:
        con: Open DuckDB connection.
    """
    IT_DIR.mkdir(parents=True, exist_ok=True)
    AMBIGUOUS_DIR.mkdir(parents=True, exist_ok=True)
    load_cache_table(con)
    report = [write_month(con, path) for path in sorted(FINGERPRINT_DIR.glob("jobs_*.parquet"))]
    header = "month,rows,it,ambiguous,non_tech,unlabelled"
    REPORT_PATH.write_text("\n".join([header, *[",".join(r) for r in report]]) + "\n")
    totals = [sum(int(r[i]) for r in report) for i in range(1, 6)]
    rows, it, ambiguous, non_tech, unlabelled = totals
    print(
        f"{rows} postings -> IT {it} ({100 * it / rows:.1f}%), "
        f"ambiguous {ambiguous} ({100 * ambiguous / rows:.1f}%), "
        f"non-tech {non_tech}, unlabelled {unlabelled}"
    )


# --- command line ----------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    """Parse the command line.

    Returns:
        The parsed options.
    """
    parser = argparse.ArgumentParser(description="Filter IT postings with Jev (title only)")
    parser.add_argument("--limit", type=int, default=0, help="ask at most this many titles")
    parser.add_argument("--yes", action="store_true", help="actually call Jev (spends money)")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="parallel requests")
    parser.add_argument("--dry-run", action="store_true", help="count and price only")
    parser.add_argument("--write-only", action="store_true", help="rebuild outputs from the cache")
    return parser.parse_args()


def main() -> None:
    """Price the job, call Jev only when told to, then rebuild the outputs."""
    args = parse_args()
    con = connect()
    if args.write_only:
        write_outputs(con)
        return
    build_titles(con)
    todo, total, cached = pending_titles(con, args.limit)
    cost = len(todo) * jev.COST_PER_CALL
    print(f"{total} distinct titles, {cached} already answered, {len(todo)} to ask; ~${cost:.2f}")
    if not todo:
        write_outputs(con)  # everything is cached: just rebuild the outputs
    elif not args.yes or args.dry_run:
        print("dry run: nothing sent (pass --yes to spend)")
    else:
        jev.run_calls(todo, QUESTION, "is_tech", JEV_CACHE_PATH, args.workers)
        write_outputs(con)


if __name__ == "__main__":
    main()
