#!/usr/bin/env python3
"""Build the per-account research input set for one rep's book: Apollo accounts export + BuiltWith export.
No contacts export is in scope for this kind of run, so contact stats are empty and there is no hub map.
Everything that names an account (domain aliases etc.) comes from book.json, which lives with the data, not in the repo.

Usage: build_inputs.py <builtwith_csv> <accounts_csv> <book_json> <out_json>"""
import csv, sys, json, re, collections

g = lambda r, k: (r.get(k) or "").strip()
bw_path, ac_path, book_path, out = sys.argv[1:5]
book = json.load(open(book_path))
bw = [r for r in csv.DictReader(open(bw_path, newline='', encoding='utf-8-sig'))
      if "." in g(r, "Root Domain") and not g(r, "Root Domain").lower().startswith("compliance")]
ac = list(csv.DictReader(open(ac_path, newline='', encoding='utf-8-sig')))

def dom(u): return re.sub(r"^https?://(www\.)?", "", (u or "").strip().lower()).strip("/")

# The BuiltWith list (the book as the rep holds it) and the Apollo view can disagree on an account's domain.
# book.json maps Apollo website domain -> {book_domain, note}; the note is what a human should know.
DOMAIN_ALIAS = {k: (v["book_domain"], v["note"]) for k, v in book.get("domain_alias", {}).items()}
bwd = {g(b, "Root Domain").lower(): b for b in bw}
STACK_KEYS = ["eCommerce Platform", "CMS Platform", "CRM Platform", "Marketing Automation Platform", "Payment Platforms",
              "CRuX Rank", "Cloudflare Rank", "Agency", "AI", "Compliance"]
# every tracked technology in the export has "<X>", "<X> First Detected", "<X> Last Detected" columns
APPS = [h[:-len(" Last Detected")] for h in (bw[0].keys() if bw else []) if h.endswith(" Last Detected")]

def stack(b):
    s = {k: g(b, k) for k in STACK_KEYS if g(b, k)}
    det = []
    for a in APPS:
        last, first = g(b, a + " Last Detected"), g(b, a + " First Detected")
        if g(b, a) == "Yes" or last:
            det.append(f"{a} ({'live' if g(b, a) == 'Yes' else 'seen'}; first {first or '?'}, last {last or '?'})")
    if det: s["Detected apps"] = "; ".join(det)
    return s

def lines(v): return [x.strip() for x in v.split("\n") if x.strip()]

accounts, used = [], set()
for a in ac:
    d = dom(a["Website"])
    bw_dom, note = DOMAIN_ALIAS.get(d, (d, ""))
    b = bwd.get(bw_dom, {})
    if b: used.add(bw_dom)
    accounts.append({
        "name": a["Company Name"].strip(), "domain": d, "website": g(a, "Website"), "linkedin": g(a, "Company Linkedin Url"),
        "book_domain": bw_dom if b else "", "domain_note": note,
        "fire": {"intent": g(a, "FIRE_Intent"), "score": g(a, "FIRE_Score_Total"), "in_market": g(a, "In-market") == "true",
                 "signals": g(a, "FIRE_Signals"), "recency": g(a, "FIRE_Recency"), "engagement": g(a, "FIRE_Engagement"),
                 "last_signal": g(a, "FIRE_Last_Signal_At")},
        # raw booleans exactly as exported ("" = blank in the export, not false)
        "signals_raw": {"in_market": g(a, "In-market"), "website_visit": g(a, "Website visit"), "key_page_visit": g(a, "Key page visit"),
                        "linkedin_engagement": g(a, "LinkedIn engagement")},
        "storeleads": {k: g(a, k) for k in ["Est. GMV (storeleads)", "CMS (storeleads)", "Headless (storeleads)"] if g(a, k)},
        "mobile_score": g(a, "Mobile Score (PSI)"),
        "apollo_builtwith": {"ecomm": lines(g(a, "BuiltWith (ecomm)")), "payments": lines(g(a, "BuiltWith (payments)"))},
        "in_sfdc": bool(g(a, "Account Salesforce ID")),   # the ID itself never leaves the export
        "builtwith": stack(b) if b else {"note": "no BuiltWith row"},
        "contacts": {"count": 0, "sample_titles": [], "countries": {}}, "in_accounts_export": True,
    })
unused = sorted(set(bwd) - used)
assert not unused, f"BuiltWith domains with no Apollo account: {unused}"
assert len({a["name"] for a in accounts}) == len(accounts), "duplicate account names"
accounts.sort(key=lambda a: a["name"].lower())
json.dump(accounts, open(out, "w"), indent=0, ensure_ascii=False)
c = collections.Counter
print("accounts", len(accounts), "| with BuiltWith row", sum(1 for a in accounts if "note" not in a["builtwith"]),
      "| domain mismatches reconciled", sum(1 for a in accounts if a["domain_note"]),
      "| no BuiltWith row:", [a["name"] for a in accounts if "note" in a["builtwith"]])
print("FIRE score present", sum(1 for a in accounts if a["fire"]["score"] != ""), "| intent", dict(c(a["fire"]["intent"] or "(blank)" for a in accounts)),
      "| in-market true", sum(1 for a in accounts if a["fire"]["in_market"]), "| signals", sum(1 for a in accounts if a["fire"]["signals"]),
      "| in SFDC", sum(1 for a in accounts if a["in_sfdc"]))
