# Vietnam IT job trends, 2024–2026 (Techmap)

Analysis behind the video *Vietnam IT Job Trends 2024–2026*, standalone, built on the
**Techmap** Vietnam job-postings feed (a paid, licensed dataset: **do not republish
raw or sample postings**; aggregate tables only, with Techmap credited).

```
data/job-dataset                 symlink -> ~/Downloads/job-dataset   (2,486 daily JSONL files, 26 GB)
01-stage-parquet.py              2024-01..2026-11 -> data/staging/jobs_YYYY-MM.parquet   (1,171,325 rows)
02-dedupe.py                     drop Techmap's isDuplicate flag      -> data/step-02-dedup/  (1,140,906)
03-filter-it-with-jev.py         Jev, TITLE ONLY, once per distinct title -> data/step-03-it/
```

Run everything with `uv run python <script>`. Nothing under `data/` is committed.

Caveat that governs every number: the duplicate flag exists only from **May 2025**, and the
feed's sources change over time (Jora/CareerBuilder in 2024–25, LinkedIn/CareerViet in 2026).
