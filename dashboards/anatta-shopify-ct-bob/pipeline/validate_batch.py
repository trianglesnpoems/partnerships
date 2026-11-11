#!/usr/bin/env python3
"""Validate one research result file against its batch (names, schema, ranges). Exit 1 with a list of problems.
Usage: validate_batch.py <build_dir> <batch_id>"""
import json, sys
B, bid = sys.argv[1], sys.argv[2]
names = next(b["names"] for b in json.load(open(f"{B}/batches/index.json")) if b["id"] == bid)
MODELS = ['DTC brand', 'Omni retailer', 'Grocery', 'B2B / wholesale', 'Restaurant / hospitality', 'Franchise services', 'Services', 'Education',
          'Government', 'Media / publishing', 'Direct selling', 'Other']
GATES = ['', 'already_plus', 'gov', 'distress', 'non_merchant', 'bad_record', 'restricted']
SH = {"whitespace": 25, "scale": 20, "model_fit": 20, "unified": 15, "timing": 10, "ecosystem": 10}
AN = {"brand_surface": 20, "modernization": 20, "scale": 20, "ltv": 20}
STR = ["name", "domain", "category", "size_est", "platform_confirmed", "hq", "ownership", "gate_reason", "story", "shopify_angle", "anatta_angle"]
err = []
try:
    d = json.load(open(f"{B}/results/{bid}.json"))
except Exception as e:
    print("PROBLEM: cannot read results file:", e); sys.exit(1)
recs = d.get("accounts") if isinstance(d, dict) else None
if not isinstance(recs, list): print("PROBLEM: top level must be {\"accounts\": [...]}"); sys.exit(1)
got = [r.get("name") for r in recs]
for n in names:
    if got.count(n) != 1: err.append(f"account {n!r} appears {got.count(n)} times (need exactly 1, spelled exactly)")
for n in got:
    if n not in names: err.append(f"unknown account name {n!r}")
is_int = lambda v: isinstance(v, int) and not isinstance(v, bool)
for r in recs:
    n = r.get("name")
    for k in STR:
        if not isinstance(r.get(k), str): err.append(f"{n}: {k} must be a string")
    if r.get("model") not in MODELS: err.append(f"{n}: model must be one of {MODELS}")
    if r.get("gate") not in GATES: err.append(f"{n}: gate must be one of {GATES}")
    if r.get("gate") and not (r.get("gate_reason") or "").strip(): err.append(f"{n}: a gate needs a plain-English gate_reason")
    if r.get("confidence") not in ("high", "med", "low"): err.append(f"{n}: confidence must be high|med|low")
    s, a = r.get("shopify") or {}, r.get("anatta") or {}
    for k, mx in SH.items():
        if not (is_int(s.get(k)) and 0 <= s[k] <= mx): err.append(f"{n}: shopify.{k} must be an integer 0..{mx}")
    if not (is_int(s.get("penalties")) and -100 <= s["penalties"] <= 0): err.append(f"{n}: shopify.penalties must be an integer -100..0")
    if not isinstance(s.get("penalty_reason"), str): err.append(f"{n}: shopify.penalty_reason must be a string")
    if is_int(s.get("penalties")) and s["penalties"] < 0 and not (s.get("penalty_reason") or "").strip(): err.append(f"{n}: a penalty needs a penalty_reason")
    for k, mx in AN.items():
        if not (is_int(a.get(k)) and 0 <= a[k] <= mx): err.append(f"{n}: anatta.{k} must be an integer 0..{mx}")
    ev = r.get("evidence")
    if not isinstance(ev, list) or any(not (isinstance(e, dict) and isinstance(e.get("claim"), str) and isinstance(e.get("source"), str)) for e in ev):
        err.append(f"{n}: evidence must be a list of {{claim, source}}")
    elif not ev: err.append(f"{n}: at least one evidence item is required")
    elif any(not e["source"].startswith("http") for e in ev): err.append(f"{n}: every evidence source must be a URL")
    if not isinstance(r.get("flags"), list) or any(not isinstance(x, str) for x in r.get("flags", [])): err.append(f"{n}: flags must be a list of strings")
    if not r.get("gate") and not (r.get("story") or "").strip(): err.append(f"{n}: story is empty")
if err:
    print(f"{len(err)} PROBLEM(S):"); [print(" -", e) for e in err]; sys.exit(1)
print(f"OK: {len(recs)} records valid for {bid}")
