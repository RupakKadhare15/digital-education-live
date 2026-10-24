"""
Back up every study table from Supabase to one timestamped .zip (CSV + JSONL).
Standard library only: no pip install needed.

Supabase's free plan has no automatic backups, so run this after each day of data collection.

Usage:
    python backup.py

Reads SUPABASE_URL and SUPABASE_SECRET_KEY from .env (the secret key is only ever used
here, on your own computer; build.py never puts it into the page).
You can also pass them directly:  python backup.py https://abcd1234.supabase.co sb_secret_...
"""
import csv
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
import zipfile

from build import load_env  # same .env reader as the build

TABLES = {  # table -> primary key, used for stable paging
    "participants": "session_id",
    "section_status": "session_id",
    "quiz_answers": "session_id",
    "events": "event_id",
}
PAGE = 1000  # Supabase returns at most 1000 rows per request by default


def fetch_all(base, key, table, pk):
    rows, offset = [], 0
    while True:
        url = f"{base}/rest/v1/{table}?select=*&order={pk}.asc&limit={PAGE}&offset={offset}"
        req = urllib.request.Request(url, headers={"apikey": key, "Authorization": f"Bearer {key}",
                                                   "Accept": "application/json"})
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    batch = json.loads(r.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", "replace")[:300]
                if e.code in (401, 403):
                    sys.exit(f"{table}: access refused ({e.code}). Use the SECRET / service_role key, not the publishable key.\n{body}")
                if attempt == 3:
                    sys.exit(f"{table}: HTTP {e.code}: {body}")
            except urllib.error.URLError as e:
                if attempt == 3:
                    sys.exit(f"{table}: could not reach {base} ({e.reason})")
            time.sleep(2 ** attempt)
        rows.extend(batch)
        print(f"  {table}: {len(rows)} rows", end="\r")
        if len(batch) < PAGE:
            print()
            return rows
        offset += PAGE


def to_csv(rows):
    buf = io.StringIO()
    if rows:
        cols = list(dict.fromkeys(k for r in rows for k in r))
        w = csv.DictWriter(buf, fieldnames=cols)
        w.writeheader()
        for r in rows:  # JSON columns (state, data, timers) are written as JSON text
            w.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in r.items()})
    return buf.getvalue()


def main():
    env = load_env()
    base = (sys.argv[1] if len(sys.argv) > 1 else env.get("SUPABASE_URL", "")).strip().rstrip("/")
    key = (sys.argv[2] if len(sys.argv) > 2 else env.get("SUPABASE_SECRET_KEY", "")).strip()
    if not base.startswith("http") or not key or key.startswith("sb_secret_..."):
        sys.exit("Set SUPABASE_URL and SUPABASE_SECRET_KEY in .env first.\n" + __doc__)
    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "backups"), exist_ok=True)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backups", f"pagerank-backup-{time.strftime('%Y%m%d-%H%M%S')}.zip")
    data = {table: fetch_all(base, key, table, pk) for table, pk in TABLES.items()}  # download everything first
    counts = {t: len(r) for t, r in data.items()}
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for table, rows in data.items():
            z.writestr(f"{table}.csv", to_csv(rows))
            z.writestr(f"{table}.jsonl", "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
        z.writestr("README.txt", "Backup of the PageRank Explorer study.\n"
                   f"Taken: {time.strftime('%Y-%m-%d %H:%M:%S')}\nRows: {json.dumps(counts)}\n"
                   "participants.* contains names and emails: remove those columns before sharing.\n")
    print(f"Saved {out}  ({', '.join(f'{t}: {n}' for t, n in counts.items())})")


if __name__ == "__main__":
    main()
