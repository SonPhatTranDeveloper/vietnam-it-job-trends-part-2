"""Queries and charts for notebook 10, language requirements (Japanese, English, Korean).

A language flag means the title or description *mentions* the language or its certificate
(for example JLPT, IELTS, TOPIK, "Bridge SE"). A mention is usually, not always, a requirement.
Longer descriptions mention more, so each trend is drawn for all sources and for the two
control sources whose descriptions keep the same length (LinkedIn, Monster Asia).
"""

from __future__ import annotations

import pandas as pd

from vnjobs.analysis import core as a

LANGUAGES = ["japanese", "english", "korean", "chinese"]
SCOPES = {"All sources": None, "LinkedIn": "linkedin_vn", "Monster Asia": "monsterasia_vn"}
FROM_MONTH = "2025-01"
MIN_ROLE_POSTINGS = 150
MIN_CONTROL_POSTINGS = 150
TOP_EMPLOYERS = 12


def mention_series(frame: pd.DataFrame, language: str) -> dict[str, pd.DataFrame]:
    """Quarterly share of postings with a description that mention a language, per scope.

    Args:
        frame: Output of :func:`analysis.load_features`.
        language: One of ``LANGUAGES``.

    Returns:
        Scope label to trend frame.
    """
    flag = frame[f"lang_{language}"]
    out = {}
    for label, source in SCOPES.items():
        base = frame.has_text if source is None else frame.has_text & (frame.source == source)
        out[label] = a.trend_frame(frame, flag, base, MIN_CONTROL_POSTINGS)
    return out


def by_role(frame: pd.DataFrame) -> pd.DataFrame:
    """Share of postings mentioning each language, per role, from 2025 on.

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        Columns ``role``, ``postings`` and one column per language (%), largest first.
    """
    recent = frame[(frame.month >= FROM_MONTH) & frame.has_text]
    rows = []
    for role, part in recent.groupby("role"):
        if len(part) < MIN_ROLE_POSTINGS:
            continue
        row = {"role": role, "postings": len(part)}
        row.update({lang: round(100 * part[f"lang_{lang}"].mean(), 1) for lang in LANGUAGES})
        rows.append(row)
    return pd.DataFrame(rows).sort_values("postings", ascending=False).reset_index(drop=True)


def by_level(frame: pd.DataFrame) -> pd.DataFrame:
    """Share mentioning each language per seniority level, from 2025 on (known levels).

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        Columns ``level``, ``postings`` and one column per language (%).
    """
    recent = frame[(frame.month >= FROM_MONTH) & frame.has_text & (frame.level != "unknown")]
    rows = []
    for level, part in recent.groupby("level"):
        row = {"level": level, "postings": len(part)}
        row.update({lang: round(100 * part[f"lang_{lang}"].mean(), 1) for lang in LANGUAGES})
        rows.append(row)
    return pd.DataFrame(rows)


def japanese_employers(frame: pd.DataFrame) -> pd.DataFrame:
    """Employers with the most Japanese-mentioning postings from 2025 on, groups combined.

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        Columns ``company``, ``japanese_postings``, ``share_of_their_postings`` (%).
    """
    recent = frame[(frame.month >= FROM_MONTH) & frame.company_key.notna()]
    employer = recent.company_group.fillna(recent.company_key.str.title())
    table = (
        recent.assign(employer=employer)
        .groupby("employer")
        .agg(postings=("lang_japanese", "size"), japanese_postings=("lang_japanese", "sum"))
    )
    table["share_of_their_postings"] = (100 * table.japanese_postings / table.postings).round(1)
    top = table.sort_values("japanese_postings", ascending=False).head(TOP_EMPLOYERS)
    return top.drop(columns="postings").rename_axis("company").reset_index()


def japanese_titles(frame: pd.DataFrame, count: int = 15) -> pd.DataFrame:
    """The commonest titles among Japanese-mentioning postings, as a sanity check.

    Args:
        frame: Output of :func:`analysis.load_features`.
        count: How many titles to return.

    Returns:
        Columns ``title`` and ``postings``.
    """
    flagged = frame[frame.lang_japanese]
    titles = flagged.title.str.strip().str.lower().value_counts().head(count)
    return titles.rename_axis("title").reset_index(name="postings")
