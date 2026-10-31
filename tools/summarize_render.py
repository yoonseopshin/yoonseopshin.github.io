#!/usr/bin/env python3
"""Summarize a side-by-side render measurement (old site vs new site).

  python3 tools/summarize_render.py render.json > report.md

render.json is a list of {file, oldPath, newPath, old: {...}, new: {...}}
measured in a browser (math TeX strings, images, tables, code blocks,
<details>, headings, text length). Prints one row per post that differs.
"""
import collections
import json
import re
import sys

rows = json.load(open(sys.argv[1]))


def norm(tex):
    return re.sub(r"\s+", "", tex)


print("| Post | Math (old→new) | Math only on one side | Images ok old/new | Tables | Code | Details | Headings | Text Δ |")
print("|---|---|---|---|---|---|---|---|---|")
total = collections.Counter()
diff_posts = 0
for r in rows:
    o, n = r["old"], r["new"]
    if o.get("missing") or n.get("missing"):
        print(f"| {r['file']} | missing content block | | | | | | | |")
        diff_posts += 1
        continue
    ot = collections.Counter(norm(t) for t in o["tex"])
    nt = collections.Counter(norm(t) for t in n["tex"])
    only_o = list((ot - nt).elements())
    only_n = list((nt - ot).elements())
    total["math_old"] += len(o["tex"])
    total["math_new"] += len(n["tex"])
    total["err_new"] += n["mathErr"]
    total["img"] += n["img"]
    total["img_ok_old"] += o["imgOk"]
    total["img_ok_new"] += n["imgOk"]
    text_delta = n["text"] - o["text"]
    same = (not only_o and not only_n and o["tables"] == n["tables"] and o["tableCells"] == n["tableCells"]
            and o["code"] == n["code"] and o["details"] == n["details"] and o["img"] == n["img"]
            and n["imgOk"] == n["img"] and abs(text_delta) <= max(20, o["text"] * 0.02) and n["mathErr"] == 0)
    if same:
        continue
    diff_posts += 1
    sides = []
    if only_o:
        sides.append("old only: " + ", ".join(f"`{t[:40]}`" for t in only_o[:3]))
    if only_n:
        sides.append("new only: " + ", ".join(f"`{t[:40]}`" for t in only_n[:3]))
    print(f"| {r['file']} | {len(o['tex'])}→{len(n['tex'])}{' err' + str(n['mathErr']) if n['mathErr'] else ''} | {'; '.join(sides)} "
          f"| {o['imgOk']}/{n['imgOk']} of {n['img']} | {o['tables']}/{n['tables']} ({o['tableCells']}/{n['tableCells']} cells) "
          f"| {o['code']}/{n['code']} | {o['details']}/{n['details']} | {o['h']}/{n['h']} | {text_delta:+d} |")
print()
print(f"posts: {len(rows)}, with any difference: {diff_posts}")
print(f"math formulas old {total['math_old']} new {total['math_new']}, MathJax errors on new {total['err_new']}")
print(f"images {total['img']}: loaded old {total['img_ok_old']}, new {total['img_ok_new']}")
