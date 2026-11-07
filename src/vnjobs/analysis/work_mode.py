"""Queries and charts for notebook 07, work mode (remote, hybrid, on-site).

Only some postings state a work mode (about a quarter by 2026) and which ones do depends on the
source, so every share here is of *postings that state one*, and the coverage is shown first.
Trends start in 2025, when the field becomes usable.
"""

from __future__ import annotations

import pandas as pd

from vnjobs.analysis import core as a

FROM_MONTH = "2025-01"
MODES = ["remote", "hybrid", "onsite"]
FLEXIBLE = ["remote", "hybrid"]
SCOPES = {
    "All sources": None,
    "LinkedIn": "linkedin_vn",
    "CareerViet": "careerviet_vn",
    "SmartRecruiters": "smartrecruiters_vn",
}
MIN_POSTINGS = 100


def coverage_by_source(frame: pd.DataFrame) -> pd.DataFrame:
    """Share of 2025-on postings that state a work mode, per source.

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        Columns ``source``, ``postings``, ``pct_state_mode``, ``remote_or_hybrid_of_stated``.
    """
    recent = frame[frame.month >= FROM_MONTH]
    rows = []
    for name, part in recent.groupby("source_name"):
        stated = part[part.work_mode.notna()]
        if len(part) < a.MIN_PERIOD_POSTINGS or len(stated) < MIN_POSTINGS:
            continue
        rows.append(
            {
                "source": name,
                "postings": len(part),
                "pct_state_mode": round(100 * len(stated) / len(part), 1),
                "remote_or_hybrid_of_stated": round(
                    100 * stated.work_mode.isin(FLEXIBLE).mean(), 1
                ),
            }
        )
    return pd.DataFrame(rows).sort_values("postings", ascending=False).reset_index(drop=True)


def mode_series(frame: pd.DataFrame, mode: str) -> dict[str, pd.DataFrame]:
    """Quarterly share of one mode among postings that state a mode, per scope.

    Args:
        frame: Output of :func:`analysis.load_features`.
        mode: ``remote``, ``hybrid`` or ``onsite``.

    Returns:
        Scope label to trend frame. Small periods are hidden (``MIN_POSTINGS`` stated).
    """
    recent = frame[frame.month >= FROM_MONTH]
    stated = recent.work_mode.notna()
    flag = recent.work_mode == mode
    out = {}
    for label, source in SCOPES.items():
        base = stated if source is None else stated & (recent.source == source)
        out[label] = a.trend_frame(recent, flag, base, MIN_POSTINGS)
    return out


def by_group(frame: pd.DataFrame, column: str, minimum: int = MIN_POSTINGS) -> pd.DataFrame:
    """Remote-or-hybrid share of stated modes, per value of a column (role, city ...).

    Args:
        frame: Output of :func:`analysis.load_features`.
        column: Column to group by, such as ``role`` or ``city_group``.
        minimum: Smallest number of stated postings to report a group.

    Returns:
        Columns ``group``, ``stated``, ``remote``, ``hybrid``, ``onsite`` (% of stated).
    """
    stated = frame[(frame.month >= FROM_MONTH) & frame.work_mode.notna()]
    rows = []
    for name, part in stated.groupby(column):
        if len(part) < minimum:
            continue
        row = {"group": name, "stated": len(part)}
        row.update({mode: round(100 * (part.work_mode == mode).mean(), 1) for mode in MODES})
        rows.append(row)
    return pd.DataFrame(rows).sort_values("remote", ascending=False).reset_index(drop=True)
