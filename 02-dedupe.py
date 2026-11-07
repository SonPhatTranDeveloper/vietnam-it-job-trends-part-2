"""Step 2 - drop the postings Techmap itself flags as duplicates.

Reads  data/staging/jobs_YYYY-MM.parquet
Writes data/step-02-dedup/jobs_YYYY-MM.parquet   (is_duplicate = false only)
       data/step-02-dedup-report.csv             per-month counts

Non-destructive: staging is kept, and nothing but `is_duplicate` decides what is
dropped. IMPORTANT LIMIT: the flag does not exist before 2025 (`has_dup_flag` is
false for those rows), so for 2024 this step removes nothing. The report shows
`flag_coverage` per month so no chart can quietly treat 2024 as "clean".

    uv run python 02-dedupe.py
"""
import glob, os
import duckdb

con = duckdb.connect()
os.makedirs("data/step-02-dedup", exist_ok=True)
rows = []
for f in sorted(glob.glob("data/staging/jobs_*.parquet")):
    mon = f.split("_")[-1][:7]
    dst = f"data/step-02-dedup/jobs_{mon}.parquet"
    con.execute(f"COPY (SELECT * FROM read_parquet('{f}') WHERE NOT is_duplicate) TO '{dst}' (FORMAT parquet, COMPRESSION zstd)")
    n, flagged, covered = con.execute(
        f"SELECT count(*), sum(is_duplicate::int), sum(has_dup_flag::int) FROM read_parquet('{f}')").fetchone()
    rows.append((mon, n, covered, flagged, n - flagged))
with open("data/step-02-dedup-report.csv", "w") as fh:
    fh.write("month,rows,rows_with_flag_field,flagged_duplicates,kept\n")
    for r in rows: fh.write(",".join(map(str, r)) + "\n")
tot = [sum(r[i] for r in rows) for i in (1, 2, 3, 4)]
print(f"{'month':8s} {'rows':>8s} {'flag_coverage':>13s} {'flagged':>8s} {'dup%':>5s} {'kept':>8s}")
for m, n, cov, fl, kept in rows:
    print(f"{m:8s} {n:8d} {100*cov//n:12d}% {fl:8d} {100*fl/n:4.0f}% {kept:8d}")
print(f"TOTAL    {tot[0]:8d} {100*tot[1]//tot[0]:12d}% {tot[2]:8d} {100*tot[2]/tot[0]:4.0f}% {tot[3]:8d}")
