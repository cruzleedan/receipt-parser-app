"""WORK-0009: a small labelling page for the owner's receipts, reachable only on the tailnet.

  python3 -I bench/label_server.py DATA_DIR HOST PORT

DATA_DIR holds sample/*.jpg, runs/*.jsonl (model answers, used to pre-fill) and
label_queue.json (the receipt ids to label). Answers are saved to DATA_DIR/labels.json.
Standard library only; binds to HOST (the d3 Tailscale address), never 0.0.0.0.
"""

import json
import os
import re
import sys
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DATA = Path(sys.argv[1])
LABELS = DATA / "labels.json"
ID_RE = re.compile(r"^r\d{3}$")

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Receipt labels</title>
<style>
:root { --bg:#f6f5f2; --fg:#1d1d1b; --muted:#6b6a66; --line:#d9d6cf; --accent:#2f5d50; --card:#fff; }
@media (prefers-color-scheme: dark) { :root { --bg:#161615; --fg:#ecebe7; --muted:#9a9891; --line:#34332f; --accent:#7fb8a6; --card:#1f1f1d; } }
* { box-sizing:border-box }
body { margin:0; font:15px/1.45 system-ui, sans-serif; background:var(--bg); color:var(--fg) }
main { display:grid; grid-template-columns:minmax(0,1fr) 360px; gap:20px; padding:16px; height:100vh }
@media (max-width:820px) { main { grid-template-columns:1fr; height:auto } }
.img { overflow:auto; background:var(--card); border:1px solid var(--line); border-radius:8px; }
.img img { width:100%; display:block }
form { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:16px; align-self:start }
h1 { font-size:16px; margin:0 0 4px } .muted { color:var(--muted); font-size:13px }
label { display:block; margin:14px 0 4px; font-weight:600 }
input[type=text] { width:100%; padding:8px 10px; font:inherit; color:inherit; background:var(--bg); border:1px solid var(--line); border-radius:6px }
.check { display:flex; gap:8px; align-items:center; margin-top:14px; font-weight:400 }
.row { display:flex; gap:8px; margin-top:18px } button { flex:1; padding:10px; font:inherit; border-radius:6px; border:1px solid var(--line); background:var(--bg); color:inherit; cursor:pointer }
button.primary { background:var(--accent); color:var(--card); border-color:var(--accent); font-weight:600 }
.bar { height:6px; background:var(--line); border-radius:3px; margin-top:10px } .bar div { height:100%; background:var(--accent); border-radius:3px }
</style></head><body><main>
<div class="img"><img id="img" alt="Receipt photo"></div>
<form id="f">
  <h1 id="title">Loading…</h1>
  <div class="muted">Pre-filled from the models. Fix anything wrong, leave right answers as they are. Use the receipt's own date and the final amount paid.</div>
  <div class="bar"><div id="bar" style="width:0"></div></div>
  <label for="merchant">Merchant</label><input type="text" id="merchant" autocomplete="off">
  <label for="date">Date (YYYY-MM-DD)</label><input type="text" id="date" autocomplete="off" placeholder="2024-07-26">
  <label for="total">Total</label><input type="text" id="total" autocomplete="off" inputmode="decimal">
  <label class="check"><input type="checkbox" id="unreadable"> Not a receipt, or too unclear to tell</label>
  <div class="row"><button type="button" id="back">Back</button><button class="primary" type="submit">Save &amp; next (Enter)</button></div>
  <div class="muted" id="saved" style="margin-top:10px"></div>
</form></main>
<script>
let items = [], i = 0;
const $ = id => document.getElementById(id);
async function load() {
  items = await (await fetch('api/items')).json();
  i = items.findIndex(x => !x.label); if (i < 0) i = items.length - 1; show();
}
function show() {
  const it = items[i], v = it.label || it.prefill;
  $('img').src = 'img/' + it.id;
  $('title').textContent = `Receipt ${i + 1} of ${items.length}` + (it.label ? ' (saved)' : '');
  $('merchant').value = v.merchant || ''; $('date').value = v.date || ''; $('total').value = v.total ?? '';
  $('unreadable').checked = !!v.unreadable;
  const done = items.filter(x => x.label).length;
  $('bar').style.width = (100 * done / items.length) + '%';
  $('saved').textContent = `${done} saved`;
  $('merchant').focus();
}
$('f').onsubmit = async e => {
  e.preventDefault();
  const label = { merchant: $('merchant').value.trim(), date: $('date').value.trim(),
                  total: $('total').value.trim(), unreadable: $('unreadable').checked };
  const r = await fetch('api/label', { method:'POST', headers:{'Content-Type':'application/json'},
                                      body: JSON.stringify({ id: items[i].id, label }) });
  if (!r.ok) { $('saved').textContent = 'Not saved: ' + await r.text(); return; }
  items[i].label = label;
  if (i < items.length - 1) { i++; show(); return; }
  show();
  const left = items.filter(x => !x.label).length;
  $('saved').textContent = left ? `Saved. ${left} still to do: use Back to find them.` : `All ${items.length} saved. You can close this page.`;
};
$('back').onclick = () => { if (i > 0) { i--; show(); } };
load();
</script></body></html>"""


def queue():
    return json.loads((DATA / "label_queue.json").read_text())


def labels():
    return json.loads(LABELS.read_text()) if LABELS.exists() else {}


def prefill(rid):
    """Most common non-empty answer across the runs, field by field."""
    votes = {"merchant": Counter(), "date": Counter(), "total": Counter()}
    for run in (DATA / "runs").glob("*.jsonl"):
        for line in run.open():
            rec = json.loads(line)
            if rec.get("id") != rid or not rec.get("raw"):
                continue
            try:
                d = json.loads(rec["raw"])
            except json.JSONDecodeError:
                continue
            if d.get("merchant_name"):
                votes["merchant"][str(d["merchant_name"]).strip()] += 1
            if d.get("date"):
                votes["date"][str(d["date"]).strip()] += 1
            if isinstance(d.get("total"), (int, float)):
                votes["total"][f"{d['total']:.2f}"] += 1
    return {k: (c.most_common(1)[0][0] if c else "") for k, c in votes.items()}


class Handler(BaseHTTPRequestHandler):
    def send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self.send(200, PAGE, "text/html; charset=utf-8")
        if self.path == "/api/items":
            done = labels()
            return self.send(200, json.dumps([{"id": r, "prefill": prefill(r), "label": done.get(r)} for r in queue()]))
        if self.path.startswith("/img/"):
            rid = self.path[5:]
            if ID_RE.match(rid) and rid in queue():
                return self.send(200, (DATA / "sample" / f"{rid}.jpg").read_bytes(), "image/jpeg")
        self.send(404, "not found", "text/plain")

    def do_POST(self):
        if self.path != "/api/label":
            return self.send(404, "not found", "text/plain")
        try:
            body = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length", 0)), 10_000)))
            rid, lab = body["id"], body["label"]
            assert ID_RE.match(rid) and rid in queue()
            clean = {k: str(lab.get(k, ""))[:200] for k in ("merchant", "date", "total")}
            clean["unreadable"] = bool(lab.get("unreadable"))
        except Exception:
            return self.send(400, "bad label", "text/plain")
        all_labels = labels()
        all_labels[rid] = clean
        tmp = LABELS.with_suffix(".tmp")
        tmp.write_text(json.dumps(all_labels, indent=1))
        os.replace(tmp, LABELS)
        self.send(200, "{}")

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    host, port = sys.argv[2], int(sys.argv[3])
    assert host not in ("0.0.0.0", "::", ""), "bind to the Tailscale address only"
    ThreadingHTTPServer((host, port), Handler).serve_forever()
