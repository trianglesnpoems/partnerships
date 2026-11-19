#!/usr/bin/env python3
"""Assemble the single-file triangulation dashboard for one rep's book.
Writes an internal and a shareable copy, each as a standalone HTML file, as a page fragment for publishing as a
claude.ai artifact (which supplies its own <html>/<head>/<body>), and as a CSV of the scored book.

Internal copy: shows which accounts are in Salesforce and the "how far to trust our own signal" section.
Shareable copy: those are removed from the DATA and the page, not just hidden, and the build asserts they are gone.
Neither copy ever contains a Salesforce record ID.

With a contacts layer (hubs.json from build_hubs.py) the page gains the Hub Map view and people on each account.
Contact emails are shown in full ONLY in the internal standalone file. They are masked to first initial + domain in
the shareable copy and in every published fragment, and the build asserts the exact masked count and that no raw
address is left.

With a Heartbeat ranking (--heartbeat rescored.json, written by the Heartbeat Source's tools/rescore.py) the page leads
with that ranking and keeps the triangulation underneath. --potential is the same run's potential.json, for the notes
behind each measure; --heartbeat-extras is its book_extras.json, for what the scans could read at each company;
--heartbeat-notes is a JSON file {"month": ..., "notes": [...], "method_notes": [...]}.
Nothing is scored here: the build only joins the ranking to the book and asserts that every score recomputes.

House wording is applied to everything a reader can see, whatever the research wrote: an email address in a note is
masked to its domain, an em dash becomes a comma, "AE" becomes "seller", and BuiltWith's Agency field is not shown.
--scrub scrub.json adds this book's own list, [[pattern, replacement, why], ...]: use it for the name of a firm that
builds for an account, which is never shown. Links are left alone, so a source stays a source. The build prints what
each rule changed. --title, --label and --slug replace the ones the scored book carries.

--openings openings.json (written by reach_rank.py) is for a list nobody pre-qualified. The reach test goes first: the
companies that can move are ranked on the score reach_rank.py built from first-hand signals, and the rest are listed
with the reason they are set aside. Each row keeps the Heartbeat's own score beside it, under "hb".

--fixes fixes.json applies corrections found after the research was written, each with its reason:
  {"reason": "...", "fixes": [{"account": name, "find": "exact text", "replace": "..."},
                              {"account": name, "match": "regex", "unless": "text", "append": "..."}]}
A correction that matches nothing stops the build.

--challenge <folder> holds the challenge of the first ten (briefs/challenge.md): in_*.json as given to the readers and
out_*.json as they answered. Each company's verdict, the reader's summary and the facts found for and against go on its
record. --challenge-settled settled.json ({company: "what was done about it"}) is required reading for a company the
challenge overturned, or one whose signals were changed after it was challenged: the line is shown beside the verdict.

Usage: assemble.py <scored.json> <out_dir> [<hubs.json> <libs_dir>] [--heartbeat rescored.json --potential potential.json
                    --heartbeat-extras book_extras.json --heartbeat-notes notes.json --heartbeat-insights insights.json
                    --proof <Heartbeat Source>/shared/anatta.json]
                    [--openings openings.json] [--fixes fixes.json] [--scrub scrub.json] [--title "..."] [--label "..."] [--slug ...]
  libs_dir holds node_modules/d3, node_modules/topojson-client, node_modules/us-atlas and na-countries-50m.json
  (see prune_countries.js)."""
import csv, json, sys, os, re, copy, collections, html as _html
argv = sys.argv[1:]
def opt(flag):
    if flag in argv:
        i = argv.index(flag); v = argv[i + 1]; del argv[i:i + 2]; return v
BEAT_P, POT_P, BEAT_NOTES_P, EXTRAS_P = opt("--heartbeat"), opt("--potential"), opt("--heartbeat-notes"), opt("--heartbeat-extras")
INSIGHTS_P, SCRUB_P, TITLE_O, LABEL_O, SLUG_O, PROOF_P = opt("--heartbeat-insights"), opt("--scrub"), opt("--title"), opt("--label"), opt("--slug"), opt("--proof")
OPEN_P, FIXES_P, CHAL_P, SETTLED_P = opt("--openings"), opt("--fixes"), opt("--challenge"), opt("--challenge-settled")
scored_p, OUT = argv[:2]
hubs_p, LIB = (argv[2], argv[3]) if len(argv) > 3 else (None, None)
here = os.path.dirname(os.path.abspath(__file__))
tpl = open(os.path.join(here, "dashboard.html"), encoding="utf-8").read()
head, body = re.match(r"<!--HEAD-->\n(.*?)<!--/HEAD-->\n(.*)$", tpl, re.S).groups()
TEMPLATE_AS_LIST = [("Two lists, one book", "Two lists, one set of accounts"), ("The whole book", "The whole list"), ("Read the book", "Read the list"), ("Our own book", "Our own list"), ("with this book", "with this list"),
                    ("scored book", "scored list"), ("Book-specific handling.", "Handling specific to this list."), (" · book lists ", " · listed as "), ("Other storefronts the book lists", "Other storefronts on the list"),
                    ("in the book", "on the list"), ("of the book", "of the list"), ("The book", "The list"), ("the book", "the list")]
sc = json.load(open(scored_p))
for k, v in (("title", TITLE_O), ("book_label", LABEL_O), ("slug", SLUG_O)):
    if v: sc["summary"][k] = v
TITLE, SLUG = sc["summary"]["title"], sc["summary"]["slug"]
if "book" not in sc["summary"]["book_label"].lower():
    for a, b in TEMPLATE_AS_LIST: body = body.replace(a, b)

# ---------- house wording, applied to every string a reader can see ----------
HOUSE = [(r"[\w.+-]+@((?:[\w-]+\.)+[a-z]{2,})", r"an address at \1", "email address masked to its domain"),
         (r"\bShopify['’]s AEs?\b", "Shopify's seller", '"AE" written as seller'), (r"\bAEs\b", "sellers", '"AE" written as seller'), (r"\bAE\b", "seller", '"AE" written as seller'),
         (r"\s*—\s*", ", ", "em dash written as a comma"),
         # other firms are left out of every note: the search for one is a partner search, and the platform in place is the current platform
         (r"\bagency workers\b", "temporary workers", "other firms left out"), (r"\bAgency Search\b", "Partner Search", "other firms left out"), (r"\b([Aa])n agency[- ]search\b", r"\1 partner search", "other firms left out"), (r"\bagency[- ]search\b", "partner search", "other firms left out"),
         (r"\boutside agencies\b", "outside firms", "other firms left out"), (r"\boutside agency\b", "outside firm", "other firms left out"), (r"\bbuild agency\b", "build firm", "other firms left out"), (r"\bagency detection\b", "builder detection", "other firms left out"),
         (r"\bcommerce agency signal\b", "commerce partner signal", "other firms left out"), (r"\ban agency gap\b", "an opening for a build partner", "other firms left out"), (r"\bagency engagement\b", "outside engagement", "other firms left out"),
         (r"\bagency (review|news)\b", r"partner \1", "other firms left out"), (r"\b([Aa])n agency\b", r"\1n outside firm", "other firms left out"), (r"\b([Nn])o agency\b", r"\1o outside firm", "other firms left out"),
         (r"\bits agency\b", "its build firm", "other firms left out"), (r"\bagencies\b", "outside firms", "other firms left out"), (r"\bagency\b", "outside firm", "other firms left out"),
         (r"\bdefended incumbent\b", "defended platform", "other firms left out"), (r"\bon its incumbent\b", "on its current platform", "other firms left out"), (r"\b([Tt])he incumbent platform\b", r"\1he current platform", "other firms left out"),
         (r"\bthe incumbent most likely\b", "the stack most likely", "other firms left out"), (r"\bThe incumbent\b", "The current platform", "other firms left out"), (r"\bincumbents?\b", "current platform", "other firms left out")]
# Where the owner calls the accounts a list, the page does too: in the notes, and in the template's own wording below.
LISTWORDS = [(r"\bin (?:the|this) book\b", "on the list"), (r"\b([Tt])he book lists\b", r"\1he list gives"), (r"\bthe book rules\b", "the list's rules"), (r"\bthe book notes\b", "the list's notes"),
             (r"\b([Tt])he book\b", r"\1he list"), (r"\b(?:your|this) book\b", "this list")]
AS_LIST = "book" not in sc["summary"]["book_label"].lower()
if AS_LIST: HOUSE += [(pat, to, "the account list called a list, not a book") for pat, to in LISTWORDS]
RAW_KEYS = {"fire", "signals_raw", "builtwith", "storeleads"}       # shown exactly as exported
SCRUB = [tuple(r) for r in json.load(open(SCRUB_P, encoding="utf-8"))] if SCRUB_P else []
JOIN_KEYS = {"name", "display", "group", "family", "lead", "rows", "partner", "book_name", "domain", "book_domain", "website", "linkedin", "source", "final_url"}   # identifiers and links: never reworded
HIDDEN_STACK_KEYS = {"Agency"}       # BuiltWith's guess at who built a site
tidied = collections.Counter()
def tidy(x, key=None):
    if isinstance(x, dict): return {k: (v if k in JOIN_KEYS or k in RAW_KEYS else tidy(v, k)) for k, v in x.items()}
    if isinstance(x, list): return [tidy(v, key) for v in x]
    if not isinstance(x, str) or re.match(r"https?://", x): return x
    for pat, to, why in SCRUB + HOUSE:
        x, n = re.subn(pat, to, x)
        if n: tidied[why] += n
    return x[:1].upper() + x[1:] if x[:4] in ("the ", "an o", "its ") and key in ("claim", "reason") else x
if FIXES_P:      # corrections found after the research was written, applied before anything is shown
    FX = json.load(open(FIXES_P, encoding="utf-8")); acc_by = {a["name"]: a for a in sc["accounts"]}
    def _walk(x, fn): return {k: _walk(v, fn) for k, v in x.items()} if isinstance(x, dict) else [_walk(v, fn) for v in x] if isinstance(x, list) else fn(x) if isinstance(x, str) else x
    for f in FX["fixes"]:
        hits = []
        def fn(s, f=f, hits=hits):
            if "find" in f and f["find"] in s: hits.append(1); return s.replace(f["find"], f["replace"])
            if "match" in f and re.search(f["match"], s) and f.get("unless", "\x00") not in s and f["append"] not in s: hits.append(1); return s.rstrip() + " " + f["append"]
            return s
        a = acc_by[f["account"]]; new = _walk(a, fn); a.clear(); a.update(new)
        assert hits, f'correction matched nothing at {f["account"]}: {f.get("find") or f.get("match")}'
    print(f'corrections applied after the research: {len(FX["fixes"])} at {len({f["account"] for f in FX["fixes"]})} accounts')
for a in sc["accounts"]:
    for k in HIDDEN_STACK_KEYS:
        if (a.get("builtwith") or {}).pop(k, None) is not None: tidied["BuiltWith's Agency field left out"] += 1
sc["accounts"] = [tidy(a) for a in sc["accounts"]]
assert head.count("__TITLE__") == 1
head = head.replace("__TITLE__", _html.escape(TITLE))
ICON = "<link rel=\"icon\" href=\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Cpath d='M8 2 L14.5 13.5 L1.5 13.5 Z' fill='none' stroke='%232a78d6' stroke-width='1.7' stroke-linejoin='round'/%3E%3C/svg%3E\">"
SFDC_ID = re.compile(r"\b00[13Q][A-Za-z0-9]{12}(?:[A-Za-z0-9]{3})?\b")   # account (001), contact (003) and lead (00Q) record IDs
INTERNAL_ONLY_ACCOUNT_KEYS = ["in_sfdc"]
INTERNAL_ONLY_SUMMARY_KEYS = ["not_in_sfdc"]
# notes about our own records, and corrections to our own earlier review of the book, stay inside
# ("CRM" and "in Salesforce" only count when they are about our own records: both are also products an account can run)
INTERNAL_FLAG = re.compile(r"\b(?:our|anatta['’]s|the) CRM\b|\bCRM (?:notes?|records?|presence)\b"
                           r"|\b(?:not|already|also|is|are) in salesforce\b(?! commerce|['’]s)|^in salesforce\b(?! commerce|['’]s)|\bin salesforce(?=[.;,)]|$)"
                           r"|\bSFDC\b|\bearlier (?:review|read)\b|\bprior (?:read|note)\b", re.I)
CDN = ('<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>\n'
       '<script src="https://cdn.jsdelivr.net/npm/topojson-client@3.1.0/dist/topojson-client.min.js"></script>')

# ---------- contacts layer (optional) ----------
hb = json.load(open(hubs_p)) if hubs_p else None
SEN = ["C-level", "Founder / Owner", "VP", "Director", "Manager / Staff", "Other"]
people_of = collections.defaultdict(list)
if hb:
    names = {a["name"] for a in sc["accounts"]}
    assert all(c["acct"] in names for c in hb["contacts"]), "a contact points at an account that is not in the scored book"
    assert sum(h["n"] for h in hb["hubs"]) == hb["summary"]["mapped"] == sum(1 for c in hb["contacts"] if c["hub"] is not None)
    assert len(hb["contacts"]) == hb["summary"]["kept"]
    for c in hb["contacts"]: people_of[c["acct"]].append(c)
    libs = {"d3": open(f"{LIB}/node_modules/d3/dist/d3.min.js", encoding="utf-8").read(),
            "topojson": open(f"{LIB}/node_modules/topojson-client/dist/topojson-client.min.js", encoding="utf-8").read()}
    assert all("</script" not in v for v in libs.values())
    topo = {"__COUNTRIES__": open(f"{LIB}/na-countries-50m.json", encoding="utf-8").read().replace("<", "\\u003c"),
            "__STATES__": open(f"{LIB}/node_modules/us-atlas/states-10m.json", encoding="utf-8").read().replace("<", "\\u003c")}

# ---------- Heartbeat ranking (optional) ----------
beat = None
if BEAT_P:
    R = json.load(open(BEAT_P, encoding="utf-8")); POT = json.load(open(POT_P, encoding="utf-8")) if POT_P else {}
    extra = json.load(open(BEAT_NOTES_P, encoding="utf-8")) if BEAT_NOTES_P else {}
    EXTRAS = json.load(open(EXTRAS_P, encoding="utf-8")) if EXTRAS_P else {}     # book_extras.json: what the scans could read, per company
    W = R["weights"]
    rows_of = collections.OrderedDict()
    for a in sc["accounts"]: rows_of.setdefault(a.get("group") or a["name"], []).append(a)
    open_groups = [g for g, rs in rows_of.items() if any(not a.get("gate") for a in rs)]
    def join(r, ranked):
        rs = rows_of[r["group"]]; lead = max((a for a in rs if not a.get("gate")), key=lambda a: a["triangle"])
        d = {"group": r["group"], "display": r["group"] if len(rs) > 1 else lead["display"], "lead": lead["name"], "rows": [a["name"] for a in rs],
             "segment": r["segment"], "fit": r["fit"], "parts": r["parts"], "why": r["why"], "book_tier": r["book_tier"], "triangle": r["triangle"], "platform": r["platform"]}
        if not ranked: return d
        e = POT.get(r["group"]) or {}
        # every score is the Heartbeat Source's; this only checks that it recomputes from the four measures it came with
        assert r["priority"] == min(100, round(sum(W[k] * r[k] for k in W)) + r["bonus"]), f'{r["group"]}: Heartbeat score does not recompute'
        d.update({k: r[k] for k in ("rank", "priority", "motion", "timing", "timingBase", "shopPay", "potential", "potentialParts", "subscription", "bonus", "first")})
        d["moves"] = [{k: m.get(k, "") for k in ("partner", "motives", "live", "evidence", "gap", "trigger", "triggerDate")} for m in r["moves"]]
        d.update({k: e[k] for k in ("online", "onlineNote", "stores", "storesNote", "sites", "sitesNote", "headroomNote", "shopPayWhy", "subscriptionNote") if e.get(k) not in (None, "")})
        if (EXTRAS.get(r["group"]) or {}).get("coverage"): d["coverage"] = EXTRAS[r["group"]]["coverage"]
        return d
    beat = {"month": extra.get("month", ""), "weights": W, "ranked": [join(r, True) for r in R["ranked"]], "outside": [join(r, False) for r in R["outside"]],
            "notes": extra.get("notes", []), "method_notes": extra.get("method_notes", [])}
    got = [r["group"] for r in beat["ranked"] + beat["outside"]]
    assert sorted(got) == sorted(open_groups), "the Heartbeat ranking and the book do not list the same companies"
    assert [r["rank"] for r in beat["ranked"]] == list(range(1, len(beat["ranked"]) + 1))
    if OPEN_P:      # the reach test goes first; the companies that can move are ranked on the score reach_rank.py built
        O = json.load(open(OPEN_P, encoding="utf-8")); hb_rows = {r["group"]: r for r in beat["ranked"]}
        assert sorted(x["group"] for k in ("ranked", "long", "later", "out") for x in O[k]) == sorted(hb_rows), "the reach ranking and the Heartbeat ranking do not cover the same companies"
        assert O["weights"] == {"path": W["motion"], "fit": W["fit"], "opening": W["timing"], "potential": W["potential"]}, "the reach ranking was not scored with the Heartbeat's weights"
        def reach_row(x):
            d = hb_rows[x["group"]]
            d["hb"] = {k: d[k] for k in ("rank", "priority", "motion", "timing", "timingBase")}       # the Heartbeat's own numbers, kept for comparison
            d["reach"] = {k: x[k] for k in ("state", "kind", "why", "again", "note", "basis") if x.get(k)}       # basis: which rule or which person made the call
            d.update({k: x[k] for k in ("window", "signals", "opening_parts", "path_parts", "family", "intent", "first")})
            d["fire"] = {k: v for k, v in x["fire"].items() if k != "signals"}      # the exported topic labels stay on the first pass's record, shown as exported
            if x["state"] in ("open", "long"):
                d.update({"priority": x["score"], "rank": x.get("rank"), "motion": x["path"], "timing": x["opening"]})
                exact = sum(round(W[k] * 100) * d[k] for k in W)        # in hundredths: halves go up, as a reader would round them
                assert d["priority"] == min(100, (exact + 50) // 100 + d["bonus"]), f'{x["group"]}: the score does not recompute'
            else:
                d.update({"priority": None, "rank": None})
            return d
        beat.update({k: [reach_row(x) for x in O[k]] for k in ("ranked", "long", "later", "out")})
        assert [r["rank"] for r in beat["ranked"]] == list(range(1, len(beat["ranked"]) + 1))
        beat["reach"] = {"as_of": O["as_of"], "classes": O["classes"], "groups": O["groups"], "shares": O["shares"], "frozen": O["frozen"], "family": O["family"],
                         "sensitivity": O["sensitivity"], "scored": len(hb_rows)}
    if CHAL_P:       # what an independent reader found when asked to knock each of the first ten out
        import glob
        settled = json.load(open(SETTLED_P, encoding="utf-8")) if SETTLED_P else {}
        answers = {c["group"]: c for p in sorted(glob.glob(os.path.join(CHAL_P, "out_*.json"))) for c in json.load(open(p, encoding="utf-8"))["companies"]}
        by_g = {r["group"]: r for r in beat["ranked"] + beat.get("long", [])}
        assert all(g in by_g for g in settled), f"a settled challenge names a company that is not ranked: {[g for g in settled if g not in by_g]}"
        for g, c in answers.items():
            if g not in by_g: continue
            ch = {"verdict": c["verdict"], "summary": c["summary"], "against": c.get("against") or [], "for": c.get("for") or [],
                  "signals": [{"status": s["status"], "note": s.get("note", ""), "source": s.get("source")} for s in c.get("signals") or []], "not_checked": c.get("not_checked") or []}
            if settled.get(g): ch["settled"] = settled[g]
            by_g[g]["challenge"] = tidy(ch)          # a reader's notes get the house wording like any other research note
        beat["challenged"] = sum(1 for r in beat["ranked"][:10] if r.get("challenge"))
    aside = beat.get("long", []) + beat.get("later", []) + beat.get("out", [])
    beat_of = {n: r for r in beat["ranked"] + aside + beat["outside"] for n in r["rows"]}
    if INSIGHTS_P:      # what the ranking says, the subscription view and the lines written for each company (see README)
        ins = json.load(open(INSIGHTS_P, encoding="utf-8")); rank_of = {r["group"]: r for r in beat["ranked"] + aside}
        assert all(g in rank_of for g in ins.get("accounts", {})), "an insight is written for a company that is not ranked"
        beat["insights"] = {k: ins[k] for k in ("headline", "intro", "findings", "accounts") if ins.get(k)}
        beat["proof"] = json.load(open(PROOF_P, encoding="utf-8"))["proof"] if PROOF_P else {}    # the Proof Genome roll-up: totals are tokens in the text
        used = set(re.findall(r"\{proof\.(\w+)\}", json.dumps(ins, ensure_ascii=False)))
        assert used <= set(beat["proof"]), f"proof tokens with no value: {sorted(used - set(beat['proof']))}"
        subs = ins.get("subscriptions")
        if subs:
            TIER_WHY = {"EXP": "Already on Shopify Plus", "X": "Gated out"}; ASIDE_WHY = {"long": "Long odds", "later": "Not now", "out": "Out of reach"}
            for row in subs["rows"]:
                r = rank_of.get(row["group"]); rs = rows_of.get(row["group"])
                assert rs, f'{row["group"]}: the subscription view names a company that is not on the list'
                context = bool(row.pop("context_only", False))       # only free loyalty or one-off plans recorded: shown on the record, not in the table
                if r:
                    row.update({"rank": r["rank"], "priority": r["priority"], "display": r["display"], "lead": r["lead"]})
                    assert (row["state"] == "live") == bool(r["bonus"]), f'{row["group"]}: the subscription view and the bonus disagree'
                    state = (r.get("reach") or {}).get("state", "open")
                    if state != "open": row.update({"why_not_ranked": ASIDE_WHY[state], "aside": state, "was": r["hb"]["rank"]})
                    row["section"] = ("live" if state == "open" else "aside") if row["state"] == "live" else "ended" if row["state"] == "ended" else "context" if context else "noted"
                else:
                    lead = max(rs, key=lambda a: a["triangle"] or 0); out_of_icp = any(o["group"] == row["group"] for o in beat["outside"])
                    row.update({"rank": None, "priority": None, "display": row["group"] if len(rs) > 1 else lead["display"], "lead": lead["name"],
                                "why_not_ranked": "Outside the ICP" if out_of_icp else TIER_WHY.get(lead["tier"], "Not ranked")})
                    row["section"] = "unranked" if row["state"] == "live" else "ended" if row["state"] == "ended" else "context" if context else "noted"
            ORDER = {"live": 0, "aside": 1, "unranked": 2, "ended": 3, "noted": 4, "context": 5}; A_ORDER = {"long": 0, "later": 1, "out": 2}
            subs["rows"].sort(key=lambda x: (ORDER[x["section"]], A_ORDER.get(x.get("aside"), 0), x["rank"] is None, x["rank"] or x.get("was") or 0, x["group"]))
            beat["subscriptions"] = subs
    # The Heartbeat layer is held to the wording rules at the source: nothing here may need rewording.
    before = json.dumps(beat, ensure_ascii=False, sort_keys=True); n0 = sum(tidied.values())
    assert json.dumps(tidy(beat), ensure_ascii=False, sort_keys=True) == before, "the Heartbeat inputs carry wording the house rules ban: fix it in the inputs (" + ", ".join(k for k in tidied) + ")"
    assert sum(tidied.values()) == n0

def mask(email):
    if not email: return ""
    local, _, dom = email.partition("@"); return f"{local[:1]}•••@{dom}"

def build(internal, target):
    masked = bool(hb) and not (internal and target == "file")     # full emails only in the internal standalone file
    accounts, summary = copy.deepcopy(sc["accounts"]), copy.deepcopy(sc["summary"])
    if internal:
        for a in accounts: a["crm_note"] = "In Salesforce" if a["in_sfdc"] else "Not in Salesforce"
    else:
        for a in accounts:
            for k in INTERNAL_ONLY_ACCOUNT_KEYS: a.pop(k, None)
            if "flags" in a: a["flags"] = [f for f in a["flags"] if not INTERNAL_FLAG.search(f)]
        for k in INTERNAL_ONLY_SUMMARY_KEYS: summary.pop(k, None)
    summary["copy_note"] = ("Internal copy: it shows which accounts are in Salesforce and how far our own signal can be trusted. Do not forward outside Anatta."
                            if internal else "CRM record IDs and internal notes are stripped; this copy is safe to share with Shopify.")
    data = {"internal": internal, "target": target, "summary": summary, "accounts": accounts}
    if beat: data["heartbeat"] = beat
    if hb:
        contacts = copy.deepcopy(hb["contacts"])
        raw_emails = [c["email"] for c in contacts if c["email"]]
        if masked:
            for c in contacts: c["email"] = mask(c["email"])
        for a in accounts:   # people per account, most senior first, for the plays and the record
            ps = sorted(people_of.get(a["name"], []), key=lambda c: (SEN.index(c["seniority"]) if c["seniority"] in SEN else 9, c["last"]))
            a["contacts"] = len(ps); a["people"] = [c["id"] for c in ps]
        data.update({"masked": masked, "contacts": contacts, "hubs": hb["hubs"], "hub_summary": hb["summary"]})
        summary["copy_note"] += (" Contact emails are masked to first initial and domain in this copy." if masked else " Contact emails are shown in full: treat this file as sensitive.")
    blob = json.dumps(data, separators=(",", ":"), ensure_ascii=False).replace("<", "\\u003c")
    assert not SFDC_ID.search(blob), "a Salesforce record ID is in the data"
    if not internal:
        assert not any(k in blob for k in ('"in_sfdc"', '"not_in_sfdc"', '"crm_note"')), "internal-only field left in the shareable copy"
        assert not any(INTERNAL_FLAG.search(f) for a in accounts for f in a.get("flags", [])), "internal CRM note left in the shareable copy"
    if hb and masked:
        leaked = [e for e in raw_emails if e in blob]
        assert not leaked, f"{len(leaked)} unmasked email(s) left in a masked build"
        assert sum(1 for c in contacts if "•••@" in c["email"]) == len(raw_emails) == hb["summary"]["with_email"], "masked count does not match the number of emails"
    tpl_body = body
    if not internal:   # the internal-only section leaves the file entirely: markup, script and wording
        tpl_body = re.sub(r"<!--INTERNAL-->.*?<!--/INTERNAL-->\n?", "", tpl_body, flags=re.S)
        tpl_body = re.sub(r"/\*INTERNAL\*/.*?/\*/INTERNAL\*/\n?", "", tpl_body, flags=re.S)
        assert "ov-signal" not in tpl_body and "INTERNAL-->" not in tpl_body
    if target == "artifact":   # a published page cannot start a download, so the save-to-file code is left out of that build
        tpl_body = re.sub(r"/\*FILEONLY\*/.*?/\*/FILEONLY\*/\n?", "", tpl_body, flags=re.S)
        assert ".download" not in tpl_body and "createObjectURL" not in tpl_body
    if not hb:                 # no contacts: the hub map view, its script and its libraries are not in the file at all
        tpl_body = re.sub(r"<!--MAP-->.*?<!--/MAP-->\n?", "", tpl_body, flags=re.S)
        tpl_body = re.sub(r"/\*MAP\*/.*?/\*/MAP\*/\n?", "", tpl_body, flags=re.S)
        assert "__LIBS__" not in tpl_body and "__COUNTRIES__" not in tpl_body
    for marker in ("<!--INTERNAL-->\n", "<!--/INTERNAL-->\n", "/*INTERNAL*/\n", "/*/INTERNAL*/\n", "/*FILEONLY*/\n", "/*/FILEONLY*/\n",
                   "<!--MAP-->\n", "<!--/MAP-->\n", "/*MAP*/\n", "/*/MAP*/\n"):
        tpl_body = tpl_body.replace(marker, "")
    page = tpl_body
    if hb:
        assert page.count("__LIBS__") == 1
        page = page.replace("__LIBS__", CDN if target == "artifact" else f'<script>{libs["d3"]}</script>\n<script>{libs["topojson"]}</script>')
        for k, v in topo.items():
            assert page.count(k) == 1; page = page.replace(k, v)
    assert page.count("__DATA__") == 1
    page = page.replace("__DATA__", blob)
    assert page.count('id="data"') == 1 and not re.search(r"__(DATA|LIBS|COUNTRIES|STATES)__", page)
    if not internal:
        for needle in ("our own signal", "not in Salesforce", "Not in Salesforce", "Do not forward"):
            assert needle not in page, f"internal wording left in the shareable copy: {needle}"
    if target == "artifact":
        return head + page, masked
    return ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n"
            + ICON + "\n" + head + "</head>\n<body>\n" + page + "</body>\n</html>\n"), masked

BEAT_COLS = {"heartbeat_rank": lambda r: r.get("rank", ""), "heartbeat_score": lambda r: r.get("priority", ""), "heartbeat_segment": lambda r: r["segment"],
             "partner_motion": lambda r: r.get("motion", ""), "anatta_icp_fit": lambda r: r["fit"], "heartbeat_timing": lambda r: r.get("timing", ""), "potential": lambda r: r.get("potential", ""),
             "subscription": lambda r: r.get("subscription", ""), "shop_pay": lambda r: r.get("shopPay", ""), "partner_to_move_first": lambda r: (r.get("first") or [""])[0]}
CSV_COLS = ["name", "display", "group", "family", "domain", "book_domain", "tier", "triangle", "shopify_fit", "anatta_fit", "gate", "gate_reason", "category", "model",
            "plat", "platform", "size_est", "hq", "ownership", "confidence", "fire_score", "fire_intent", "fire_in_market", "fire_signals",
            "fire_last_signal", "story", "shopify_angle", "anatta_angle", "flags", "adjustments"]
if beat and beat.get("reach"):        # the reach test went first: the sheet says where each company landed and keeps the Heartbeat's own numbers beside it
    _REACH = {"open": "in reach", "long": "long odds", "later": "not now", "out": "out of reach"}; _WIN = dict(beat["reach"]["groups"])
    BEAT_COLS = {"reach": lambda r: _REACH[r["reach"]["state"]] if r.get("reach") else "outside the ICP", "reach_reason": lambda r: (r.get("reach") or {}).get("why", "") if r.get("reach") else r.get("why", ""),
                 "rank": lambda r: r.get("rank") or "", "score": lambda r: r.get("priority") if r.get("priority") is not None else "", "opening_rests_on": lambda r: _WIN.get(r.get("window"), "") if (r.get("reach") or {}).get("state") in ("open", "long") else "",
                 "way_in": lambda r: r.get("motion", "") if r.get("priority") is not None else "", "anatta_icp_fit": lambda r: r["fit"], "opening": lambda r: r.get("timing", "") if r.get("priority") is not None else "", "potential": lambda r: r.get("potential", ""),
                 "icp_segment": lambda r: r["segment"], "subscription": lambda r: r.get("subscription", ""), "shop_pay": lambda r: r.get("shopPay", ""), "partner_to_move_first": lambda r: (r.get("first") or [""])[0],
                 "heartbeat_rank_alone": lambda r: (r.get("hb") or {}).get("rank", ""), "heartbeat_score_alone": lambda r: (r.get("hb") or {}).get("priority", "")}
if beat and beat.get("insights"):     # with an insight layer the CSV carries the one-line read and the programs that count
    _sub = {x["group"]: x for x in (beat.get("subscriptions") or {}).get("rows", [])}
    BEAT_COLS["subscription_programs"] = lambda r: "; ".join(f'{p["name"]} ({p["store"]}; {p["engine"]})' for p in (_sub.get(r["group"]) or {}).get("programs", []) if p.get("counts") and p.get("status") == "live")
    BEAT_COLS["heartbeat_read"] = lambda r: (beat["insights"].get("accounts", {}).get(r["group"]) or {}).get("read", "")
def write_csv(path, internal):
    cols = (CSV_COLS + (["platform_read", "storeleads_sales"] if sc["summary"].get("sources") else []) + (["contacts"] if hb else [])
            + (["second_look_would_be"] if any(a.get("second_look") for a in sc["accounts"]) else []) + (list(BEAT_COLS) if beat else []) + (["in_salesforce"] if internal else []))
    def val(a, k):
        if k.startswith("fire_"): return a["fire"][k[5:]]
        if k == "flags": return " | ".join(f for f in a.get("flags", []) if internal or not INTERNAL_FLAG.search(f))
        if k == "adjustments": return " | ".join(a.get("adjustments", []))
        if k == "in_salesforce": return "yes" if a["in_sfdc"] else "no"
        if k == "contacts": return len(people_of.get(a["name"], []))
        if k == "platform_read": return (a.get("platform_read") or {}).get("verdict", "")
        if k == "storeleads_sales": return (a.get("storeleads") or {}).get("Estimated yearly sales", "")
        if k in BEAT_COLS:                # the company's Heartbeat row, on each of its ungated rows
            return BEAT_COLS[k](beat_of[a["name"]]) if a["name"] in beat_of and not a.get("gate") else ""
        if k == "second_look_would_be":   # the tier on the second look's own figures, only where it differs from the tier shown
            v = (a.get("second_look") or {}).get("reviewer", {}).get("tier", "")
            return v if v and v != a["tier"] and a.get("gate") != "not_pursued" else ""
        return a.get(k, "")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(cols)
        for a in sc["accounts"]: w.writerow([val(a, k) for k in cols])
    text = open(path, encoding="utf-8").read()
    assert not SFDC_ID.search(text), "a Salesforce record ID is in the CSV"
    if not internal: assert "in_salesforce" not in text
    print(f"{os.path.relpath(path, OUT):55s} {len(text.encode('utf-8')) / 1024:6.0f} KB  {'internal' if internal else 'shareable'}/csv")

os.makedirs(f"{OUT}/artifact", exist_ok=True)
for internal in (True, False):
    kind = "internal" if internal else "shareable"
    for target, path in (("file", f"{OUT}/{SLUG}-{kind}.html"), ("artifact", f"{OUT}/artifact/{SLUG}-{kind}.html")):
        page, masked = build(internal, target)
        open(path, "w", encoding="utf-8").write(page)
        emails = "" if not hb else ", emails masked" if masked else ", FULL emails"
        print(f"{os.path.relpath(path, OUT):55s} {len(page.encode('utf-8')) / 1024:6.0f} KB  {kind}/{target}{emails}")
    write_csv(f"{OUT}/{SLUG}-accounts-{kind}.csv", internal)
t = sc["summary"]["tiers"]
print("accounts", sc["summary"]["accounts"], "| tiers", {k: t[k] for k in sorted(t)}, ("| contacts %d in %d hubs" % (hb["summary"]["kept"], hb["summary"]["hubs"])) if hb else "| no contacts layer")
if tidied: print("house wording applied to the research notes:", "; ".join(f"{k} ({n})" for k, n in sorted(tidied.items())))
