"""WORK-0006: score run_bench.py outputs against CORD-v2 ground truth (gt_parse JSON per image).

  python -I bench/score.py --truth /data/cord results/*.jsonl

CORD has no merchant or date ground truth, so only amounts and line items are scored:
- total / subtotal / tax: correct within 1 % (only receipts whose ground truth has the field).
  CORD prints Indonesian thousands ("60.000" = 60000); a model value of 60.0 for "60.000" is
  also accepted, since that reading is ambiguous on the receipt itself.
- line items: F1 over (name, price) pairs; a predicted item matches a ground-truth item when the
  price matches and the names are at least 0.6 similar (difflib), greedy one-to-one.
"""

import argparse
import difflib
import json
import re
import statistics
import sys
from pathlib import Path


def gt_number(s):
    if s is None:
        return None
    if isinstance(s, list):
        s = s[0] if s else None
        if s is None:
            return None
    s = str(s)
    neg = "-" in s
    digits = re.sub(r"[^\d.,]", "", s)
    if not digits:
        return None
    if re.fullmatch(r"\d{1,3}([.,]\d{3})+", digits):
        v = float(re.sub(r"[.,]", "", digits))
    else:
        digits = digits.replace(",", ".")
        if digits.count(".") > 1:
            digits = digits.replace(".", "", digits.count(".") - 1)
        try:
            v = float(digits)
        except ValueError:
            return None
    return -v if neg else v


def pred_number(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return gt_number(v)


def same_amount(pred, truth):
    if pred is None or truth is None:
        return False
    tol = max(abs(truth) * 0.01, 0.01)
    return abs(pred - truth) <= tol or abs(pred * 1000 - truth) <= tol


def as_list(x):
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def truth_fields(gt):
    st = gt.get("sub_total") or {}
    tot = gt.get("total") or {}
    if isinstance(st, list):
        st = st[0] if st else {}
    if isinstance(tot, list):
        tot = tot[0] if tot else {}
    items = []
    for m in as_list(gt.get("menu")):
        if isinstance(m, dict) and m.get("nm"):
            items.append((str(m["nm"] if not isinstance(m["nm"], list) else " ".join(m["nm"])), gt_number(m.get("price"))))
    return {
        "total": gt_number(tot.get("total_price")),
        "subtotal": gt_number(st.get("subtotal_price")),
        "tax": gt_number(st.get("tax_price")),
        "items": items,
    }


def pred_fields(rec):
    raw = rec.get("raw")
    if raw is None:
        return None
    try:
        d = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            return None
        try:
            d = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    if not isinstance(d, dict):
        return None
    if rec.get("format") == "cord":
        t = truth_fields(d)
        return {k: t[k] for k in ("total", "subtotal", "tax")} | {"items": t["items"]}
    items = []
    for it in as_list(d.get("items")):
        if isinstance(it, dict) and it.get("name"):
            items.append((str(it["name"]), pred_number(it.get("total_price"))))
    return {
        "total": pred_number(d.get("total")),
        "subtotal": pred_number(d.get("subtotal")),
        "tax": pred_number(d.get("tax")),
        "items": items,
    }


def item_counts(pred, truth):
    used, tp = set(), 0
    for name, price in pred:
        for j, (tn, tprice) in enumerate(truth):
            if j in used or not same_amount(price, tprice):
                continue
            if difflib.SequenceMatcher(None, name.lower(), tn.lower()).ratio() >= 0.6:
                used.add(j)
                tp += 1
                break
    return tp, len(pred), len(truth)


def score(path, truth_dir):
    recs = [json.loads(l) for l in open(path)]
    n = len(recs)
    ok_json = 0
    fields = {k: [0, 0] for k in ("total", "subtotal", "tax")}
    tp = np_ = nt = 0
    secs = [r["seconds"] for r in recs]
    for r in recs:
        gt = truth_fields(json.loads((Path(truth_dir) / f"{r['id']}.json").read_text()))
        p = pred_fields(r)
        if p is not None:
            ok_json += 1
        for k in fields:
            if gt[k] is None:
                continue
            fields[k][1] += 1
            if p and same_amount(p[k], gt[k]):
                fields[k][0] += 1
        a, b, c = item_counts(p["items"] if p else [], gt["items"])
        tp, np_, nt = tp + a, np_ + b, nt + c
    prec = tp / np_ if np_ else 0
    rec = tp / nt if nt else 0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
    pct = lambda x: f"{100 * x[0] / x[1]:.0f}% ({x[0]}/{x[1]})" if x[1] else "n/a"
    return {
        "run": Path(path).stem,
        "n": n,
        "valid_json": f"{100 * ok_json / n:.0f}%",
        "total": pct(fields["total"]),
        "subtotal": pct(fields["subtotal"]),
        "tax": pct(fields["tax"]),
        "item_f1": f"{f1:.2f}",
        "median_s": f"{statistics.median(secs):.1f}",
        "p90_s": f"{sorted(secs)[int(0.9 * (n - 1))]:.1f}",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--truth", required=True)
    ap.add_argument("runs", nargs="+")
    a = ap.parse_args()
    rows = [score(p, a.truth) for p in a.runs]
    cols = list(rows[0])
    print("| " + " | ".join(cols) + " |")
    print("|" + "---|" * len(cols))
    for r in rows:
        print("| " + " | ".join(str(r[c]) for c in cols) + " |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
