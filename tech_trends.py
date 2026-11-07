"""Queries and charts for notebook 02, technology trends.

A posting "names" a technology when the dictionary in ``taxonomy.py`` finds it in the title or
description. Descriptions differ a lot between sources and years, so every share here is taken
over the postings that name at least one technology, and a CareerBuilder-only line is drawn
beside the all-source line to separate the market from the source mix.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure

import analysis as a
import taxonomy as tx

TOP_N = 25
PANELS = 16
# Sources whose description length stays steady, so a change in what they name is not a change
# in how much they write. CareerBuilder doubled its description length in 2025, so it is not one.
CONTROLS = {"Monster Asia": "monsterasia_vn", "LinkedIn": "linkedin_vn"}
VERBOSITY_SOURCES = {
    "CareerBuilder": "careerbuilder_vn",
    "Monster Asia": "monsterasia_vn",
    "LinkedIn": "linkedin_vn",
    "Jora": "jora_vn",
}
LATE_FROM = "2025-01"
MIN_SHIFT_POSTINGS = 200  # skip a window with fewer tech-naming postings than this


def naming_postings(frame: pd.DataFrame) -> pd.DataFrame:
    """Keep postings that have a description and name at least one technology.

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        The filtered rows.
    """
    return frame[frame.has_text & (frame.techs.map(len) > 0)]


def technology_counts(frame: pd.DataFrame) -> pd.DataFrame:
    """Count how many postings name each technology.

    Args:
        frame: Tech-naming postings from :func:`naming_postings`.

    Returns:
        Columns ``tech``, ``category``, ``postings`` and ``share`` (% of the frame), largest first.
    """
    counts = frame.techs.explode().value_counts().rename_axis("tech").reset_index(name="postings")
    counts["category"] = counts.tech.map(tx.TECH_CATEGORY)
    counts["share"] = (100 * counts.postings / len(frame)).round(1)
    return counts


def tech_series(frame: pd.DataFrame, names: list[str], base: pd.Series | None = None) -> dict:
    """Build the per-period share series for several technologies.

    Args:
        frame: Tech-naming postings.
        names: Technologies to follow.
        base: Optional mask choosing the postings that count (for example one source).

    Returns:
        Technology name to trend frame (see :func:`analysis.trend_frame`).
    """
    return {name: a.trend_frame(frame, a.has_any(frame, "techs", [name]), base) for name in names}


def category_series(frame: pd.DataFrame, categories: list[str]) -> dict:
    """Build the per-period share of postings naming any technology of a category.

    Args:
        frame: Tech-naming postings.
        categories: Category names from ``taxonomy.TECH_CATEGORY``.

    Returns:
        Category to trend frame.
    """
    members = {c: [n for n, cat in tx.TECH_CATEGORY.items() if cat == c] for c in categories}
    return {
        c: a.trend_frame(frame, a.has_any(frame, "techs", names)) for c, names in members.items()
    }


def window_share(frame: pd.DataFrame, name: str, mask: pd.Series) -> float:
    """Share of postings in a window that name a technology.

    Args:
        frame: Tech-naming postings.
        name: The technology.
        mask: Boolean series selecting the window.

    Returns:
        Percentage, or NaN when the window is too small.
    """
    window = frame[mask]
    if len(window) < MIN_SHIFT_POSTINGS:
        return float("nan")
    return round(100 * a.has_any(window, "techs", [name]).mean(), 1)


def shift_table(
    frame: pd.DataFrame,
    names: list[str],
    early: tuple[str, str],
    source: str | None = None,
) -> pd.DataFrame:
    """Compare each technology's share in an early window with January 2025 onward.

    Args:
        frame: Tech-naming postings.
        names: Technologies to compare.
        early: First and last month (``YYYY-MM``) of the early window.
        source: Restrict to one source id, or ``None`` for every source.

    Returns:
        Columns ``tech``, ``early``, ``late``, ``change`` (points), ordered by change.
    """
    scope = frame if source is None else frame[frame.source == source]
    early_mask = (scope.month >= early[0]) & (scope.month <= early[1])
    late_mask = scope.month >= LATE_FROM
    rows = [
        {
            "tech": n,
            "early": window_share(scope, n, early_mask),
            "late": window_share(scope, n, late_mask),
        }
        for n in names
    ]
    table = pd.DataFrame(rows)
    table["change"] = (table.late - table.early).round(1)
    return table.sort_values("change", ascending=False).reset_index(drop=True)


def verbosity_series(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Average number of technologies named per tech-naming posting, per period and source.

    Args:
        frame: Tech-naming postings.

    Returns:
        Source label to a frame with ``period_date`` and ``mean_techs``.
    """
    prepared = frame.assign(count=frame.techs.map(len))
    series = {}
    for label, source in {"All sources": None, **VERBOSITY_SOURCES}.items():
        scope = prepared if source is None else prepared[prepared.source == source]
        grouped = scope.groupby("period_date").agg(
            n=("count", "size"), mean_techs=("count", "mean")
        )
        grouped = grouped[
            (grouped.n >= a.MIN_PERIOD_POSTINGS) & (grouped.index <= a.period_date_limit())
        ]
        series[label] = grouped.reset_index().assign(mean_techs=lambda g: g.mean_techs.round(2))
    return series


def tag_agreement(frame: pd.DataFrame) -> pd.DataFrame:
    """Compare dictionary matches in the text with the board's own SKILLS tags, per year.

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        Columns ``year``, ``postings`` (with skill tags and a description), ``tag_mentions``,
        ``found_in_text`` (% of tag technologies the text matching also found) and
        ``text_in_tags`` (% of text technologies that the tags also list).
    """
    tagged = frame[frame.has_skill_tags & frame.has_text]
    rows = []
    for year, part in tagged.groupby("year"):
        tag_total = int(part.tag_techs.map(len).sum())
        text_total = int(part.techs.map(len).sum())
        both = int(
            sum(len(set(t) & set(x)) for t, x in zip(part.tag_techs, part.techs, strict=True))
        )
        rows.append(
            {
                "year": year,
                "postings": len(part),
                "tag_mentions": tag_total,
                "found_in_text": round(100 * both / tag_total, 1) if tag_total else float("nan"),
                "text_in_tags": round(100 * both / text_total, 1) if text_total else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def chart_source_check(frame: pd.DataFrame, names: list[str]) -> Figure:
    """Draw the same technologies for all sources and for the two control sources.

    Args:
        frame: Tech-naming postings.
        names: Technologies to draw (a handful).

    Returns:
        The figure with one panel per scope, sharing a y axis.
    """
    scopes = [("All sources", None)] + [
        (label, frame.source == source) for label, source in CONTROLS.items()
    ]
    fig, axes = plt.subplots(1, len(scopes), figsize=(15, 4.6), sharey=True)
    for ax, (label, base) in zip(axes, scopes, strict=True):
        for name, part in tech_series(frame, names, base).items():
            ax.plot(part.period_date, part.share, marker="o", markersize=3, label=name)
        a.style_time_axis(ax)
        ax.set_title(label)
    axes[0].set_ylabel("Share of tech-naming postings (%)")
    axes[0].legend(ncol=2, fontsize=9)
    return fig


def coverage_by_year(frame: pd.DataFrame) -> pd.DataFrame:
    """Show how often a description exists and names a technology, per year.

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        Columns ``year``, ``postings``, ``pct_with_description``, ``pct_naming_a_technology``.
    """
    grouped = frame.groupby("year")
    return pd.DataFrame(
        {
            "postings": grouped.size(),
            "pct_with_description": (100 * grouped.has_text.mean()).round(1),
            "pct_naming_a_technology": (
                100 * grouped.techs.agg(lambda s: (s.map(len) > 0).mean())
            ).round(1),
        }
    ).reset_index()
