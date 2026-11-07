"""Queries and charts for notebook 05, companies.

Company names exist for almost every posting from 2022 on but only 44 % of 2021 and none of 2020
(the 2020 feed has no company field), so company trends start in 2021 and the first year is
flagged. Names are normalised (``taxonomy.company_key``): legal suffixes, branch notes and
punctuation are dropped so "KMS Technology, Inc." and "KMS Technology" are one employer.
Counts of distinct companies grow with the number of postings, so concentration is the more
honest measure of how hiring is spread.
"""

from __future__ import annotations

import pandas as pd

from vnjobs import taxonomy as tx
from vnjobs.analysis import core as a

TOP_N = 25
TOP_SHARE = 10
FROM_YEAR = 2021
BIG_HIRER_POSTINGS = 10


def named(frame: pd.DataFrame) -> pd.DataFrame:
    """Keep postings that name a company, from 2021 on.

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        The filtered rows.
    """
    return frame[frame.company_key.notna() & (frame.year >= FROM_YEAR)]


def coverage_by_year(frame: pd.DataFrame) -> pd.DataFrame:
    """Share of postings that name a company, per year.

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        Columns ``year``, ``postings``, ``pct_company_named``.
    """
    grouped = frame.groupby("year")
    return pd.DataFrame(
        {
            "postings": grouped.size(),
            "pct_company_named": (100 * grouped.company_key.agg(lambda s: s.notna().mean())).round(
                1
            ),
        }
    ).reset_index()


def top_hirers(frame: pd.DataFrame, first_month: str, last_month: str) -> pd.DataFrame:
    """Rank employers by IT postings in a window, with corporate groups combined.

    A company that belongs to a known group (FPT, Bosch, Vingroup ...) is counted under the
    group, so "Bosch" and "Bosch Group" are one employer.

    Args:
        frame: Postings that name a company.
        first_month: First month of the window, as ``YYYY-MM``.
        last_month: Last month of the window.

    Returns:
        Columns ``company``, ``postings``, ``share`` (% of the window's named postings).
    """
    window = frame[(frame.month >= first_month) & (frame.month <= last_month)]
    employer = window.company_group.fillna(window.company_key.str.title())
    counts = employer.value_counts().head(TOP_N).rename_axis("company").reset_index(name="postings")
    counts["share"] = (100 * counts.postings / len(window)).round(2)
    return counts


def concentration_by_year(frame: pd.DataFrame) -> pd.DataFrame:
    """How concentrated hiring is, per year and scope.

    Args:
        frame: Postings that name a company.

    Returns:
        Columns ``year``, ``postings``, ``companies``, ``top10_share`` (% of postings from the
        ten biggest hirers), ``pct_companies_posting_once``.
    """
    rows = []
    for year, part in frame.groupby("year"):
        counts = part.company_key.value_counts()
        rows.append(
            {
                "year": year,
                "postings": len(part),
                "companies": len(counts),
                "top10_share": round(100 * counts.head(TOP_SHARE).sum() / len(part), 1),
                "pct_companies_posting_once": round(100 * (counts == 1).mean(), 1),
            }
        )
    return pd.DataFrame(rows)


def kind_shares(frame: pd.DataFrame) -> pd.DataFrame:
    """Share of postings from banks, recruitment agencies and big corporate groups, per year.

    Args:
        frame: Postings that name a company.

    Returns:
        Columns ``year``, ``bank``, ``agency`` and one column per corporate group (%).
    """
    keyed = frame.assign(
        bank=frame.company_key.str.contains(tx.BANK_PATTERN, regex=True),
        agency=frame.company_key.str.contains(tx.AGENCY_PATTERN, regex=True),
    )
    rows = []
    for year, part in keyed.groupby("year"):
        row = {
            "year": year,
            "bank": round(100 * part.bank.mean(), 1),
            "agency": round(100 * part.agency.mean(), 1),
        }
        for group, _ in tx.COMPANY_GROUPS:
            row[group] = round(100 * (part.company_group == group).mean(), 1)
        rows.append(row)
    return pd.DataFrame(rows)


def returning_hirers(frame: pd.DataFrame) -> pd.DataFrame:
    """Count employers that posted IT jobs in several different years.

    Args:
        frame: Postings that name a company.

    Returns:
        Columns ``years_active`` and ``companies``.
    """
    years = frame.groupby("company_key").year.nunique()
    return (
        years.value_counts().sort_index().rename_axis("years_active").reset_index(name="companies")
    )


def leader_share_series(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Quarterly share of postings from the biggest hirers, to see concentration over time.

    Args:
        frame: Postings that name a company.

    Returns:
        ``{"Top 10 hirers": trend frame}`` where ``share`` is the % of postings from the ten
        employers with the most postings overall.
    """
    leaders = frame.company_key.value_counts().head(TOP_SHARE).index
    return {"Top 10 employers overall": a.trend_frame(frame, frame.company_key.isin(leaders))}
