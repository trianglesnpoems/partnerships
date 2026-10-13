#!/usr/bin/env python3
"""Authoritative scoring: merge research batch files + verifier verdicts with the account inputs,
compute both fit scores, blend, gate, tier. Single source of truth for every number on the dashboard.

Usage: score.py <build2_dir> <out_json>
"""
import json, sys, glob, os, re, collections

B, OUT = sys.argv[1], sys.argv[2]
inputs = {a["name"]: a for a in json.load(open(f"{B}/accounts_input.json"))}

# ---------- load research (rework files override batch files) ----------
records = {}
sources = {}
# precedence: triage < research batches < rework
for f in sorted(glob.glob(f"{B}/results/triage.json")) + sorted(glob.glob(f"{B}/results/batch_*.json")) + sorted(glob.glob(f"{B}/results/r_batch_*.json")) + sorted(glob.glob(f"{B}/results/rework_*.json")):
    try:
        d = json.load(open(f))
    except Exception as e:
        print("BAD JSON", f, e); continue
    for r in d.get("accounts", []):
        if r.get("name") in inputs:
            records[r["name"]] = r; sources[r["name"]] = os.path.basename(f)
        else:
            print("unknown account name in", os.path.basename(f), "->", r.get("name"))

verdicts = collections.defaultdict(list)
for f in sorted(glob.glob(f"{B}/verify/*.json")):
    try:
        v = json.load(open(f))
    except Exception as e:
        print("BAD JSON", f, e); continue
    lens = "platform" if f.endswith("__platform.json") else "model"
    v["lens"] = lens
    verdicts[v.get("name")].append(v)

# ---------- deterministic pieces ----------
def fire_intent(f):
    p = {"High": 10, "Medium": 7, "Low": 3}.get(f["intent"], 2)
    if f["in_market"]: p += 5
    s = None if f["score"] == "" else float(f["score"])
    if s is not None: p += 5 if s >= 50 else 3 if s >= 35 else 1 if s > 0 else 0
    if f["signals"]: p += 3
    return min(20, p)

def bonus(f):
    b = 0
    if f["in_market"]: b += 3
    if f["intent"] == "High": b += 3
    if re.search(r"shopify", f["signals"] or "", re.I): b += 4
    return b

GATE_TEXT = {
    "already_plus": "Already on Shopify Plus — expansion / reference, not a replatform prospect",
    "gov": "Government or military — not a Shopify merchant",
    "distress": "Financial distress, wound down or absorbed",
    "non_merchant": "No plausible commerce surface",
    "bad_record": "Not a real account record",
    "restricted": "Category Shopify cannot host",
}
clamp = lambda v, lo, hi: max(lo, min(hi, v))

out = []
for name, a in inputs.items():
    r = records.get(name)
    f = a["fire"]
    if not r:
        out.append({"name": name, "domain": a["domain"], "missing": True, "tier": "NA", "shopify_fit": None, "anatta_fit": None, "triangle": None,
                    "gate": "", "gate_reason": "", "contacts": a["contacts"]["count"], "in_accounts_export": a["in_accounts_export"]})
        continue
    s, an = r["shopify"], r["anatta"]
    sf_raw = s["whitespace"] + s["scale"] + s["model_fit"] + s["unified"] + s["timing"] + s["ecosystem"]
    sf = clamp(sf_raw + s["penalties"], 0, 100)
    intent_pts = fire_intent(f)
    af = clamp(an["brand_surface"] + an["modernization"] + an["scale"] + an["ltv"] + intent_pts, 0, 100)
    gate = r.get("gate", "") or ""
    gate_reason = r.get("gate_reason", "")
    # ---------- apply verifier verdicts ----------
    vs = verdicts.get(name, [])
    adj_notes = []
    sf_sugg = [v["shopify_fit_suggested"] for v in vs if v["verdict"] in ("adjust", "refute") and v.get("shopify_fit_suggested") is not None]
    af_sugg = [v["anatta_fit_suggested"] for v in vs if v["verdict"] in ("adjust", "refute") and v.get("anatta_fit_suggested") is not None]
    if sf_sugg:
        new = round((sf + sum(sf_sugg) / len(sf_sugg)) / 2)  # conservative: average of research and verifier views
        adj_notes.append(f"Shopify fit {sf}→{new} after verification"); sf = new
    if af_sugg:
        new = round((af + sum(af_sugg) / len(af_sugg)) / 2)
        adj_notes.append(f"Anatta fit {af}→{new} after verification"); af = new
    gate_sugg = [v["gate_suggested"] for v in vs if v["verdict"] == "refute" and v.get("gate_suggested") not in (None, "keep")]
    if gate_sugg:
        # a refuting verifier can add or remove a gate; take the first and record why
        newg = gate_sugg[0]
        if newg != gate:
            adj_notes.append(f"Gate '{gate or 'none'}'→'{newg or 'none'}' after verification")
            gate = newg
            gate_reason = next(v["reason"] for v in vs if v["verdict"] == "refute" and v.get("gate_suggested") == newg)
    # non_merchant gate only bites when the Shopify score is genuinely low
    if gate == "non_merchant" and sf >= 20:
        adj_notes.append(f"non_merchant gate ignored: Shopify fit {sf} ≥ 20"); gate = ""
    tri = min(100, round(0.55 * sf + 0.45 * af + bonus(f)))
    if gate == "already_plus": tier = "EXP"
    elif gate: tier = "X"
    elif tri >= 62 and sf >= 63: tier = "T1"
    elif tri >= 48: tier = "T2"
    elif tri >= 36: tier = "T3"
    else: tier = "T4"
    bw = a["builtwith"]
    out.append({
        "name": name, "domain": a["domain"], "website": a["website"], "linkedin": a["linkedin"], "missing": False,
        "category": r["category"], "model": r["model"], "size_est": r["size_est"], "platform": r["platform_confirmed"],
        "hq": r["hq"], "ownership": r["ownership"],
        "shopify_sub": {k: s[k] for k in ["whitespace", "scale", "model_fit", "unified", "timing", "ecosystem", "penalties"]},
        "penalty_reason": s["penalty_reason"],
        "anatta_sub": {"brand_surface": an["brand_surface"], "modernization": an["modernization"], "scale": an["scale"], "ltv": an["ltv"], "intent": intent_pts},
        "shopify_fit": sf, "anatta_fit": af, "bonus": bonus(f), "triangle": tri, "tier": tier,
        "gate": gate, "gate_reason": gate_reason or GATE_TEXT.get(gate, ""),
        "story": r["story"], "shopify_angle": r["shopify_angle"], "anatta_angle": r["anatta_angle"],
        "evidence": r["evidence"], "flags": r["flags"], "confidence": r["confidence"],
        "verification": [{"lens": v["lens"], "verdict": v["verdict"], "reason": v["reason"]} for v in vs], "adjustments": adj_notes,
        "fire": f, "storeleads": a["storeleads"], "builtwith": {k: v for k, v in bw.items() if k != "note"},
        "contacts": a["contacts"]["count"], "contact_titles": a["contacts"]["sample_titles"], "in_accounts_export": a["in_accounts_export"],
        "source": sources.get(name),
    })

out.sort(key=lambda x: (x["triangle"] is None, -(x["triangle"] or 0), x["name"]))
tiers = collections.Counter(x["tier"] for x in out)
summary = {"accounts": len(out), "scored": sum(1 for x in out if not x["missing"]), "missing": [x["name"] for x in out if x["missing"]],
           "tiers": dict(tiers), "verified": sum(1 for x in out if x.get("verification")), "adjusted": sum(1 for x in out if x.get("adjustments")),
           "confidence": dict(collections.Counter(x.get("confidence", "n/a") for x in out)),
           "not_in_accounts_export": [x["name"] for x in out if not x["in_accounts_export"]],
           "zero_contact_accounts": sum(1 for x in out if x["contacts"] == 0)}
json.dump({"summary": summary, "accounts": out}, open(OUT, "w"), indent=0, ensure_ascii=False)
print(json.dumps(summary, indent=1))
print("\nTOP 30:")
for x in out[:30]:
    print(f'{x["tier"]:3s} tri={x["triangle"]:3} sf={x["shopify_fit"]:3} af={x["anatta_fit"]:3} c={x["contacts"]:3d} conf={x.get("confidence","-"):4s} {x["name"][:34]:34s} | {x.get("platform","")[:30]:30s} | {x.get("model","")}')
print("\nGATED:")
for x in out:
    if x["tier"] in ("X", "EXP"): print(f'{x["tier"]:3s} {x["name"][:34]:34s} gate={x["gate"]:13s} {x["gate_reason"][:80]}')
