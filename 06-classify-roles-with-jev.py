"""Step 6 - label each IT job title with a role family, using Jev on the TITLE ONLY.

The rules in ``taxonomy.py`` give every title a role, but they leave about 14 % as "other" and
cannot tell a software developer from a technician or an electrical engineer. Jev answers one
choice question, ``role``, from the title alone. Identical titles get identical answers, so the
job is done once per DISTINCT cleaned title and cached in ``data/step-06-role-cache.jsonl``.

Reads ``data/step-05-features/`` (the unique IT postings). The notebooks join the cache back
by the same cleaned-title key (``analysis.load_features``); nothing else is written.

SPENDING. About $0.000022 per distinct title. Nothing is sent unless you pass ``--yes``.
Needs TYPESAFE_API_KEY in the environment or ``.env.local`` (git-ignored).

    uv run python 06-classify-roles-with-jev.py --dry-run
    uv run python 06-classify-roles-with-jev.py --limit 300 --yes     # pilot: 300 commonest titles
    uv run python 06-classify-roles-with-jev.py --yes                 # every distinct title
"""

from __future__ import annotations

import argparse

import duckdb

import jev
from common import FEATURES_DIR, ROLE_CACHE_PATH, clean_title_sql, connect

DEFAULT_WORKERS = 64
MIN_TITLE_LENGTH = 3

ROLES = {
    "ai_ml": "AI / machine-learning / LLM engineer or researcher, data scientist.",
    "data": "Data engineer, data analyst, BI developer, database administrator, ETL.",
    "backend": "Backend developer (Java, .NET, PHP, Python, Node, Go ...).",
    "frontend": "Frontend / web UI developer (React, Angular, Vue, JavaScript).",
    "fullstack": "Full-stack developer.",
    "mobile": "Mobile developer (Android, iOS, Flutter, React Native).",
    "devops_cloud": "DevOps, SRE, cloud, platform or infrastructure engineer.",
    "security": "Information-security / cyber-security engineer or analyst.",
    "qa_test": "QA, QC, tester, test automation engineer.",
    "game": "Game developer or game designer-programmer.",
    "embedded_iot": "Embedded, firmware, IoT, FPGA or hardware-software engineer.",
    "it_support_infra": "IT support, helpdesk, system or network administrator.",
    "erp_consulting": "ERP / SAP / Odoo / Salesforce developer or IT consultant.",
    "ba_pm_product": "Business analyst, project manager, product owner, scrum master.",
    "design": "UI / UX designer or graphic designer.",
    "software_other": "Software developer or IT engineer whose specialty is not stated.",
    "technical_non_software": (
        "Technician or engineer in a non-software field: electrical, mechanical, automation, "
        "telecom field work, maintenance, quality or production engineering."
    ),
    "not_it": "Not an IT job at all (sales, accounting, HR, driver, retail, teacher ...).",
}
QUESTION = {
    "role": {
        "type": "choice",
        "instructions": "Which role family best matches this job title?",
        "criteria": ROLES,
    }
}


def build_titles(con: duckdb.DuckDBPyConnection) -> list[tuple[str, str]]:
    """List the distinct cleaned IT titles that Jev has not labelled yet, commonest first.

    Args:
        con: Open DuckDB connection.

    Returns:
        ``(title_key, title)`` pairs.
    """
    clean = clean_title_sql()
    rows = con.execute(
        f"""SELECT lower({clean}) AS title_key, any_value({clean}) AS title
        FROM read_parquet('{FEATURES_DIR}/*.parquet')
        WHERE NOT fp_dup AND length({clean}) >= {MIN_TITLE_LENGTH}
        GROUP BY 1 ORDER BY count(*) DESC"""
    ).fetchall()
    cached = jev.read_cache(ROLE_CACHE_PATH)
    return [(key, title) for key, title in rows if key not in cached]


def parse_args() -> argparse.Namespace:
    """Parse the command line.

    Returns:
        The parsed options.
    """
    parser = argparse.ArgumentParser(description="Label IT titles with a role family (Jev)")
    parser.add_argument("--limit", type=int, default=0, help="ask at most this many titles")
    parser.add_argument("--yes", action="store_true", help="actually call Jev (spends money)")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="parallel requests")
    parser.add_argument("--dry-run", action="store_true", help="count and price only")
    return parser.parse_args()


def main() -> None:
    """Price the job and call Jev only when told to."""
    args = parse_args()
    todo = build_titles(connect())
    todo = todo[: args.limit] if args.limit else todo
    cost = len(todo) * jev.COST_PER_CALL
    print(f"{len(todo)} titles to ask; ~${cost:.2f}")
    if not todo or not args.yes or args.dry_run:
        print("nothing sent" + ("" if args.yes else " (pass --yes to spend)"))
        return
    jev.run_calls(todo, QUESTION, "role", ROLE_CACHE_PATH, args.workers)


if __name__ == "__main__":
    main()
