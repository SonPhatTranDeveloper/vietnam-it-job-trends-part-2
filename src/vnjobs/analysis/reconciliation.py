"""Queries for notebook 15, does part 1 still hold?

Part 1 (3,469 postings, scraped in October 2026 from ITviec, TopCV, VietnamWorks, TopDev and
LinkedIn, classified by an LLM from the full description) made three headline claims: data/AI/ML is
the biggest group but one of the least open to newcomers; only about a quarter of IT postings
open to intern, fresher and junior (backend and DevOps under 15 %); remote is about 3 %. This
module recomputes those numbers from the part 1 dataset itself and sets them beside the Techmap
feed (this project), for 2026 January to October, all sources and LinkedIn alone (the one site
the two datasets share). The part 1 file lives in the sibling repo and is only read.
"""

from __future__ import annotations

import json

import pandas as pd

from vnjobs.analysis import core as a

PART1_PATH = a.ROOT.parent / "vietnam-it-job-trends" / "data" / "step-07-jev-extracted.jsonl"
FIELDS = (
    "site",
    "title_category",
    "seniority_category",
    "work_model_category",
    "location_category",
)
ENTRY_PART1 = ("Intern", "Fresher", "Junior")
WINDOW = ("2026-01", "2026-10")
TOP_N = 10
OVERALL = "ALL IT POSTINGS"

CATEGORY_OF_ROLE = {
    "data": "Data / AI / ML",
    "ai_ml": "Data / AI / ML",
    "backend": "Backend",
    "fullstack": "Fullstack",
    "frontend": "Frontend",
    "mobile": "Mobile",
    "qa_test": "QA / Testing",
    "devops_cloud": "DevOps / SRE / Cloud",
    "security": "Security / Cyber",
    "it_support_infra": "Infrastructure / IT Support",
    "game": "Game Development",
    "ba_pm_product": "Product / BA / Agile",
    "design": "UI/UX Design",
}


def load_part1() -> pd.DataFrame | None:
    """Read the part 1 dataset (without descriptions).

    Returns:
        One row per part 1 posting with the classification fields and ``tech_stack``, or
        ``None`` when the sibling repo is not on this machine.
    """
    if not PART1_PATH.exists():
        return None
    rows = []
    with PART1_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            classification = record.get("classification") or {}
            extracted = record.get("extracted_info") or {}
            rows.append(
                {
                    "site": record.get("site"),
                    **{k: classification.get(k) for k in FIELDS[1:]},
                    "tech_stack": extracted.get("tech_stack") or [],
                }
            )
    return pd.DataFrame(rows)


def part2_window(frame: pd.DataFrame, source: str | None = None) -> pd.DataFrame:
    """The Techmap postings for January to October 2026, with part 1's category names.

    Args:
        frame: Output of :func:`analysis.load_features`.
        source: A source id, or ``None`` for every source.

    Returns:
        The rows plus a ``category`` column using part 1's names.
    """
    window = frame[(frame.month >= WINDOW[0]) & (frame.month <= WINDOW[1])]
    window = window if source is None else window[window.source == source]
    return window.assign(category=window.role.map(CATEGORY_OF_ROLE).fillna("Other"))


def is_entry_part1(levels: pd.Series) -> pd.Series:
    """Flag part 1 postings classified intern, fresher or junior.

    Args:
        levels: Part 1 ``seniority_category`` values.

    Returns:
        A boolean series.
    """
    return levels.fillna("").map(lambda s: any(word in s for word in ENTRY_PART1))


def role_mix(part1: pd.DataFrame, scopes: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Share of postings in each part 1 category, for part 1 and each Techmap scope.

    Args:
        part1: Output of :func:`load_part1`.
        scopes: Label to Techmap postings (with ``category``).

    Returns:
        Columns ``category``, ``part 1`` and one column per scope (% of postings).
    """
    table = pd.DataFrame({"part 1": part1.title_category.value_counts(normalize=True) * 100})
    for label, frame in scopes.items():
        table[label] = frame.category.value_counts(normalize=True) * 100
    return (
        table.round(1).sort_values("part 1", ascending=False).rename_axis("category").reset_index()
    )


def entry_rates(frame: pd.DataFrame, strict: bool = False) -> pd.Series:
    """Entry-level share of known-level Techmap postings per category, plus an overall row.

    Args:
        frame: Techmap postings with a ``category`` column.
        strict: When true, count only levels read from the title or the board's label.

    Returns:
        Percentages indexed by category, with an ``ALL IT POSTINGS`` row.
    """
    known = frame[frame.level != "unknown"]
    if strict:
        known = known[known.level_from.isin(["title", "label"])]
    flag = known.level.isin(["intern", "junior"])
    rates = 100 * flag.groupby(known.category).mean()
    rates.loc[OVERALL] = 100 * flag.mean()
    return rates


def entry_rates_part1(part1: pd.DataFrame) -> pd.Series:
    """Entry-level share of known-level part 1 postings per category, plus an overall row.

    Args:
        part1: Output of :func:`load_part1`.

    Returns:
        Percentages indexed by category, with an ``ALL IT POSTINGS`` row.
    """
    known = part1[part1.seniority_category != "Unknown"]
    flag = is_entry_part1(known.seniority_category)
    rates = 100 * flag.groupby(known.title_category).mean()
    rates.loc[OVERALL] = 100 * flag.mean()
    return rates


def entry_by_category(part1: pd.DataFrame, scopes: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Entry-level share of known-level postings per category, part 1 against Techmap.

    Techmap scopes appear twice: with the full level definition used in this project, and
    "title or label only" (no fallback from required experience), which is closer to how part 1
    read the level.

    Args:
        part1: Output of :func:`load_part1`.
        scopes: Label to Techmap postings (with ``category``).

    Returns:
        Columns ``category``, ``part 1``, and the Techmap columns (% entry among known level).
    """
    columns = {"part 1": entry_rates_part1(part1)}
    for label, frame in scopes.items():
        columns[f"{label}, full"] = entry_rates(frame)
        columns[f"{label}, title/label only"] = entry_rates(frame, strict=True)
    table = pd.DataFrame(columns).round(1)
    order = [c for c in table.index if c != OVERALL] + [OVERALL]
    return table.loc[order].rename_axis("category").reset_index()


def work_mode(part1: pd.DataFrame, scopes: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Remote, hybrid and on-site shares, of all postings and of those that state a mode.

    Args:
        part1: Output of :func:`load_part1`.
        scopes: Label to Techmap postings.

    Returns:
        Columns ``dataset``, ``mode``, ``pct_of_all_postings``, ``pct_of_stated``.
    """
    names = {"Remote": "remote", "Hybrid": "hybrid", "On-site": "onsite"}
    rows = []
    modes1 = part1.work_model_category.map(names)
    datasets = {"part 1": modes1, **{label: frame.work_mode for label, frame in scopes.items()}}
    for label, modes in datasets.items():
        stated = modes.notna().sum()
        for mode in ("remote", "hybrid", "onsite"):
            hits = int((modes == mode).sum())
            rows.append(
                {
                    "dataset": label,
                    "mode": mode,
                    "pct_of_all_postings": round(100 * hits / len(modes), 1),
                    "pct_of_stated": round(100 * hits / stated, 1),
                    "pct_stating_a_mode": round(100 * stated / len(modes), 1),
                }
            )
    return pd.DataFrame(rows)


def locations(part1: pd.DataFrame, scopes: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """City split of postings with a known city, part 1 against Techmap.

    Args:
        part1: Output of :func:`load_part1`.
        scopes: Label to Techmap postings.

    Returns:
        Columns ``city`` and one column per dataset (% of postings in the three big cities
        plus other).
    """
    names = {
        "Ha Noi": "Hà Nội",
        "Ho Chi Minh": "Hồ Chí Minh",
        "Da Nang": "Đà Nẵng",
        "Other": "Other",
    }
    table = pd.DataFrame(
        {"part 1": part1.location_category.map(names).value_counts(normalize=True) * 100}
    )
    for label, frame in scopes.items():
        known = frame[frame.city_group != "Unknown"]
        table[label] = known.city_group.value_counts(normalize=True) * 100
    return table.round(1).rename_axis("city").reset_index()


def top_technologies(part1: pd.DataFrame, techmap: pd.DataFrame) -> pd.DataFrame:
    """The ten most-named technologies in each dataset, as a share of postings naming any.

    Only the ranking is compared: the two dictionaries differ.

    Args:
        part1: Output of :func:`load_part1`.
        techmap: Techmap postings (2026 window) with a description.

    Returns:
        Columns ``rank``, ``part 1`` and ``Techmap`` (technology and share).
    """
    named1 = part1[part1.tech_stack.map(len) > 0]
    top1 = named1.tech_stack.explode().str.strip().value_counts().head(TOP_N)
    named2 = techmap[techmap.has_text & (techmap.techs.map(len) > 0)]
    top2 = named2.techs.explode().value_counts().head(TOP_N)
    rows = []
    for rank in range(TOP_N):
        rows.append(
            {
                "rank": rank + 1,
                "part 1": f"{top1.index[rank]} ({100 * top1.iloc[rank] / len(named1):.0f} %)",
                "Techmap": f"{top2.index[rank]} ({100 * top2.iloc[rank] / len(named2):.0f} %)",
            }
        )
    return pd.DataFrame(rows)
