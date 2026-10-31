#!/usr/bin/env python3
"""Check the built site (_site) against the URL list of the old blog.

  python3 tools/verify_urls.py [_site]

It resolves paths the way GitHub Pages does (directory -> index.html) without
running a server, then checks three things:

1. Every old URL in migration/baseline-urls.tsv either is still a real page or
   is a redirect page that points, in one hop, at the expected new URL.
2. Every URL in sitemap.xml is a real page (not a redirect, not missing).
3. Every internal link and asset reference in every HTML page resolves.

Exit code is non-zero if anything fails.
"""
import html
import os
import re
import sys
import urllib.parse

SITE = sys.argv[1] if len(sys.argv) > 1 else "_site"
HOST = "https://yoonseopshin.github.io"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.path.join(ROOT, "migration", "baseline-urls.tsv")
SLUGS = os.path.join(ROOT, "migration", "slugs.tsv")

REFRESH = re.compile(r'http-equiv="refresh" content="0; url=([^"]+)"')
CANON = re.compile(r'<link rel="canonical" href="([^"]+)"')


def resolve(path):
    """Return the file GitHub Pages would serve for a URL path, or None."""
    path = urllib.parse.unquote(path.split("#")[0].split("?")[0])
    p = os.path.join(SITE, path.lstrip("/"))
    if path.endswith("/"):
        p = os.path.join(p, "index.html")
    if os.path.isfile(p):
        return p
    if os.path.isfile(p + ".html"):
        return p + ".html"
    if os.path.isdir(p) and os.path.isfile(os.path.join(p, "index.html")):
        return os.path.join(p, "index.html")
    return None


def redirect_target(f):
    if not f.endswith(".html"):
        return None
    head = open(f, encoding="utf-8", errors="replace").read(2000)
    m = REFRESH.search(head)
    if not m:
        return None
    c = CANON.search(head)
    target = html.unescape(m.group(1))
    if not c or html.unescape(c.group(1)) != target:
        return ("bad-canonical", target)
    return target


def to_path(url):
    if url.startswith(HOST):
        url = url[len(HOST):] or "/"
    return url


def main():
    fails = []
    slug = dict(l.rstrip("\n").split("\t") for l in open(SLUGS) if l.strip())
    expect = {}
    for line in open(BASELINE, encoding="utf-8"):
        cols = line.rstrip("\n").split("\t")
        if cols[0] == "kind":
            continue
        kind, fname, old = cols[0], cols[1], cols[4]
        if kind == "post":
            n = re.search(r"-(\d+)\.md$", fname).group(1)
            expect[old] = f"/posts/{slug[n]}/"
        elif re.match(r"^/page\d+/$", old):
            expect[old] = "/"
        elif old == "/year-archive/":
            expect[old] = "/archives/"
        else:
            expect[old] = old  # same path must still be a real page

    ok_redirect = ok_same = 0
    for old, new in expect.items():
        f = resolve(old)
        if not f:
            fails.append(f"old URL missing: {old}")
            continue
        tgt = redirect_target(f)
        if new == old:
            if tgt:
                fails.append(f"expected a real page, got redirect: {old} -> {tgt}")
            else:
                ok_same += 1
            continue
        if not tgt:
            fails.append(f"expected redirect: {old} -> {new}, got a page")
            continue
        if isinstance(tgt, tuple):
            fails.append(f"redirect canonical mismatch: {old}")
            continue
        if to_path(tgt) != new:
            fails.append(f"wrong target: {old} -> {tgt} (want {new})")
            continue
        tf = resolve(new)
        if not tf:
            fails.append(f"redirect target missing: {old} -> {new}")
        elif redirect_target(tf):
            fails.append(f"redirect chain: {old} -> {new} -> {redirect_target(tf)}")
        else:
            ok_redirect += 1

    sitemap = open(os.path.join(SITE, "sitemap.xml"), encoding="utf-8").read()
    locs = re.findall(r"<loc>([^<]+)</loc>", sitemap)
    ok_sitemap = 0
    for loc in locs:
        p = to_path(html.unescape(loc))
        f = resolve(p)
        if not f:
            fails.append(f"sitemap URL missing: {loc}")
        elif redirect_target(f):
            fails.append(f"sitemap lists a redirect: {loc}")
        else:
            ok_sitemap += 1
    old_in_sitemap = [o for o, n in expect.items() if o != n and any(to_path(l) == o for l in locs)]
    for o in old_in_sitemap:
        fails.append(f"old URL in sitemap: {o}")

    link_re = re.compile(r'(?:href|src)="([^"]+)"')
    checked = 0
    broken = {}
    for dp, _, files in os.walk(SITE):
        for fn in files:
            if not fn.endswith(".html"):
                continue
            fp = os.path.join(dp, fn)
            text = open(fp, encoding="utf-8", errors="replace").read()
            if REFRESH.search(text[:2000]):
                continue
            # Script bodies hold JS templates such as href="{url}"; they are not links.
            text = re.sub(r"<script\b[^>]*>.*?</script>", "", text, flags=re.S)
            page = "/" + os.path.relpath(fp, SITE).replace(os.sep, "/")
            for raw in link_re.findall(text):
                u = html.unescape(raw)
                if u.startswith(HOST):
                    u = u[len(HOST):] or "/"
                elif re.match(r"^[a-z]+:|^//|^#", u):
                    continue
                if not u.startswith("/"):
                    u = urllib.parse.urljoin(page, u)
                checked += 1
                if not resolve(u):
                    broken.setdefault(u, set()).add(page)
    for u, pages in sorted(broken.items()):
        fails.append(f"broken internal link: {u} (in {len(pages)} pages, e.g. {sorted(pages)[0]})")

    print(f"old URLs: {len(expect)}  redirect OK: {ok_redirect}  same-path OK: {ok_same}")
    print(f"sitemap URLs: {len(locs)}  real pages: {ok_sitemap}")
    print(f"internal links checked: {checked}  broken targets: {len(broken)}")
    for f in fails:
        print("FAIL", f)
    print("RESULT", "PASS" if not fails else f"FAIL ({len(fails)})")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
