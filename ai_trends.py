"""Queries and charts for notebook 06, the AI and LLM boom.

Three signals, from most to least reliable:

* **AI roles** (title only): the share of IT postings whose role is AI/ML. Titles do not depend
  on how long a source writes, so this is the cleanest signal.
* **"AI" in the title**: the upper-case word AI in the job title.
* **LLM tools named in the description** (LLM, GPT/OpenAI, LangChain, RAG, generative AI, AI
  agents, prompt engineering, vector databases, Hugging Face): description-based, so it is
  checked against LinkedIn, whose descriptions stay the same length from 2023.
"""

from __future__ import annotations

import pandas as pd

import analysis as a
import taxonomy as tx

LLM_TECHS = [name for name, category in tx.TECH_CATEGORY.items() if category == "llm"]
SCOPES = {"All sources": None, "CareerBuilder": "careerbuilder_vn", "LinkedIn": "linkedin_vn"}
FIRST_SHARE = 1.0  # percent of postings that marks "the term is in use"


def signal_series(frame: pd.DataFrame, flag: pd.Series, base_key: str | None = None) -> dict:
    """Build one signal's quarterly share for every scope.

    Args:
        frame: Output of :func:`analysis.load_features`.
        flag: Boolean series, true where the posting shows the signal.
        base_key: ``"named"`` to take the share over tech-naming postings instead of all.

    Returns:
        Scope label to trend frame.
    """
    base = frame.has_text & (frame.techs.map(len) > 0) if base_key == "named" else None
    out = {}
    for label, source in SCOPES.items():
        scope = (
            base if source is None else (frame.source == source) & (True if base is None else base)
        )
        out[label] = a.trend_frame(frame, flag, scope)
    return out


def llm_flag(frame: pd.DataFrame) -> pd.Series:
    """Flag postings that name at least one LLM-era tool.

    Args:
        frame: Output of :func:`analysis.load_features`.

    Returns:
        A boolean series.
    """
    return a.has_any(frame, "techs", LLM_TECHS)


def first_period_above(
    series: dict[str, pd.DataFrame], threshold: float = FIRST_SHARE
) -> pd.DataFrame:
    """Find the first period in which each scope's share reaches a threshold.

    Args:
        series: Scope label to trend frame.
        threshold: Share (%) to reach.

    Returns:
        Columns ``scope``, ``first_period`` (or ``never``), ``share_then``.
    """
    rows = []
    for label, frame in series.items():
        hit = frame[frame.share >= threshold].head(1)
        rows.append(
            {
                "scope": label,
                "first_period": hit.period.iloc[0] if len(hit) else "never",
                "share_then": hit.share.iloc[0] if len(hit) else float("nan"),
            }
        )
    return pd.DataFrame(rows)
