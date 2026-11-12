"""WORK-0009: score runs on receipts that have no answer key.

  python -I bench/consistency.py RUN.jsonl [RUN.jsonl ...]  > table.md

Per run: valid JSON, total present, items add up (sum of item prices within 1 % of the
subtotal or the total), agreement with the majority of runs on total, date and merchant
(majority = at least 3 runs give the same value), median and p90 seconds.
Also writes disagreements.json next to the first run: receipts where runs disagree on total.
"""

import difflib
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path


def num(v):
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    if isinstance(v, str):
        d = re.sub(r"[^\d.]", "", v.replace(",", ""))
        try:
            return round(float(d), 2) if d else None
        except ValueError:
            return None
    return None


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.dates import normalise_date  # noqa: E402  (the parser's own date reading, WORK-0008)


def _old_iso_date(v):
    if not isinstance(v, str):
        return None
    m = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", v)
    if m:
        return f"{int(m[1]):04d}-{int(m[2]):02d}-{int(m[3]):02d}"
    # Philippine receipts print month first: MM/DD/YYYY or MM/DD/YY.
    m = re.search(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})", v)
    if m:
        y = int(m[3]) + (2000 if len(m[3]) == 2 else 0)
        mo, d = int(m[1]), int(m[2])
        if mo > 12:
            mo, d = d, mo
        return f"{y:04d}-{mo:02d}-{d:02d}"
    return None


def iso_date(v):
    return normalise_date(v)


def merchant(v):
    return re.sub(r"[^a-z0-9 ]", "", v.lower()).strip() if isinstance(v, str) and v.strip() else None


def parse(rec):
    raw = rec.get("raw")
    if not raw:
        return None
    try:
        d = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.S)
        try:
            d = json.loads(m.group(0)) if m else None
        except json.JSONDecodeError:
            d = None
    if not isinstance(d, dict):
        return None
    items = [num(i.get("total_price")) for i in d.get("items") or [] if isinstance(i, dict)]
    return {
        "total": num(d.get("total")), "subtotal": num(d.get("subtotal")),
        "date": iso_date(d.get("date")), "merchant": merchant(d.get("merchant_name")),
        "items": [x for x in items if x is not None],
    }


def close(a, b):
    return a is not None and b is not None and abs(a - b) <= max(abs(b) * 0.01, 0.01)


def majority(values, same):
    best, count = None, 0
    for v in values:
        if v is None:
            continue
        c = sum(1 for w in values if w is not None and same(v, w))
        if c > count:
            best, count = v, c
    return best if count >= 3 else None


def main(paths):
    runs = {Path(p).stem: {json.loads(l)["id"]: json.loads(l) for l in open(p)} for p in paths}
    parsed = {r: {i: parse(rec) for i, rec in recs.items()} for r, recs in runs.items()}
    ids = sorted(set.intersection(*(set(v) for v in runs.values())))
    names_same = lambda a, b: difflib.SequenceMatcher(None, a, b).ratio() >= 0.8
    maj = {}
    for i in ids:
        vals = {f: [parsed[r][i][f] if parsed[r][i] else None for r in runs] for f in ("total", "date", "merchant")}
        maj[i] = {"total": majority(vals["total"], close), "date": majority(vals["date"], lambda a, b: a == b),
                  "merchant": majority(vals["merchant"], names_same)}
    # Same receipt photographed more than once: identical majority merchant, date and total.
    groups = {}
    for i in ids:
        k = maj[i]
        if k["total"] is not None and k["date"] and k["merchant"]:
            groups.setdefault((k["merchant"], k["date"], k["total"]), []).append(i)
    dups = {i for g in groups.values() for i in g[1:]}
    (Path(paths[0]).parent / "duplicates.json").write_text(json.dumps([g for g in groups.values() if len(g) > 1]))
    print(f"re-photographed receipts left out: {len(dups)} (groups in duplicates.json)\n")
    ids = [i for i in ids if i not in dups]
    rows = []
    for r in runs:
        n = len(ids)
        p = [parsed[r][i] for i in ids]
        valid = sum(1 for x in p if x)
        has_total = sum(1 for x in p if x and x["total"] is not None)
        adds = sum(1 for x in p if x and x["items"] and (close(sum(x["items"]), x["subtotal"]) or close(sum(x["items"]), x["total"])))
        agree = {}
        for f, same in (("total", close), ("date", lambda a, b: a == b), ("merchant", names_same)):
            base = [i for i in ids if maj[i][f] is not None]
            hit = sum(1 for i in base if parsed[r][i] and parsed[r][i][f] is not None and same(parsed[r][i][f], maj[i][f]))
            agree[f] = f"{100 * hit / len(base):.0f}%" if base else "n/a"
        secs = sorted(runs[r][i]["seconds"] for i in ids)
        rows.append([r, n, f"{100*valid/n:.0f}%", f"{100*has_total/n:.0f}%", f"{100*adds/n:.0f}%",
                     agree["total"], agree["date"], agree["merchant"],
                     f"{statistics.median(secs):.1f}", f"{secs[int(0.9*(n-1))]:.1f}"])
    head = ["run", "n", "valid JSON", "total present", "items add up", "agrees: total", "agrees: date", "agrees: merchant", "median s", "p90 s"]
    print("| " + " | ".join(head) + " |\n|" + "---|" * len(head))
    for row in rows:
        print("| " + " | ".join(map(str, row)) + " |")
    dis = [i for i in ids if len({parsed[r][i]["total"] if parsed[r][i] else None for r in runs}) > 2]
    (Path(paths[0]).parent / "disagreements.json").write_text(json.dumps(dis))
    print(f"\nreceipts with 3+ different totals across runs: {len(dis)} of {len(ids)}")


if __name__ == "__main__":
    main(sys.argv[1:])
