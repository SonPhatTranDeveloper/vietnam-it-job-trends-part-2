"""Queries and charts for notebook 01, market volume.

The feed's source mix changes by era, so a raw count of IT postings mostly tracks which
sources were being scraped. These functions therefore always pair a count with the IT share
of the same source's postings, which is the figure that survives a change of source.
"""

from __future__ import annotations

import duckdb
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure

from vnjobs.analysis import core as a

TOP_SOURCES = 6  # sources drawn on their own in the stacked chart; the rest become "Other"
SHARE_SOURCES = ("careerbuilder_vn", "monsterasia_vn", "linkedin_vn", "jora_vn", "careerjet_vn")
QUARTER_FROM_YEAR = 2023  # earlier years are too small to split into quarters
MIN_YTD_POSTINGS = 200  # hide sources too small to compare year to date
MIN_YEAR_POSTINGS = 1000  # drop source-years too thin to give a stable share


def monthly_by_source(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Count unique IT postings per month and source up to the last full month.

    Args:
        con: Connection from :func:`analysis.connect`.

    Returns:
        Columns ``month``, ``source``, ``it_postings``.
    """
    return a.query(
        con,
        f"""SELECT month, source, count(*) AS it_postings FROM it
        WHERE month <= '{a.LAST_FULL_MONTH}' GROUP BY month, source ORDER BY month""",
    )


def share_by_source_year(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Compute, per year and source, the IT postings and their share of all postings.

    Args:
        con: Connection from :func:`analysis.connect`.

    Returns:
        Columns ``year``, ``source``, ``all_postings``, ``it_postings``, ``it_share``.
    """
    return a.query(
        con,
        f"""SELECT substr(p.month, 1, 4) AS year, p.source,
               sum(p.postings) AS all_postings,
               coalesce(sum(i.n), 0) AS it_postings,
               round(100.0 * coalesce(sum(i.n), 0) / sum(p.postings), 1) AS it_share
        FROM all_postings p
        LEFT JOIN (SELECT month, source, count(*) AS n FROM it GROUP BY ALL) i
          USING (month, source)
        WHERE p.month <= '{a.LAST_FULL_MONTH}'
        GROUP BY ALL ORDER BY p.source, year""",
    )


def monthly_source_share(con: duckdb.DuckDBPyConnection, source: str) -> pd.DataFrame:
    """Return one source's monthly IT postings and IT share of its postings.

    Args:
        con: Connection from :func:`analysis.connect`.
        source: Raw source id, for example ``careerbuilder_vn``.

    Returns:
        Columns ``month``, ``all_postings``, ``it_postings``, ``it_share``.
    """
    return a.query(
        con,
        f"""SELECT p.month, p.postings AS all_postings, coalesce(i.n, 0) AS it_postings,
               round(100.0 * coalesce(i.n, 0) / p.postings, 2) AS it_share
        FROM all_postings p
        LEFT JOIN (SELECT month, count(*) AS n FROM it WHERE source = '{source}' GROUP BY month) i
          USING (month)
        WHERE p.source = '{source}' AND p.month <= '{a.LAST_FULL_MONTH}' ORDER BY p.month""",
    )


def period_table(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Total IT postings per period: years before 2023, quarters from 2023 on.

    Args:
        con: Connection from :func:`analysis.connect`.

    Returns:
        Columns ``period``, ``it_postings``, ``all_postings``, ``it_share``.
    """
    period = (
        f"CASE WHEN CAST(substr(month, 1, 4) AS INT) < {QUARTER_FROM_YEAR} "
        "THEN substr(month, 1, 4) "
        "ELSE substr(month, 1, 4) || '-Q' || ((CAST(substr(month, 6, 2) AS INT) + 2) // 3) END"
    )
    return a.query(
        con,
        f"""WITH i AS (SELECT {period} AS period, count(*) AS it_postings FROM it
                       WHERE month <= '{a.LAST_FULL_MONTH}' GROUP BY 1),
             t AS (SELECT {period} AS period, sum(postings) AS all_postings FROM all_postings
                       WHERE month <= '{a.LAST_FULL_MONTH}' GROUP BY 1)
        SELECT period, it_postings, all_postings,
               round(100.0 * it_postings / all_postings, 1) AS it_share
        FROM i JOIN t USING (period) ORDER BY period""",
    )


def ytd_table(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Compare January to the last full month of 2026 with the same months of 2025.

    Args:
        con: Connection from :func:`analysis.connect`.

    Returns:
        Columns ``source``, ``it_2025``, ``it_2026``, ``all_2025``, ``all_2026``,
        ``share_2025``, ``share_2026`` for the sources with at least ``MIN_YTD_POSTINGS``
        IT postings in either window. There is deliberately no total row: the two windows
        hold different sets of sources.
    """
    last = a.LAST_FULL_MONTH[5:]
    body = f"""SELECT source,
          count(*) FILTER (WHERE month BETWEEN '2025-01' AND '2025-{last}') AS it_2025,
          count(*) FILTER (WHERE month BETWEEN '2026-01' AND '2026-{last}') AS it_2026
        FROM it GROUP BY source"""
    totals = f"""SELECT source,
          sum(postings) FILTER (WHERE month BETWEEN '2025-01' AND '2025-{last}') AS all_2025,
          sum(postings) FILTER (WHERE month BETWEEN '2026-01' AND '2026-{last}') AS all_2026
        FROM all_postings GROUP BY source"""
    frame = a.query(con, f"SELECT * FROM ({body}) JOIN ({totals}) USING (source)")
    keep = (frame.it_2025 >= MIN_YTD_POSTINGS) | (frame.it_2026 >= MIN_YTD_POSTINGS)
    frame = frame[keep].copy()
    frame["source"] = frame["source"].map(a.source_label)
    frame["share_2025"] = (100 * frame.it_2025 / frame.all_2025).round(1)
    frame["share_2026"] = (100 * frame.it_2026 / frame.all_2026).round(1)
    return frame.sort_values("it_2026", ascending=False).reset_index(drop=True)


def chart_stacked_sources(monthly: pd.DataFrame) -> Figure:
    """Stack monthly IT postings by source to show how the mix changes.

    Args:
        monthly: Output of :func:`monthly_by_source`.

    Returns:
        The figure.
    """
    ranked = monthly.groupby("source").it_postings.sum().nlargest(TOP_SOURCES).index
    grouped = monthly.assign(
        group=monthly.source.where(monthly.source.isin(ranked), "other").map(a.source_label)
    )
    wide = grouped.pivot_table(index="month", columns="group", values="it_postings", aggfunc="sum")
    wide = wide.fillna(0)
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.stackplot(range(len(wide)), wide.T.values, labels=wide.columns, colors=a.SERIES_COLOURS)
    ticks = [i for i, month in enumerate(wide.index) if month.endswith("-01")]
    ax.set_xticks(ticks, [wide.index[i][:4] for i in ticks])
    ax.set_ylabel("Unique IT postings per month")
    ax.set_title("IT postings by source: the mix changes, so the total is not a market gauge")
    ax.legend(loc="upper left", ncol=2)
    return fig


def chart_share_by_source(shares: pd.DataFrame) -> Figure:
    """Draw the IT share of postings per year, one line per major source.

    Args:
        shares: Output of :func:`share_by_source_year`.

    Returns:
        The figure.
    """
    fig, ax = plt.subplots(figsize=(11, 5))
    for source in SHARE_SOURCES:
        part = shares[shares.source == source]
        part = part[part.all_postings >= MIN_YEAR_POSTINGS]
        ax.plot(part.year, part.it_share, marker="o", label=a.source_label(source))
    ax.set_ylabel("IT share of the source's postings (%)")
    ax.set_title("IT share depends on the source far more than on the year")
    ax.legend()
    return fig


def chart_careerbuilder(frame: pd.DataFrame) -> Figure:
    """Draw CareerBuilder's monthly IT postings and IT share on two panels.

    Args:
        frame: Output of :func:`monthly_source_share` for CareerBuilder.

    Returns:
        The figure.
    """
    fig, (top, bottom) = plt.subplots(2, 1, figsize=(11, 6.5), sharex=True)
    positions = range(len(frame))
    top.plot(positions, frame.it_postings, color=a.PALETTE["data"])
    top.set_ylabel("IT postings")
    top.set_title("CareerBuilder, the biggest source that spans the years (from Nov 2020)")
    bottom.plot(positions, frame.it_share, color=a.PALETTE["tension"])
    bottom.set_ylabel("IT share of postings (%)")
    ticks = [i for i, month in enumerate(frame.month) if month.endswith("-01")]
    bottom.set_xticks(ticks, [frame.month.iloc[i][:4] for i in ticks])
    return fig


SEASON_SOURCE = "careerbuilder_vn"
SEASON_YEARS = (2021, 2025)  # full calendar years of CareerBuilder data
MONTHS_IN_YEAR = 12


def seasonality(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Average monthly index of CareerBuilder postings over the full years 2021 to 2025.

    Each month's count is divided by that year's average month, so 1.0 is a normal month.

    Args:
        con: Connection from :func:`analysis.connect`.

    Returns:
        Columns ``month`` (1 to 12), ``all_index``, ``it_index`` (mean over years) and the
        lowest and highest yearly ``it_min`` / ``it_max`` index.
    """
    first, last = SEASON_YEARS
    monthly = a.query(
        con,
        f"""SELECT cast(substr(p.month, 1, 4) AS INT) AS year,
               cast(substr(p.month, 6, 2) AS INT) AS month,
               p.postings AS all_postings, coalesce(i.n, 0) AS it_postings
        FROM all_postings p
        LEFT JOIN (SELECT month, count(*) AS n FROM it WHERE source = '{SEASON_SOURCE}'
                   GROUP BY month) i USING (month)
        WHERE p.source = '{SEASON_SOURCE}'
          AND cast(substr(p.month, 1, 4) AS INT) BETWEEN {first} AND {last}""",
    )
    full = monthly.groupby("year").month.transform("count") == MONTHS_IN_YEAR
    monthly = monthly[full]
    for column in ("all_postings", "it_postings"):
        monthly[column.replace("postings", "index")] = monthly[column] / monthly.groupby("year")[
            column
        ].transform("mean")
    grouped = monthly.groupby("month")
    return (
        pd.DataFrame(
            {
                "all_index": grouped.all_index.mean(),
                "it_index": grouped.it_index.mean(),
                "it_min": grouped.it_index.min(),
                "it_max": grouped.it_index.max(),
            }
        )
        .round(2)
        .reset_index()
    )


def chart_seasonality(table: pd.DataFrame) -> Figure:
    """Draw the monthly index with the range across years.

    Args:
        table: Output of :func:`seasonality`.

    Returns:
        The figure.
    """
    fig, ax = plt.subplots(figsize=(10, 4.6))
    ax.fill_between(
        table.month,
        table.it_min,
        table.it_max,
        color=a.PALETTE["data"],
        alpha=0.15,
        label="IT, range over years",
    )
    ax.plot(table.month, table.it_index, marker="o", color=a.PALETTE["data"], label="IT postings")
    ax.plot(
        table.month, table.all_index, marker="o", color=a.PALETTE["chrome"], label="All postings"
    )
    ax.axhline(1, color=a.PALETTE["muted"], linewidth=1)
    ax.set_xticks(range(1, 13))
    ax.set_xlabel("Month")
    ax.set_ylabel("Index (1.0 = average month of the year)")
    ax.set_title("CareerBuilder seasonality, 2021 to 2025")
    ax.legend()
    return fig
