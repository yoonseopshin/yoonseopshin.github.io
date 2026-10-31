#!/usr/bin/env python3
"""Prove the migrated posts keep the old text.

  python3 tools/verify_content.py <old _posts dir>

For each old post (YYYY-MM-DD-<n>.md) it finds the new file through
migration/slugs.tsv and compares:
  - body: must be byte-identical except for the edits listed in ALLOWED_BODY
  - front matter: title, categories, date (from the file name) must match;
    tags may only change by the case merges in TAG_MERGE
Prints every difference it finds and exits non-zero on an unexpected one.
"""
import os
import re
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD = sys.argv[1]
NEW = os.path.join(ROOT, "_posts")
SLUGS = dict(l.rstrip("\n").split("\t") for l in open(os.path.join(ROOT, "migration", "slugs.tsv")) if l.strip())

# Edits made on purpose. Each is (post number, old text, new text).
ALLOWED_BODY = [
    # Liquid swallowed these in code blocks on the old site; raw keeps them visible.
    ("62", "{{ task.description }}", "{% raw %}{{ task.description }}{% endraw %}"),
    ("78", "${{ secrets.FIREBASE_SECRET }}", "${% raw %}{{ secrets.FIREBASE_SECRET }}{% endraw %}"),
    # The post linked 78-1.png, but only 78-1.jpg was ever committed.
    ("78", "/assets/images/78-1.png", "/assets/images/78-1.jpg"),
    # Links to other posts on this blog pointed at the dead sys09270883.github.io host.
    ("34", "https://sys09270883.github.io/algorithm/28/", "/posts/coordinate-compression/"),
    ("48", "https://sys09270883.github.io/ps/39/", "/posts/boj-17353-falling-stars/"),
    ("48", "https://sys09270883.github.io/ps/15/", "/posts/boj-11428-sequence-and-query-16/"),
    ("62", "https://sys09270883.github.io/web/61/", "/posts/vue-drf-todo-app-rest-api/"),
]
TAG_MERGE = {"Android": "android", "Web": "web", "Django": "django", "Python": "python"}


def split(path):
    t = open(path, encoding="utf-8").read()
    m = re.match(r"---\n(.*?)\n---\n", t, re.S)
    return yaml.safe_load(m.group(1)), t[m.end():]


def main():
    bad, notes = [], []
    for f in sorted(os.listdir(OLD)):
        m = re.match(r"^(\d{4}-\d{2}-\d{2})-(\d+)\.md$", f)
        if not m:
            continue
        date, n = m.groups()
        newf = os.path.join(NEW, f"{date}-{SLUGS[n]}.md")
        if not os.path.exists(newf):
            bad.append(f"{f}: new file missing")
            continue
        ofm, obody = split(os.path.join(OLD, f))
        nfm, nbody = split(newf)
        expect = obody
        for num, a, b in ALLOWED_BODY:
            if num == n:
                assert a in expect, (f, a)
                expect = expect.replace(a, b)
        if expect != nbody:
            bad.append(f"{f}: body differs")
        elif expect != obody:
            notes.append(f"{f}: body has the allowed edits only")
        for k in ("title", "categories"):
            if ofm.get(k) != nfm.get(k):
                bad.append(f"{f}: {k} changed {ofm.get(k)!r} -> {nfm.get(k)!r}")
        if ofm.get("excerpt") != nfm.get("description"):
            bad.append(f"{f}: excerpt/description differ")
        if bool(ofm.get("use_math")) != bool(nfm.get("math")):
            bad.append(f"{f}: math flag differs")
        otags = []
        for t in ofm.get("tags") or []:
            t = TAG_MERGE.get(t, t)
            if t not in otags:
                otags.append(t)
        if otags != nfm.get("tags"):
            bad.append(f"{f}: tags differ {otags} vs {nfm.get('tags')}")
        elif otags != (ofm.get("tags") or []):
            notes.append(f"{f}: tags case-merged")
    for x in notes:
        print("NOTE", x)
    for x in bad:
        print("FAIL", x)
    print("RESULT", "PASS" if not bad else f"FAIL ({len(bad)})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
