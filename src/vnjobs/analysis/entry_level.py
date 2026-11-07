"""Queries and charts for notebook 11, the entry-level reality check.

Three questions about "junior" postings, from 2025 on (when levels and experience are usable):
how many ask for several years of experience, how many require a degree, and do they ask for as
many technologies as senior postings. To avoid circular logic, "entry" here counts only
postings whose level came from the title or the board's label, not from the experience figure
itself (that fallback labels anything up to a year as junior by construction).
"""

from __future__ import annotations

import pandas as pd

from vnjobs.analysis import core as a

FROM_MONTH = "2025-01"
ENTRY = ["intern", "junior"]
MIN_ROLE_POSTINGS = 100
YEAR_BUCKETS = [(0, 12, "up to 1 year"), (13, 24, "2 years"), (25, 36, "3 years")]
DEGREE_ORDER = ["high_school", "associate_or_certificate", "bachelor", "master"]
LEVEL_ORDER = ["intern", "junior", "mid", "mid_senior", "senior", "lead", "manager"]
CONTROL_SOURCE = "linkedin_vn"
TWO_YEARS = 24  # months
THREE_YEARS = 36
MANY_TECHNOLOGIES = 5
FIRST_DEGREE_YEAR = 2024


def entry_with_experience(frame: pd.DataFrame) -> pd.DataFrame:
    """Entry-level postings (title or label) that state a required experience, 2025 on.

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        The matching rows.
    """
    recent = frame[(frame.month >= FROM_MONTH) & frame.level.isin(ENTRY)]
    labelled = recent[recent.level_from.isin(["title", "label"])]
    return labelled[labelled.exp_months.notna()]


def experience_buckets(entry: pd.DataFrame) -> pd.DataFrame:
    """Distribution of required experience among entry-level postings.

    Args:
        entry: Output of :func:`entry_with_experience`.

    Returns:
        Columns ``required``, ``postings``, ``share`` (%).
    """
    rows = []
    for low, high, label in YEAR_BUCKETS:
        rows.append({"required": label, "postings": int(entry.exp_months.between(low, high).sum())})
    rows.append(
        {"required": "4 years or more", "postings": int((entry.exp_months > THREE_YEARS).sum())}
    )
    table = pd.DataFrame(rows)
    table["share"] = (100 * table.postings / len(entry)).round(1)
    return table


def entry_by_role(entry: pd.DataFrame) -> pd.DataFrame:
    """Required experience of entry-level postings, per role.

    Args:
        entry: Output of :func:`entry_with_experience`.

    Returns:
        Columns ``role``, ``postings``, ``pct_2_years_plus``, ``pct_3_years_plus``,
        ``median_years``, for roles with enough postings.
    """
    rows = []
    for role, part in entry.groupby("role"):
        if len(part) < MIN_ROLE_POSTINGS:
            continue
        rows.append(
            {
                "role": role,
                "postings": len(part),
                "pct_2_years_plus": round(100 * (part.exp_months >= TWO_YEARS).mean(), 1),
                "pct_3_years_plus": round(100 * (part.exp_months >= THREE_YEARS).mean(), 1),
                "median_years": round(part.exp_months.median() / 12, 1),
            }
        )
    return (
        pd.DataFrame(rows).sort_values("pct_3_years_plus", ascending=False).reset_index(drop=True)
    )


def degree_by_level(frame: pd.DataFrame) -> pd.DataFrame:
    """Minimum degree by seniority level, among postings that state a degree (2025 on).

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        Columns ``level``, ``stated`` and the share of each minimum degree (%).
    """
    stated = frame[(frame.month >= FROM_MONTH) & frame.degree.notna() & (frame.level != "unknown")]
    rows = []
    for level in LEVEL_ORDER:
        part = stated[stated.level == level]
        if part.empty:
            continue
        row = {"level": level, "stated": len(part)}
        row.update({d: round(100 * (part.degree == d).mean(), 1) for d in DEGREE_ORDER})
        rows.append(row)
    return pd.DataFrame(rows)


def degree_coverage(frame: pd.DataFrame) -> pd.DataFrame:
    """Share of postings that state a degree, per year and source.

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        Columns ``year``, ``source``, ``postings``, ``pct_state_degree`` for 2024 on.
    """
    recent = frame[frame.year >= FIRST_DEGREE_YEAR]
    grouped = recent.groupby(["year", "source_name"]).degree.agg(
        postings="size", pct_state_degree=lambda s: round(100 * s.notna().mean(), 1)
    )
    big = grouped[grouped.postings >= a.MIN_PERIOD_POSTINGS]
    return big.reset_index().rename(columns={"source_name": "source"})


def technologies_by_level(frame: pd.DataFrame) -> pd.DataFrame:
    """Average technologies named per posting by level, inside LinkedIn, 2025 on.

    LinkedIn's descriptions keep the same length across the period, so the comparison between
    levels is not a description-length effect.

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        Columns ``level``, ``postings``, ``mean_technologies``, ``pct_naming_5_plus``.
    """
    scope = frame[
        (frame.month >= FROM_MONTH)
        & (frame.source == CONTROL_SOURCE)
        & frame.has_text
        & (frame.level != "unknown")
    ]
    counts = scope.techs.map(len)
    rows = []
    for level in LEVEL_ORDER:
        part = counts[scope.level == level]
        if part.empty:
            continue
        rows.append(
            {
                "level": level,
                "postings": len(part),
                "mean_technologies": round(part.mean(), 1),
                "pct_naming_5_plus": round(100 * (part >= MANY_TECHNOLOGIES).mean(), 1),
            }
        )
    return pd.DataFrame(rows)
