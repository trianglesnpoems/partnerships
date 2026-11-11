#!/usr/bin/env python3
"""Rule-based triage for one rep's book. Only universities are gated by rule; a book is small (tens of accounts) and the
CRuX column is unreliable, so every other account is researched (obvious non-fits get a one-search pass, see make_batches.py).
Writes results/triage.json in the research record schema. Research records always win over triage.
Usage: triage.py <build_dir>"""
import json, sys, os, re
B = sys.argv[1]
acc = json.load(open(f"{B}/accounts_input.json"))
g = lambda d, k: (d.get(k) or "").strip()
out = []
for a in acc:
    nm, bw = a["name"], a["builtwith"]
    if not (re.match(r"university\b", nm, re.I) or a["domain"].endswith(".edu")): continue
    f, raw = a["fire"], a["signals_raw"]
    noise = [t for t, on in [("Medium intent", f["intent"] == "Medium"), ("an In-market flag", f["in_market"]),
                             ("a website visit", raw["website_visit"] == "true"), ("a key-page visit", raw["key_page_visit"] == "true")] if on]
    out.append({
        "name": nm, "domain": a["domain"], "category": "Higher education", "model": "Education", "size_est": "not researched (rule triage)",
        "platform_confirmed": g(bw, "eCommerce Platform") or "none detected", "hq": "", "ownership": "",
        "shopify": {"whitespace": 0, "scale": 0, "model_fit": 2, "unified": 0, "timing": 0, "ecosystem": 0, "penalties": -20, "penalty_reason": "education"},
        "anatta": {"brand_surface": 0, "modernization": 0, "scale": 0, "ltv": 0},
        "gate": "non_merchant", "gate_reason": "University — campus-store commerce is incidental and procured separately.",
        "story": "Not a Shopify prospect: a university." + (f" Our signal here ({', '.join(noise)}) most likely resolved to a campus network, not a buyer." if noise else ""),
        "shopify_angle": "", "anatta_angle": "", "evidence": [],
        "flags": ["Triaged by rule, not researched"] + ([f"Carries {', '.join(noise)} in our data: treat as noise"] if noise else []), "confidence": "low"})
os.makedirs(f"{B}/results", exist_ok=True)
json.dump({"accounts": out}, open(f"{B}/results/triage.json", "w"), indent=0, ensure_ascii=False)
triaged = {r["name"] for r in out}
json.dump([a["name"] for a in acc if a["name"] not in triaged], open(f"{B}/remaining.json", "w"))
print("triaged", len(out), "| remaining for research", len(acc) - len(out))
for r in out: print(f'  {r["gate"]:12s} {r["name"]}')
