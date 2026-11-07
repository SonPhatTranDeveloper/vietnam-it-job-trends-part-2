"""Queries and charts for notebook 12, which industries hire IT staff.

The feed's industry tags differ by board: CareerBuilder uses Vietnamese tags, LinkedIn and
CareerViet use English ones, and the tag sets do not match. ``taxonomy.sectors_of`` groups them
into about ten sectors by keyword, and a posting can belong to more than one. Because the
taxonomies differ, two windows are shown separately and never joined into one trend: 2021-22
(CareerBuilder) and 2025-26 (LinkedIn, CareerViet and others).
"""

from __future__ import annotations

import pandas as pd

from vnjobs.analysis import core as a

WINDOWS = {"2021-22": ("2021-01", "2022-12"), "2025-26": ("2025-01", "2026-10")}
MIN_ROLE_POSTINGS = 200
TOP_ROLES = ["backend", "fullstack", "data", "ai_ml", "devops_cloud", "qa_test", "security"]


def tagged(frame: pd.DataFrame, window: tuple[str, str]) -> pd.DataFrame:
    """Postings in a window that have industry tags.

    Args:
        frame: Output of :func:`analysis.load_features`.
        window: First and last month, ``YYYY-MM``.

    Returns:
        The postings with a non-empty ``sectors`` list.
    """
    inside = frame[(frame.month >= window[0]) & (frame.month <= window[1])]
    return inside[inside.sectors.map(len) > 0]


def coverage(frame: pd.DataFrame) -> pd.DataFrame:
    """Share of postings with industry tags, per window and source.

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        Columns ``window``, ``source``, ``postings``, ``pct_with_industry``.
    """
    rows = []
    for label, (first, last) in WINDOWS.items():
        inside = frame[(frame.month >= first) & (frame.month <= last)]
        for name, part in inside.groupby("source_name"):
            if len(part) < a.MIN_PERIOD_POSTINGS:
                continue
            share = round(100 * (part.sectors.map(len) > 0).mean(), 1)
            rows.append(
                {"window": label, "source": name, "postings": len(part), "pct_with_industry": share}
            )
    return pd.DataFrame(rows)


def sector_shares(
    frame: pd.DataFrame, window: tuple[str, str], source: str | None = None
) -> pd.DataFrame:
    """Share of tagged postings in each sector for a window.

    Args:
        frame: Output of :func:`analysis.load_features`.
        window: First and last month, ``YYYY-MM``.
        source: A source id, or ``None`` for every source.

    Returns:
        Columns ``sector``, ``postings``, ``share`` (% of tagged postings; shares add to more
        than 100 because a posting can have several sectors), largest first.
    """
    part = tagged(frame, window)
    part = part if source is None else part[part.source == source]
    counts = (
        part.sectors.explode().value_counts().rename_axis("sector").reset_index(name="postings")
    )
    counts["share"] = (100 * counts.postings / len(part)).round(1)
    return counts


def sector_by_role(frame: pd.DataFrame) -> pd.DataFrame:
    """For 2025-26, the share of each role's tagged postings that sit in each sector.

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        One row per role in ``TOP_ROLES`` (index ``role``) and one column per sector (%).
    """
    part = tagged(frame, WINDOWS["2025-26"])
    sectors = sorted(part.sectors.explode().dropna().unique())
    rows = []
    for role in TOP_ROLES:
        group = part[part.role == role]
        if len(group) < MIN_ROLE_POSTINGS:
            continue
        row = {"role": role, "postings": len(group)}
        row.update(
            {s: round(100 * group.sectors.map(lambda x, s=s: s in x).mean(), 1) for s in sectors}
        )
        rows.append(row)
    return pd.DataFrame(rows)


def entry_by_sector(frame: pd.DataFrame) -> pd.DataFrame:
    """For 2025-26, entry-level share of known-level postings per sector.

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        Columns ``sector``, ``known_level_postings``, ``entry`` (%).
    """
    part = tagged(frame, WINDOWS["2025-26"])
    part = part[part.level != "unknown"].explode("sectors")
    grouped = part.groupby("sectors")["level"].agg(
        known_level_postings="size",
        entry=lambda s: round(100 * s.isin(["intern", "junior"]).mean(), 1),
    )
    big = grouped[grouped.known_level_postings >= MIN_ROLE_POSTINGS]
    return big.sort_values("entry", ascending=False).rename_axis("sector").reset_index()
