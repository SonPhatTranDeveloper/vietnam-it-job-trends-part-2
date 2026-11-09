# Aggregate data pack

Yearly counts and shares for the **149,360 unique IT postings** behind the video, 2021–2026
(2026 = January–October). Source: [Techmap](https://techmap.io) Vietnam job-postings feed,
cleaned and classified by this repo's pipeline (`pipeline/01`–`06`), exported by
`pipeline/07-export-aggregates.py`.

**Aggregate only.** No postings, titles, company names or description text. Any cell
under 10 postings is left empty. Techmap's licence allows aggregates; please credit
Techmap if you reuse these numbers.

| File | Rows are | Notes |
| --- | --- | --- |
| `postings_by_year.csv` | year | unique IT postings per year |
| `role_by_year.csv` | year × role | role family (Jev when confident, rules otherwise) |
| `level_by_year.csv` | year × level | `unknown` = no level found in title, tags or required experience |
| `city_by_year.csv` | year × city | top 8 overall, the rest folded into `Other`; shares include `Unknown` |
| `work_mode_by_year.csv` | year × work mode | the feed carries no work mode before 2023 |
| `technology_by_year.csv` | year × technology | top 40; share of the postings that name at least one technology |
