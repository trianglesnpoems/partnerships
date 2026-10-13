#!/usr/bin/env python3
"""Assemble the single-file triangulation dashboard (masked + internal variants).
Usage: assemble2.py <scored.json> <hubs.json> <libs_dir> <out_dir> [rework_count]"""
import json, sys, os, re, copy
scored_p, hubs_p, LIB, OUT = sys.argv[1:5]
rework_count = int(sys.argv[5]) if len(sys.argv) > 5 else 0
here = os.path.dirname(os.path.abspath(__file__))
tpl = open(os.path.join(here, "dashboard.html"), encoding="utf-8").read()
sc = json.load(open(scored_p)); hb = json.load(open(hubs_p))

def norm(s): return re.sub(r"[^a-z0-9]+", " ", s.replace("®", "").lower()).strip()
ALIAS = {"federated co operatives ltd": "co op", "kings peterson s nuts summer harvest king nut company": "king nut company"}
acct_idx = {norm(a["name"]): i for i, a in enumerate(sc["accounts"])}
contacts = []
unjoined = set()
for c in hb["contacts"]:
    key = ALIAS.get(norm(c["company"]), norm(c["company"]))
    i = acct_idx.get(key)
    if i is None and c["company"] not in ("(no company listed)",): unjoined.add(c["company"])
    contacts.append({**{k: c[k] for k in ["id", "first", "last", "title", "company", "email", "linkedin", "city", "state", "country", "seniority", "func", "intent", "inmarket", "hub", "region"]},
                     "acct": i, "acctName": sc["accounts"][i]["name"] if i is not None else ""})
assert not unjoined, f"contacts whose company has no account row: {sorted(unjoined)}"
assert len(contacts) == hb["summary"]["unique_contacts"]
mapped = sum(1 for c in contacts if c["hub"] is not None)
assert mapped == hb["summary"]["mapped"] == sum(h["n"] for h in hb["hubs"])

hubs = [{k: h[k] for k in ["id", "name", "seed", "lat", "lng", "country", "inset", "region", "n", "accounts", "cities", "contacts"]} for h in hb["hubs"]]
hub_summary = {**{k: v for k, v in hb["summary"].items() if k != "accounts_without_contacts"},
               "override_count": sum(1 for c in hb["contacts"] if c["geo"] == "override")}
summary = {**sc["summary"], "generated": "2026-10-13", "rework_count": rework_count}

def safe(s): return s.replace("</", "<\\/")
libs = {"__D3__": open(f"{LIB}/d3-7.9.0/dist/d3.min.js").read(), "__TOPOJSON__": open(f"{LIB}/topojson-client-3.1.0/dist/topojson-client.min.js").read(),
        "__COUNTRIES__": safe(open(f"{LIB}/na-countries-50m.json").read()), "__STATES__": safe(open(f"{LIB}/us-atlas-3.0.1/states-10m.json").read())}
def mask(email):
    if not email: return ""
    local, _, dom = email.partition("@"); return f"{local[:1]}•••@{dom}"
os.makedirs(OUT, exist_ok=True)
raw_emails = [c["email"] for c in contacts]
for masked, fname in [(True, "anatta-shopify-triangulation.html"), (False, "anatta-shopify-triangulation-internal.html")]:
    cs = copy.deepcopy(contacts)
    if masked:
        for c in cs: c["email"] = mask(c["email"])
    data = {"masked": masked, "summary": summary, "accounts": sc["accounts"], "hubs": hubs, "contacts": cs, "hub_summary": hub_summary}
    html = tpl.replace("__DATA__", safe(json.dumps(data, separators=(",", ":"), ensure_ascii=False)))
    for k, v in libs.items(): html = html.replace(k, v)
    for k in ["__DATA__", "__D3__", "__TOPOJSON__", "__COUNTRIES__", "__STATES__"]: assert k not in html
    if masked:
        leaked = [e for e in raw_emails if e and e in html]
        assert not leaked, f"unmasked emails leaked into masked build: {leaked[:3]}"
        assert sum(1 for c in cs if "•••@" in c["email"]) == sum(1 for c in contacts if c["email"])
    open(f"{OUT}/{fname}", "w", encoding="utf-8").write(html)
    print(fname, f"{os.path.getsize(f'{OUT}/{fname}')/1024:.0f} KB", "masked" if masked else "UNMASKED")
print("accounts", len(sc["accounts"]), "| contacts", len(contacts), "| joined to account", sum(1 for c in contacts if c["acct"] is not None), "| hubs", len(hubs))
