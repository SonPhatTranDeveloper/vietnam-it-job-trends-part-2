# Vietnam IT job trends, 2020–2026 (Techmap)

Analysis behind the video *Vietnam IT Job Trends 2024–2026*, standalone, built on the
**Techmap** Vietnam job-postings feed (a paid, licensed dataset: **do not republish
raw or sample postings**; aggregate tables only, with Techmap credited).

```
data/job-dataset                 symlink -> ~/Downloads/job-dataset   (2,486 daily JSONL files, 26 GB)

pipeline/                        the numbered steps; run in order with `uv run python pipeline/<file>`
  01-stage-parquet.py            all of 2020-01..2026-11 -> data/staging/            (1,966,151 rows)
  02-dedupe.py                   drop Techmap's isDuplicate flag -> data/step-02-dedup/   (1,935,732)
  03-fingerprint.py              mark (company, title, city, month) repeats -> data/step-03-fp/
  04-filter-it-with-jev.py       Jev, TITLE ONLY, once per distinct title -> data/step-04-it/ (170,348)
  05-extract-features.py         technologies, role, level, work mode, salary ... -> data/step-05-features/
  06-classify-roles-with-jev.py  Jev role family per distinct IT title -> data/step-06-role-cache.jsonl

src/vnjobs/                      the installed package (uv sync installs it, so notebooks just import it)
  common.py                      paths (from the repo root), DuckDB connection, title cleaning
  jev.py                         the Jev client and its resumable cache, shared by steps 04 and 06
  taxonomy.py                    every dictionary and rule (technologies, roles, levels, salary parser)
  analysis/core.py               data access, period axis, chart helpers shared by the notebooks
  analysis/<theme>.py            queries and charts for one notebook each (volume, technologies, roles,
                                 seniority, companies, ai, work_mode, salary, data_ai, languages,
                                 entry_level, industries, persistence, benefits, reconciliation)

notebooks/                       one per theme, reading the features; they write only aggregates:
  01-market-volume  02-technology-trends  03-roles  04-seniority
  05-companies  06-ai-and-llm  07-work-mode  08-salary  09-data-and-ai-jobs
  10-language-requirements  11-entry-level-reality  12-industries
  13-persistent-vacancies  14-benefits  15-part-1-reconciliation
tables/  charts/                 the aggregate CSVs and PNGs the notebooks save (safe to share, credit Techmap)
```

Run everything with `uv run python <script>`; see `AGENT.MD` for the coding rules. Nothing under `data/` is committed.

Caveat that governs every number: the duplicate flag exists only from **May 2025**, and the
feed's sources change over time (Jora/CareerBuilder in 2024–25, LinkedIn/CareerViet in 2026).
