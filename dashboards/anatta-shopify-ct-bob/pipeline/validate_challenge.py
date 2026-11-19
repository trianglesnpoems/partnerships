#!/usr/bin/env python3
"""Check one challenge file: an independent reader's attempt to knock a company out of the first ten.

    validate_challenge.py <input.json> <output.json>

The input is the dossier the reader was given ({"batch", "companies": [{"group", "claim_opening": {"signals": [...]}, ...}]}),
the output is what briefs/challenge.md asks for. Prints OK or one line per problem, and exits 1 on any problem."""
import json, re, sys

VERDICTS = ("holds", "weaker", "wrong")
STATUS = ("confirmed", "changed", "not found")


def problems(inp, out):
    bad = []
    if out.get("batch") != inp.get("batch"):
        bad.append(f'batch is {out.get("batch")!r}, the input is {inp.get("batch")!r}')
    want = [c["group"] for c in inp["companies"]]
    got = [c.get("group") for c in out.get("companies", [])]
    if sorted(got) != sorted(want):
        bad.append(f"companies differ from the input: missing {sorted(set(want) - set(got))}, extra {sorted(set(got) - set(want))}")
    asked = {c["group"]: c for c in inp["companies"]}
    for c in out.get("companies", []):
        g = c.get("group"); src = asked.get(g)
        if not src:
            continue
        if c.get("verdict") not in VERDICTS:
            bad.append(f"{g}: verdict must be one of {VERDICTS}")
        if not (isinstance(c.get("summary"), str) and 20 <= len(c["summary"]) <= 420):
            bad.append(f"{g}: summary is one or two sentences (20 to 420 characters)")
        sigs = c.get("signals")
        n = len(src["claim_opening"]["signals"])
        if not isinstance(sigs, list) or len(sigs) != n:
            bad.append(f"{g}: one entry per signal in the input, in order ({n} expected)")
            sigs = []
        for i, s in enumerate(sigs):
            if s.get("status") not in STATUS:
                bad.append(f"{g}: signal {i + 1} status must be one of {STATUS}")
            if not s.get("note"):
                bad.append(f"{g}: signal {i + 1} needs a note saying what the source says")
            if s.get("status") != "not found" and not re.match(r"https?://", s.get("source") or ""):
                bad.append(f"{g}: signal {i + 1} needs the link that was read")
        for k in ("against", "for"):
            rows = c.get(k)
            if not isinstance(rows, list):
                bad.append(f'{g}: "{k}" is a list (empty when there is nothing)')
                continue
            for r in rows:
                if not re.fullmatch(r"20\d\d-(0[1-9]|1[0-2])", r.get("date") or ""):
                    bad.append(f'{g}: an entry under "{k}" needs a date as YYYY-MM')
                if not r.get("text") or not re.match(r"https?://", r.get("source") or ""):
                    bad.append(f'{g}: an entry under "{k}" needs its text and the link that was read')
        if not isinstance(c.get("not_checked"), list):
            bad.append(f'{g}: "not_checked" is a list (empty when everything was read)')
        if c.get("verdict") == "holds" and (c.get("against") or any(s.get("status") != "confirmed" for s in sigs)):
            bad.append(f'{g}: "holds" needs every signal confirmed and nothing under "against"')
        if c.get("verdict") == "wrong" and not c.get("against") and all(s.get("status") == "confirmed" for s in sigs):
            bad.append(f'{g}: "wrong" needs the evidence: an entry under "against", or a signal that changed or was not found')
        if "—" in json.dumps(c, ensure_ascii=False):
            bad.append(f"{g}: no em dashes")
    return bad


if __name__ == "__main__":
    inp, out = (json.load(open(p, encoding="utf-8")) for p in sys.argv[1:3])
    bad = problems(inp, out)
    print("\n".join(bad) if bad else f'OK: {len(out["companies"])} companies, ' + ", ".join(f'{c["group"]}: {c["verdict"]}' for c in out["companies"]))
    sys.exit(1 if bad else 0)
