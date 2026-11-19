#!/usr/bin/env python3
"""Rule-based triage for one rep's book. Universities are gated by rule. A book can also name owner and holding
entities to gate without research (book.json "triage": {"holding": {account name: reason}}): a private-equity firm or a
holding company runs no storefront, and the companies it owns sit on their own rows. "research_anyway" lists accounts
the university rule would catch by name but that are stores in their own right.
Every other account is researched (obvious non-fits get a one-search pass, see make_batches.py).
Writes results/triage.json in the research record schema. Research records always win over triage.
Usage: triage.py <build_dir> [book_json]"""
import json, sys, os, re
B = sys.argv[1]
book = json.load(open(sys.argv[2])) if len(sys.argv) > 2 else {}
HOLDING = book.get("triage", {}).get("holding", {})      # account name -> plain-English reason
KEEP = set(book.get("triage", {}).get("research_anyway", []))   # a store whose name merely starts with "University"
acc = json.load(open(f"{B}/accounts_input.json"))
assert all(n in {a["name"] for a in acc} for n in HOLDING), [n for n in HOLDING if n not in {a["name"] for a in acc}]
g = lambda d, k: (d.get(k) or "").strip()
out = []
for a in acc:
    nm, bw = a["name"], a["builtwith"]
    edu = bool(re.match(r"university\b", nm, re.I) or a["domain"].endswith(".edu")) and nm not in KEEP
    if not (edu or nm in HOLDING): continue
    f, raw = a["fire"], a["signals_raw"]
    noise = [t for t, on in [("High intent", f["intent"] == "High"), ("Medium intent", f["intent"] == "Medium"), ("an In-market flag", f["in_market"]),
                             ("a website visit", raw["website_visit"] == "true"), ("a key-page visit", raw["key_page_visit"] == "true")] if on]
    base = {"name": nm, "domain": a["domain"], "size_est": "not researched (rule triage)", "platform_confirmed": g(bw, "eCommerce Platform") or "none detected",
            "hq": "", "ownership": "", "anatta": {"brand_surface": 0, "modernization": 0, "scale": 0, "ltv": 0}, "gate": "non_merchant",
            "shopify_angle": "", "anatta_angle": "", "evidence": [], "confidence": "low"}
    if edu:
        out.append({**base, "category": "Higher education", "model": "Education",
                    "shopify": {"whitespace": 0, "scale": 0, "model_fit": 2, "unified": 0, "timing": 0, "ecosystem": 0, "penalties": -20, "penalty_reason": "education"},
                    "gate_reason": "University — campus-store commerce is incidental and procured separately.",
                    "story": "Not a Shopify prospect: a university." + (f" Our signal here ({', '.join(noise)}) most likely resolved to a campus network, not a buyer." if noise else ""),
                    "flags": ["Triaged by rule, not researched"] + ([f"Carries {', '.join(noise)} in our data: treat as noise"] if noise else [])})
    else:
        out.append({**base, "category": "Owner / holding entity", "model": "Other", "platform_confirmed": "No storefront of its own",
                    "shopify": {"whitespace": 0, "scale": 0, "model_fit": 0, "unified": 0, "timing": 0, "ecosystem": 0, "penalties": -25, "penalty_reason": "owner or holding entity, not a merchant"},
                    "gate_reason": HOLDING[nm], "story": "Not a Shopify prospect in itself. " + HOLDING[nm],
                    "flags": ["Triaged by rule, not researched"] + ([f"Carries {', '.join(noise)} in our data: it belongs to the owner, not to a storefront"] if noise else [])})
os.makedirs(f"{B}/results", exist_ok=True)
json.dump({"accounts": out}, open(f"{B}/results/triage.json", "w"), indent=0, ensure_ascii=False)
triaged = {r["name"] for r in out}
json.dump([a["name"] for a in acc if a["name"] not in triaged], open(f"{B}/remaining.json", "w"))
print("triaged", len(out), "| remaining for research", len(acc) - len(out))
for r in out: print(f'  {r["gate"]:12s} {r["category"][:24]:24s} {r["name"]}')
