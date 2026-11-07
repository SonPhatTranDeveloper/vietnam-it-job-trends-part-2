"""Queries and charts for notebook 17, top employers year by year.

Notebook 05 ranks employers for two windows. A bump chart needs a ranking for every year, so this
module repeats that ranking per year, with corporate groups combined as there. Two limits shape
how to read it: only 44 % of 2021 postings name a company, and 2026 stops at October. Rankings
are also drawn for each large source on its own, because an employer that posts on one board only
rises and falls with that board.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure

from vnjobs.analysis import companies as co
from vnjobs.analysis import core as a

TOP_N = 10
MAX_RANK_SHOWN = 15  # an employer ranked lower than this in a year is drawn as absent
MIN_YEAR_POSTINGS = 500  # a year with fewer named postings is too thin to rank
SCOPES = {"All sources": None, "CareerBuilder": "careerbuilder_vn", "LinkedIn": "linkedin_vn"}


def employer_of(frame: pd.DataFrame) -> pd.Series:
    """Name each posting's employer, with corporate groups combined.

    Args:
        frame: Postings that name a company.

    Returns:
        The group name when the company belongs to a known group, else the title-cased name.
    """
    return frame.company_group.fillna(frame.company_key.str.title())


def yearly_ranking(frame: pd.DataFrame, source: str | None = None) -> pd.DataFrame:
    """Rank employers by IT postings within each year.

    Args:
        frame: Output of :func:`analysis.load_features`.
        source: Restrict to one source id, or ``None`` for every source.

    Returns:
        Columns ``year``, ``company``, ``postings``, ``share`` (% of the year's named postings)
        and ``rank``, for years with enough postings.
    """
    named = co.named(frame)
    if source is not None:
        named = named[named.source == source]
    counts = (
        named.assign(company=employer_of(named))
        .groupby(["year", "company"])
        .size()
        .rename("postings")
        .reset_index()
    )
    totals = counts.groupby("year").postings.transform("sum")
    counts["share"] = (100 * counts.postings / totals).round(2)
    counts["rank"] = counts.groupby("year").postings.rank(method="first", ascending=False)
    return counts[totals >= MIN_YEAR_POSTINGS].astype({"rank": int})


def top_by_year(ranking: pd.DataFrame) -> pd.DataFrame:
    """Keep each year's top employers.

    Args:
        ranking: Output of :func:`yearly_ranking`.

    Returns:
        The rows ranked ``TOP_N`` or better, ordered by year and rank.
    """
    top = ranking[ranking["rank"] <= TOP_N]
    return top.sort_values(["year", "rank"]).reset_index(drop=True)


def years_in_top(ranking: pd.DataFrame) -> pd.DataFrame:
    """Count how many years each employer spent in the top ranks.

    Args:
        ranking: Output of :func:`yearly_ranking`.

    Returns:
        Columns ``company``, ``years_in_top`` and ``best_rank``, most years first.
    """
    top = ranking[ranking["rank"] <= TOP_N]
    summary = top.groupby("company")["rank"].agg(years_in_top="size", best_rank="min")
    return summary.sort_values(["years_in_top", "best_rank"], ascending=[False, True]).reset_index()


def chart_bump(ranking: pd.DataFrame, title: str) -> Figure:
    """Draw a bump chart of every employer that reached the top ranks in any year.

    Args:
        ranking: Output of :func:`yearly_ranking`.
        title: Chart title, naming the scope.

    Returns:
        A figure with one line per employer and rank 1 at the top.
    """
    members = ranking[ranking["rank"] <= TOP_N].company.unique()
    shown = ranking[ranking.company.isin(members) & (ranking["rank"] <= MAX_RANK_SHOWN)]
    fig, ax = plt.subplots(figsize=(11, 7))
    for index, (company, line) in enumerate(shown.groupby("company")):
        colour = a.SERIES_COLOURS[index % len(a.SERIES_COLOURS)]
        ax.plot(line.year, line["rank"], marker="o", color=colour, label=company)
        last = line.iloc[-1]
        ax.annotate(company, (last.year, last["rank"]), xytext=(6, 0), textcoords="offset points")
    ax.set_ylim(MAX_RANK_SHOWN + 0.5, 0.5)
    ax.set_xlim(shown.year.min() - 0.3, shown.year.max() + 1.6)
    ax.set_xticks(sorted(shown.year.unique()))
    ax.set_ylabel("Rank by IT postings")
    ax.set_title(title)
    ax.grid(axis="x", alpha=0.3)
    return fig
