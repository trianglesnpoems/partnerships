#!/usr/bin/env python3
"""Rank a list nobody has pre-qualified: ask whether each company can move, then rank those that can by the evidence
that a decision is open.

The Heartbeat score was built on a Shopify seller's account list, where every company is already in reach and every
scale is a floor ("$200M+ online" is full marks). On an internal list that also holds national retailers, the largest
company fills every scale and comes first, although nothing says it can be won. This tool puts two things in front:

  Reach     decided per company, with a reason, before any scoring:
              open    the store runs on a platform that companies of its size do leave
              long    an in-house build at enterprise scale, but a dated first-hand event says the question is open
              later   it chose or rebuilt inside the last two years: listed with the date, not ranked
              out     it builds its own platform at national scale, or does not run its own store: listed, not ranked

  Opening   0 to 100, built the way the Heartbeat builds timing: 60% from what the research found, 40% from FIRE.
            The research share now counts the company's own dated actions only (a filing, a call, a posting, a page
            read first-hand), each put in a class:
              decision   1.00   it has said a platform or IT decision is open, or is hiring the person who will make it
              mandate    0.75   a new owner, or a new chief executive or chair
              tech-lead  0.60   the technology or e-commerce chief's seat is open, new or about to change
              leader     0.30   another senior change
              growth     0.15   new stores, markets or lines on the platform it has
            The strongest counts in full and the next at a quarter; 0.15 more when the store runs on software its
            vendor has frozen; capped at 1. A signal counts in full for 9 months (the Heartbeat's own window), at half
            from 10 to 12, and not after.
            Evidence against a move is a signal too. "staffing" (it is hiring people to build on the platform it has)
            halves the research share when it is inside 9 months and no older than the signal the opening rests on.
            "rebuilding" (a rebuild is in flight) is not scored here: reach_infer.py sets such a company aside. FIRE keeps the Heartbeat's share and scale, and is counted here once: it no
            longer also serves as the trigger on partner moves. The Shop Pay lift is the Heartbeat's own (+15, +7).

  Way in    the Heartbeat's partner motion, with one change: a FIRE reading is not a trigger. A move's trigger is a
            dated event of its own (the account's, or its partner's market) or one of the first-hand signals above,
            inside 9 months. Plus 15 when Shopify already runs a store for the same owner.

  Score = the Heartbeat's own weights: 35% way in + 30% Anatta fit + 20% opening + 15% potential, plus its flat 10 for a
  live subscription. Fit, potential, the Shop Pay lift and the subscription rule are the Heartbeat's own, unchanged.
  The order with the opening at 30%, 40% and 50% is written beside it, to show how little the weights decide.

  Each ranked company also carries what its opening rests on, named by its strongest signal inside 9 months:
              open       a first-hand decision signal
              changing   a first-hand mandate or tech-lead signal
              fire       no such signal, but FIRE reads intent (a third party's reading, not yet confirmed)
              quiet      none of these

    reach_rank.py --rescored rescored.json --book book.json --reach reach.json --signals signals.json \
                  --as-of 2026-11-19 --out openings.json

  rescored.json   written by the Heartbeat Source's tools/rescore.py
  book.json       the account list the Heartbeat tools read: FIRE fields, groups, gates, sister stores on Shopify
  reach.json      {company: {"state": open|long|later|out, "kind": "...", "why": "...", "again": "2027", "note": "..."}}
  signals.json    {company: [{"cls": decision|mandate|tech-lead|leader|growth|frozen, "date": "YYYY-MM", "text": "...", "source": "..."}]}
"""
import argparse, collections, datetime, json

CLS = {"decision": 1.0, "mandate": 0.75, "tech-lead": 0.6, "leader": 0.3, "growth": 0.15}
FROZEN, FAMILY = 0.15, 15
RESEARCH_SHARE, FIRE_SHARE = 60, 40                                  # the Heartbeat's own split of timing
LIFT = {"yes": 15, "partly": 7, "no": 0}                              # the Heartbeat's Shop Pay lift
WEIGHTS = {"path": 0.35, "fit": 0.30, "opening": 0.20, "potential": 0.15}     # the Heartbeat's own: partner motion, fit, timing, potential
FIRE_ONLY = 10                                                       # FIRE's intent reading, 0 to 20, at or above which "fire" is shown
TRIGGERS = ("decision", "mandate", "tech-lead", "leader")           # what gives a partner a dated reason to move
GROUPS = [("open", "Decision open"), ("changing", "Decider changing"), ("fire", "FIRE only"), ("quiet", "Quiet")]


def mi(s):
    y, m = s.split("-")[:2]
    return int(y) * 12 + int(m) - 1


def recency(date, now):
    """1 inside 9 months either side of today, a half from 10 to 12 months back, nothing older."""
    age = now - mi(date)
    return 1.0 if -9 <= age <= 9 else 0.5 if 9 < age <= 12 else 0.0


def opening(sigs, intent, shop, now):
    live = sorted(((CLS[s["cls"]] * recency(s["date"], now), s) for s in sigs if s["cls"] in CLS), key=lambda x: -x[0])
    live = [(p, s) for p, s in live if p > 0]
    top = live[0][0] if live else 0
    second = 0.25 * live[1][0] if len(live) > 1 else 0
    frozen = FROZEN if any(s["cls"] == "frozen" for s in sigs) else 0
    first_hand = min(1.0, top + second + frozen)
    full = [s for s in sigs if s["cls"] in CLS and recency(s["date"], now) == 1.0]      # only a signal inside 9 months names what the opening rests on
    lead_sig = max(full, key=lambda s: CLS[s["cls"]]) if full else None
    halved = bool(lead_sig) and any(s["cls"] == "staffing" and recency(s["date"], now) == 1.0 and mi(s["date"]) >= mi(lead_sig["date"]) for s in sigs)
    if halved:
        first_hand *= 0.5
    research = RESEARCH_SHARE * first_hand; fire = FIRE_SHARE * max(0, intent - 2) / 18; lift = LIFT.get(shop or "no", 0)
    total = min(100, half_up(research + fire) + lift)
    lead = lead_sig["cls"] if lead_sig else None
    group = "open" if lead == "decision" else "changing" if lead in ("mandate", "tech-lead") else "fire" if intent >= FIRE_ONLY else "quiet"
    return total, {"first_hand": round(research, 1), "fire": round(fire, 1), "shop_pay": lift, "halved": halved}, group


def move_score(m, company_trigger, now):
    """One partner move, 0 to 5, as the Heartbeat scores it. A FIRE reading is not a trigger: such a move counts one only when the
    company has a first-hand signal inside 9 months. A move whose trigger is a dated event of its own keeps it."""
    if (m.get("trigger") or "").startswith("FIRE logged") or not m.get("triggerDate"):
        trig = company_trigger
    else:
        trig = abs(mi(m["triggerDate"]) - now) <= 9
    return len(set(m["motives"])) + (1 if m.get("live") else 0) + (1 if trig else 0)


def motion(moves, company_trigger, now):
    s = sorted((move_score(m, company_trigger, now) for m in moves), reverse=True) + [0, 0, 0]
    return round(100 * (0.6 * s[0] + 0.25 * s[1] + 0.15 * s[2]) / 5)     # the Heartbeat's own line, kept as written


def half_up(x):
    """Round with halves going up, so the number on the page is the one a reader gets by hand."""
    return int(x + 0.5 + 1e-9)


def score(w, p, fit, pot, bonus, weights=WEIGHTS):
    """Whole-number weights are summed exactly, in hundredths, so 41.5 is 42 here and on a calculator alike."""
    pct = {k: v * 100 for k, v in weights.items()}
    if all(abs(v - round(v)) < 1e-9 for v in pct.values()):
        total = round(pct["path"]) * p + round(pct["fit"]) * fit + round(pct["opening"]) * w + round(pct["potential"]) * pot
        return min(100, (total + 50) // 100 + bonus)
    return min(100, half_up(weights["path"] * p + weights["fit"] * fit + weights["opening"] * w + weights["potential"] * pot) + bonus)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    for a in ("rescored", "book", "reach", "signals", "as-of", "out"):
        ap.add_argument("--" + a, required=True)
    A = ap.parse_args()
    J = lambda p: json.load(open(p, encoding="utf-8"))
    R, B, REACH, SIG = J(A.rescored), J(A.book), J(A.reach), J(A.signals)
    today = datetime.date.fromisoformat(A.as_of); now = today.year * 12 + today.month - 1
    rows = collections.defaultdict(list)
    for a in B["accounts"]:
        if not a.get("gate"):
            rows[a.get("group") or a["name"]].append(a)
    out = {"as_of": A.as_of, "weights": WEIGHTS, "classes": CLS, "frozen": FROZEN, "family": FAMILY,
           "shares": {"research": RESEARCH_SHARE, "fire": FIRE_SHARE}, "groups": GROUPS,
           "ranked": [], "long": [], "later": [], "out": []}
    for r in R["ranked"]:
        g = r["group"]; rc = REACH.get(g) or {"state": "open"}; sigs = SIG.get(g, [])
        lead = max(rows[g], key=lambda a: a["triangle"]); intent = lead["anatta_sub"]["intent"]; fire = lead.get("fire") or {}
        w, wparts, grp = opening(sigs, intent, r["shopPay"], now)
        company_trigger = any(s["cls"] in TRIGGERS and -9 <= now - mi(s["date"]) <= 9 for s in sigs)
        family = sorted({x["name"] for a in rows[g] for x in (a.get("shopify_in_family") or [])})
        mo = motion(r["moves"], company_trigger, now); p = min(100, mo + (FAMILY if family else 0))
        best = max(r["moves"], key=lambda m: move_score(m, company_trigger, now)) if r["moves"] else None        # the first of equals, as in the Heartbeat
        row = {"group": g, "state": rc["state"], "kind": rc.get("kind"), "why": rc.get("why"), "again": rc.get("again"), "note": rc.get("note"), "basis": rc.get("basis"),
               "opening": w, "opening_parts": wparts, "window": grp, "signals": sigs, "intent": intent,
               "fire": {k: fire.get(k) for k in ("intent", "signals", "last_signal", "in_market") if fire.get(k) not in (None, "")},
               "path": p, "path_parts": {"motion": mo, "family": FAMILY if family else 0, "trigger": company_trigger}, "family": family,
               "first": [best["partner"], move_score(best, company_trigger, now)] if best else None,
               "fit": r["fit"], "potential": r["potential"], "bonus": r["bonus"], "shopPay": r["shopPay"],
               "heartbeat": {"score": r["priority"], "rank": r["rank"], "motion": r["motion"], "timing": r["timing"]}}
        if rc["state"] in ("open", "long"):
            row["score"] = score(w, p, r["fit"], r["potential"], r["bonus"])
        out[{"open": "ranked", "long": "long", "later": "later", "out": "out"}[rc["state"]]].append(row)
    out["ranked"].sort(key=lambda x: (-x["score"], -x["opening"], -x["path"], -x["fit"]))
    for i, x in enumerate(out["ranked"], 1):
        x["rank"] = i
    out["long"].sort(key=lambda x: -x["score"])
    for k in ("later", "out"):
        out[k].sort(key=lambda x: x["heartbeat"]["rank"])
    # how far the order depends on the weights: the first ten with the opening at 20% (the Heartbeat's own), 30%, 40% and 50%
    order_by = lambda ww: [x["group"] for x in sorted(out["ranked"], key=lambda x: (-score(x["opening"], x["path"], x["fit"], x["potential"], x["bonus"], ww), -x["opening"], -x["path"], -x["fit"]))[:10]]
    sens = {}
    for wo in (0.20, 0.30, 0.40, 0.50):
        rest = (1 - wo) / 0.80; sens[str(int(wo * 100))] = order_by({"opening": wo, "path": 0.35 * rest, "fit": 0.30 * rest, "potential": 0.15 * rest})
    out["sensitivity"] = sens
    json.dump(out, open(A.out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    c = collections.Counter(x["window"] for x in out["ranked"])
    print(f"{len(R['ranked'])} companies inside the ICP | in reach {len(out['ranked'])} | long odds {len(out['long'])} | not now {len(out['later'])} | out of reach {len(out['out'])}")
    print("in reach: " + ", ".join(f"{label.lower()} {c.get(k, 0)}" for k, label in GROUPS))
    print(f"{'#':>2} {'was':>3} {'company':32} {'score':>5} | {'open':>4} {'way':>3} {'fit':>3} {'pot':>3} {'sub':>3} | {'Heartbeat':>9} | window")
    for x in out["ranked"] + out["long"]:
        print(f"{x.get('rank', '-'):>2} {x['heartbeat']['rank']:>3} {x['group'][:32]:32} {x['score']:>5} | {x['opening']:>4} {x['path']:>3} {x['fit']:>3} {x['potential']:>3} "
              f"{('+' + str(x['bonus'])) if x['bonus'] else '':>3} | {x['heartbeat']['score']:>9} | {x['window']}{' (long odds)' if x['state'] == 'long' else ''}")
    for n in (4, 10):
        print(f"with the opening weighted 20% to 50%: the same companies fill the first {n} in {sum(1 for k in sens if set(sens[k][:n]) == set(sens['20'][:n]))} of {len(sens)} cases")


if __name__ == "__main__":
    main()
