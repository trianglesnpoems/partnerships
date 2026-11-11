#!/usr/bin/env python3
"""Pick the accounts that get an adversarial second look and write one job file per lens.
Same policy as the Oct 2026 build: provisional T1 gets both lenses (platform & scale; business model & gates), provisional T2
gets the platform lens. There are no contacts in this book, so instead of "gated with 10+ contacts" the model lens also
covers every researched gate that is a judgment call (distress, gov, already_plus).
Usage: make_verify.py <build_dir> <scored_json>"""
import json, sys, os
B, scored_p = sys.argv[1], sys.argv[2]
sc = json.load(open(scored_p))
raw = {}
for f in sorted(os.listdir(f"{B}/results")):
    if f.startswith(("batch_", "rework_")):
        for r in json.load(open(f"{B}/results/{f}"))["accounts"]: raw[r["name"]] = r
jobs = {"platform": [], "model": []}
for x in sc["accounts"]:
    if x["missing"] or x["name"] not in raw: continue
    prov = {"shopify_fit": x["shopify_fit"], "anatta_fit": x["anatta_fit"], "triangle": x["triangle"], "tier": x["tier"], "fire": x["fire"]}
    job = {"name": x["name"], "provisional": prov, "record": raw[x["name"]]}
    if x["tier"] in ("T1", "T2"): jobs["platform"].append(job)
    if x["tier"] == "T1" or x["gate"] in ("distress", "gov", "already_plus"): jobs["model"].append(job)
os.makedirs(f"{B}/verify_jobs", exist_ok=True); os.makedirs(f"{B}/verify", exist_ok=True)
for lens, L in jobs.items():
    json.dump(L, open(f"{B}/verify_jobs/{lens}.json", "w"), indent=1, ensure_ascii=False)
    print(lens, len(L), [j["name"] for j in L])
