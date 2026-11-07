"""Step 3 - keep the IT postings, using Jev on the TITLE ONLY.

Jev (TypeSafe, `jev-latest`) answers one choice question, `is_tech`, from the
posting title alone. Because only the title is sent, identical titles get
identical answers, so the job is done once per DISTINCT cleaned title and joined
back to every posting. Cleaning = drop (...) and [...] and a trailing city, keep
the original casing ("QA", ".NET"), compare case-insensitively.

Reads  data/step-02-dedup/jobs_*.parquet
Writes data/step-03-titles.parquet            distinct titles + posting counts
       data/step-03-jev-cache.jsonl           resumable: one line per answered title
       data/step-03-it/jobs_YYYY-MM.parquet   postings kept, with jev_label / jev_conf

Part 1's conservative rule is kept for comparability: a posting is dropped only
when Jev says `non_tech` with confidence >= 0.7. Tech and ambiguous are kept and
labelled, so the share of "ambiguous" stays visible.

SPENDING. A Jev call costs about $0.000022 (part 1's own estimate). Nothing is
sent unless you pass --yes. `--dry-run` prints the count and the cost and exits.
Needs TYPESAFE_API_KEY in the environment or in .env.local (git-ignored).

    uv run python 03-filter-it-with-jev.py --dry-run
    uv run python 03-filter-it-with-jev.py --limit 1000 --yes      # pilot
    uv run python 03-filter-it-with-jev.py --yes                   # everything
    uv run python 03-filter-it-with-jev.py --write-only            # rebuild outputs from the cache
"""
import argparse, concurrent.futures, glob, json, os, sys, threading, time, urllib.error, urllib.request
from pathlib import Path
import duckdb
from tqdm import tqdm

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-latest"
DROP_CONFIDENCE = 0.7
MAX_WORKERS = 32
COST_PER_CALL = 0.000022
CACHE = Path("data/step-03-jev-cache.jsonl")
LOCK = threading.Lock()

QUESTION = {"is_tech": {"type": "choice", "instructions": "Is this a hands-on technical (tech) job?",
  "criteria": {
    "tech": ("Technical role: developer/engineer (backend, frontend, fullstack, mobile, embedded, game), "
             "data engineer, data scientist, data analyst, ML/AI engineer, DevOps/SRE/Cloud/Platform, "
             "QA/automation tester, security engineer, solution architect, system/network admin, IT support/helpdesk."),
    "non_tech": ("Non-technical role: product owner/manager, project manager, scrum master, business analyst, "
                 "UI/UX designer, graphic designer, and any non-IT role (sales, marketing, accounting, HR, admin, "
                 "driver, retail, manufacturing, hospitality, etc.).")}}}

CLEAN = r"""trim(regexp_replace(regexp_replace(regexp_replace(title, '\s*[\(\[][^\)\]]*[\)\]]', '', 'g'),
  '(?i)\s*[-|–,]\s*(hà nội|hồ chí minh|hcm|tp\.? ?hcm|đà nẵng|hn|remote)\b.*$', '', 'g'), '\s+', ' ', 'g'))"""

def load_key():
    k = os.environ.get("TYPESAFE_API_KEY")
    if k: return k
    p = Path(".env.local")
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            n, _, v = line.strip().partition("=")
            if n == "TYPESAFE_API_KEY" and v: return v
    sys.exit("No TYPESAFE_API_KEY (environment or .env.local)")

def ask(title, key):
    body = json.dumps({"model": MODEL, "state": f"Title: {title}", "questions": QUESTION}).encode()
    for attempt in range(5):
        req = urllib.request.Request(ENDPOINT, data=body, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)["answers"]["is_tech"]
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < 4: time.sleep(2 ** attempt); continue
            raise
        except urllib.error.URLError:
            if attempt < 4: time.sleep(2 ** attempt); continue
            raise

def build_titles(con):
    con.execute(f"""COPY (
      SELECT lower({CLEAN}) AS title_key, any_value({CLEAN}) AS title, count(*) AS postings
      FROM read_parquet('data/step-02-dedup/*.parquet') WHERE length({CLEAN}) >= 3 GROUP BY 1
    ) TO 'data/step-03-titles.parquet' (FORMAT parquet, COMPRESSION zstd)""")

def read_cache():
    out = {}
    if CACHE.exists():
        for line in CACHE.read_text(encoding="utf-8").splitlines():
            try: r = json.loads(line); out[r["title_key"]] = r
            except Exception: pass
    return out

def write_outputs(con):
    os.makedirs("data/step-03-it", exist_ok=True)
    cache = read_cache()
    con.execute("CREATE OR REPLACE TABLE jev(title_key VARCHAR, jev_label VARCHAR, jev_conf DOUBLE)")
    con.executemany("INSERT INTO jev VALUES (?,?,?)", [(k, v["label"], v["conf"]) for k, v in cache.items()])
    kept = dropped = 0
    for f in sorted(glob.glob("data/step-02-dedup/jobs_*.parquet")):
        mon = f.split("_")[-1][:7]
        con.execute(f"""COPY (
          SELECT p.*, j.jev_label, j.jev_conf FROM read_parquet('{f}') p
          LEFT JOIN jev j ON j.title_key = lower({CLEAN.replace('title','p.title')})
          WHERE NOT (j.jev_label = 'non_tech' AND j.jev_conf >= {DROP_CONFIDENCE})
        ) TO 'data/step-03-it/jobs_{mon}.parquet' (FORMAT parquet, COMPRESSION zstd)""")
    n = con.execute("SELECT count(*), count(jev_label), sum((jev_label='tech')::int) FROM read_parquet('data/step-03-it/*.parquet')").fetchone()
    print(f"kept {n[0]} postings; {n[1]} carry a Jev label ({n[2]} 'tech'); the rest are unlabelled and kept")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--yes", action="store_true", help="actually call Jev (spends money)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--write-only", action="store_true")
    a = ap.parse_args()
    con = duckdb.connect(); con.execute("PRAGMA threads=8")
    if a.write_only: write_outputs(con); return
    build_titles(con)
    cache = read_cache()
    todo = [(k, t) for k, t in con.execute("SELECT title_key, title FROM read_parquet('data/step-03-titles.parquet') ORDER BY postings DESC").fetchall() if k not in cache]
    total = con.execute("SELECT count(*) FROM read_parquet('data/step-03-titles.parquet')").fetchone()[0]
    if a.limit: todo = todo[:a.limit]
    print(f"{total} distinct titles, {len(cache)} already answered, {len(todo)} to ask; estimated cost ${len(todo)*COST_PER_CALL:.2f}")
    if a.dry_run or not todo or not a.yes:
        print("dry run: nothing sent" if not a.yes and todo else "nothing to send"); 
        if not todo: write_outputs(con)
        return
    key = load_key(); CACHE.parent.mkdir(parents=True, exist_ok=True)
    def work(item):
        k, t = item
        try:
            ans = ask(t, key)
            rec = {"title_key": k, "title": t, "label": ans.get("choice"), "conf": float(ans.get("confidence") or 0)}
            with LOCK:
                with CACHE.open("a", encoding="utf-8") as fh: fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"\nfailed: {t!r}: {e}", file=sys.stderr)
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        list(tqdm(ex.map(work, todo), total=len(todo), unit="title"))
    print(f"{len(todo)} calls in {time.time()-t0:.0f}s ({len(todo)/(time.time()-t0):.1f}/s)")
    write_outputs(con)

if __name__ == "__main__":
    main()
