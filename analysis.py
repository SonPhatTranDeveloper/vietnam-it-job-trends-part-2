"""Shared helpers for the analysis notebooks: data access, chart style and saved outputs.

Every notebook starts from the same two views so the numbers agree between them:

* ``it``  - one row per unique IT posting (Jev says tech, ``fp_dup`` is false).
* ``feat`` - the same postings with the step 05 features (technologies, role, level ...).
* ``all_postings`` - one row per month and source with the unique-posting count of the
  whole feed, used as the denominator for "IT share" charts.

Raw postings never leave ``data/`` (the Techmap licence); notebooks save only aggregate
tables to ``tables/`` and charts to ``charts/``.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from common import clean_title_sql

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
TABLES_DIR = ROOT / "tables"
CHARTS_DIR = ROOT / "charts"

# 2026-11 is only a few days old when this was written, so trends stop at the last full month.
LAST_FULL_MONTH = "2026-10"
# Quarterly trends stop at the last complete quarter; October alone would be a one-month quarter.
LAST_FULL_QUARTER_MONTH = "2026-09"
QUARTER_FROM_YEAR = 2023  # earlier years are too thin to split into quarters
MIN_PERIOD_POSTINGS = 400  # a period with fewer postings is left off a trend line
MONTHS_PER_QUARTER = 3
ROLE_CONFIDENCE = 0.6  # a Jev role label at or above this replaces the rule-based role
ROLE_CACHE_PATH = DATA_DIR / "step-06-role-cache.jsonl"

# Palette from part 1 (white ground), each AA on white and tested for colour-blind pairs.
PALETTE = {
    "data": "#0E7490",
    "chrome": "#A16207",
    "tension": "#9F1239",
    "struct": "#0F172A",
    "muted": "#94A3B8",
}
SERIES_COLOURS = [
    "#0E7490",
    "#A16207",
    "#9F1239",
    "#0F172A",
    "#7C3AED",
    "#15803D",
    "#94A3B8",
    "#F59E0B",
    "#14B8A6",
    "#EC4899",
    "#64748B",
]

SOURCE_LABELS = {
    "careerbuilder_vn": "CareerBuilder",
    "jora_vn": "Jora",
    "linkedin_vn": "LinkedIn",
    "careerjet_vn": "CareerJet",
    "monsterasia_vn": "Monster Asia",
    "indeed_vn": "Indeed",
    "careerviet_vn": "CareerViet",
    "smartrecruiters_vn": "SmartRecruiters",
    "zohorecruit_vn": "Zoho Recruit",
    "techmap_vn": "Techmap",
    "foundit_vn": "Foundit",
    "manatal_vn": "Manatal",
    "dejobs_vn": "DEjobs",
    "lever_vn": "Lever",
}


def connect() -> duckdb.DuckDBPyConnection:
    """Open DuckDB with the ``it`` and ``all_postings`` views the notebooks share.

    Returns:
        A connection whose views read the step 03 and step 04 Parquet files.
    """
    temp_dir = DATA_DIR / ".duckdb-tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("PRAGMA threads=8")
    con.execute(f"SET temp_directory='{temp_dir}'")
    con.execute(
        f"""CREATE VIEW it AS
        SELECT * FROM read_parquet('{DATA_DIR / "step-04-it" / "*.parquet"}')
        WHERE NOT fp_dup"""
    )
    con.execute(
        f"""CREATE VIEW feat AS
        SELECT *, lower({clean_title_sql()}) AS title_key
        FROM read_parquet('{DATA_DIR / "step-05-features" / "*.parquet"}')
        WHERE NOT fp_dup"""
    )
    con.execute(
        f"""CREATE VIEW all_postings AS
        SELECT month, source, count(*) AS postings
        FROM read_parquet('{DATA_DIR / "step-03-fp" / "*.parquet"}')
        WHERE NOT fp_dup GROUP BY month, source"""
    )
    return con


def query(con: duckdb.DuckDBPyConnection, sql: str) -> pd.DataFrame:
    """Run a query and return the result as a DataFrame.

    Args:
        con: Connection from :func:`connect`.
        sql: The SQL to run.

    Returns:
        The result rows.
    """
    return con.sql(sql).df()


def source_label(source: str) -> str:
    """Turn a feed source id such as ``jora_vn`` into a display name.

    Args:
        source: The raw ``source`` value from the feed.

    Returns:
        A readable name, or the raw value when it is not a known source.
    """
    return SOURCE_LABELS.get(source, source)


def apply_style() -> None:
    """Set the matplotlib defaults so every chart uses the part 1 look."""
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": PALETTE["struct"],
            "axes.labelcolor": PALETTE["struct"],
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.prop_cycle": plt.cycler(color=SERIES_COLOURS),
            "xtick.color": PALETTE["struct"],
            "ytick.color": PALETTE["struct"],
            "axes.grid": True,
            "grid.color": "#E2E8F0",
            "grid.linewidth": 0.8,
            "font.size": 11,
            "figure.dpi": 110,
            "legend.frameon": False,
        }
    )


def save_table(frame: pd.DataFrame, name: str) -> Path:
    """Save an aggregate table to ``tables/<name>.csv``.

    Args:
        frame: The aggregate rows. Must not hold individual postings.
        name: File name without extension.

    Returns:
        The path written.
    """
    TABLES_DIR.mkdir(exist_ok=True)
    path = TABLES_DIR / f"{name}.csv"
    frame.to_csv(path, index=False)
    return path


def save_chart(figure: Figure, name: str) -> Path:
    """Save a chart to ``charts/<name>.png`` at video resolution.

    Args:
        figure: The figure to save.
        name: File name without extension.

    Returns:
        The path written.
    """
    CHARTS_DIR.mkdir(exist_ok=True)
    path = CHARTS_DIR / f"{name}.png"
    figure.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
    return path


def period_of(month: str) -> str:
    """Map a ``YYYY-MM`` month to its trend period: a year before 2023, a quarter after.

    Args:
        month: The month, as ``YYYY-MM``.

    Returns:
        ``"2021"`` or ``"2024-Q3"``.
    """
    year, number = int(month[:4]), int(month[5:7])
    if year < QUARTER_FROM_YEAR:
        return str(year)
    return f"{year}-Q{(number - 1) // MONTHS_PER_QUARTER + 1}"


def period_date(period: str) -> pd.Timestamp:
    """Place a period at its midpoint so years and quarters share one honest time axis.

    Args:
        period: Output of :func:`period_of`.

    Returns:
        July 1st for a year, the middle month of the quarter for a quarter.
    """
    if "-Q" not in period:
        return pd.Timestamp(int(period), 7, 1)
    year, quarter = period.split("-Q")
    return pd.Timestamp(int(year), (int(quarter) - 1) * MONTHS_PER_QUARTER + 2, 15)


def load_features(
    con: duckdb.DuckDBPyConnection, last_month: str = LAST_FULL_MONTH
) -> pd.DataFrame:
    """Load the unique IT postings with their features and period columns.

    Args:
        con: Connection from :func:`connect`.
        last_month: Last month to keep.

    Returns:
        One row per posting with ``year``, ``period`` and ``period_date`` added.
    """
    frame = query(con, f"SELECT * FROM feat WHERE month <= '{last_month}'")
    frame["year"] = frame.month.str[:4].astype(int)
    frame["period"] = frame.month.map(period_of)
    frame["period_date"] = frame.period.map(period_date)
    frame["source_name"] = frame.source.map(source_label)
    return add_jev_roles(frame)


def add_jev_roles(frame: pd.DataFrame) -> pd.DataFrame:
    """Join Jev's role labels (step 06) and pick the final role for each posting.

    The final role is Jev's label when it is confident (``ROLE_CONFIDENCE``), otherwise the
    rule-based role from step 05. Without the cache every posting keeps its rule-based role.

    Args:
        frame: Features with a ``title_key`` column.

    Returns:
        The frame with ``role_rule``, ``role_jev``, ``role_conf`` and ``role`` (final) columns.
    """
    frame = frame.rename(columns={"role": "role_rule"})
    frame["role_jev"] = None
    frame["role_conf"] = 0.0
    if ROLE_CACHE_PATH.exists():
        cache = pd.read_json(ROLE_CACHE_PATH, lines=True)[["title_key", "label", "conf"]]
        cache = cache.drop_duplicates("title_key").set_index("title_key")
        frame["role_jev"] = frame.title_key.map(cache.label)
        frame["role_conf"] = frame.title_key.map(cache.conf).fillna(0.0)
    trusted = frame.role_jev.notna() & (frame.role_conf >= ROLE_CONFIDENCE)
    frame["role"] = frame.role_rule.where(~trusted, frame.role_jev)
    return frame


def trend_frame(
    frame: pd.DataFrame,
    flag: pd.Series,
    base: pd.Series | None = None,
    min_n: int = MIN_PERIOD_POSTINGS,
) -> pd.DataFrame:
    """Share of postings with a property, per period, hiding periods that are too small.

    Args:
        frame: Output of :func:`load_features`.
        flag: Boolean series, true where the posting has the property.
        base: Boolean series choosing which postings count in the denominator; all when omitted.
        min_n: Smallest denominator a period needs to be kept.

    Returns:
        Columns ``period``, ``period_date``, ``n`` (denominator), ``hits`` and ``share`` (%),
        ordered in time, for complete periods with at least ``min_n`` postings.
    """
    mask = base if base is not None else pd.Series(True, index=frame.index)
    grouped = (
        frame[mask]
        .assign(hit=flag[mask])
        .groupby(["period", "period_date"])
        .hit.agg(n="size", hits="sum")
        .reset_index()
    )
    grouped["share"] = (100 * grouped.hits / grouped.n).round(2)
    complete = grouped.period_date <= period_date_limit()
    return grouped[complete & (grouped.n >= min_n)].sort_values("period_date")


def period_date_limit() -> pd.Timestamp:
    """Latest period midpoint that belongs to a complete period.

    Returns:
        The midpoint of the quarter that holds ``LAST_FULL_QUARTER_MONTH``.
    """
    return period_date(period_of(LAST_FULL_QUARTER_MONTH))


def style_time_axis(ax: Axes, start: int = 2020) -> None:
    """Show one tick per year on a time axis.

    Args:
        ax: The axes to format.
        start: First year on the axis.
    """
    ticks = [pd.Timestamp(year, 1, 1) for year in range(start, 2028)]
    ax.set_xticks(ticks, [str(t.year) for t in ticks])
    ax.set_xlim(pd.Timestamp(start, 1, 1), pd.Timestamp(2026, 12, 1))


def trend_lines(
    series: dict[str, pd.DataFrame],
    title: str,
    ylabel: str,
    value: str = "share",
    start: int = 2020,
) -> Figure:
    """Draw one line per series on the shared time axis.

    Args:
        series: Label to frame (needs ``period_date`` and the ``value`` column).
        title: Chart title.
        ylabel: Y axis label.
        value: Column to plot.
        start: First year on the time axis.

    Returns:
        The figure.
    """
    fig, ax = plt.subplots(figsize=(11, 5))
    for label, part in series.items():
        ax.plot(part.period_date, part[value], marker="o", markersize=4, label=label)
    style_time_axis(ax, start)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend(ncol=2)
    return fig


def small_multiples(
    series: dict[str, pd.DataFrame], title: str, ylabel: str, columns: int = 4
) -> Figure:
    """Draw each series in its own small panel with a shared time axis.

    Args:
        series: Label to frame (needs ``period_date`` and ``share``).
        title: Overall title.
        ylabel: Y axis label for the left-most panels.
        columns: Panels per row.

    Returns:
        The figure.
    """
    rows = -(-len(series) // columns)
    fig, axes = plt.subplots(rows, columns, figsize=(3.2 * columns, 2.4 * rows), sharex=True)
    for ax, (label, part) in zip(axes.flat, series.items(), strict=False):
        ax.plot(part.period_date, part.share, color=PALETTE["data"], linewidth=1.8)
        ax.set_title(label, fontsize=10)
        ax.set_xticks([pd.Timestamp(y, 1, 1) for y in (2021, 2023, 2025)], ["21", "23", "25"])
    for ax in axes.flat[len(series) :]:
        ax.set_visible(False)
    for ax in axes[:, 0]:
        ax.set_ylabel(ylabel, fontsize=9)
    fig.suptitle(title, y=1.02)
    fig.tight_layout()
    return fig


def stacked_share(
    frame: pd.DataFrame, group: str, order: list[str], title: str, start: int = 2020
) -> Figure:
    """Stack each group's share of the period's postings (100 % per period).

    Args:
        frame: Output of :func:`load_features` (or a filtered copy).
        group: Column whose values become the stacked bands.
        order: Band order from bottom to top; values not listed are dropped.
        title: Chart title.
        start: First year on the time axis.

    Returns:
        The figure.
    """
    counts = frame.groupby(["period_date", group]).size().unstack(fill_value=0)
    counts = counts[counts.sum(axis=1) >= MIN_PERIOD_POSTINGS]
    counts = counts[counts.index <= period_date_limit()]
    shares = 100 * counts.div(counts.sum(axis=1), axis=0)
    shares = shares[[name for name in order if name in shares.columns]]
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.stackplot(shares.index, shares.T.values, labels=shares.columns, colors=SERIES_COLOURS * 3)
    style_time_axis(ax, start)
    ax.set_ylim(0, 100)
    ax.set_ylabel("Share of postings (%)")
    ax.set_title(title)
    ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5))
    return fig


def barh(frame: pd.DataFrame, label: str, value: str, title: str, xlabel: str) -> Figure:
    """Draw a horizontal bar chart, largest at the top.

    Args:
        frame: Rows to draw.
        label: Column with the bar labels.
        value: Column with the bar lengths.
        title: Chart title.
        xlabel: X axis label.

    Returns:
        The figure.
    """
    ordered = frame.sort_values(value)
    fig, ax = plt.subplots(figsize=(9, 0.32 * len(ordered) + 1.6))
    ax.barh(ordered[label], ordered[value], color=PALETTE["data"])
    ax.set_xlabel(xlabel)
    ax.set_title(title)
    ax.grid(axis="y", visible=False)
    return fig


def has_any(frame: pd.DataFrame, column: str, names: list[str]) -> pd.Series:
    """Flag postings whose list column holds at least one of the names.

    Args:
        frame: Output of :func:`load_features`.
        column: List column such as ``techs``.
        names: The values to look for.

    Returns:
        A boolean series.
    """
    wanted = set(names)
    return frame[column].map(lambda values: bool(wanted.intersection(values)))
