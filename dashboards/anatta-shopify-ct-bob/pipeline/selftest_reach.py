#!/usr/bin/env python3
"""Self-test for the reach step, on a made-up list. Run it after changing reach_infer.py or reach_rank.py.

    python3 selftest_reach.py

Six invented companies, one for each thing that went wrong or could: a national retailer on its own platform with
every signal an intent tool can give; a company that has just rebuilt; one whose store an operator runs; one far larger
than anything the score was built on; one that has said a decision is open; one that is quiet. The test passes when the
giant is not ranked whatever its numbers, the mover comes first, a FIRE reading is no partner trigger, a half rounds
up, and research that contradicts the rules stops the run."""
import json, os, subprocess, sys, tempfile
sys.dont_write_bytecode = True        # this test loads reach_rank.py as a module: leave no cache beside it

HERE = os.path.dirname(os.path.abspath(__file__))
AS_OF = "2026-11-19"


def acct(name, **kw):
    a = {"name": name, "group": "", "gate": "", "triangle": 60, "whitespace_capped": False, "cap_reason": "",
         "anatta_sub": {"intent": 2}, "fire": {}, "shopify_in_family": []}
    a.update(kw)
    return a


def move(partner, live=True, trigger="", date=""):
    return {"partner": partner, "motives": ["Better together"], "live": live, "evidence": "seen", "gap": "", "trigger": trigger, "triggerDate": date}


def row(group, fit, potential, moves, bonus=0, shop="yes"):
    return {"group": group, "fit": fit, "potential": potential, "moves": moves, "bonus": bonus, "shopPay": shop, "priority": 0, "rank": 0, "motion": 0, "timing": 0}


BOOK = {"accounts": [
    acct("Giant", whitespace_capped=True, cap_reason="In-house platform at national scale. Giant builds its own platform with 20,000 engineers.", anatta_sub={"intent": 20}),
    acct("Rebuilt"), acct("Operator"), acct("Huge"), acct("Mover", anatta_sub={"intent": 11}), acct("Quiet", anatta_sub={"intent": 16}),
]}
RESEARCH = {"companies": [
    {"group": "Giant", "events": [{"date": "2026-02", "kind": "leadership", "text": "Feb 1, 2026: A. Person became CEO of Giant.", "source": "https://example.com/g"}]},
    {"group": "Rebuilt", "events": [{"date": "2026-06", "kind": "platform-done", "text": "Jun 2026: Rebuilt finished its move to another vendor's platform.", "source": "https://example.com/r"}]},
    {"group": "Operator", "events": []},
    {"group": "Huge", "events": []},
    {"group": "Mover", "events": [{"date": "2026-09", "kind": "platform", "text": "Sep 3, 2026: Mover's owner said it is reviewing its commerce platform.", "source": "https://example.com/m"},
                                  {"date": "2026-10", "kind": "leadership", "text": "Oct 2026: Chief Technology Officer role posted.", "source": "https://example.com/m2"}]},
    {"group": "Quiet", "events": []},
]}
EXTRAS = {g: {"coverage": {"stores": 1, "read": 1, "unread": [], "operator_run": []}} for g in ("Giant", "Rebuilt", "Huge", "Mover", "Quiet")}
EXTRAS["Operator"] = {"coverage": {"stores": 0, "read": 0, "unread": [], "operator_run": ["Operator"]}}
POTENTIAL = {"Giant": {"online": 90000}, "Rebuilt": {"online": 80}, "Operator": {"online": 20}, "Huge": {"online": 2500}, "Mover": {"online": 150}, "Quiet": {"online": 120}}
REFERENCE = {"A": {"online": 700}, "B": {"online": 40}}
FIRE_TRIGGER = "FIRE logged intent on Sep 20th 2026: Shopify"
RESCORED = {"weights": {"motion": 0.35, "fit": 0.30, "timing": 0.20, "potential": 0.15}, "ranked": [
    row("Giant", 98, 100, [move("P1", trigger=FIRE_TRIGGER, date="2026-09")] * 3, bonus=10),
    row("Rebuilt", 90, 60, [move("P1")]), row("Operator", 60, 40, []), row("Huge", 85, 90, [move("P1")]),
    row("Mover", 70, 55, [move("P1", trigger=FIRE_TRIGGER, date="2026-09"), move("P2", live=False)]),
    row("Quiet", 83, 51, [move("P1", trigger=FIRE_TRIGGER, date="2026-09")], shop="no"),
]}


def run(script, *args):
    return subprocess.run([sys.executable, "-I", os.path.join(HERE, script), *args], capture_output=True, text=True)


def main():
    d = tempfile.mkdtemp(); p = lambda n: os.path.join(d, n)
    for name, data in (("book.json", BOOK), ("research.json", RESEARCH), ("extras.json", EXTRAS), ("potential.json", POTENTIAL), ("reference.json", REFERENCE), ("rescored.json", RESCORED)):
        json.dump(data, open(p(name), "w"))
    infer = ["--book", p("book.json"), "--extras", p("extras.json"), "--potential", p("potential.json"), "--reference", p("reference.json"),
             "--as-of", AS_OF, "--out-reach", p("reach.json"), "--out-signals", p("signals.json")]
    r = run("reach_infer.py", "--research", p("research.json"), *infer)
    assert r.returncode == 0, r.stdout + r.stderr
    reach, sig = json.load(open(p("reach.json"))), json.load(open(p("signals.json")))
    want = {"Giant": ("out", "builds its own platform"), "Rebuilt": ("later", "just decided"), "Operator": ("out", "no store of its own"),
            "Huge": ("out", "enterprise scale"), "Mover": ("open", None), "Quiet": ("open", None)}
    for g, (state, kind) in want.items():
        assert (reach[g]["state"], reach[g].get("kind")) == (state, kind), (g, reach[g])
        assert reach[g].get("basis"), f"{g}: no basis"
    assert reach["Rebuilt"]["again"] == "2028"
    assert [s["cls"] for s in sig["Mover"]] == ["decision", "tech-lead"] and [s["cls"] for s in sig["Giant"]] == ["mandate"], sig
    r = run("reach_rank.py", "--rescored", p("rescored.json"), "--book", p("book.json"), "--reach", p("reach.json"), "--signals", p("signals.json"), "--as-of", AS_OF, "--out", p("openings.json"))
    assert r.returncode == 0, r.stdout + r.stderr
    o = json.load(open(p("openings.json")))
    assert [x["group"] for x in o["ranked"]] == ["Mover", "Quiet"], [x["group"] for x in o["ranked"]]
    assert {x["group"] for x in o["out"]} == {"Giant", "Operator", "Huge"} and [x["group"] for x in o["later"]] == ["Rebuilt"]
    assert all("score" not in x for x in o["out"] + o["later"]), "a company set aside carries a score"
    mover, quiet = o["ranked"]
    assert mover["window"] == "open" and mover["path_parts"]["trigger"] is True
    assert quiet["window"] == "fire" and quiet["path_parts"] == {"motion": 24, "family": 0, "trigger": False}, quiet["path_parts"]     # a FIRE reading is no partner trigger
    assert quiet["opening"] == 31 and quiet["score"] == 47, (quiet["opening"], quiet["score"])     # 0.35*24 + 0.30*83 + 0.20*31 + 0.15*51 = 47.15
    half = dict(quiet); from importlib import util
    spec = util.spec_from_file_location("reach_rank", os.path.join(HERE, "reach_rank.py")); rr = util.module_from_spec(spec); spec.loader.exec_module(rr)
    assert rr.score(15, 17, 83, 51, 0) == 42, "41.5 must round up to 42"
    # research that contradicts the rules stops the run until a person settles it
    bad = json.loads(json.dumps(RESEARCH)); bad["companies"][0]["reach"] = {"state": "open", "why": "it looks attractive"}
    json.dump(bad, open(p("research_bad.json"), "w"))
    r = run("reach_infer.py", "--research", p("research_bad.json"), *infer)
    assert r.returncode == 1 and "NOT SETTLED" in r.stdout, r.stdout
    json.dump({"reach": {"Giant": {"state": "out", "kind": "builds its own platform", "why": "Giant builds its own platform.", "reason": "The record says so; the research call was wrong."}}}, open(p("ov.json"), "w"))
    r = run("reach_infer.py", "--research", p("research_bad.json"), "--overrides", p("ov.json"), *infer)
    assert r.returncode == 0 and json.load(open(p("reach.json")))["Giant"]["state"] == "out", r.stdout
    print("reach self-test passed: the giant is set aside whatever its numbers, the mover leads, a FIRE reading is no trigger, halves round up, and a contradiction stops the run")


if __name__ == "__main__":
    main()
