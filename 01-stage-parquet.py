"""Stage the Techmap Vietnam job feed as Parquet, one file per month.

Reads data/job-dataset/techmap_jobs_vn_YYYY-MM-DD.jsonl (symlinked, 26 GB for
2020-2026) and writes data/staging/jobs_YYYY-MM.parquet for the chosen window.

* Drops the two heavy raw columns (`html`, `rawPage`) and the schema.org blob
  (`json`); keeps `text` (the description) for later steps.
* Keeps the nested objects as JSON so nothing is lost, and flattens only the
  handful of fields every later step needs.
* The dataset's schema drifts: before 2025 there is no isDuplicate /
  isRecruiter / isDirect / portal column at all. They come through as NULL, and
  `has_dup_flag` records which rows could have been flagged in the first place.
* Skips months that are already staged, so a re-run only fills the gaps.

    .venv/bin/python 01-stage-parquet.py --from 2024-01 --to 2026-11
"""
import argparse, glob, os, time
import duckdb

SRC = "data/job-dataset"
OUT = "data/staging"

COLUMNS = """{
  'idInSource':'VARCHAR','portal':'VARCHAR','source':'VARCHAR','sourceCC':'VARCHAR',
  'locale':'VARCHAR','name':'VARCHAR','url':'VARCHAR','text':'VARCHAR',
  'dateScraped':'VARCHAR','dateCreated':'VARCHAR',
  'isDuplicate':'BOOLEAN','isDuplicateOf':'JSON','isRecruiter':'BOOLEAN','isDirect':'BOOLEAN',
  'position':'JSON','salary':'JSON','orgTags':'JSON','location':'JSON','company':'JSON'
}"""

def months(a, b):
    y, m = map(int, a.split("-")); y2, m2 = map(int, b.split("-"))
    while (y, m) <= (y2, m2):
        yield f"{y:04d}-{m:02d}"
        m += 1
        if m == 13: y, m = y + 1, 1

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="a", default="2024-01")
    ap.add_argument("--to", dest="b", default="2026-11")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    con = duckdb.connect()
    con.execute("PRAGMA threads=8")
    total = 0
    for mon in months(a.a, a.b):
        dst = f"{OUT}/jobs_{mon}.parquet"
        files = sorted(glob.glob(f"{SRC}/techmap_jobs_vn_{mon}-*.jsonl"))
        if os.path.exists(dst):
            print(f"{mon} skip (staged)"); continue
        if not files:
            print(f"{mon} no files"); continue
        t = time.time()
        lst = "[" + ",".join("'" + f + "'" for f in files) + "]"
        con.execute(f"""
        COPY (
          SELECT
            idInSource, portal, source, sourceCC, locale, name AS title, url, text,
            strptime(left(dateCreated, 10), '%Y-%m-%d')::DATE AS date_created,
            left(dateScraped, 19) AS date_scraped,
            '{mon}' AS month,
            isDuplicate IS NOT NULL AS has_dup_flag,
            COALESCE(isDuplicate, false) AS is_duplicate,
            COALESCE(isRecruiter, false) AS is_recruiter,
            isDirect AS is_direct,
            json_extract_string(company, '$.nameOrg') AS company_name,
            json_extract_string(location, '$.orgAddress.city') AS city,
            json_extract_string(position, '$.careerLevel') AS career_level,
            json_extract_string(position, '$.workPlace') AS work_place,
            json_extract_string(salary, '$.text') AS salary_text,
            TRY_CAST(json_extract(salary, '$.value') AS DOUBLE) AS salary_value,
            json_extract_string(salary, '$.period') AS salary_period,
            position, salary, orgTags AS org_tags, location, company
          FROM read_json({lst}, format='newline_delimited', columns={COLUMNS},
                         maximum_object_size=134217728, ignore_errors=true)
        ) TO '{dst}' (FORMAT parquet, COMPRESSION zstd)
        """)
        n = con.execute(f"SELECT count(*) FROM read_parquet('{dst}')").fetchone()[0]
        total += n
        print(f"{mon} {n:7d} rows  {os.path.getsize(dst)/1e6:7.1f} MB  {time.time()-t:5.1f}s", flush=True)
    print("staged rows this run:", total)

if __name__ == "__main__":
    main()
