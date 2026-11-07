"""Turn each IT posting into the features the analysis notebooks count.

Reads ``data/step-04-it/`` and writes ``data/step-05-features/jobs_YYYY-MM.parquet`` with one
row per IT posting (repeats stay in, marked ``fp_dup``) and no description text. Features:

* ``techs``: technologies named in the title and description (dictionary in ``taxonomy.py``).
* ``tag_techs``: technologies named in the board's own ``SKILLS`` tags, for an accuracy check.
* ``role``: role family from title rules.
* ``level`` / ``level_from`` / ``exp_months``: seniority, which signal decided it, and the
  required experience when the feed states one.
* ``work_mode``, ``city_group``, ``company_key`` / ``company_group``.
* ``salary_low`` / ``salary_high`` (VND per month) and ``salary_negotiable``.

    uv run python 05-extract-features.py
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

import taxonomy as tx
from common import DATA_DIR, FEATURES_DIR, IT_DIR, connect, month_of

REPORT_PATH = DATA_DIR / "step-05-report.csv"
MIN_TEXT_CHARS = 200  # shorter descriptions are treated as "no description"
_AI_WORD = re.compile(r"\bAI\b")  # case-sensitive: lower-case "ai" is the Vietnamese "anyone"
_MONTH_NOISE = re.compile(r"monthsofexperience:\s*no requirements", re.IGNORECASE)

# Explicit types, because a month where a column is all NULL would otherwise be written as NULL.
SCHEMA = pa.schema(
    [
        ("month", pa.string()),
        ("source", pa.string()),
        ("fp_dup", pa.bool_()),
        ("title", pa.string()),
        ("role", pa.string()),
        ("techs", pa.list_(pa.string())),
        ("tag_techs", pa.list_(pa.string())),
        ("has_skill_tags", pa.bool_()),
        ("has_text", pa.bool_()),
        ("ai_in_title", pa.bool_()),
        ("ai_in_text", pa.bool_()),
        ("work_mode", pa.string()),
        ("city_group", pa.string()),
        ("company_key", pa.string()),
        ("company_group", pa.string()),
        ("level", pa.string()),
        ("level_from", pa.string()),
        ("exp_months", pa.int32()),
        ("salary_low", pa.float64()),
        ("salary_high", pa.float64()),
        ("salary_negotiable", pa.bool_()),
    ]
)

READ_SQL = """SELECT month, source, fp_dup, title, text, company_name, city, career_level,
       work_place, salary_text, org_tags::VARCHAR AS org_tags
FROM read_parquet('{path}')"""


def tag_list(tags: dict[str, Any], key: str) -> list[str]:
    """Read one list from the decoded ``orgTags`` object, dropping empty entries.

    Args:
        tags: The decoded ``orgTags`` JSON (possibly empty).
        key: Tag name such as ``SKILLS`` or ``CAREER_LEVELS``.

    Returns:
        The non-empty string values.
    """
    return [value for value in tags.get(key) or [] if isinstance(value, str) and value.strip()]


def decode_tags(raw: str | None) -> dict[str, Any]:
    """Decode the ``org_tags`` JSON string.

    Args:
        raw: The JSON text, or ``None``.

    Returns:
        The decoded object, or an empty dict when missing or malformed.
    """
    try:
        decoded = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {}
    return decoded if isinstance(decoded, dict) else {}


def level_features(title: str, career_level: str | None, tags: dict[str, Any]) -> dict[str, Any]:
    """Compute the seniority features for one posting.

    Args:
        title: The job title.
        career_level: The ``position.careerLevel`` value.
        tags: The decoded ``orgTags``.

    Returns:
        ``level``, ``level_from`` and ``exp_months``.
    """
    labels = [career_level or "", *tag_list(tags, "CAREER_LEVELS")]
    labels += [label for label in tag_list(tags, "EXPERIENCE_REQUIREMENTS") if label]
    labels = [label for label in labels if not _MONTH_NOISE.search(label)]
    months = tx.experience_months(labels)
    level, source = tx.classify_level(title, labels, months)
    return {"level": level, "level_from": source, "exp_months": months}


def salary_features(salary_text: str | None) -> dict[str, Any]:
    """Compute the salary features for one posting.

    Args:
        salary_text: The advertised salary text.

    Returns:
        ``salary_low``, ``salary_high`` (VND per month) and ``salary_negotiable``.
    """
    low, high, negotiable = tx.parse_salary(salary_text)
    return {"salary_low": low, "salary_high": high, "salary_negotiable": negotiable}


def row_features(row: dict[str, Any]) -> dict[str, Any]:
    """Compute every feature for one posting.

    Args:
        row: One row of :data:`READ_SQL`.

    Returns:
        The feature row to write.
    """
    title = row["title"] or ""
    text = row["text"] or ""
    tags = decode_tags(row["org_tags"])
    skills = [s for s in tag_list(tags, "SKILLS") if "experience" not in s.lower()]
    key = tx.company_key(row["company_name"])
    return {
        "month": row["month"],
        "source": row["source"],
        "fp_dup": row["fp_dup"],
        "title": title,
        "role": tx.classify_role(title),
        "techs": tx.find_techs(f"{title} {text}".lower()),
        "tag_techs": tx.find_techs(" , ".join(skills).lower()),
        "has_skill_tags": bool(skills),
        "has_text": len(text) >= MIN_TEXT_CHARS,
        "ai_in_title": bool(_AI_WORD.search(title)),
        "ai_in_text": bool(_AI_WORD.search(text)),
        "work_mode": tx.work_mode(row["work_place"]),
        "city_group": tx.city_group(row["city"]),
        "company_key": key,
        "company_group": tx.company_group(key),
        **level_features(title, row["career_level"], tags),
        **salary_features(row["salary_text"]),
    }


def month_rows(con: duckdb.DuckDBPyConnection, path: Path) -> list[dict[str, Any]]:
    """Read one month of IT postings as dictionaries.

    Args:
        con: Open DuckDB connection.
        path: The month's step 04 Parquet file.

    Returns:
        One dict per posting.
    """
    result = con.execute(READ_SQL.format(path=path))
    names = [column[0] for column in result.description]
    return [dict(zip(names, values, strict=True)) for values in result.fetchall()]


def write_month(features: list[dict[str, Any]], month: str) -> None:
    """Write one month of feature rows to Parquet.

    Args:
        features: Output of :func:`row_features` for every posting in the month.
        month: The month, as ``YYYY-MM``.
    """
    if not features:
        return
    columns = {name: [row[name] for row in features] for name in SCHEMA.names}
    pq.write_table(
        pa.table(columns, schema=SCHEMA), FEATURES_DIR / f"jobs_{month}.parquet", compression="zstd"
    )


def write_report(con: duckdb.DuckDBPyConnection) -> list[list[Any]]:
    """Write per-year coverage of each feature and return the rows.

    Args:
        con: Open DuckDB connection.

    Returns:
        The report rows, header first.
    """
    result = con.execute(
        f"""SELECT substr(month, 1, 4) AS year, count(*) AS postings,
               round(100 * avg((len(techs) > 0)::INT), 1) AS pct_with_tech,
               round(100 * avg((role = 'other')::INT), 1) AS pct_role_other,
               round(100 * avg((level = 'unknown')::INT), 1) AS pct_level_unknown,
               round(100 * avg((work_mode IS NOT NULL)::INT), 1) AS pct_work_mode,
               round(100 * avg((salary_low IS NOT NULL)::INT), 1) AS pct_salary,
               round(100 * avg((company_key IS NOT NULL)::INT), 1) AS pct_company
        FROM read_parquet('{FEATURES_DIR / "*.parquet"}') GROUP BY year ORDER BY year"""
    )
    rows = [[column[0] for column in result.description], *result.fetchall()]
    with REPORT_PATH.open("w", newline="") as handle:
        csv.writer(handle).writerows(rows)
    return rows


def main() -> None:
    """Extract features for every IT month and print the per-year coverage."""
    FEATURES_DIR.mkdir(parents=True, exist_ok=True)
    con = connect()
    for path in sorted(IT_DIR.glob("jobs_*.parquet")):
        month = month_of(path)
        write_month([row_features(row) for row in month_rows(con, path)], month)
        print(month, flush=True)
    for row in write_report(con):
        print(*row, sep="\t")


if __name__ == "__main__":
    main()
