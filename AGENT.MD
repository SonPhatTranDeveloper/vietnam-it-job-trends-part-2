# AGENT.MD

Rules for any agent (or person) changing code in this repo. The project turns the Techmap
Vietnam job-postings feed (2020-2026, ~1.97M postings, symlinked at `data/job-dataset`) into
the tables behind a standalone video on IT hiring trends. Read this before editing.

## Code rules

1. **Every function has a docstring.** Google style: a one-line summary, then `Args:`,
   `Returns:` (or `Yields:`) and `Raises:` where they apply. Modules and classes get one too.
2. **Every function declares its return type**, including `-> None`, and annotates every
   argument. Use precise types (`list[tuple[str, str]]`, `dict[str, Any]`), not bare `list`.
3. **Comment the "why", not the "what".** A short comment above any step whose reason is not
   obvious: a data quirk, a limit, a trade-off, a number that was chosen on purpose. Never
   restate the code. Name magic numbers as constants (`MAX_ATTEMPTS`, `IT_CONFIDENCE`).
4. **Keep functions small and single-purpose.** Cyclomatic complexity at most **8**, at most
   **8 branches**, **25 statements** and **5 arguments**; ruff enforces all four. If a
   function needs a section comment to explain its parts, split it into functions instead.
5. **No work at import time.** Scripts expose `main()` and run it under
   `if __name__ == "__main__":`. Shared paths, constants and helpers live in `common.py`.
6. **Use `pathlib`**, not `os.path` or `glob`. Build SQL in small functions, not inline in
   `main()`.

## Tooling (always through `uv`)

```bash
uv sync                          # create .venv and install locked dependencies
uv run python 01-stage-parquet.py
uv run ruff check .              # lint: docstrings, annotations, complexity, imports
uv run ruff format .             # format
```

A change is done only when `uv run ruff check .` and `uv run ruff format --check .` are both
clean and the script you touched still runs. Do not silence a rule with `# noqa` to get past
a complexity or docstring finding; fix the function. `noqa` is for a genuine, commented
exception only.

## Pipeline

| Step | Script | Reads -> writes |
| --- | --- | --- |
| 1 | `01-stage-parquet.py` | `data/job-dataset/*.jsonl` -> `data/staging/jobs_YYYY-MM.parquet` (all years) |
| 2 | `02-dedupe.py` | staging -> `data/step-02-dedup/`, drops Techmap's `isDuplicate` flag |
| 3 | `03-fingerprint.py` | dedup -> `data/step-03-fp/`, marks (company, title, city, month) repeats as `fp_dup` |
| 4 | `04-filter-it-with-jev.py` | fingerprint -> `data/step-04-it/`, `data/step-04-ambiguous/`, report |

Every step skips or overwrites its own outputs, so re-running is safe. Nothing under `data/`
is committed.

## Data and safety

- **Licence.** Techmap's Vietnam feed is a paid, licensed dataset. Never commit or publish
  raw or sample postings; only aggregate tables, with Techmap credited. Confirm the terms
  before anything is published.
- **Secrets.** The Jev key lives in `.env.local` (git-ignored). Never print it, log it,
  paste it into a file that is tracked, or put it in a commit message.
- **Money.** Step 4 calls a paid API (about $0.000022 per distinct title; ~$13.5 for all years). It sends nothing
  unless run with `--yes`; always run `--dry-run` first and state the estimated cost before
  spending. The answers are cached in `data/step-04-jev-cache.jsonl`, so a stop loses
  nothing and a re-run never pays twice for a title.
- **Never delete or write through `data/job-dataset`.** It is a symlink to the original 26 GB
  download. Delete derived folders by name, never with a glob over `data/`.

## Things that are easy to get wrong

- The `isDuplicate` flag only exists from **May 2025**. Before that, step 2 removes nothing.
  Step 3's `fp_dup` mark covers every month; use `fp_dup = false` for a headline number and
  `fp_dup = true` as the sensitivity check. Say which one a trend chart used.
- The feed's sources change over time (Indeed, then CareerBuilder, then Jora and LinkedIn,
  then LinkedIn and CareerViet), and so do salary and seniority coverage. A trend that mixes
  sources shows the mix changing, not the market. Compare within one source.
- Jev sees only the **title**. Titles such as "Kỹ thuật" or "Engineer" are ambiguous without
  context, so IT means `tech` at confidence 0.6 or above and the rest is reported as
  `ambiguous`, never folded into IT.
