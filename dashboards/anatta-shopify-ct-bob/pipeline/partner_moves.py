#!/usr/bin/env python3
"""Write the partner moves for every company in a book, from the partner facts, by stated rules.

The Heartbeat score puts partner motion first: 60% of the best partner's move score, 25% of the second's, 15% of the
third's, where a move scores one point per motive (Displacement, Portfolio, Better together), one if the partner is
live in the group and one if a dated trigger falls within nine months of the issue month. That scoring lives in the
Heartbeat Source (tools/rescore.py) and is not repeated here. This step only writes the rows it scores, in the shape
the Heartbeat Source keeps them (data/<seller>/book_extras.json), so the ranking can be traced to what a scan saw.

The rules follow the Heartbeat Source playbook ("Why a partner moves") and the rows written by hand for its first issue:

  Better together   a partner that is live at the company today has to come through any move to Shopify.
                    Gorgias and Recharge also join once a store is on Shopify, so their rows carry it when not live.
  Portfolio         the partner is live at some of the company's stores and not at others. A store counts as "not at"
                    only when it was read by a scan that saw the partner at a sister store.
  Displacement      a rival runs in the partner's lane. A partner already live in a lane gets that lane; where none
                    is, the lane's lead partner gets the row (email and SMS: Klaviyo; reviews: Yotpo; help desk:
                    Gorgias; search: Algolia; returns: Loop). A partner that was seen and then removed gets a
                    displacement row too, and the first question is why it left.
  Trigger           one dated event per row: the Salesforce and Braze deal where Salesforce Marketing Cloud is the
                    rival; a FIRE intent signal, or a platform choice that is open (a public review, a search, an
                    end-of-life date), for a row that carries Better together; a leadership or ownership change, or
                    an open platform choice, for a row that carries Displacement; a new store launch for a row that
                    carries Portfolio; the month a removed partner dropped off. A move that has just finished onto
                    another vendor ("platform-done") is never a trigger: it closes doors.

A company is one buying centre: the rows of the book that share its `group`. Its stores are the rows that sell on a
storefront the company runs: a corporate or info site (`info_rows` in the research file), a row with no online store and
a store someone else operates are left out, so Portfolio is never claimed against a site that has no checkout.
Research supplies two judgment inputs per company (see the brief): dated `events`, and `recharge_play`.

Usage: partner_moves.py <book.json> <partner_facts.json> <partner_registry.json> <research.json> <out book_extras.json> [--month "November 2026"]
"""
import json, re, sys, datetime, collections

args = sys.argv[1:]
MONTH = "November 2026"
if "--month" in args:
    i = args.index("--month"); MONTH = args[i + 1]; del args[i:i + 2]
BOOK, FACTS, REG, RESEARCH, OUT = args[:5]
_m = datetime.datetime.strptime(MONTH, "%B %Y"); NOW = _m.year * 12 + _m.month - 1
WINDOW = 9
mi = lambda s: int(s[:4]) * 12 + int(s[5:7]) - 1
in_window = lambda ym: bool(ym) and abs(mi(ym) - NOW) <= WINDOW
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
mon = lambda ym: f"{MON[int(ym[5:7]) - 1]} {ym[:4]}" if ym else ""

book = json.load(open(BOOK, encoding="utf-8"))
facts = {a["name"]: a for a in json.load(open(FACTS, encoding="utf-8"))["accounts"]}
reg = {x["name"]: x for x in json.load(open(REG, encoding="utf-8"))["registry"]}
_research = json.load(open(RESEARCH, encoding="utf-8"))
research = {c["group"]: c for c in _research["companies"]}
INFO_ROWS = set(_research.get("info_rows", []))      # rows whose own site is a corporate or info site with no checkout
OWN_ROWS = set(_research.get("own_store_rows", []))  # rows the book marks as operator-run where the operator is the company itself

# Lanes where a rival can be taken out, the partner that leads each, and the partners that hold it when live.
DISPLACE = {
    "messaging": {"lead": "Klaviyo", "holders": ["Klaviyo", "Attentive", "Braze", "Iterable"], "lanes": ("email", "sms"), "word": "email and SMS"},
    "reviews": {"lead": "Yotpo", "holders": ["Yotpo", "Okendo"], "lanes": ("reviews",), "word": "reviews"},
    "helpdesk": {"lead": "Gorgias", "holders": ["Gorgias", "Kustomer"], "lanes": ("helpdesk",), "word": "customer service"},
    "search": {"lead": "Algolia", "holders": ["Algolia", "Constructor", "Fast Simon"], "lanes": ("search",), "word": "site search"},
    "returns": {"lead": "Loop", "holders": ["Loop", "AfterShip"], "lanes": ("returns",), "word": "returns"},
}
LANE_OF = {l: k for k, v in DISPLACE.items() for l in v["lanes"]}
JOINS_ON_SHOPIFY = {"Gorgias", "Recharge"}          # the playbook also names Global-e and Shoplift; no row is written for them unprompted
SUB_PARTNERS = {"Recharge", "Skio", "Stay.ai", "Ordergroove"}
NOT_A_ROW = {"Shopify", "OpenAI", "Stripe", "Adyen", "Vercel", "Avalara"}     # payments and infrastructure: Shopify's own reasons go in the play
NOT_A_RIVAL = {"4Cite", "Trustpilot", "Route"}       # identity resolution, a company-review site, package protection: nothing a lead partner replaces
LIGHT = {"Mailchimp", "Constant Contact"}            # small-business tools: at a large company usually a side newsletter, so they count only when nothing else runs the lane
def is_rival(v):
    r = reg.get(v["vendor"]) or {}
    return not v["partner"] and r.get("doorTier") != "A" and v["vendor"] not in NOT_A_RIVAL and v["lane"] in LANE_OF
BRAZE = ("Salesforce agreed to buy Braze on Oct 20, 2026, closing after Feb 1, 2027. Marketing Cloud’s future is open until then.", "2026-10")

def fire_date(s):
    m = re.match(r"([A-Za-z]{3})\w* (\d+)\w* (\d{4})$", s or "")
    return f"{m.group(3)}-{MON.index(m.group(1)) + 1:02d}" if m and m.group(1) in MON else ""

groups = collections.OrderedDict()
for a in book["accounts"]:
    groups.setdefault(a.get("group") or a["name"], []).append(a)

out, report = {}, []
for g, rows in groups.items():
    if not any(not r.get("gate") for r in rows): continue
    res = research.get(g) or {}
    if (res.get("icp") or {}).get("audience") in ("b2b-catalog", "none"): continue      # outside the ICP: listed, not ranked, no moves worked
    # the company's stores: rows that sell. A gated row counts only when it is a live store already on Shopify Plus.
    # A store someone else operates (a grocer's Instacart shop, a team shop run by Fanatics) carries the operator's tools, not the company's.
    stores = [r for r in rows if r.get("gate") in ("", None, "already_plus") and r["name"] not in INFO_ROWS
              and (r.get("plat") not in ("No online store", "Third-party storefront") or r["name"] in OWN_ROWS)]
    nm = lambda r: r.get("display") or r["name"]
    seen = collections.defaultdict(dict)        # vendor -> row name -> fact
    for r in stores:
        for v in (facts.get(r["name"]) or {}).get("vendors", []):
            if v["state"] != "brief sighting": seen[v["vendor"]][nm(r)] = v
    live_at = lambda vendor: {n: v for n, v in seen.get(vendor, {}).items() if v["state"] == "live"}
    rivals = collections.defaultdict(dict)      # displacement lane -> rival -> [row names]
    for vendor, at in seen.items():
        hits = {n: v for n, v in at.items() if is_rival(v) and v["state"].startswith("live")}
        if not hits: continue
        dns_only = all(v["state"] == "live (dns only)" for v in hits.values())     # a mail or name-server record, no tag on the page
        rivals[LANE_OF[next(iter(hits.values()))["lane"]]][vendor + (" (in DNS)" if dns_only else "")] = sorted(hits)
    for lane, cfg in DISPLACE.items():          # a light tool counts only when nothing else runs the lane
        rv = rivals.get(lane) or {}
        if any(k not in LIGHT for k in rv) or any(live_at(p) for p in cfg["holders"]):
            for k in [k for k in rv if k in LIGHT]: del rv[k]
    # dated things that can open a door
    fire = [(fire_date(r["fire"]["last_signal"]), r["fire"]["last_signal"], r["fire"]["signals"]) for r in rows if not r.get("gate") and r["fire"].get("signals")]
    intent = max(((d, when, [s.strip() for s in sig.split(",") if s.strip().startswith("Intent:")]) for d, when, sig in fire if "Intent:" in sig), default=None)
    leader = max(((d, when) for d, when, sig in fire if "Leadership Change" in sig), default=None)
    # Research events, by what they open. A platform event opens doors only while the choice is open (a public review, a
    # search, an end-of-life date): a move that has just finished onto another vendor closes them, so "platform-done" is
    # never a trigger. A launch counts only for a row that carries Portfolio (a new store the partner does not cover yet).
    events = sorted((e for e in res.get("events") or [] if in_window(e["date"]) and e["kind"] != "platform-done"), key=lambda e: e["date"], reverse=True)
    ev = lambda *kinds: next((e for e in events if e["kind"] in kinds), None)
    def trigger(m, gap_vendors=()):
        if any(x.startswith("Salesforce Marketing Cloud") for x in gap_vendors): return BRAZE
        if "Better together" in m["motives"] and intent and in_window(intent[0]): return (f"FIRE logged {', '.join(intent[2])} on {intent[1]}", intent[0])
        if "Better together" in m["motives"] and ev("platform"): return (ev("platform")["text"], ev("platform")["date"])
        if "Displacement" in m["motives"]:
            if leader and in_window(leader[0]): return (f"FIRE logged a leadership change on {leader[1]}", leader[0])
            e = ev("leadership", "ownership", "platform")
            if e: return (e["text"], e["date"])
        if "Portfolio" in m["motives"] and ev("launch"): return (ev("launch")["text"], ev("launch")["date"])
        return ("", "")
    since = lambda at: ", ".join(f"{n} since {mon(v['first'])}" if v["first"] else n for n, v in sorted(at.items(), key=lambda kv: kv[1]["first"] or "9999"))
    def scans(at):          # which scans saw it; a tool seen by one scan only says so, because it is the claim to confirm first
        srcs = [x for x in ("BuiltWith", "Store Leads", "Live site") if any(x in v["sources"] for v in at.values())]
        return ", ".join(srcs).replace("Live site", "the live site") + (", one scan only" if len(srcs) == 1 else "")
    stop = lambda t: t if t.endswith(".") else t + "."
    moves = {}
    # 1. every partner that is live somewhere in the group
    for vendor, at in seen.items():
        v0 = next(iter(at.values()))
        if not v0["partner"] or vendor in NOT_A_ROW: continue
        live = live_at(vendor)
        if not live: continue
        alias = sorted({a for v in live.values() for a in v.get("seen_as") or []})
        m = {"partner": vendor, "motives": ["Better together"], "live": True, "gap": "", "gain": "Keeps the seat through the move",
             "evidence": f"Live at {since(live)} ({scans(live)})." + (f" Seen as {', '.join(alias)}, which {vendor} owns." if alias else "")}
        # "Not seen at a sister store" only means something where that store was read by a scan that saw the partner elsewhere.
        saw = {src for v in live.values() for src in v["sources"]}
        covered = lambda r: any(((facts.get(r["name"]) or {}).get("scans") or {}).get(k) for k, src in (("builtwith", "BuiltWith"), ("storeleads", "Store Leads"), ("live", "Live site")) if src in saw)
        missing = [nm(r) for r in stores if nm(r) not in live and covered(r)]
        if len(stores) > 1 and missing:
            m["motives"].insert(0, "Portfolio"); m["gap"] = "Not seen at " + ", ".join(missing[:6]) + (f" and {len(missing) - 6} more" if len(missing) > 6 else "")
            m["gain"] = "More stores in a group it already serves"
        moves[vendor] = m
    # 2. displacement, lane by lane
    for lane, cfg in DISPLACE.items():
        rv = rivals.get(lane)
        if not rv: continue
        holder = next((p for p in cfg["holders"] if p in moves), None)
        names = sorted(rv)
        if holder:
            m = moves[holder]
            m["motives"].insert(0, "Displacement")
            m["evidence"] += f" {', '.join(names)} {'runs' if len(names) == 1 else 'run'} beside it."
            m["gap"] = "; ".join(x for x in [", ".join(names), m["gap"]] if x)
        else:
            p = cfg["lead"]
            m = {"partner": p, "motives": ["Displacement"] + (["Better together"] if p in JOINS_ON_SHOPIFY else []), "live": False,
                 "evidence": stop(f"{', '.join(names)} {'runs' if len(names) == 1 else 'run'} {cfg['word']} at {', '.join(sorted({n for ns in rv.values() for n in ns})[:4])}"),
                 "gap": ", ".join(names), "gain": "A new logo"}
            moves[p] = m
        moves[m["partner"]]["_gap_vendors"] = names
    # 3. a partner seen and then removed, not live anywhere now
    for vendor, at in seen.items():
        v0 = next(iter(at.values()))
        if not v0["partner"] or vendor in NOT_A_ROW or vendor in moves or live_at(vendor): continue
        gone = {n: v for n, v in at.items() if v["state"] == "removed"}
        if not gone: continue
        n, v = max(gone.items(), key=lambda kv: kv[1]["last"])
        moves[vendor] = {"partner": vendor, "motives": ["Displacement"], "live": False, "evidence": f"Ran at {n} from {mon(v['first'])} to {mon(v['last'])}, then dropped off the site.",
                         "gap": "Ask first why it left", "gain": "A logo won back", "_removed": v["last"]}
    # 4. the subscription row, where research names a play and no subscription partner is live
    if res.get("recharge_play") and not any(p in moves and moves[p]["live"] for p in SUB_PARTNERS):
        moves.setdefault("Recharge", {"partner": "Recharge", "motives": ["Better together"], "live": False, "evidence": res.get("recharge_why", ""), "gap": "No subscription tool seen today", "gain": "Joins once a store is on Shopify"})
    # triggers, then the shape the Heartbeat Source keeps
    final = []
    for m in moves.values():
        t, td = trigger(m, m.pop("_gap_vendors", ()))
        rem = m.pop("_removed", None)
        if not t and rem and in_window(rem): t, td = f"{m['partner']} dropped off the site in {mon(rem)}", rem
        m["motives"] = list(dict.fromkeys(m["motives"]))
        final.append({"partner": m["partner"], "motives": m["motives"], "live": m["live"], "evidence": m["evidence"], "gap": m["gap"], "trigger": t, "triggerDate": td, "gain": m["gain"], "ask": ""})
    score = lambda m: len(set(m["motives"])) + (1 if m["live"] else 0) + (1 if in_window(m["triggerDate"]) else 0)
    final.sort(key=lambda m: (-score(m), not m["live"], m["partner"]))
    # What the scans could see. With no store read, "no partner" means "not known", and the page has to say so.
    was_read = lambda r: any(((facts.get(r["name"]) or {}).get("scans") or {}).values())
    out[g] = {"moves": final,
              "coverage": {"stores": len(stores), "read": sum(1 for r in stores if was_read(r)), "unread": [nm(r) for r in stores if not was_read(r)],
                           "operator_run": [nm(r) for r in rows if not r.get("gate") and r.get("plat") == "Third-party storefront" and r["name"] not in OWN_ROWS]}}
    report.append((g, [(m["partner"], score(m)) for m in final]))

json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print(f"{len(out)} companies inside the ICP | {sum(len(v['moves']) for v in out.values())} partner moves | {sum(1 for v in out.values() if not v['moves'])} with none")
blind = [g for g, v in out.items() if not v["coverage"]["read"]]
print(f"no store read by any scan (partner motion unknown, scored 0): {len(blind)}: {', '.join(blind)}")
c = collections.Counter(m["partner"] for v in out.values() for m in v["moves"])
print("rows per partner:", ", ".join(f"{k} {n}" for k, n in c.most_common()))
print("motives:", dict(collections.Counter(" + ".join(m["motives"]) for v in out.values() for m in v["moves"])))
print("with a trigger in the window:", sum(1 for v in out.values() for m in v["moves"] if in_window(m["triggerDate"])))
for g, ms in report:
    print(f"  {g[:34]:34} " + ", ".join(f"{p} {s}" for p, s in ms[:6]))
