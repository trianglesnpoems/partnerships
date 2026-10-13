#!/usr/bin/env python3
"""Rule-based triage: obvious non-fits get a record WITHOUT web research so agent time goes to accounts that could matter.
Writes results/triage.json in the same record schema the research agents use. Research records always win over triage.
Usage: triage.py <build2_dir> <done_names_json>"""
import json, sys, re, os
B = sys.argv[1]; done = set(json.load(open(sys.argv[2])))
acc = json.load(open(f"{B}/accounts_input.json"))
g = lambda d, k: (d.get(k) or "").strip()

GOV = {"Defense Commissary Agency": "US Department of Defense agency (commissaries.com); federal procurement, not a Shopify merchant.",
       "U S Government Printing Office": "Federal agency (gpo.gov)."}
EDU = {"Elizabethtown College", "La Sierra University", "Memorial University, Newfoundland and Labrador", "Messiah University", "Stevenson University",
       "Texas Southern University", "The University of Winnipeg", "Western Kentucky University"}
BAD = {"Jessica English": "A person's name with a university domain (salisbury.edu) — not a company record.",
       "Engg": "Placeholder record (engg.com) with no identifiable business.",
       "Infiniti": "Record points at infinitinews.com, a Nissan press site, not a merchant.",
       "Jeep Japan": "Regional automaker marketing site, not a merchant account."}
NONMERCH = {"SonicWall": "Cybersecurity vendor selling through channel partners; no consumer or Shopify-shaped storefront. 118 contacts in the book, but not a Shopify prospect.",
            "Logitech Support": "A support portal (logi.com) standing in for Logitech; not an account Anatta or Shopify would sell into through this list.",
            "American Bar Association": "Professional association; publications store is incidental.",
            "New England Journal Of Medicine": "Medical journal / publisher; subscription business, not commerce.",
            "Chicago Reader, Inc.": "Alt-weekly newspaper; WooCommerce merch store is incidental.",
            "Shedd Aquarium": "Nonprofit aquarium; ticketing and a small gift shop."}
DISTRESS = {"Lucky Vitamin (Acquired by Fruit Yield)": "Acquired and absorbed; the standalone business no longer exists as a prospect.",
            "Martha Stewart Living Omnimedia, Inc.": "Entity dissolved into Marquee Brands; wholeliving.com is a legacy domain."}
DEALERS = {"Daytona Dodge Chrysler Jeep & Ram", "Garber Buick", "Gunn Buick GMC", "Hennessy Jaguar", "New Country Motor Car Group"}

def crux_low(bw): return g(bw, "CRuX Rank") in ("", "Top 50m")
out = []
for a in acc:
    if a["name"] in done: continue
    bw = a["builtwith"]; f = a["fire"]; nm = a["name"]
    rec = None
    base = {"name": nm, "domain": a["domain"], "category": "", "model": "Other", "size_est": "not researched (rule triage)", "platform_confirmed": g(bw, "eCommerce Platform") or "none detected",
            "hq": "", "ownership": "", "shopify": {"whitespace": 0, "scale": 0, "model_fit": 0, "unified": 0, "timing": 0, "ecosystem": 0, "penalties": 0, "penalty_reason": ""},
            "anatta": {"brand_surface": 0, "modernization": 0, "scale": 0, "ltv": 0}, "gate": "", "gate_reason": "", "story": "", "shopify_angle": "", "anatta_angle": "",
            "evidence": [], "flags": ["Triaged by rule, not researched — re-open if the account matters"], "confidence": "low"}
    if nm in GOV:
        rec = {**base, "category": "Government", "model": "Government", "gate": "gov", "gate_reason": GOV[nm], "story": "Not a Shopify prospect: " + GOV[nm],
               "shopify": {**base["shopify"], "penalties": -40, "penalty_reason": "government"}}
    elif nm in EDU or a["domain"].endswith(".edu"):
        rec = {**base, "category": "Higher education", "model": "Education", "gate": "non_merchant", "gate_reason": "University / college — campus-store commerce is incidental and procured separately.",
               "story": "Not a Shopify prospect off the bat: a university. FIRE intent likely reflects a bookstore or athletics vendor search, not a replatform.",
               "shopify": {**base["shopify"], "model_fit": 2, "penalties": -20, "penalty_reason": "education"}}
    elif nm in BAD:
        rec = {**base, "category": "Bad record", "gate": "bad_record", "gate_reason": BAD[nm], "story": BAD[nm], "shopify": {**base["shopify"], "penalties": -40, "penalty_reason": "bad record"}}
    elif nm in NONMERCH:
        rec = {**base, "category": "Non-merchant", "gate": "non_merchant", "gate_reason": NONMERCH[nm], "story": "Not a Shopify prospect off the bat: " + NONMERCH[nm],
               "shopify": {**base["shopify"], "model_fit": 3, "scale": 5, "penalties": -25, "penalty_reason": "not a merchant"}}
    elif nm in DISTRESS:
        rec = {**base, "category": "Absorbed / defunct", "gate": "distress", "gate_reason": DISTRESS[nm], "story": DISTRESS[nm], "shopify": {**base["shopify"], "penalties": -30, "penalty_reason": "absorbed"}}
    elif nm in DEALERS:
        rec = {**base, "category": "Auto dealership", "model": "Services",
               "shopify": {"whitespace": 4, "scale": 6, "model_fit": 3, "unified": 2, "timing": 1, "ecosystem": 3, "penalties": -15, "penalty_reason": "services-only, no product catalogue"},
               "anatta": {"brand_surface": 3, "modernization": 6, "scale": 8, "ltv": 3},
               "story": "A car dealership: inventory listings and service booking, not a product catalogue. Dealer DMS/OEM platforms run the web presence; no Shopify replatform story and no Anatta engagement."}
    elif a["contacts"]["count"] == 0 and not g(bw, "eCommerce Platform") and crux_low(bw) and f["intent"] not in ("High", "Medium") and not f["in_market"]:
        rec = {**base, "category": "Long tail", "model": "Other",
               "shopify": {"whitespace": 6, "scale": 2, "model_fit": 6, "unified": 2, "timing": 1, "ecosystem": 3, "penalties": 0, "penalty_reason": ""},
               "anatta": {"brand_surface": 4, "modernization": 5, "scale": 2, "ltv": 3},
               "story": "Long tail by rule: no contacts in any export, no online store detected by BuiltWith, negligible web traffic and no FIRE intent. Not researched; re-open if a contact or signal appears."}
    if rec: out.append(rec)
os.makedirs(f"{B}/results", exist_ok=True)
json.dump({"accounts": out}, open(f"{B}/results/triage.json", "w"), indent=0, ensure_ascii=False)
triaged = {r["name"] for r in out}
remaining = [a for a in acc if a["name"] not in done and a["name"] not in triaged]
print("triaged", len(out), "| already researched", len(done), "| remaining for research", len(remaining))
for r in out: print(f'  {r["gate"] or "T4-rule":12s} {r["name"]}')
json.dump([a["name"] for a in remaining], open(f"{B}/remaining.json", "w"))
