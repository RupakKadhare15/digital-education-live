"""
Build the study page from src/index.html + .env  →  dist/index.html

    python build.py            build dist/index.html
    python build.py --serve    build, then preview at http://localhost:8000

Reads SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY from .env (or from real environment
variables, which win; that is how Netlify passes them in). Standard library only.

Only the publishable key is ever written into the page. The build stops if the
value looks like a secret / service_role key, because anything in the page is public.
"""
import base64
import http.server
import json
import os
import re
import socketserver
import sys
from functools import partial

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "src", "index.html")
DIST = os.path.join(ROOT, "dist")


def load_env(path=os.path.join(ROOT, ".env")):
    """Minimal .env reader: KEY=value lines, # comments, optional quotes. Real env vars take priority."""
    values = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[7:]
                if "=" not in line:
                    sys.exit(f".env line {n} has no '=': {line}")
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip()
                if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
                    v = v[1:-1]
                else:
                    v = v.split(" #", 1)[0].strip()
                values[k] = v
    for k in list(values) + ["SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_ANON_KEY"]:
        if os.environ.get(k):
            values[k] = os.environ[k]
    return values


def jwt_role(key):
    """Legacy Supabase keys are JWTs; return their 'role' claim (anon / service_role) if decodable."""
    parts = key.split(".")
    if len(parts) != 3:
        return None
    try:
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        return json.loads(base64.urlsafe_b64decode(payload)).get("role")
    except Exception:
        return None


def check(env):
    url = env.get("SUPABASE_URL", "").strip().rstrip("/")
    key = (env.get("SUPABASE_PUBLISHABLE_KEY") or env.get("SUPABASE_ANON_KEY") or "").strip()
    problems = []
    if not url or "YOUR-PROJECT-REF" in url:
        problems.append("SUPABASE_URL is missing. Copy it from Supabase → Project Settings → API Keys / Data API.")
    elif not re.match(r"^https?://[^\s/]+$", url):
        problems.append(f"SUPABASE_URL should look like https://abcd1234.supabase.co (got {url!r}).")
    if not key or key.startswith("sb_publishable_...") or "YOUR-" in key:
        problems.append("SUPABASE_PUBLISHABLE_KEY is missing. Use the publishable key (or legacy anon key).")
    elif key.startswith("sb_secret_") or jwt_role(key) == "service_role":
        problems.append("SUPABASE_PUBLISHABLE_KEY holds a SECRET key. Never put it in the page: anyone could read and delete "
                        "all study data. Use the publishable key (sb_publishable_...) or the legacy anon key instead.")
    if problems:
        sys.exit("Build stopped:\n  - " + "\n  - ".join(problems) + "\n\nEdit .env (see .env.example) and run again.")
    if not re.match(r"^https://[a-z0-9-]+\.supabase\.co$", url):
        print(f"Note: {url} is not a *.supabase.co address; fine for a custom domain or local testing.")
    return url, key


def build():
    url, key = check(load_env())
    with open(SRC, encoding="utf-8") as f:
        html = f.read()
    for token, value in (("'%%SUPABASE_URL%%'", url), ("'%%SUPABASE_PUBLISHABLE_KEY%%'", key)):
        if html.count(token) != 1:
            sys.exit(f"src/index.html should contain {token} exactly once.")
        html = html.replace(token, json.dumps(value))
    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    shown = key[:18] + "…" if len(key) > 20 else key
    print(f"Built dist/index.html  →  {url}  (key {shown})")
    return out


def serve(port=8000):
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=DIST)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("localhost", port), handler) as httpd:
        print(f"Preview: http://localhost:{port}/   (add ?condition=ai or ?condition=control)   Ctrl+C to stop")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    build()
    if "--serve" in sys.argv:
        serve(int(os.environ.get("PORT", 8000)))
