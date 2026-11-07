"""Queries and charts for notebook 18, skill inflation by level.

Question: do junior postings name more technologies than they used to? The level used here is
read from the posting *title* only (junior, intern, senior), because the board label and the
stated experience are not available before 2025. The count of technologies named depends on how
much a source writes, so the comparison is only made inside the two control sources whose
descriptions keep a steady length (LinkedIn and Monster Asia), and the senior line is drawn
beside the junior one: if both rise together it is the descriptions, not a junior-specific shift.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.figure import Figure

from vnjobs.analysis import core as a
from vnjobs.analysis import technologies as t

CONTROLS = {"LinkedIn": "linkedin_vn", "Monster Asia": "monsterasia_vn"}
ENTRY_LEVELS = ("junior", "intern")
MIN_GROUP_POSTINGS = 30  # a period with fewer postings in a group is left off the line
EARLY = ("2023-01", "2024-12")
LATE = ("2025-07", "2026-09")  # 2025-Q1 and Q2 hold almost no title-junior postings on LinkedIn
Z_95 = 1.96


def level_postings(frame: pd.DataFrame) -> pd.DataFrame:
    """Keep tech-naming postings whose level comes from the title, as entry or senior.

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        The filtered rows with a ``group`` column (``"junior"`` or ``"senior"``) and ``n_techs``.
    """
    named = t.naming_postings(frame)
    from_title = named[named.level_from == "title"]
    entry = from_title.level.isin(ENTRY_LEVELS)
    kept = from_title[entry | (from_title.level == "senior")]
    return kept.assign(
        group=np.where(kept.level.isin(ENTRY_LEVELS), "junior", "senior"),
        n_techs=kept.techs.map(len),
    )


def mean_with_interval(values: pd.Series) -> dict[str, float]:
    """Summarise a column as n, mean and a 95 % interval for the mean.

    Args:
        values: The numbers to summarise.

    Returns:
        Keys ``n``, ``mean``, ``low`` and ``high``.
    """
    n = len(values)
    mean = float(values.mean())
    half = Z_95 * float(values.std(ddof=1)) / np.sqrt(n) if n > 1 else float("nan")
    return {
        "n": n,
        "mean": round(mean, 2),
        "low": round(mean - half, 2),
        "high": round(mean + half, 2),
    }


def series_by_period(postings: pd.DataFrame) -> pd.DataFrame:
    """Average technologies named per posting, per period, source and level group.

    Args:
        postings: Output of :func:`level_postings`.

    Returns:
        Columns ``source``, ``group``, ``period``, ``period_date``, ``n``, ``mean``, ``low``,
        ``high``, for periods with at least ``MIN_GROUP_POSTINGS`` postings.
    """
    rows = []
    limit = a.period_date_limit()
    for name, source in CONTROLS.items():
        scope = postings[postings.source == source]
        for (group, period, date), part in scope.groupby(["group", "period", "period_date"]):
            if len(part) >= MIN_GROUP_POSTINGS and date <= limit:
                rows.append(
                    {"source": name, "group": group, "period": period, "period_date": date}
                    | mean_with_interval(part.n_techs)
                )
    return pd.DataFrame(rows).sort_values(["source", "group", "period_date"])


def window_change(postings: pd.DataFrame) -> pd.DataFrame:
    """Compare the early and late windows for each source and level group.

    Args:
        postings: Output of :func:`level_postings`.

    Returns:
        One row per source and group with early and late mean, n, the change in technologies
        and the percentage change.
    """
    rows = []
    for name, source in CONTROLS.items():
        scope = postings[postings.source == source]
        for group in ("junior", "senior"):
            part = scope[scope.group == group]
            early = part[(part.month >= EARLY[0]) & (part.month <= EARLY[1])].n_techs
            late = part[(part.month >= LATE[0]) & (part.month <= LATE[1])].n_techs
            if len(early) < MIN_GROUP_POSTINGS or len(late) < MIN_GROUP_POSTINGS:
                continue
            e, f = mean_with_interval(early), mean_with_interval(late)
            rows.append(
                {
                    "source": name,
                    "group": group,
                    "early_n": e["n"],
                    "early_mean": e["mean"],
                    "late_n": f["n"],
                    "late_mean": f["mean"],
                    "change": round(f["mean"] - e["mean"], 2),
                    "change_pct": round(100 * (f["mean"] / e["mean"] - 1), 1),
                }
            )
    return pd.DataFrame(rows)


def chart_series(series: pd.DataFrame) -> Figure:
    """Draw junior and senior averages with their 95 % intervals, one panel per source.

    Args:
        series: Output of :func:`series_by_period`.

    Returns:
        A figure with one panel per control source and a shared y axis.
    """
    fig, axes = plt.subplots(1, len(CONTROLS), figsize=(13, 4.6), sharey=True)
    colours = {"junior": a.PALETTE["data"], "senior": a.PALETTE["tension"]}
    for ax, name in zip(axes, CONTROLS, strict=True):
        for group, colour in colours.items():
            line = series[(series.source == name) & (series.group == group)]
            ax.plot(line.period_date, line["mean"], color=colour, marker="o", label=group)
            ax.fill_between(line.period_date, line.low, line.high, color=colour, alpha=0.15)
        ax.set_title(name)
        ax.set_ylabel("Technologies named per posting")
        a.style_time_axis(ax, start=2021)
        ax.legend()
    fig.tight_layout()
    return fig
