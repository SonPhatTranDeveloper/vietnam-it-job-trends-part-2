"""Export a small, aggregate-only data pack to aggregates/ (for the public repo).

Yearly counts and shares only, 2021-2026 (2026 = January-October), unique IT postings.
No row-level data, no titles, no company names, no description text; any cell under
10 postings is suppressed. Techmap's licence allows aggregates, not postings.

Run: uv run python pipeline/07-export-aggregates.py
"""
from pathlib import Path

import pandas as pd

from vnjobs.analysis import core

OUT = Path(__file__).resolve().parent.parent / "aggregates"
MIN_CELL = 10
TOP_CITIES = 8
TOP_TECH = 40


def share_table(frame: pd.DataFrame, column: str, top: int | None = None) -> pd.DataFrame:
    """Count postings per year and category, with each category's share of the year.

    Args:
        frame: Unique IT postings with ``year`` and ``column``.
        column: Category column to count.
        top: Keep the ``top`` largest categories overall and fold the rest into "Other".

    Returns:
        Columns ``year``, ``column``, ``postings``, ``share_pct``.
    """
    values = frame[column].fillna("unknown")
    if top:
        keep = values.value_counts().head(top).index
        values = values.where(values.isin(keep), "Other")
    counts = frame.assign(**{column: values}).groupby(["year", column]).size().rename("postings").reset_index()
    counts["share_pct"] = (100 * counts.postings / counts.groupby("year").postings.transform("sum")).round(1)
    return suppress(counts)


def suppress(table: pd.DataFrame) -> pd.DataFrame:
    """Blank out counts below MIN_CELL so no small group can be traced back to postings.

    Args:
        table: A table with ``postings`` (and optionally ``share_pct``).

    Returns:
        The table with small cells set to empty.
    """
    small = table.postings < MIN_CELL
    table["postings"] = table.postings.astype("Int64").mask(small)
    if "share_pct" in table:
        table["share_pct"] = table.share_pct.mask(small)
    return table


def main() -> None:
    """Build and write the aggregate pack."""
    con = core.connect()
    frame = core.load_features(con)
    frame = frame[~frame.fp_dup & (frame.year >= 2021)]
    OUT.mkdir(exist_ok=True)

    frame.groupby("year").size().rename("it_postings").reset_index().to_csv(OUT / "postings_by_year.csv", index=False)
    share_table(frame, "role").to_csv(OUT / "role_by_year.csv", index=False)
    share_table(frame, "level").to_csv(OUT / "level_by_year.csv", index=False)
    share_table(frame, "city_group", TOP_CITIES).rename(columns={"city_group": "city"}).to_csv(OUT / "city_by_year.csv", index=False)
    share_table(frame, "work_mode").to_csv(OUT / "work_mode_by_year.csv", index=False)

    # technologies: share of postings that name at least one technology
    named = frame[frame.techs.map(len) > 0]
    base = named.groupby("year").size()
    tech = named[["year", "techs"]].explode("techs")
    top = tech.techs.value_counts().head(TOP_TECH).index
    counts = tech[tech.techs.isin(top)].groupby(["year", "techs"]).size().rename("postings").reset_index()
    counts["share_of_postings_naming_a_technology_pct"] = (100 * counts.postings / counts.year.map(base)).round(1)
    counts = counts.rename(columns={"techs": "technology"})
    small = counts.postings < MIN_CELL
    counts["postings"] = counts.postings.astype("Int64").mask(small)
    counts.loc[small, "share_of_postings_naming_a_technology_pct"] = None
    counts.to_csv(OUT / "technology_by_year.csv", index=False)
    print("wrote", sorted(p.name for p in OUT.glob("*.csv")), "total", len(frame))


if __name__ == "__main__":
    main()
