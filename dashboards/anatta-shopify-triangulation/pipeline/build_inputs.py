#!/usr/bin/env python3
"""Build the per-account research input set: accounts export + BuiltWith + contact stats.
Usage: build_inputs.py <builtwith_csv> <accounts_csv> <contacts_dir_old> <contacts3_csv> <out_json>"""
import csv, sys, json, re, glob, collections
g = lambda r, k: (r.get(k) or "").strip()
def ckey(r):
    g2 = lambda k: (r.get(k) or "").strip().lower()
    return g2("Email") or g2("Person Linkedin Url") or (g2("First Name") + "|" + g2("Last Name") + "|" + g2("Company Name"))
bw_path, ac_path, old_dir, c3_path, out = sys.argv[1:6]
bw = [r for r in csv.DictReader(open(bw_path, newline='', encoding='utf-8-sig'))
      if "." in g(r, "Root Domain") and not g(r, "Root Domain").lower().startswith("compliance")]
ac = list(csv.DictReader(open(ac_path, newline='', encoding='utf-8-sig')))
contacts = []
for f in sorted(glob.glob(old_dir + "/*contacts*.csv")) + [c3_path]:
    contacts += list(csv.DictReader(open(f, newline='', encoding='utf-8-sig')))
seen = {}
for r in contacts:
    k = ckey(r)
    if k.strip("|") and k not in seen: seen[k] = r
contacts = list(seen.values())

def dom(u): return re.sub(r"^https?://(www\.)?", "", (u or "").strip().lower()).strip("/")
def norm(s): return re.sub(r"[^a-z0-9]+", " ", s.replace("®", "").lower()).strip()
ALIAS = {"federated co operatives ltd": "co op"}  # FCL's Apollo account is listed as "Co-op" (co-op.crs)
bwd = {g(b, "Root Domain").lower(): b for b in bw}
APPS = ["Salesforce Commerce Cloud", "Salesforce Marketing Cloud Personalisation", "Recharge Payments", "Klaviyo", "Intelligems",
        "Shopify Plus", "Kustomer", "Gladly", "Yotpo", "Vercel", "Adyen", "Okendo", "Dynamic Yield", "Constructor IO", "OrderGroove", "route"]
def stack(b):
    s = {k: g(b, k) for k in ["eCommerce Platform", "CMS Platform", "CRM Platform", "Marketing Automation Platform", "Payment Platforms",
                               "CRuX Rank", "Cloudflare Rank", "Agency", "Hosting Provider", "AI", "Compliance"] if g(b, k)}
    det = []
    for a in APPS:
        last = g(b, a + " Last Detected"); first = g(b, a + " First Detected")
        if g(b, a) == "Yes" or last:
            det.append(f"{a} ({'live' if g(b, a) == 'Yes' else 'seen'}; first {first or '?'}, last {last or '?'})")
    if det: s["Detected apps"] = "; ".join(det)
    return s

by_co = collections.defaultdict(list)
for c in contacts: by_co[ALIAS.get(norm(g(c, "Company Name")), norm(g(c, "Company Name")))].append(c)

def cstats(key):
    cs = by_co.get(key, [])
    titles = collections.Counter(g(c, "Title") for c in cs if g(c, "Title"))
    sen = [t for t, _ in titles.most_common() if re.search(r"chief|ceo|cfo|coo|cmo|cio|cto|president|founder|owner|vp|vice president|director", t, re.I)][:8]
    return {"count": len(cs), "sample_titles": sen, "countries": dict(collections.Counter(g(c, "Country") or "?" for c in cs).most_common(4))}

accounts = []
for a in ac:
    d = dom(a["Website"]); b = bwd.get(d, {})
    accounts.append({
        "name": a["Company Name"].strip(), "domain": d, "website": g(a, "Website"), "linkedin": g(a, "Company Linkedin Url"),
        "fire": {"intent": g(a, "FIRE_Intent"), "score": g(a, "FIRE_Score_Total"), "in_market": g(a, "In-market") == "true",
                 "signals": g(a, "FIRE_Signals"), "recency": g(a, "FIRE_Recency"), "engagement": g(a, "FIRE_Engagement"),
                 "last_signal": g(a, "FIRE_Last_Signal_At")},
        "storeleads": {k: g(a, k) for k in ["Est. GMV (storeleads)", "CMS (storeleads)", "Headless (storeleads)"] if g(a, k)},
        "mobile_score": g(a, "Mobile Score (PSI)"), "builtwith": stack(b) if b else {"note": "no BuiltWith row"},
        "contacts": cstats(norm(a["Company Name"])), "in_accounts_export": True,
    })
# companies that have contacts but no account row
listed = {norm(a["Company Name"]) for a in ac} | set(ALIAS.values())
EXTRA = {"ubreakifix": ("uBreakiFix", "ubreakifix.com"), "kings peterson s nuts summer harvest king nut company": ("King Nut Company", "kingnut.com")}
for k, cs in by_co.items():
    if k and k not in listed and k in EXTRA:
        nm, d = EXTRA[k]
        accounts.append({"name": nm, "domain": d, "website": "http://www." + d, "linkedin": "",
                         "fire": {"intent": "", "score": "", "in_market": False, "signals": "", "recency": "", "engagement": "", "last_signal": ""},
                         "storeleads": {}, "mobile_score": "", "builtwith": {"note": "not in accounts export; no BuiltWith row"},
                         "contacts": cstats(k), "in_accounts_export": False})
unknown = [k for k in by_co if k and k not in listed and k not in EXTRA]
assert not unknown, f"contact companies with no account mapping: {unknown}"
accounts.sort(key=lambda a: a["name"].lower())
json.dump(accounts, open(out, "w"), indent=0, ensure_ascii=False)
print("accounts", len(accounts), "| unique contacts", len(contacts), "| accounts with contacts", sum(1 for a in accounts if a["contacts"]["count"]),
      "| with BuiltWith", sum(1 for a in accounts if "note" not in a["builtwith"]), "| bytes", len(json.dumps(accounts)))
