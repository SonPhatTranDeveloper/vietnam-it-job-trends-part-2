"""Queries and charts for notebook 13, persistent vacancies.

A *vacancy key* is the same company, cleaned title and city group. Because each month's postings
are already de-duplicated, a key's number of rows is the number of different months it was listed
in. A key first seen in month ``m`` is called **persistent** if it is listed in at least three of
the six months from ``m`` on. Only keys first seen early enough to be watched for six months are
counted. This is a proxy for "listed for a long time": boards also repost to stay fresh, and a
scraper that revisits a board looks the same as a vacancy that stays open, so the notebook never
calls it time-to-fill and always compares within one source.
"""

from __future__ import annotations

import pandas as pd

WINDOW_MONTHS = 6
PERSISTENT_MONTHS = 3
LAST_FIRST_MONTH = "2026-04"  # six full months (to 2026-10) can still be watched
SOURCES = {"CareerBuilder": "careerbuilder_vn", "LinkedIn": "linkedin_vn"}
MIN_KEYS = 200
MIN_COMPANY_KEYS = 40
TOP_COMPANIES = 12


def month_index(months: pd.Series) -> pd.Series:
    """Turn ``YYYY-MM`` strings into a running month number.

    Args:
        months: Series of ``YYYY-MM`` strings.

    Returns:
        Integers that increase by one per calendar month.
    """
    return months.str[:4].astype(int) * 12 + months.str[5:7].astype(int)


def vacancy_table(frame: pd.DataFrame) -> pd.DataFrame:
    """Build one row per vacancy key first seen early enough, with its persistence flag.

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        Columns ``key``, ``first_month``, ``source``, ``role``, ``company``, ``persistent``.
    """
    named = frame[frame.company_key.notna()].copy()
    named["key"] = named.company_key + "|" + named.title_key + "|" + named.city_group
    named["idx"] = month_index(named.month)
    first = named.groupby("key").idx.transform("min")
    named["within"] = (named.idx - first) < WINDOW_MONTHS
    watched = named[named.within]
    counts = watched.groupby("key").size().rename("months_listed")
    firsts = named.sort_values("idx").drop_duplicates("key")
    firsts = firsts[firsts.month <= LAST_FIRST_MONTH].set_index("key")
    table = firsts[["month", "source", "role", "company_key"]].join(counts)
    table["persistent"] = table.months_listed >= PERSISTENT_MONTHS
    return table.rename(columns={"month": "first_month", "company_key": "company"}).reset_index()


def persistence_by(table: pd.DataFrame, column: str, source: str) -> pd.DataFrame:
    """Share of vacancy keys that are persistent, per value of a column, inside one source.

    Args:
        table: Output of :func:`vacancy_table`.
        column: ``role`` or the first year.
        source: A source id.

    Returns:
        Columns ``group``, ``keys``, ``pct_persistent`` for groups with at least ``MIN_KEYS``.
    """
    part = table[table.source == source]
    grouped = part.groupby(column).persistent.agg(
        keys="size", pct_persistent=lambda s: round(100 * s.mean(), 1)
    )
    big = grouped[grouped["keys"] >= MIN_KEYS]
    return (
        big.reset_index()
        .rename(columns={column: "group"})
        .sort_values("pct_persistent", ascending=False)
    )


def by_first_year(table: pd.DataFrame) -> pd.DataFrame:
    """Persistent share by the year a vacancy key was first seen, per source.

    Args:
        table: Output of :func:`vacancy_table`.

    Returns:
        Columns ``year``, ``source`` and ``pct_persistent`` / ``keys``.
    """
    rows = []
    for label, source in SOURCES.items():
        part = table[table.source == source].assign(year=lambda t: t.first_month.str[:4])
        for year, group in part.groupby("year"):
            if len(group) >= MIN_KEYS:
                rows.append(
                    {
                        "year": year,
                        "source": label,
                        "keys": len(group),
                        "pct_persistent": round(100 * group.persistent.mean(), 1),
                    }
                )
    return pd.DataFrame(rows)


def persistent_companies(table: pd.DataFrame) -> pd.DataFrame:
    """Employers with the highest persistent share, among those with enough vacancy keys.

    Args:
        table: Output of :func:`vacancy_table`.

    Returns:
        Columns ``company``, ``keys``, ``pct_persistent``.
    """
    grouped = table.groupby("company").persistent.agg(
        keys="size", pct_persistent=lambda s: round(100 * s.mean(), 1)
    )
    big = grouped[grouped["keys"] >= MIN_COMPANY_KEYS]
    top = big.sort_values("pct_persistent", ascending=False).head(TOP_COMPANIES)
    top = top.rename_axis("company").reset_index()
    top["company"] = top.company.str.title()
    return top
