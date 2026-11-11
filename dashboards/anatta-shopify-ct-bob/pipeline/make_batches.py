#!/usr/bin/env python3
"""Split the non-triaged accounts into research batches. Related rows (one buying centre) stay in one batch.
"full" batches get the normal 2–4 searches per account; "light" batches are accounts with no visible commerce surface
(manufacturers, processors, distributors without a store) and get one search each.
The plan itself (which account goes in which batch) is book data: it is read from book.json's "batch_plan".
Usage: make_batches.py <build_dir> <book_json> [prior_review_json]"""
import json, sys, os
B, BOOK = sys.argv[1], sys.argv[2]
prior = json.load(open(sys.argv[3])) if len(sys.argv) > 3 else {}
acc = {a["name"]: a for a in json.load(open(f"{B}/accounts_input.json"))}
remaining = set(json.load(open(f"{B}/remaining.json")))
PLAN = [(b["id"], b["depth"], b["names"]) for b in json.load(open(BOOK))["batch_plan"]]
planned = [n for _, _, names in PLAN for n in names]
assert len(planned) == len(set(planned)), "an account is in two batches"
assert set(planned) == remaining, (sorted(remaining - set(planned)), sorted(set(planned) - remaining))
os.makedirs(f"{B}/batches", exist_ok=True)
index = []
for bid, depth, names in PLAN:
    rows = []
    for n in names:
        a = dict(acc[n]); a.pop("in_sfdc", None); a.pop("contacts", None); a.pop("in_accounts_export", None)
        if a["domain"] in prior: a["prior_review"] = prior[a["domain"]]
        rows.append(a)
    json.dump(rows, open(f"{B}/batches/{bid}.json", "w"), indent=1, ensure_ascii=False)
    index.append({"id": bid, "depth": depth, "names": names, "file": f"{B}/batches/{bid}.json"})
    print(bid, depth, len(names), "accounts,", os.path.getsize(f"{B}/batches/{bid}.json") // 1024, "KB")
json.dump(index, open(f"{B}/batches/index.json", "w"), indent=1, ensure_ascii=False)
