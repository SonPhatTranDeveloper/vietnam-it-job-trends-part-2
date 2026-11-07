"""Queries and charts for notebook 09, data and AI/ML jobs.

"Data / AI jobs" are the postings whose final role (see ``03-roles``) is ``data`` or ``ai_ml``.
Inside them a second, title-only split separates data engineers, analysts, scientists, ML
engineers and so on. Titles do not depend on how long a source writes, but sources still
differ in role mix, so trends are drawn for all sources, CareerBuilder and LinkedIn.
"""

from __future__ import annotations

import re

import pandas as pd

from vnjobs import taxonomy as tx
from vnjobs.analysis import core as a

DATA_AI_ROLES = ["data", "ai_ml"]
GROUPS = {"Data": ["data"], "AI / ML": ["ai_ml"]}
SCOPES = {"All sources": None, "CareerBuilder": "careerbuilder_vn", "LinkedIn": "linkedin_vn"}
FROM_MONTH = "2025-01"
SALARY_MIN_POSTINGS = 100
EMPLOYERS = 15
CATEGORIES = ["language", "cloud", "database", "data", "ai", "llm"]
LONG_EXPERIENCE_MONTHS = 60

# Ordered: the first pattern that matches the lower-cased title wins.
SUBROLE_RULES = (
    ("ML engineer", r"(machine learning|\bml\b|mlops|deep learning|computer vision|\bnlp\b)"),
    (
        "AI engineer",
        r"(\bai\b|artificial intelligence|\bllm\b|generative|prompt|trí tuệ nhân tạo|agent)",
    ),
    ("Data scientist", r"(data scientist|nhà khoa học dữ liệu|research scientist)"),
    (
        "Data engineer",
        r"(data engineer|big data|etl|data platform|data architect|data warehouse|kỹ sư dữ liệu)",
    ),
    ("BI / reporting", r"(\bbi\b|business intelligence|power bi|tableau|report)"),
    ("Data analyst", r"(data analy|analytics|phân tích dữ liệu|phân tích số liệu|\banalyst\b)"),
    ("Database admin", r"(\bdba\b|database admin|quản trị cơ sở dữ liệu|database)"),
)
SUBROLE_ORDER = [name for name, _ in SUBROLE_RULES] + ["Other data / AI"]
_SUBROLE_PATTERNS = tuple((name, re.compile(pattern)) for name, pattern in SUBROLE_RULES)


def subrole_of(title: str) -> str:
    """Split a data or AI title into a finer family.

    Args:
        title: The job title, in any case.

    Returns:
        The first matching family, or ``"Other data / AI"``.
    """
    lowered = title.lower()
    for name, pattern in _SUBROLE_PATTERNS:
        if pattern.search(lowered):
            return name
    return "Other data / AI"


def data_ai(frame: pd.DataFrame) -> pd.DataFrame:
    """Keep the data and AI/ML postings and add the ``subrole`` and ``group`` columns.

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        The data and AI/ML postings.
    """
    kept = frame[frame.role.isin(DATA_AI_ROLES)].copy()
    kept["subrole"] = kept.title.map(subrole_of)
    kept["group"] = kept.role.map({"data": "Data", "ai_ml": "AI / ML"})
    return kept


def share_series(frame: pd.DataFrame, roles: list[str]) -> dict[str, pd.DataFrame]:
    """Quarterly share of IT postings in some roles, for every scope.

    Args:
        frame: Output of :func:`analysis.load_features`.
        roles: Final roles to count.

    Returns:
        Scope label to trend frame.
    """
    flag = frame.role.isin(roles)
    return {
        label: a.trend_frame(frame, flag, None if source is None else frame.source == source)
        for label, source in SCOPES.items()
    }


def comparison(frame: pd.DataFrame) -> pd.DataFrame:
    """Compare data jobs, AI/ML jobs and all other IT jobs on seniority, experience and mode.

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        One row per group (Data, AI / ML, Other IT roles) with, for 2025 on: postings, the
        entry-level share of known-level postings, median required years and the share asking
        five years or more (postings that state it), remote and hybrid shares (postings that
        state a mode), the Hồ Chí Minh share, and the median monthly salary in million VND
        (blank under ``SALARY_MIN_POSTINGS`` salaries).
    """
    recent = frame[frame.month >= FROM_MONTH]
    groups = {
        "Data": recent[recent.role == "data"],
        "AI / ML": recent[recent.role == "ai_ml"],
        "Other IT roles": recent[~recent.role.isin(DATA_AI_ROLES)],
    }
    return pd.DataFrame([{"group": name, **_summary(part)} for name, part in groups.items()])


def _summary(part: pd.DataFrame) -> dict[str, float]:
    """Summarise one group of postings for :func:`comparison`.

    Args:
        part: Postings of one group from 2025 on.

    Returns:
        The metrics for one row of the comparison.
    """
    known = part[part.level != "unknown"]
    stated_exp = part[part.exp_months.notna()]
    stated_mode = part[part.work_mode.notna()]
    paid = part[part.salary_low.notna()]
    mid = (paid.salary_low + paid.salary_high) / 2 / 1e6
    return {
        "postings": len(part),
        "entry_pct": round(100 * known.level.isin(["intern", "junior"]).mean(), 1),
        "median_years": round(stated_exp.exp_months.median() / 12, 1),
        "pct_5_years_plus": round(
            100 * (stated_exp.exp_months >= LONG_EXPERIENCE_MONTHS).mean(), 1
        ),
        "remote_pct": round(100 * (stated_mode.work_mode == "remote").mean(), 1),
        "hybrid_pct": round(100 * (stated_mode.work_mode == "hybrid").mean(), 1),
        "hcm_pct": round(100 * (part.city_group == "Hồ Chí Minh").mean(), 1),
        "median_salary_m": round(mid.median(), 1)
        if len(paid) >= SALARY_MIN_POSTINGS
        else float("nan"),
        "salaries": len(paid),
    }


def category_demand(frame: pd.DataFrame) -> pd.DataFrame:
    """Share of tech-naming postings that name any tool of each category, per group (2025 on).

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        Columns ``group`` and one column per category (%).
    """
    recent = frame[(frame.month >= FROM_MONTH) & frame.has_text & (frame.techs.map(len) > 0)]
    groups = {
        "Data": recent[recent.role == "data"],
        "AI / ML": recent[recent.role == "ai_ml"],
        "Other IT roles": recent[~recent.role.isin(DATA_AI_ROLES)],
    }
    rows = []
    for name, part in groups.items():
        row = {"group": name}
        for category in CATEGORIES:
            members = [n for n, c in tx.TECH_CATEGORY.items() if c == category]
            row[category] = round(100 * a.has_any(part, "techs", members).mean(), 1)
        rows.append(row)
    return pd.DataFrame(rows)


def top_employers(frame: pd.DataFrame) -> pd.DataFrame:
    """Employers with the most data and AI/ML postings from 2025 on, groups combined.

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        Columns ``company``, ``data``, ``ai_ml`` and ``total`` postings.
    """
    recent = frame[(frame.month >= FROM_MONTH) & frame.role.isin(DATA_AI_ROLES)]
    named = recent[recent.company_key.notna()]
    employer = named.company_group.fillna(named.company_key.str.title())
    table = pd.crosstab(employer, named.role).reindex(columns=DATA_AI_ROLES, fill_value=0)
    table["total"] = table.sum(axis=1)
    top = table.sort_values("total", ascending=False).head(EMPLOYERS)
    return top.rename_axis("company").reset_index()
