#!/usr/bin/env python3
"""Check the deployed site over HTTP.

  python3 tools/verify_live.py [https://yoonseopshin.github.io]

- every old URL in migration/baseline-urls.tsv answers 200 and either is the
  real page or a redirect page whose meta refresh and canonical point at the
  expected new URL, which itself answers 200 and is not a redirect
- every sitemap URL answers 200 and is not a redirect
- the sibling project site /static-hosting/ still serves its JSON files
"""
import os
import re
import sys
import urllib.parse
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "https://yoonseopshin.github.io").rstrip("/")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFRESH = re.compile(r'http-equiv="refresh" content="0; url=([^"]+)"')
CANON = re.compile(r'<link rel="canonical" href="([^"]+)"')


def get(path):
    url = BASE + urllib.parse.quote(urllib.parse.unquote(path), safe="/%.-_~")
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "verify-live"}), timeout=30) as r:
            return r.status, r.read().decode("utf-8", "replace"), r.headers.get("content-type", "")
    except urllib.error.HTTPError as e:
        return e.code, "", ""


def target(body):
    m = REFRESH.search(body[:3000])
    if not m:
        return None
    c = CANON.search(body[:3000])
    t = m.group(1).replace("https://yoonseopshin.github.io", "")
    return t if c and c.group(1).replace("https://yoonseopshin.github.io", "") == t else ("bad-canonical", t)


def main():
    slug = dict(l.rstrip("\n").split("\t") for l in open(os.path.join(ROOT, "migration", "slugs.tsv")) if l.strip())
    fails, ok = [], 0
    for line in open(os.path.join(ROOT, "migration", "baseline-urls.tsv"), encoding="utf-8"):
        c = line.rstrip("\n").split("\t")
        if c[0] == "kind":
            continue
        old = c[4]
        if c[0] == "post":
            want = "/posts/%s/" % slug[re.search(r"-(\d+)\.md$", c[1]).group(1)]
        elif re.match(r"^/page\d+/$", old):
            want = "/"
        elif old == "/year-archive/":
            want = "/archives/"
        else:
            want = old
        code, body, _ = get(old)
        t = target(body) if code == 200 else None
        if code != 200:
            fails.append(f"{old}: HTTP {code}")
        elif want == old:
            ok += t is None
            if t:
                fails.append(f"{old}: unexpected redirect to {t}")
        elif t != want:
            fails.append(f"{old}: redirects to {t}, want {want}")
        else:
            c2, b2, _ = get(want)
            if c2 != 200 or target(b2):
                fails.append(f"{old} -> {want}: HTTP {c2} or chained")
            else:
                ok += 1
    code, sm, _ = get("/sitemap.xml")
    locs = [l.replace("https://yoonseopshin.github.io", "") for l in re.findall(r"<loc>([^<]+)</loc>", sm)]
    sm_ok = 0
    for p in locs:
        c2, b2, _ = get(p)
        if c2 != 200 or target(b2):
            fails.append(f"sitemap {p}: HTTP {c2} or redirect")
        else:
            sm_ok += 1
    for p in ["/static-hosting/app-config.json", "/static-hosting/cpa-scheduled.json"]:
        c2, _, ct = get(p)
        print(f"{p}: HTTP {c2} {ct}")
        if c2 != 200 or "json" not in ct:
            fails.append(f"{p}: HTTP {c2} {ct}")
    print(f"old URLs OK: {ok}  sitemap OK: {sm_ok}/{len(locs)}")
    for f in fails:
        print("FAIL", f)
    print("RESULT", "PASS" if not fails else f"FAIL ({len(fails)})")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
