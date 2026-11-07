"""Queries and charts for notebook 14, benefits and perks (CareerBuilder only).

Benefit tags exist for about 90 % of 2021-22 postings but only 15-20 % after that, and which
boards fill them changes by year, so a cross-source trend would mostly show who fills the tag.
This notebook therefore stays inside CareerBuilder, shows the coverage first, and takes every
share over the CareerBuilder postings that carry benefit tags.
"""

from __future__ import annotations

import pandas as pd

from vnjobs import taxonomy as tx
from vnjobs.analysis import core as a

SOURCE = "careerbuilder_vn"
BENEFITS = list(tx.BENEFIT_WORDS)
SHOWN = ["insurance", "training", "bonus", "salary_review", "health_care", "laptop", "travel"]
MIN_TAGGED = 300


def careerbuilder(frame: pd.DataFrame) -> pd.DataFrame:
    """Keep the CareerBuilder postings.

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        The CareerBuilder rows.
    """
    return frame[frame.source == SOURCE]


def coverage_by_year(frame: pd.DataFrame) -> pd.DataFrame:
    """Share of CareerBuilder postings that carry benefit tags, per year.

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        Columns ``year``, ``postings``, ``with_benefit_tags``, ``pct_with_benefit_tags``.
    """
    rows = []
    for year, part in careerbuilder(frame).groupby("year"):
        tagged = int((part.benefits.map(len) > 0).sum())
        rows.append(
            {
                "year": year,
                "postings": len(part),
                "with_benefit_tags": tagged,
                "pct_with_benefit_tags": round(100 * tagged / len(part), 1),
            }
        )
    return pd.DataFrame(rows)


def benefit_series(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Share of tagged CareerBuilder postings offering each benefit, per period.

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        Benefit name to trend frame.
    """
    scope = careerbuilder(frame)
    tagged = scope.benefits.map(len) > 0
    return {
        name: a.trend_frame(scope, a.has_any(scope, "benefits", [name]), tagged, MIN_TAGGED)
        for name in SHOWN
    }


def by_year_table(frame: pd.DataFrame) -> pd.DataFrame:
    """Share offering each benefit per year, among tagged CareerBuilder postings.

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        Columns ``year``, ``tagged`` and one column per benefit (%), for years with enough postings.
    """
    rows = []
    for year, part in careerbuilder(frame).groupby("year"):
        tagged = part[part.benefits.map(len) > 0]
        if len(tagged) < MIN_TAGGED:
            continue
        row = {"year": year, "tagged": len(tagged)}
        row.update({b: round(100 * a.has_any(tagged, "benefits", [b]).mean(), 1) for b in BENEFITS})
        rows.append(row)
    return pd.DataFrame(rows)
