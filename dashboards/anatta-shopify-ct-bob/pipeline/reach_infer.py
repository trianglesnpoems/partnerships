#!/usr/bin/env python3
"""Derive the reach calls and the signal classes from the research record, by rule.

reach_rank.py needs two things per company: can its store move, and which dated first-hand signals say a decision is
open. Written by hand they do not scale and they drift from the research. This tool reads them off what the research
already recorded, says which rule decided each one, and lets a person overrule a rule only with a reason.

    reach_infer.py --book book.json --research research.json --extras book_extras.json --potential potential.json \
                   --reference <the reference seller's potential.json> --as-of 2026-11-19 \
                   [--overrides overrides.json] [--compare-reach reach.json --compare-signals signals.json] \
                   --out-reach reach.json --out-signals signals.json [--report report.md]

Reach, first rule that applies:
  out    no store of its own      the scans found no store the company runs, only stores an outside operator runs
  out    builds its own platform  the first pass capped it as "In-house platform at national scale" and no decision signal is on file
  out    enterprise scale         it sells more online than the largest company on the list the score was built on
                                  (--reference), and no decision signal is on file
  long   long odds                either of the two above, with a decision signal inside 9 months
  later  just decided             the first pass capped it as "Recently replatformed", or a "platform-done" event is on file
                                  inside 24 months; "again" is the year of that decision plus two
  open                            none of these

Signals, from the dated events the research recorded (a "platform-done" event is not a signal: it closes a door):
  platform      decision, or frozen when the text says the store still runs software its vendor has stopped building on
  ownership     mandate when the company itself changed hands, growth when it bought another
  leadership    mandate for a new chief executive or chair, tech-lead for a technology or e-commerce chief, leader otherwise
  store-opening, launch   growth

Overrides (each needs "reason"; the report lists every one):
  {"reach":   {company: {"state": ..., "kind": ..., "why": ..., "again": ..., "reason": "..."}},
   "class":   [{"group": ..., "date": "YYYY-MM", "cls": ..., "reason": "..."}],        a rule classed an event wrongly
   "add":     {company: [{"cls": ..., "date": ..., "text": ..., "source": ..., "reason": "..."}]},   a signal the events do not hold
   "drop":    [{"group": ..., "date": "YYYY-MM", "reason": "..."}],                    an event that is not a signal
   "wording": {company: {"why": "...", "note": "..."}}}                                a shorter line for the page; changes no call

Research written to briefs/reach_and_signals.md carries its own answers: a "reach" call per company and a "signal" class
on each event. Then this tool is the second opinion. It uses the research's answer, works out its own by rule, and
lists every place the two differ. A difference is settled by a person in the overrides file, with a reason; until then
the run fails (--allow-unsettled prints them and goes on).

A rule that fires is evidence the research already held. Where this tool and a person disagree, the report says so, and
the disagreement is the thing to look at: either the rule is wrong or the research is."""
import argparse, collections, datetime, json, re, sys

LABEL = re.compile(r"^((?:Shares the [^.]+\. |Runs on the same [^.]+\. )?)(In-house platform at national scale|Recently replatformed|Hard to convert)\.\s*(?:Borderline\.\s*)?(.*)$", re.S)
TECH = re.compile(r"\b(?:Chief|VP|Vice President|SVP|EVP|Head|Director)\b[^.;:]{0,60}\b(?:Technology|Information|Digital|e-?Commerce|Unified Commerce)\b|\b(?:CTO|CIO|CDO)\b|technology leadership", re.I)
CHIEF = re.compile(r"(?:became|named|appointed|as)\s+(?:the\s+)?(?:new\s+)?(?:Interim\s+|President and\s+)?(?:CEO\b|Chief Executive)|(?:CEO|chief executive)\b[^.;]{0,40}\b(?:left|resigned|retired|stepped down)\b|Executive Chair", re.I)
FROZEN = re.compile(r"\bstill runs?\b|\bfrozen\b|no new features|stopped (?:building|developing)", re.I)
CHANGED_HANDS = re.compile(r"emerged from|under new ownership|new owner|taken private|controlling interest", re.I)
BOUGHT = r"(?:purchase of|acquisition of|to acquire|acquired|bought)\s+(?:the\s+)?[^.;]{0,40}?"
CLASSES = ("decision", "mandate", "tech-lead", "leader", "growth", "frozen")


def mi(s):
    y, m = s.split("-")[:2]
    return int(y) * 12 + int(m) - 1


def first_sentence(t):
    m = re.match(r"(.+?[.!?])(?=\s+[A-Z(]|$)", t.strip(), re.S)
    return (m.group(1) if m else t).strip()


def short_name(g):
    g = re.sub(r"\s*\([^)]*\)|\*+$", "", g).strip()
    return " ".join(g.split()[:2]) if len(g.split()) > 1 else g


def classify(g, e):
    """The class of one dated event, and the rule that gave it. None for an event that is not a signal."""
    kind, text = e.get("kind"), e.get("text") or ""
    if kind == "platform-done":
        return None, "a move that has finished closes a door"
    if kind == "platform":
        return ("frozen", "platform event: the store still runs software its vendor has stopped building on") if FROZEN.search(text) else ("decision", "platform event: a review, a search or a posting about the platform")
    if kind == "ownership":
        target = CHANGED_HANDS.search(text) or re.search(BOUGHT + re.escape(short_name(g)), text, re.I)
        return ("mandate", "ownership event: the company itself changed hands") if target else ("growth", "ownership event: the company bought another")
    if kind == "leadership":
        if CHIEF.search(text):
            return "mandate", "leadership event: a new chief executive or chair"
        if TECH.search(text):
            return "tech-lead", "leadership event: the technology or e-commerce chief's seat"
        return "leader", "leadership event: another senior change"
    if kind in ("store-opening", "launch"):
        return "growth", f"{kind} event"
    return None, f"event kind {kind!r} is not a signal"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    for a in ("book", "research", "extras", "potential", "as-of", "out-reach", "out-signals"):
        ap.add_argument("--" + a, required=True)
    ap.add_argument("--reference", action="append", default=[], help="potential.json of the list the score was built on; repeatable")
    ap.add_argument("--scale-ceiling", type=float, help="online sales, in $M, above which a company is enterprise scale (instead of --reference)")
    for a in ("overrides", "compare-reach", "compare-signals", "report"):
        ap.add_argument("--" + a)
    ap.add_argument("--allow-unsettled", action="store_true", help="go on when the research and the rules differ and no override settles it")
    A = ap.parse_args()
    J = lambda p: json.load(open(p, encoding="utf-8"))
    B, RS, EX, POT = J(A.book), J(A.research), J(A.extras), J(A.potential)
    OV = J(A.overrides) if A.overrides else {}
    today = datetime.date.fromisoformat(A.as_of); now = today.year * 12 + today.month - 1
    ref = [v["online"] for p in A.reference for v in J(p).values() if isinstance(v, dict) and v.get("online")]
    ceiling = A.scale_ceiling if A.scale_ceiling is not None else (max(ref) if ref else None)
    if ceiling is None:
        sys.exit("give --reference (the potential.json of the list the score was built on) or --scale-ceiling")
    rows = collections.defaultdict(list)
    for a in B["accounts"]:
        if not a.get("gate"):
            rows[a.get("group") or a["name"]].append(a)
    events = {c["group"]: c.get("events") or [] for c in RS["companies"]}
    said = {c["group"]: c.get("reach") for c in RS["companies"] if c.get("reach")}       # the research's own reach calls, where it made them
    unsettled = []
    scored = [g for g in rows if isinstance(POT.get(g), dict)]          # inside the ICP: the research gave it a potential entry
    for sect in ("reach", "add", "wording"):
        for g in OV.get(sect, {}):
            assert g in scored, f'override "{sect}" names {g!r}, which is not a company inside the ICP'
    for o in OV.get("class", []) + OV.get("drop", []) + [x for v in OV.get("add", {}).values() for x in v] + list(OV.get("reach", {}).values()):
        assert o.get("reason"), f"an override needs its reason: {o}"

    # ---- signals
    signals, sig_basis, used = {}, {}, set()
    for g in scored:
        out = []
        for e in events.get(g, []):
            cls, rule = classify(g, e)
            drop = next((o for o in OV.get("drop", []) if o["group"] == g and o["date"] == e["date"] and o.get("kind", e.get("kind")) == e.get("kind")), None)
            if drop:
                used.add(id(drop)); sig_basis.setdefault(g, []).append((e["date"], None, f'dropped by hand: {drop["reason"]}')); continue
            over = next((o for o in OV.get("class", []) if o["group"] == g and o["date"] == e["date"] and o.get("kind", e.get("kind")) == e.get("kind")), None)
            given = e.get("signal")
            if over:
                assert over["cls"] in CLASSES, over
                used.add(id(over)); rule = f'classed by hand as {over["cls"]} (the rule said {cls}): {over["reason"]}'; cls = over["cls"]
            elif given is not None:
                assert given in CLASSES + ("none",), f"{g}: unknown signal class {given!r}"
                if given != (cls or "none"):
                    unsettled.append(f'{g}, event of {e["date"]}: the research classed it {given}, the rule says {cls or "none"}')
                rule = f"classed by the research as {given}" + ("" if given == (cls or "none") else f" (the rule says {cls or 'none'})"); cls = None if given == "none" else given
            if cls:
                out.append({"cls": cls, "date": e["date"], "text": e["text"], "source": e.get("source")}); sig_basis.setdefault(g, []).append((e["date"], cls, rule))
        for x in OV.get("add", {}).get(g, []):
            assert x["cls"] in CLASSES and re.fullmatch(r"20\d\d-(0[1-9]|1[0-2])", x["date"]) and x.get("text"), x
            out.append({"cls": x["cls"], "date": x["date"], "text": x["text"], "source": x.get("source")}); sig_basis.setdefault(g, []).append((x["date"], x["cls"], f'added by hand: {x["reason"]}'))
        if out:
            signals[g] = out
    for o in OV.get("class", []) + OV.get("drop", []):
        assert id(o) in used, f"an override matches no event: {o}"

    # ---- reach
    reach, basis = {}, {}
    for g in scored:
        ih = rc = None
        for a in sorted(rows[g], key=lambda a: -(a.get("triangle") or 0)):
            m = LABEL.match(a.get("cap_reason") or "") if a.get("whitespace_capped") else None
            if m and m.group(2).startswith("In-house") and not ih:
                ih = first_sentence(m.group(3))
            if m and m.group(2).startswith("Recently") and not rc:
                rc = first_sentence(m.group(3))
        cov = (EX.get(g) or {}).get("coverage") or {}
        online = POT[g].get("online")
        done = sorted((e for e in events.get(g, []) if e.get("kind") == "platform-done" and 0 <= now - mi(e["date"]) <= 24), key=lambda e: e["date"])
        deciding = [s for s in signals.get(g, []) if s["cls"] == "decision" and -9 <= now - mi(s["date"]) <= 9]
        if not cov.get("stores") and cov.get("operator_run"):
            r = {"state": "out", "kind": "no store of its own", "why": "Its online store runs on an outside operator's storefront."}
            why = f'the scans found no store the company runs itself, only stores an outside operator runs ({", ".join(cov["operator_run"][:3])})'
        elif ih or (online is not None and online > ceiling):
            kind = "builds its own platform" if ih else "enterprise scale"
            line = ih or f"About ${online / 1000:.2f}B a year online, above the largest company on the list the score was built on (${ceiling:,.0f}M)."
            if deciding:
                r = {"state": "long", "kind": "long odds", "why": line}
                why = ("the first research pass marked it hard to move, as an in-house platform at national scale" if ih else f"it sells ${online:,.0f}M a year online, above the largest company on the reference list (${ceiling:,.0f}M)") + f', and a decision signal dated {deciding[-1]["date"]} is on file'
            else:
                r = {"state": "out", "kind": kind, "why": line}
                why = ("the first research pass marked it hard to move, as an in-house platform at national scale" if ih else f"it sells ${online:,.0f}M a year online, above the largest company on the reference list (${ceiling:,.0f}M)") + "; no decision signal inside 9 months is on file"
        elif rc or done:
            years = [int(done[-1]["date"][:4])] if done else []
            years += [int(y) for y in re.findall(r"\b(20\d\d)\b", rc or "") if int(y) <= today.year][:1]
            r = {"state": "later", "kind": "just decided", "why": done[-1]["text"] if done else rc, "again": str((max(years) if years else today.year) + 2)}
            why = (f'a platform move that finished in {done[-1]["date"]} is on file' if done else "the first research pass marked it hard to move, as recently replatformed")
        else:
            r = {"state": "open"}; why = "no rule against it"
        basis[g] = why
        o = OV.get("reach", {}).get(g)
        s = said.get(g)
        if s and not o:
            if s.get("state") == r["state"] or (s.get("state") == "out" and r["state"] == "long"):     # same call: keep the research's own sentence
                r = dict(r, why=s.get("why") or r.get("why")) if r["state"] != "open" else r
                basis[g] = f"the research and the rules agree ({why})"
            else:
                unsettled.append(f'{g}: the research says {s.get("state")} ({s.get("why", "")[:90]}), the rules say {r["state"]} ({why})')
        if o:
            basis[g] = f'set by hand to {o["state"]} (the rules said {r["state"]}: {why}): {o["reason"]}'
            r = {k: o[k] for k in ("state", "kind", "why", "again") if o.get(k)}
        w = OV.get("wording", {}).get(g) or {}
        if w.get("why") and r["state"] != "open":
            r["why"] = w["why"]
        if w.get("note"):
            r["note"] = w["note"]
        r["basis"] = basis[g]
        reach[g] = r

    json.dump(reach, open(A.out_reach, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    json.dump(signals, open(A.out_signals, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    c = collections.Counter(r["state"] for r in reach.values())
    n_sig = sum(len(v) for v in signals.values())
    by_hand = {"reach": len(OV.get("reach", {})), "class": len(OV.get("class", [])), "add": sum(len(v) for v in OV.get("add", {}).values()), "drop": len(OV.get("drop", []))}
    print(f"{len(scored)} companies inside the ICP | open {c['open']} | long odds {c['long']} | not now {c['later']} | out of reach {c['out']} | scale ceiling ${ceiling:,.0f}M")
    print(f"{n_sig} signals at {len(signals)} companies | decided by rule: {len(scored) - by_hand['reach']} of {len(scored)} reach calls, {n_sig - by_hand['class'] - by_hand['add']} of {n_sig} signals | by hand, each with a reason: {by_hand}")
    report = [f"# Reach calls and signals, by rule ({A.as_of})", "", f"{len(scored)} companies inside the ICP. Scale ceiling: ${ceiling:,.0f}M online, the largest company on the reference list.", ""]

    # ---- agreement with calls made another way (by hand, or by the research itself)
    if A.compare_reach:
        old = J(A.compare_reach); same = [g for g in scored if (old.get(g) or {}).get("state") == reach[g]["state"]]
        diff = [(g, (old.get(g) or {}).get("state"), reach[g]["state"]) for g in scored if g not in same]
        print(f"reach calls: {len(same)} of {len(scored)} agree with {A.compare_reach.split('/')[-1]}" + (": " + "; ".join(f"{g}: {a} there, {b} here" for g, a, b in diff) if diff else ""))
        report += [f"## Reach against the calls on file: {len(same)} of {len(scored)} agree", ""] + [f"- **{g}**: {a} on file, {b} by rule ({basis[g]})" for g, a, b in diff] + [""]
    if A.compare_signals:
        old = J(A.compare_signals); key = lambda L: sorted((s["date"], s["cls"]) for s in L)
        agree = [g for g in scored if key(old.get(g, [])) == key(signals.get(g, []))]
        diff = [g for g in scored if g not in agree]
        print(f"signals: {len(agree)} of {len(scored)} companies carry the same dated classes as {A.compare_signals.split('/')[-1]}" + (": differ at " + "; ".join(diff) if diff else ""))
        report += [f"## Signals against the classes on file: {len(agree)} of {len(scored)} companies agree", ""]
        report += [f"- **{g}**: on file {key(old.get(g, []))}, by rule {key(signals.get(g, []))}" for g in diff] + [""]
    report += ["## Every call", ""] + [f"- **{g}**: {reach[g]['state']}" + (f" ({reach[g].get('kind')})" if reach[g].get("kind") else "") + f". {basis[g]}" for g in sorted(scored, key=lambda g: ({"open": 0, "long": 1, "later": 2, "out": 3}[reach[g]["state"]], g))]
    report += ["", "## Every signal", ""] + [f"- **{g}** {d} {cls or 'not a signal'}: {rule}" for g in sorted(sig_basis) for d, cls, rule in sig_basis[g]]
    if unsettled:
        report[2:2] = [f"## Not settled: the research and the rules differ at {len(unsettled)}", ""] + [f"- {u}" for u in unsettled] + [""]
        print(f"NOT SETTLED: the research and the rules differ at {len(unsettled)}. Settle each in the overrides file, with a reason:")
        for u in unsettled:
            print("  -", u)
    if A.report:
        open(A.report, "w", encoding="utf-8").write("\n".join(report) + "\n")
    if unsettled and not A.allow_unsettled:
        sys.exit(1)


if __name__ == "__main__":
    main()
