"""Queries and charts for notebook 08, advertised salary.

Salary is a thin, selective signal: most postings carry no figure (or only "negotiable"), the
text comes in many formats, and which boards publish a range changes by year. Figures are
advertised monthly VND (USD at a fixed 25,000), the midpoint of the stated range, nominal (no
inflation adjustment). Read this as "what advertised ranges looked like", not as market pay.
"""

from __future__ import annotations

import pandas as pd

MIN_GROUP_POSTINGS = 150
MIN_YEAR_POSTINGS = 300
PERCENTILES = (0.25, 0.5, 0.75)


def with_midpoint(frame: pd.DataFrame) -> pd.DataFrame:
    """Keep postings with a parsed salary and add the monthly midpoint in millions of VND.

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        The rows with a salary, plus ``mid`` (million VND per month).
    """
    paid = frame[frame.salary_low.notna()].copy()
    paid["mid"] = (paid.salary_low + paid.salary_high) / 2 / 1e6
    return paid


def coverage_by_year(frame: pd.DataFrame) -> pd.DataFrame:
    """Share of postings with a usable salary and with a "negotiable"-style text, per year.

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        Columns ``year``, ``postings``, ``pct_with_figure``, ``pct_negotiable``.
    """
    grouped = frame.groupby("year")
    return pd.DataFrame(
        {
            "postings": grouped.size(),
            "pct_with_figure": (100 * grouped.salary_low.agg(lambda s: s.notna().mean())).round(1),
            "pct_negotiable": (100 * grouped.salary_negotiable.mean()).round(1),
        }
    ).reset_index()


def quantiles_by_year(frame: pd.DataFrame, source: str | None = None) -> pd.DataFrame:
    """Quartiles of the monthly midpoint per year.

    Args:
        frame: Output of :func:`analysis.load_features`.
        source: A source id, or ``None`` for every source.

    Returns:
        Columns ``year``, ``postings``, ``p25``, ``median``, ``p75`` (million VND per month),
        for years with at least ``MIN_YEAR_POSTINGS`` salaries.
    """
    paid = with_midpoint(frame)
    paid = paid if source is None else paid[paid.source == source]
    rows = []
    for year, part in paid.groupby("year"):
        if len(part) < MIN_YEAR_POSTINGS:
            continue
        p25, median, p75 = part.mid.quantile(PERCENTILES)
        rows.append(
            {
                "year": year,
                "postings": len(part),
                "p25": round(p25, 1),
                "median": round(median, 1),
                "p75": round(p75, 1),
            }
        )
    return pd.DataFrame(rows)


def median_by_group(frame: pd.DataFrame, column: str, years: tuple[int, int]) -> pd.DataFrame:
    """Median monthly midpoint per value of a column, within a range of years.

    Args:
        frame: Output of :func:`analysis.load_features`.
        column: Column to group by, such as ``role`` or ``level``.
        years: First and last year to include.

    Returns:
        Columns ``group``, ``postings``, ``median`` (million VND per month).
    """
    paid = with_midpoint(frame)
    paid = paid[paid.year.between(*years)]
    grouped = paid.groupby(column).mid.agg(postings="size", median="median")
    grouped = grouped[grouped.postings >= MIN_GROUP_POSTINGS].round(1)
    return (
        grouped.reset_index()
        .rename(columns={column: "group"})
        .sort_values("median", ascending=False)
    )


def source_check(frame: pd.DataFrame) -> pd.DataFrame:
    """Median midpoint per year and source, for source-years with enough salaries.

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        Columns ``year``, ``source``, ``postings``, ``median``.
    """
    paid = with_midpoint(frame)
    grouped = paid.groupby(["year", "source_name"]).mid.agg(postings="size", median="median")
    grouped = grouped[grouped.postings >= MIN_YEAR_POSTINGS].round(1)
    return grouped.reset_index().rename(columns={"source_name": "source"})
