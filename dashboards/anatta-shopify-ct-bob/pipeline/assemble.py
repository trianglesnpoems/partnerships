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
behind each measure; --heartbeat-notes is a JSON file {"month": ..., "notes": [...], "method_notes": [...]}.
Nothing is scored here: the build only joins the ranking to the book and asserts that every score recomputes.

Usage: assemble.py <scored.json> <out_dir> [<hubs.json> <libs_dir>] [--heartbeat rescored.json --potential potential.json --heartbeat-notes notes.json]
  libs_dir holds node_modules/d3, node_modules/topojson-client, node_modules/us-atlas and na-countries-50m.json
  (see prune_countries.js)."""
import csv, json, sys, os, re, copy, collections, html as _html
argv = sys.argv[1:]
def opt(flag):
    if flag in argv:
        i = argv.index(flag); v = argv[i + 1]; del argv[i:i + 2]; return v
BEAT_P, POT_P, BEAT_NOTES_P = opt("--heartbeat"), opt("--potential"), opt("--heartbeat-notes")
scored_p, OUT = argv[:2]
hubs_p, LIB = (argv[2], argv[3]) if len(argv) > 3 else (None, None)
here = os.path.dirname(os.path.abspath(__file__))
tpl = open(os.path.join(here, "dashboard.html"), encoding="utf-8").read()
head, body = re.match(r"<!--HEAD-->\n(.*?)<!--/HEAD-->\n(.*)$", tpl, re.S).groups()
sc = json.load(open(scored_p))
TITLE, SLUG = sc["summary"]["title"], sc["summary"]["slug"]
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
        return d
    beat = {"month": extra.get("month", ""), "weights": W, "ranked": [join(r, True) for r in R["ranked"]], "outside": [join(r, False) for r in R["outside"]],
            "notes": extra.get("notes", []), "method_notes": extra.get("method_notes", [])}
    got = [r["group"] for r in beat["ranked"] + beat["outside"]]
    assert sorted(got) == sorted(open_groups), "the Heartbeat ranking and the book do not list the same companies"
    assert [r["rank"] for r in beat["ranked"]] == list(range(1, len(beat["ranked"]) + 1))
    beat_of = {n: r for r in beat["ranked"] + beat["outside"] for n in r["rows"]}

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
