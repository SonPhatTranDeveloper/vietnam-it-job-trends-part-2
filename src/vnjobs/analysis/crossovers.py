"""Queries and charts for notebook 16, technology crossovers.

A crossover is the period after which one technology stays ahead of another for good. The
all-source line can cross because the source mix changed, not because the market did, so a
crossover is only reported as a finding when it also happens, within two quarters, inside each
of the two control sources (LinkedIn and Monster Asia) whose descriptions keep a steady length.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure

from vnjobs.analysis import core as a

PAIRS = [
    ("Python", "Java"),
    ("Python", "JavaScript"),
    ("Docker", "JavaScript"),
    ("Docker", "React"),
    ("CI/CD", "JavaScript"),
    ("AWS", "Java"),
    ("Kubernetes", "React"),
    ("Machine Learning", "React"),
]
SCOPES = {"All sources": None, "LinkedIn": "linkedin_vn", "Monster Asia": "monsterasia_vn"}
CONTROLS = ["LinkedIn", "Monster Asia"]
# Monster Asia is small, so the usual 400-posting floor would hide most of its quarters. A share
# over 100 tech-naming postings is noisy but readable, and the "stays ahead for good" rule
# below is what protects against a single noisy quarter.
MIN_SCOPE_POSTINGS = 100
# Two quarters, so a one-quarter difference between the two controls still counts as agreement.
# A lead smaller than this is a tie, not a crossover: on LinkedIn Python and Java sit within
# a point or two of each other for a year, and a half-point lead would date the crossover
# to a quarter where nothing visible happened.
LEAD_MARGIN = 2.0
AGREE_WITHIN = pd.Timedelta(days=200)


def pair_names() -> list[str]:
    """List every technology that appears in a pair, once each.

    Returns:
        The technology names, in first-seen order.
    """
    return list(dict.fromkeys(name for pair in PAIRS for name in pair))


def series_by_scope(named: pd.DataFrame) -> pd.DataFrame:
    """Build the per-period share of every paired technology, for each scope.

    Args:
        named: Tech-naming postings from :func:`technologies.naming_postings`.

    Returns:
        Columns ``scope``, ``tech``, ``period``, ``period_date``, ``n``, ``hits``, ``share``.
    """
    rows = []
    for scope, source in SCOPES.items():
        base = None if source is None else named.source == source
        for tech in pair_names():
            flag = a.has_any(named, "techs", [tech])
            trend = a.trend_frame(named, flag, base, min_n=MIN_SCOPE_POSTINGS)
            rows.append(trend.assign(scope=scope, tech=tech))
    return pd.concat(rows, ignore_index=True)


def lasting_crossover(
    gap: pd.DataFrame, margin: float = LEAD_MARGIN
) -> tuple[str, str, pd.Timestamp | None]:
    """Find the period after which the first technology stays ahead of the second.

    Args:
        gap: Columns ``period``, ``period_date`` and ``gap`` (first minus second, in points),
            ordered in time.
        margin: Points the first technology must lead by to count as ahead.

    Returns:
        ``(status, period, date)``. Status is ``"crosses"``, ``"always ahead"``, ``"never
        ahead"`` or ``"no data"``; period and date are set only for ``"crosses"``.
    """
    if gap.empty:
        return "no data", "", None
    if (gap.gap > margin).all():
        return "always ahead", "", None
    if gap.gap.iloc[-1] <= margin:
        return "never ahead", "", None
    last_behind = gap[gap.gap <= margin].period_date.max()
    first_ahead = gap[gap.period_date > last_behind].iloc[0]
    return "crosses", str(first_ahead.period), first_ahead.period_date


def gap_frame(series: pd.DataFrame, scope: str, first: str, second: str) -> pd.DataFrame:
    """Subtract two technologies' shares period by period inside one scope.

    Args:
        series: Output of :func:`series_by_scope`.
        scope: One of ``SCOPES``.
        first: The technology expected to overtake.
        second: The technology it is compared with.

    Returns:
        Columns ``period``, ``period_date``, ``gap``; only periods where both exist.
    """
    in_scope = series[series.scope == scope]
    left = in_scope[in_scope.tech == first].set_index(["period", "period_date"]).share
    right = in_scope[in_scope.tech == second].set_index(["period", "period_date"]).share
    gap = (left - right).dropna().rename("gap").reset_index()
    return gap.sort_values("period_date").reset_index(drop=True)


def crossover_table(series: pd.DataFrame) -> pd.DataFrame:
    """Report the lasting crossover of every pair inside every scope.

    Args:
        series: Output of :func:`series_by_scope`.

    Returns:
        Columns ``pair``, ``scope``, ``status``, ``period``.
    """
    rows = []
    for first, second in PAIRS:
        for scope in SCOPES:
            status, period, _ = lasting_crossover(gap_frame(series, scope, first, second))
            rows.append(
                {"pair": f"{first} > {second}", "scope": scope, "status": status, "period": period}
            )
    return pd.DataFrame(rows)


def agreement_table(series: pd.DataFrame) -> pd.DataFrame:
    """Say which crossovers hold in both control sources, within two quarters of each other.

    Args:
        series: Output of :func:`series_by_scope`.

    Returns:
        Columns ``pair``, ``linkedin``, ``monster_asia``, ``all_sources`` (each a period or a
        status) and ``holds_in_both_controls``.
    """
    rows = []
    for first, second in PAIRS:
        found = {s: lasting_crossover(gap_frame(series, s, first, second)) for s in SCOPES}
        dates = [found[s][2] for s in CONTROLS]
        holds = all(d is not None for d in dates) and abs(dates[0] - dates[1]) <= AGREE_WITHIN
        rows.append(
            {
                "pair": f"{first} > {second}",
                "linkedin": found["LinkedIn"][1] or found["LinkedIn"][0],
                "monster_asia": found["Monster Asia"][1] or found["Monster Asia"][0],
                "all_sources": found["All sources"][1] or found["All sources"][0],
                "holds_in_both_controls": holds,
            }
        )
    return pd.DataFrame(rows)


def chart_pairs(series: pd.DataFrame) -> Figure:
    """Draw each pair as two lines per scope, so a crossover can be read by eye.

    Args:
        series: Output of :func:`series_by_scope`.

    Returns:
        A grid with one row per pair and one column per scope.
    """
    fig, axes = plt.subplots(
        len(PAIRS), len(SCOPES), figsize=(14, 2.3 * len(PAIRS)), sharex=True, sharey="row"
    )
    for row, (first, second) in enumerate(PAIRS):
        for col, scope in enumerate(SCOPES):
            ax = axes[row][col]
            for tech, colour in ((first, a.PALETTE["data"]), (second, a.PALETTE["tension"])):
                line = series[(series.scope == scope) & (series.tech == tech)]
                ax.plot(line.period_date, line.share, color=colour, label=tech)
            if row == 0:
                ax.set_title(scope)
            if col == 0:
                ax.set_ylabel("% of postings")
                ax.legend(loc="upper left", fontsize=8)
            a.style_time_axis(ax, start=2021)
    fig.tight_layout()
    return fig
