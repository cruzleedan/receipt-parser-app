"""WORK-0009: score runs against the owner's labels (labels.json from label_server.py).

  python3 -I bench/score_labels.py LABELS.json RUN.jsonl [RUN.jsonl ...]

Receipts marked unreadable are left out. Total: within 0.5 % (or 0.01). Date: same calendar
date after normalising (consistency.iso_date). Merchant: one name contains the other, or
difflib similarity >= 0.6, after lower-casing and dropping punctuation (receipts print the
trading name and the company name differently). "All three" needs every field right.
"""

import difflib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from consistency import iso_date, merchant, num, parse  # noqa: E402


def merchant_ok(pred, truth):
    if not pred or not truth:
        return False
    return pred in truth or truth in pred or difflib.SequenceMatcher(None, pred, truth).ratio() >= 0.6


def main(label_path, runs):
    labels = {k: v for k, v in json.loads(Path(label_path).read_text()).items() if not v.get("unreadable")}
    head = ["run", "labelled", "total", "date", "merchant", "all three", "no answer"]
    print("| " + " | ".join(head) + " |\n|" + "---|" * len(head))
    for path in runs:
        recs = {json.loads(l)["id"]: json.loads(l) for l in open(path)}
        n = t = d = m = a = none = 0
        for rid, lab in labels.items():
            if rid not in recs:
                continue
            n += 1
            p = parse(recs[rid])
            if p is None:
                none += 1
                continue
            truth_total, truth_date, truth_merchant = num(lab["total"]), iso_date(lab["date"]), merchant(lab["merchant"])
            ok_t = p["total"] is not None and truth_total is not None and abs(p["total"] - truth_total) <= max(abs(truth_total) * 0.005, 0.01)
            ok_d = p["date"] is not None and p["date"] == truth_date
            ok_m = merchant_ok(p["merchant"], truth_merchant)
            t, d, m, a = t + ok_t, d + ok_d, m + ok_m, a + (ok_t and ok_d and ok_m)
        pct = lambda x: f"{100 * x / n:.0f}% ({x})" if n else "n/a"
        print(f"| {Path(path).stem} | {n} | {pct(t)} | {pct(d)} | {pct(m)} | {pct(a)} | {none} |")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
