"""Queries and charts for notebook 04, seniority and the junior share.

The feed only says a posting's level in a usable way from 2025: before that most career-level
labels are generic ("Nhân viên", staff). So the trends here start in January 2025, and the level
of a posting comes from its title first, then the board's label, then the required experience
(``level_from`` in the features). Postings whose level cannot be read stay ``unknown`` and are
left out of every share, with the size of that group shown.
"""

from __future__ import annotations

import pandas as pd
from matplotlib.figure import Figure

import analysis as a

FROM_MONTH = "2025-01"
LEVEL_ORDER = ["intern", "junior", "mid", "mid_senior", "senior", "lead", "manager"]
ENTRY = ["intern", "junior"]
SCOPES = {"All sources": None, "CareerBuilder": "careerbuilder_vn", "LinkedIn": "linkedin_vn"}
MIN_ROLE_POSTINGS = 150
MIN_SOURCE_POSTINGS = 500
LONG_EXPERIENCE_MONTHS = 60


def recent_known(frame: pd.DataFrame) -> pd.DataFrame:
    """Keep postings from 2025 on whose level could be read.

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        The filtered rows.
    """
    return frame[(frame.month >= FROM_MONTH) & (frame.level != "unknown")]


def level_coverage(frame: pd.DataFrame) -> pd.DataFrame:
    """Show, per year, how many postings have a readable level and which signal gave it.

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        Columns ``year``, ``postings``, ``pct_known`` and the share decided by each signal.
    """
    grouped = frame.groupby("year")
    table = pd.DataFrame({"postings": grouped.size()})
    table["pct_known"] = (100 * grouped["level"].agg(lambda s: (s != "unknown").mean())).round(1)
    for signal in ("title", "label", "experience"):
        table[f"pct_from_{signal}"] = (
            100 * grouped["level_from"].agg(lambda s, k=signal: (s == k).mean())
        ).round(1)
    return table.reset_index()


def level_mix_by_source(frame: pd.DataFrame) -> pd.DataFrame:
    """Level mix of the 2025-on postings, per large source.

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        Columns ``source``, ``postings``, ``pct_known``, ``junior_of_known`` and
        ``senior_plus_of_known`` (senior, lead and manager), for sources above the size limit.
    """
    recent = frame[frame.month >= FROM_MONTH]
    rows = []
    for name, part in recent.groupby("source_name"):
        if len(part) < MIN_SOURCE_POSTINGS:
            continue
        known = part[part.level != "unknown"]
        rows.append(
            {
                "source": name,
                "postings": len(part),
                "pct_known": round(100 * len(known) / len(part), 1),
                "junior_of_known": round(100 * known.level.isin(ENTRY).mean(), 1),
                "senior_plus_of_known": round(
                    100 * known.level.isin(["senior", "lead", "manager"]).mean(), 1
                ),
            }
        )
    return pd.DataFrame(rows).sort_values("postings", ascending=False).reset_index(drop=True)


def junior_series(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Quarterly entry-level share of postings with a known level, per scope.

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        Scope label to trend frame (``share`` is the % of known-level postings).
    """
    recent = frame[frame.month >= FROM_MONTH]
    known = recent.level != "unknown"
    entry = recent.level.isin(ENTRY)
    out = {}
    for label, source in SCOPES.items():
        base = known if source is None else known & (recent.source == source)
        out[label] = a.trend_frame(recent, entry, base)
    return out


def chart_level_mix(frame: pd.DataFrame, source: str | None, title: str) -> Figure:
    """Stack the level mix of known-level postings by quarter, from 2025.

    Args:
        frame: Output of :func:`analysis.load_features`.
        source: A source id, or ``None`` for all sources.
        title: Chart title.

    Returns:
        The figure.
    """
    known = recent_known(frame)
    scoped = known if source is None else known[known.source == source]
    return a.stacked_share(scoped, "level", LEVEL_ORDER, title, start=2025)


def entry_by_role(frame: pd.DataFrame) -> pd.DataFrame:
    """Entry-level and senior-plus shares of known-level postings, per role.

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        Columns ``role``, ``postings``, ``entry`` and ``senior_plus`` (%), largest roles only.
    """
    known = recent_known(frame)
    rows = []
    for role, part in known.groupby("role"):
        if len(part) < MIN_ROLE_POSTINGS:
            continue
        rows.append(
            {
                "role": role,
                "postings": len(part),
                "entry": round(100 * part.level.isin(ENTRY).mean(), 1),
                "senior_plus": round(
                    100 * part.level.isin(["senior", "lead", "manager"]).mean(), 1
                ),
            }
        )
    return pd.DataFrame(rows).sort_values("entry", ascending=False).reset_index(drop=True)


def experience_by_role(frame: pd.DataFrame) -> pd.DataFrame:
    """Required experience, per role, for postings that state it (2025 on).

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        Columns ``role``, ``postings``, ``median_years`` and ``pct_5_years_plus``.
    """
    stated = frame[(frame.month >= FROM_MONTH) & frame.exp_months.notna()]
    rows = []
    for role, part in stated.groupby("role"):
        if len(part) < MIN_ROLE_POSTINGS:
            continue
        rows.append(
            {
                "role": role,
                "postings": len(part),
                "median_years": round(part.exp_months.median() / 12, 1),
                "pct_5_years_plus": round(
                    100 * (part.exp_months >= LONG_EXPERIENCE_MONTHS).mean(), 1
                ),
            }
        )
    return pd.DataFrame(rows).sort_values("median_years").reset_index(drop=True)
