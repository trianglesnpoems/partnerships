#!/usr/bin/env python3
"""Validate a verifier's output file against its job list. Usage: validate_verify.py <build_dir> <lens> <part> [names_json]
The output file is <build_dir>/verify/<part>__<lens>.json = {"verdicts": [...]}, one verdict per account in the lens's
job file <build_dir>/verify_jobs/<lens>.json (or per name in names_json when the job is split between verifiers)."""
import json, sys
B, lens, part = sys.argv[1], sys.argv[2], sys.argv[3]
names = json.loads(sys.argv[4]) if len(sys.argv) > 4 else [j["name"] for j in json.load(open(f"{B}/verify_jobs/{lens}.json"))]
GATES = ['keep', '', 'already_plus', 'gov', 'distress', 'non_merchant', 'bad_record', 'restricted']
err = []
try:
    d = json.load(open(f"{B}/verify/{part}__{lens}.json"))
except Exception as e:
    print("PROBLEM: cannot read output file:", e); sys.exit(1)
vs = d.get("verdicts") if isinstance(d, dict) else None
if not isinstance(vs, list): print('PROBLEM: top level must be {"verdicts": [...]}'); sys.exit(1)
got = [v.get("name") for v in vs]
for n in names:
    if got.count(n) != 1: err.append(f"{n!r} appears {got.count(n)} times (need exactly 1, spelled exactly)")
for n in got:
    if n not in names: err.append(f"unknown account name {n!r}")
ok_fit = lambda v: v is None or (isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 100)
for v in vs:
    n = v.get("name")
    if v.get("verdict") not in ("confirmed", "adjust", "refute"): err.append(f"{n}: verdict must be confirmed|adjust|refute")
    for k in ("shopify_fit_suggested", "anatta_fit_suggested"):
        if k not in v or not ok_fit(v[k]): err.append(f"{n}: {k} must be an integer 0..100 or null")
    if v.get("gate_suggested") not in GATES: err.append(f"{n}: gate_suggested must be one of {GATES}")
    if not isinstance(v.get("reason"), str) or not v["reason"].strip(): err.append(f"{n}: reason is required")
    ev = v.get("evidence")
    if not isinstance(ev, list) or not ev or any(not (isinstance(e, dict) and isinstance(e.get("claim"), str) and str(e.get("source", "")).startswith("http")) for e in ev):
        err.append(f"{n}: evidence must be a non-empty list of {{claim, source URL}}")
    if v.get("verdict") == "adjust" and v.get("shopify_fit_suggested") is None and v.get("anatta_fit_suggested") is None:
        err.append(f"{n}: an 'adjust' verdict needs at least one suggested fit value")
    if v.get("verdict") == "confirmed" and (v.get("shopify_fit_suggested") is not None or v.get("anatta_fit_suggested") is not None or v.get("gate_suggested") != "keep"):
        err.append(f"{n}: a 'confirmed' verdict leaves both suggested fits null and gate_suggested 'keep'")
if err:
    print(f"{len(err)} PROBLEM(S):"); [print(" -", e) for e in err]; sys.exit(1)
print(f"OK: {len(vs)} verdicts valid for {part}__{lens}")
