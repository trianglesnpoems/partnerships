#!/usr/bin/env python3
"""Assemble the single-file triangulation dashboard for one rep's book.
Writes an internal and a shareable copy, each as a standalone HTML file, as a page fragment for publishing as a
claude.ai artifact (which supplies its own <html>/<head>/<body>), and as a CSV of the scored book.

Internal copy: shows which accounts are in Salesforce and the "how far to trust our own signal" section.
Shareable copy: those are removed from the DATA, not just hidden, and the build asserts they are gone.
Neither copy ever contains a Salesforce record ID.

Usage: assemble.py <scored.json> <out_dir>"""
import csv, json, sys, os, re, copy
scored_p, OUT = sys.argv[1:3]
here = os.path.dirname(os.path.abspath(__file__))
tpl = open(os.path.join(here, "dashboard.html"), encoding="utf-8").read()
head, body = re.match(r"<!--HEAD-->\n(.*?)<!--/HEAD-->\n(.*)$", tpl, re.S).groups()
sc = json.load(open(scored_p))
import html as _html
TITLE, SLUG = sc["summary"]["title"], sc["summary"]["slug"]
assert head.count("__TITLE__") == 1
head = head.replace("__TITLE__", _html.escape(TITLE))
ICON = "<link rel=\"icon\" href=\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Cpath d='M8 2 L14.5 13.5 L1.5 13.5 Z' fill='none' stroke='%232a78d6' stroke-width='1.7' stroke-linejoin='round'/%3E%3C/svg%3E\">"
SFDC_ID = re.compile(r"\b001[A-Za-z0-9]{12,15}\b")
INTERNAL_ONLY_ACCOUNT_KEYS = ["in_sfdc"]
INTERNAL_ONLY_SUMMARY_KEYS = ["not_in_sfdc"]
INTERNAL_FLAG = re.compile(r"\bCRM\b|\bin salesforce\b|\bSFDC\b", re.I)   # notes about our own records stay inside

def build(internal, target):
    accounts, summary = copy.deepcopy(sc["accounts"]), copy.deepcopy(sc["summary"])
    if not internal:
        for a in accounts:
            for k in INTERNAL_ONLY_ACCOUNT_KEYS: a.pop(k, None)
            if "flags" in a: a["flags"] = [f for f in a["flags"] if not INTERNAL_FLAG.search(f)]
        for k in INTERNAL_ONLY_SUMMARY_KEYS: summary.pop(k, None)
    data = {"internal": internal, "target": target, "summary": summary, "accounts": accounts}
    blob = json.dumps(data, separators=(",", ":"), ensure_ascii=False).replace("<", "\\u003c")
    assert not SFDC_ID.search(blob), "a Salesforce record ID is in the data"
    if not internal:
        assert '"in_sfdc"' not in blob and '"not_in_sfdc"' not in blob, "internal-only field left in the shareable copy"
        assert not any(INTERNAL_FLAG.search(f) for a in accounts for f in a.get("flags", [])), "internal CRM note left in the shareable copy"
    page = body.replace("__DATA__", blob)
    assert "__DATA__" not in page and page.count('id="data"') == 1
    if target == "artifact":
        return head + page
    return ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n"
            + ICON + "\n" + head + "</head>\n<body>\n" + page + "</body>\n</html>\n")

CSV_COLS = ["name", "display", "group", "domain", "book_domain", "tier", "triangle", "shopify_fit", "anatta_fit", "gate", "gate_reason", "category", "model",
            "plat", "platform", "size_est", "hq", "ownership", "confidence", "fire_score", "fire_intent", "fire_in_market", "fire_signals",
            "fire_last_signal", "story", "shopify_angle", "anatta_angle", "flags", "adjustments"]
def write_csv(path, internal):
    cols = CSV_COLS + (["in_salesforce"] if internal else [])
    def val(a, k):
        if k.startswith("fire_"): return a["fire"][k[5:]]
        if k == "flags": return " | ".join(f for f in a.get("flags", []) if internal or not INTERNAL_FLAG.search(f))
        if k == "adjustments": return " | ".join(a.get("adjustments", []))
        if k == "in_salesforce": return "yes" if a["in_sfdc"] else "no"
        return a.get(k, "")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(cols)
        for a in sc["accounts"]: w.writerow([val(a, k) for k in cols])
    text = open(path, encoding="utf-8").read()
    assert not SFDC_ID.search(text), "a Salesforce record ID is in the CSV"
    if not internal: assert "in_salesforce" not in text
    print(f"{os.path.relpath(path, OUT):55s} {len(text.encode('utf-8')) / 1024:6.0f} KB  {'internal' if internal else 'shareable'}/csv")

os.makedirs(f"{OUT}/artifact", exist_ok=True)
for internal in (True, False):
    kind = "internal" if internal else "shareable"
    for target, path in (("file", f"{OUT}/{SLUG}-{kind}.html"), ("artifact", f"{OUT}/artifact/{SLUG}-{kind}.html")):
        html = build(internal, target)
        open(path, "w", encoding="utf-8").write(html)
        print(f"{os.path.relpath(path, OUT):55s} {len(html.encode('utf-8')) / 1024:6.0f} KB  {kind}/{target}")
    write_csv(f"{OUT}/{SLUG}-accounts-{kind}.csv", internal)
t = sc["summary"]["tiers"]
print("accounts", sc["summary"]["accounts"], "| tiers", {k: t[k] for k in sorted(t)})
