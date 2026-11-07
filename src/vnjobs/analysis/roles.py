"""Queries and charts for notebook 03, roles.

A role comes from the job *title* only, so unlike technologies it does not depend on how long
a source writes its descriptions. What does change is which sources are scraped, so each role
trend is drawn for all sources and again inside two large sources (CareerBuilder from 2020,
LinkedIn from 2023). The role is Jev's label when it is confident and the rule-based label
otherwise (see ``analysis.add_jev_roles``).
"""

from __future__ import annotations

import re

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure

from vnjobs.analysis import core as a

ROLE_ORDER = [
    "backend",
    "frontend",
    "fullstack",
    "mobile",
    "software_other",
    "devops_cloud",
    "data",
    "ai_ml",
    "qa_test",
    "security",
    "it_support_infra",
    "embedded_iot",
    "game",
    "erp_consulting",
    "ba_pm_product",
    "design",
    "technical_non_software",
    "not_it",
    "other",
]
NOT_SOFTWARE = ["technical_non_software", "not_it"]
# Bands for the stacked chart: 19 roles are too many colours to read.
GROUPS = {
    "backend": "Backend",
    "frontend": "Web & mobile dev",
    "fullstack": "Web & mobile dev",
    "mobile": "Web & mobile dev",
    "software_other": "Software (unspecified)",
    "devops_cloud": "DevOps / cloud",
    "data": "Data",
    "ai_ml": "AI / ML",
    "qa_test": "QA / test",
    "it_support_infra": "IT support / infra",
    "security": "Security",
    "technical_non_software": "Not software / not IT",
    "not_it": "Not software / not IT",
}
GROUP_ORDER = [
    "Backend",
    "Web & mobile dev",
    "Software (unspecified)",
    "DevOps / cloud",
    "Data",
    "AI / ML",
    "QA / test",
    "Security",
    "IT support / infra",
    "Other roles",
    "Not software / not IT",
]
SCOPES = {"All sources": None, "CareerBuilder": "careerbuilder_vn", "LinkedIn": "linkedin_vn"}
TITLES_PER_ROLE = 5
TESTING_WORDS = r"test|tester|kiểm thử|software|phần mềm|automation|sdet|selenium|\bqa\b"
QUALITY_CONTROL_WORDS = (
    r"chất lượng|quality control|\bqc\b|iqc|oqc|ipqc|lab|sản xuất|production|kiểm nghiệm"
)
MIN_AGREEMENT_POSTINGS = 50
MIN_JOB_LENGTH = 4


def scope_mask(frame: pd.DataFrame, source: str | None) -> pd.Series | None:
    """Build the posting mask for one source scope.

    Args:
        frame: Output of :func:`analysis.load_features`.
        source: A source id, or ``None`` for every source.

    Returns:
        A boolean series, or ``None`` for all sources.
    """
    return None if source is None else frame.source == source


def with_groups(frame: pd.DataFrame) -> pd.DataFrame:
    """Add the ``role_group`` column used by the stacked chart.

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        The frame with ``role_group`` (rare roles fall into "Other roles").
    """
    return frame.assign(role_group=frame.role.map(GROUPS).fillna("Other roles"))


def role_counts(frame: pd.DataFrame) -> pd.DataFrame:
    """Count postings per final role.

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        Columns ``role``, ``postings``, ``share`` (%), in ``ROLE_ORDER``.
    """
    counts = frame.role.value_counts().rename_axis("role").reset_index(name="postings")
    counts["share"] = (100 * counts.postings / len(frame)).round(1)
    counts["order"] = counts.role.map({r: i for i, r in enumerate(ROLE_ORDER)})
    return counts.sort_values("order").drop(columns="order").reset_index(drop=True)


def role_series(frame: pd.DataFrame, role: str) -> dict[str, pd.DataFrame]:
    """Build one role's share-of-postings trend for every scope.

    Args:
        frame: Output of :func:`analysis.load_features`.
        role: A role family.

    Returns:
        Scope label to trend frame.
    """
    flag = frame.role == role
    return {
        label: a.trend_frame(frame, flag, scope_mask(frame, source))
        for label, source in SCOPES.items()
    }


def chart_role_panels(frame: pd.DataFrame, roles: list[str]) -> Figure:
    """Draw several roles, one panel each, with a line per scope.

    Args:
        frame: Output of :func:`analysis.load_features`.
        roles: Roles to draw.

    Returns:
        The figure.
    """
    columns = 3
    rows = -(-len(roles) // columns)
    fig, axes = plt.subplots(rows, columns, figsize=(13, 3.1 * rows), sharex=True)
    for ax, role in zip(axes.flat, roles, strict=False):
        for label, part in role_series(frame, role).items():
            ax.plot(part.period_date, part.share, marker="o", markersize=3, label=label)
        ax.set_title(role)
        ax.set_xticks([pd.Timestamp(y, 1, 1) for y in (2021, 2023, 2025)], ["21", "23", "25"])
    for ax in axes.flat[len(roles) :]:
        ax.set_visible(False)
    axes.flat[0].legend(fontsize=8)
    for ax in axes[:, 0]:
        ax.set_ylabel("% of the scope's postings", fontsize=9)
    fig.tight_layout()
    return fig


def non_software_by_year(frame: pd.DataFrame) -> pd.DataFrame:
    """Share of "IT" postings that are really technicians or not IT at all, per year and scope.

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        Columns ``year``, ``scope``, ``postings``, ``technical_non_software``, ``not_it``
        (percentages of that scope's postings that year).
    """
    rows = []
    for label, source in SCOPES.items():
        mask = scope_mask(frame, source)
        part = frame if mask is None else frame[mask]
        for year, group in part.groupby("year"):
            row = {"year": year, "scope": label, "postings": len(group)}
            for role in NOT_SOFTWARE:
                row[role] = round(100 * (group.role == role).mean(), 1)
            rows.append(row)
    return pd.DataFrame(rows)


def agreement_by_rule(frame: pd.DataFrame) -> pd.DataFrame:
    """Compare the rule-based role with Jev's confident label, per rule role.

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        Columns ``rule_role``, ``postings`` and ``agree`` (% where Jev picked the same role),
        for postings that have a confident Jev label.
    """
    judged = frame[frame.role_jev.notna() & (frame.role_conf >= a.ROLE_CONFIDENCE)]
    rows = [
        {
            "rule_role": role,
            "postings": len(part),
            "agree": round(100 * (part.role_rule == part.role_jev).mean(), 1),
        }
        for role, part in judged.groupby("role_rule")
    ]
    return pd.DataFrame(rows)


def top_disagreements(frame: pd.DataFrame, count: int = 25) -> pd.DataFrame:
    """List the commonest titles where Jev's confident label differs from the rule.

    Args:
        frame: Output of :func:`analysis.load_features`.
        count: How many titles to return.

    Returns:
        Columns ``title``, ``postings``, ``rule``, ``jev``.
    """
    judged = frame[frame.role_jev.notna() & (frame.role_conf >= a.ROLE_CONFIDENCE)]
    differ = judged[judged.role_rule != judged.role_jev]
    grouped = (
        differ.assign(title=differ.title.str.strip())
        .groupby(["title", "role_rule", "role_jev"])
        .size()
        .reset_index(name="postings")
    )
    top = grouped.sort_values("postings", ascending=False).head(count)
    return top.rename(columns={"role_rule": "rule", "role_jev": "jev"}).reset_index(drop=True)


def top_titles(frame: pd.DataFrame) -> pd.DataFrame:
    """List the commonest titles of each role.

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        Columns ``role``, ``title``, ``postings``.
    """
    clean = frame.assign(title=frame.title.str.strip().str.lower())
    counts = clean.groupby(["role", "title"]).size().reset_index(name="postings")
    top = counts.sort_values("postings", ascending=False).groupby("role").head(TITLES_PER_ROLE)
    top["order"] = top.role.map({r: i for i, r in enumerate(ROLE_ORDER)})
    return top.sort_values(["order", "postings"], ascending=[True, False]).drop(columns="order")


def qa_split(frame: pd.DataFrame) -> pd.DataFrame:
    """Split QA/test postings into software testing and quality control, per year.

    A title counts as software testing when it names testing, a tester, software or automation
    and does not name quality control, a lab or production. This is a title-keyword estimate:
    "Quality Engineer" and "QA/QC Engineer" cannot be told apart from a title alone.

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        Columns ``year``, ``qa_postings``, ``pct_software_testing`` and ``pct_other_qa``.
    """
    qa = frame[frame.role == "qa_test"]
    title = qa.title.str.lower()
    testing = title.str.contains(TESTING_WORDS, regex=True) & ~title.str.contains(
        QUALITY_CONTROL_WORDS, regex=True
    )
    grouped = qa.assign(testing=testing).groupby("year")["testing"]
    table = pd.DataFrame(
        {"qa_postings": grouped.size(), "pct_software_testing": 100 * grouped.mean()}
    )
    table["pct_other_qa"] = 100 - table.pct_software_testing
    return table.round(1).reset_index()


NEW_TITLES_FROM = "2024-01"
NEW_TITLE_MIN_POSTINGS = 20
NEW_TITLES_SHOWN = 40
# Words that change a title without changing the job: promo prefixes, requisition codes, bank
# department tags and seniority.
_TITLE_NOISE = re.compile(
    r"(^mới\b|\[[^\]]*\]|\([^)]*\)|\s-\s.*$|\b(senior|sr|middle|mid|junior|jr|fresher|intern|"
    r"expert|lead|principal|trainee|staff|associate|entry)\b|\b[a-z]{1,3}\d+[\d.]*\b|[/,&:+-])"
)


def title_family(title_key: str) -> str:
    """Reduce a cleaned title to the job it names, without level, codes or promo words.

    Args:
        title_key: The lower-cased cleaned title.

    Returns:
        The title with noise removed and spaces collapsed.
    """
    return re.sub(r"\s+", " ", _TITLE_NOISE.sub(" ", title_key)).strip()


def emerging_titles(frame: pd.DataFrame) -> pd.DataFrame:
    """List job names first seen from 2024 on that already have a meaningful number of postings.

    A title is reduced to its family (see :func:`title_family`), so "Middle AI Engineer" and
    "Senior AI Engineer (HO25.366)" are one job. A family is "emerging" when it never appears
    before 2024 and reaches at least ``NEW_TITLE_MIN_POSTINGS`` postings. Company-specific names
    are not filtered out, so read the list as candidates.

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        Columns ``job``, ``first_month``, ``postings``, ``role``, ordered by postings.
    """
    clean = frame.assign(job=frame.title_key.map(title_family))
    clean = clean[clean.job.str.len() >= MIN_JOB_LENGTH]
    grouped = clean.groupby("job").agg(
        first_month=("month", "min"),
        postings=("month", "size"),
        role=("role", lambda s: s.mode().iat[0]),
    )
    fresh = grouped[
        (grouped.first_month >= NEW_TITLES_FROM) & (grouped.postings >= NEW_TITLE_MIN_POSTINGS)
    ]
    return fresh.sort_values("postings", ascending=False).head(NEW_TITLES_SHOWN).reset_index()
