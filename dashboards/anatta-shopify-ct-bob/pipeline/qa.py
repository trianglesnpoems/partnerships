"""Release QA for a book ranked the Heartbeat way. Run after assemble.py. Exit code 1 if anything fails.

    python3 qa.py --internal out/<slug>-internal.html --shareable out/<slug>-shareable.html \\
        --source <Heartbeat Source folder> --seller <slug> --issue <its issues/....json> \\
        [--facts partner_facts.json] [--csv-internal a.csv --csv-shareable b.csv] [--ids-from <the CRM export>.csv] \\
        [--scrub scrub.json] [--reach reach.json --signals signals.json --as-of YYYY-MM-DD] [--no-page]

It follows the Heartbeat Source's own tools/qa.py, on the page this pipeline builds.

Part 1, data (always). Every Heartbeat number on the page is recomputed from the inputs and compared: Anatta fit from
the ICP entry, potential from the research, timing with the Shop Pay lift, partner motion from the moves, the
subscription bonus, the score, the order. Then: every partner a move calls live is live in the partner facts, every
proof line traces to the Proof Genome, no unpublished client is named unless naming.json clears it, the insight lines
keep the writing rules, the two editions and the two CSVs agree, and nothing private is in a file that leaves.

Part 2, the page (needs Playwright for Node; qa_page.js beside this file). Both editions at 390x844 and 1440x900: no
script errors, nothing wider than the screen, the ranking in score order, every ranked company opens with its score,
links open safely, and no banned wording anywhere a reader can see.

With --reach, --signals and --as-of the page was built with the reach test in front (reach_rank.py). Then every company
the Heartbeat scored must be ranked or set aside with its reason, the Heartbeat's own numbers are checked where the page
keeps them, and the opening, the way in, the score and the order are recomputed here from the reach calls, the signals,
the moves and the research: a second implementation, not a call to reach_rank.py.

The Heartbeat wording rules are applied in full to everything the Heartbeat layer shows. The triangulation underneath
was written to the triangulation template, which calls the account list "the book", so that one phrase is counted
there and reported, not failed.
"""
import argparse, csv, json, os, re, subprocess, sys

ap = argparse.ArgumentParser()
ap.add_argument('--internal', required=True); ap.add_argument('--shareable', required=True)
ap.add_argument('--source', required=True, help='the Heartbeat Source folder (tools/, data/<seller>/, data/shared/)')
ap.add_argument('--seller', required=True); ap.add_argument('--issue', required=True)
ap.add_argument('--facts'); ap.add_argument('--csv-internal'); ap.add_argument('--csv-shareable'); ap.add_argument('--ids-from')
ap.add_argument('--scrub', help="the book's scrub list given to assemble.py: nothing it removes may be left")
ap.add_argument('--reach'); ap.add_argument('--signals'); ap.add_argument('--as-of')
ap.add_argument('--no-page', action='store_true')
A = ap.parse_args()
os.environ['HB_SELLER'] = A.seller
sys.path.insert(0, os.path.join(A.source, 'tools'))
import paths, icp, potential as pot       # the model itself: the same code the ranking ran on

J = lambda p: json.load(open(p, encoding='utf-8'))
book, POT, EXTRAS, R, ISSUE = J(paths.BOOK), J(paths.POTENTIAL), J(paths.EXTRAS), J(paths.RESCORED), J(A.issue)
genome, NAMING, REG = J(paths.GENOME), J(paths.NAMING), J(paths.REGISTRY)
fails, notes, passes = [], [], 0


def check(ok, what, detail=''):
    global passes
    if ok:
        passes += 1
    else:
        fails.append(f'{what}{": " + str(detail) if detail != "" else ""}')


def page_data(path):
    html = open(path, encoding='utf-8').read()
    m = re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S)
    return html, json.loads(m.group(1))


# What a reader must never see. Each is (pattern, why, applies to the triangulation layer too).
BANNED = [
    (r'(?i)\b(?:your|the|his|her|their|enterprise) book\b|\bbook closed\b', '"book" phrasing', False),
    (r'(?i)\byour (?:people|ten)\b|\bits people\b|\bof your 10\b', 'possessive framing', True),
    (r'—', 'em dash', True),
    (r'\bAEs?\b', '"AE"', True),
    (r'(?i)\bincumbent\b|\b(?<!agentic )agenc(?:y|ies)\b', 'other agencies', False),
    (r'(?i)deal size|sizing framework|\b(?:Small|Medium|Large|Strategic) · \$', 'deal size', True),
    (r'\bundefined\b|\bNaN\b|\[object Object\]|\{people\}|\{accounts\}|\{proof\.\w+\}', 'unfilled value', True),
    (r'[\w.+-]+@[\w-]+\.[a-z]{2,}', 'email address', True),
]


def scan(text, where, strict=True):
    for pat, why, everywhere in BANNED:
        if not strict and not everywhere:
            n = len(re.findall(pat, text))
            if n:
                notes.append(f'{why}: {n} in {where} (triangulation wording, counted, not failed)')
            continue
        m = re.search(pat, text)
        check(not m, f'{why} in {where}', text[max(0, m.start() - 50):m.end() + 50].replace('\n', ' ') if m else '')


strings = lambda x: [s for s in re.findall(r'"((?:[^"\\]|\\.)*)"', json.dumps(x, ensure_ascii=False)) if ' ' in s]
# Firms that build or run stores for a living. Naming the one that works for an account is the thing the rule is for,
# so these fail anywhere a reader can see, whatever the layer. A link to a firm's own case study stays: it is the source.
FIRMS = (r'\b(?:64labs|Deloitte Digital|Accenture|Publicis Sapient|Sapient|OSF Digital|Astound|Merkle|Capgemini|EPAM|Blue Acorn|Avatria|BORN Group|Wunderman|VML|R/GA|'
         r'Corra|Gorilla Group|Vaimo|Tryzens|Pivotree|Slalom|LiveArea|PFSweb|Zaelab|Apply Digital|Redstage|Razorfish|Isobar|Valtech|Thoughtworks|Infosys|Wipro|Cognizant|'
         r'HCLTech|Tech Mahindra|LTIMindtree|Perficient|Rightpoint|Bounteous|Hero Digital|Domaine|Half Helix|Fuel Made|Blend Commerce|Swanky|We Make Websites|Eastside Co|'
         r'Absolute Web|Something Digital|IBM iX|Kasama|Mobikasa|Codal|PixelMEDIA|MediaMonks|Media\.Monks)\b')


SCRUBBED = [r[0] for r in J(A.scrub)] if A.scrub else []


def no_firms(text, where):
    bare = re.sub(r'https?://\S+', '', text)
    for pat in SCRUBBED:
        if pat.startswith('^'):
            continue        # anchored rules reword a whole note: the names they carry are checked by the unanchored ones
        m = re.search(pat, bare)
        check(not m, f'wording on the scrub list is still in {where}', bare[max(0, m.start() - 60):m.end() + 60].replace('\n', ' ') if m else '')
    m = re.search(FIRMS, bare)
    check(not m, f'a firm that builds stores is named in {where}', bare[max(0, m.start() - 60):m.end() + 60].replace('\n', ' ') if m else '')

# ---------------------------------------------------------------- Part 1: data
html_i, D = page_data(A.internal)
html_s, DS = page_data(A.shareable)
HB = D.get('heartbeat')
check(HB is not None, 'the page carries the Heartbeat ranking')
if HB is None:
    print('FAIL the page carries no Heartbeat ranking'); sys.exit(1)
W = R['weights']
check(HB['weights'] == W and W == {'motion': 0.35, 'fit': 0.30, 'timing': 0.20, 'potential': 0.15}, 'weights are 35, 30, 20, 15', HB['weights'])
import datetime
_m = datetime.datetime.strptime(ISSUE['issue']['month'], '%B %Y'); NOW = _m.year * 12 + _m.month - 1
check(HB['month'] == ISSUE['issue']['month'], 'the page shows the issue month', (HB['month'], ISSUE['issue']['month']))
mi = lambda s: int(s.split('-')[0]) * 12 + int(s.split('-')[1]) - 1


def move_score(m):
    trig = bool(m.get('triggerDate')) and abs(mi(m['triggerDate']) - NOW) <= 9
    return len(set(m['motives'])) + (1 if m.get('live') else 0) + (1 if trig else 0)


def motion(moves):
    s = sorted((move_score(m) for m in moves), reverse=True) + [0, 0, 0]
    return round(100 * (0.6 * s[0] + 0.25 * s[1] + 0.15 * s[2]) / 5)


groups = {}
for a in book['accounts']:
    if not a.get('gate'):
        groups.setdefault(a.get('group') or a['name'], []).append(a)
scored = {r['group']: r for r in R['ranked']}
REACHM = HB.get('reach')        # the reach test went first: the page ranks those that can move and sets the rest aside
check(bool(REACHM) == bool(A.reach), 'the page and this run agree on whether the reach test was applied', (bool(REACHM), bool(A.reach)))
ASIDE = HB.get('long', []) + HB.get('later', []) + HB.get('out', [])
onpage = {r['group']: r for r in HB['ranked'] + ASIDE}
hbv = lambda r, k: r['hb'][k] if REACHM else r[k]       # the Heartbeat's own number for a row, wherever the page keeps it
if REACHM:
    check(sorted(onpage) == sorted(scored) and len(onpage) == len(HB['ranked']) + len(ASIDE), 'every company the Heartbeat scored is ranked or set aside, once', sorted(set(onpage) ^ set(scored)))
    check([hbv(r, 'rank') for r in sorted(onpage.values(), key=lambda r: hbv(r, 'rank'))] == list(range(1, len(scored) + 1)), "the Heartbeat's own ranks are kept, 1 to n")
else:
    check(list(onpage) == [r['group'] for r in R['ranked']], 'the page ranks the same companies in the same order as the scored list')
    order = sorted(HB['ranked'], key=lambda r: (-r['priority'], -r['motion'], -r['fit']))
    check([r['group'] for r in order] == list(onpage), 'the ranking is in score order, ties by partner motion then Anatta fit')
check([r['rank'] for r in HB['ranked']] == list(range(1, len(HB['ranked']) + 1)), 'ranks run 1 to n with no gap')
MOTIVES = {'Displacement', 'Portfolio', 'Better together'}
REL = {p['name'] for p in (REG.get('partners') if isinstance(REG, dict) else REG) or [] if p.get('rel')}
live_bonus = 0
for g, r in onpage.items():
    recs, e, x = groups.get(g), POT.get(g), scored.get(g)
    check(bool(recs) and e is not None and x is not None, f'{g}: on the list, researched and scored')
    if not recs or e is None or x is None:
        continue
    lead = max(recs, key=lambda a: a['triangle'])
    check(r['lead'] == lead['name'], f'{g}: the row it opens is its highest-scoring record', (r['lead'], lead['name']))
    members = {a['name'] for a in book['accounts'] if (a.get('group') or a['name']) == g}
    check({a['name'] for a in recs} <= set(r['rows']) <= members, f'{g}: lists the company\'s records and no one else\'s')
    entry = icp.GROUPS.get(g)
    check(entry is not None, f'{g}: has an ICP entry')
    if entry is None:
        continue
    f, parts = icp.fit(entry)
    check(r['fit'] == f == x['fit'] and r['parts'] == parts, f'{g}: Anatta fit recomputes from the ICP entry', (r['fit'], f))
    check(r['segment'] == icp.segment(entry) != 'Outside', f'{g}: segment')
    check(r['why'] == entry[4], f'{g}: the fit reason is the ICP entry\'s')
    p, pparts = pot.potential(e)
    check(r['potential'] == p == x['potential'] and r['potentialParts'] == pparts, f'{g}: potential recomputes from the research', (r['potential'], p))
    for k in ('online', 'stores', 'sites'):
        check(r.get(k) == e.get(k), f'{g}: {k} on the page is the researched figure', (r.get(k), e.get(k)))
    base = round(100 * (0.6 * lead['shopify_sub']['timing'] / 10 + 0.4 * max(0, lead['anatta_sub']['intent'] - 2) / 18))
    base = EXTRAS.get(g, {}).get('timing', base)
    check(hbv(r, 'timingBase') == base, f'{g}: timing before the lift', (hbv(r, 'timingBase'), base))
    check(e.get('shopPay') in ('yes', 'partly', 'no') and r['shopPay'] == e.get('shopPay'), f'{g}: Shop Pay fit matches the research', (r['shopPay'], e.get('shopPay')))
    check(bool(e.get('shopPayWhy')), f'{g}: Shop Pay fit has its reason')
    t = min(100, base + pot.LIFT[e.get('shopPay', 'no')])
    check(hbv(r, 'timing') == t == x['timing'], f'{g}: timing with the Shop Pay lift', (hbv(r, 'timing'), t))
    moves = EXTRAS.get(g, {}).get('moves', [])
    shown = lambda m: {k: m.get(k) for k in ('partner', 'motives', 'live', 'evidence', 'gap', 'trigger', 'triggerDate')}
    check([shown(m) for m in r['moves']] == [shown(m) for m in moves], f'{g}: the moves on the page are the moves that were scored')
    mo = motion(moves)
    check(hbv(r, 'motion') == mo == x['motion'], f'{g}: partner motion recomputes from the moves', (hbv(r, 'motion'), mo))
    for m in moves:
        check(set(m['motives']) <= MOTIVES and m['motives'], f'{g}: {m["partner"]} motives are from the three', m['motives'])
        check(not m.get('triggerDate') or re.fullmatch(r'20\d\d-(0[1-9]|1[0-2])', m['triggerDate']), f'{g}: {m["partner"]} trigger date is YYYY-MM', m.get('triggerDate'))
        check(bool(m.get('triggerDate')) == bool(m.get('trigger')), f'{g}: {m["partner"]} trigger has both its text and its date')
        check(bool(m.get('evidence')), f'{g}: {m["partner"]} move states its evidence')
        if REL:
            check(m['partner'] in REL, f'{g}: {m["partner"]} is a partner in the registry')
    best = sorted(moves, key=lambda m: -move_score(m))[0] if moves else None
    if not REACHM:
        check((r['first'] or None) == ([best['partner'], move_score(best)] if best else None), f'{g}: partner to move first', r['first'])
    check(r['subscription'] == e.get('subscription', 'none') and r['subscription'] in ('live', 'ended', 'none'), f'{g}: subscription state matches the research', (r['subscription'], e.get('subscription')))
    b = pot.bonus(e)
    live_bonus += 1 if b else 0
    check(r['bonus'] == b, f'{g}: subscription bonus', (r['bonus'], b))
    check(r['subscription'] == 'none' or bool(e.get('subscriptionNote')), f'{g}: a live or ended program names its evidence')
    score = min(100, round(W['motion'] * mo + W['fit'] * f + W['timing'] * t + W['potential'] * p) + b)
    check(hbv(r, 'priority') == score == x['priority'] and hbv(r, 'rank') == x['rank'], f'{g}: the Heartbeat score recomputes', (hbv(r, 'priority'), score))
out_groups = {g for g in groups if icp.GROUPS.get(g) and icp.segment(icp.GROUPS[g]) == 'Outside'} | {g for g in groups if not icp.GROUPS.get(g) and icp.segment(icp.default(max(groups[g], key=lambda a: a['triangle']))) == 'Outside'}
check({r['group'] for r in HB['outside']} == out_groups, 'every company outside the ICP is listed and none is ranked', sorted({r['group'] for r in HB['outside']} ^ out_groups))
check(set(onpage) | out_groups == set(groups), 'every ungated company is ranked or listed as outside', sorted(set(groups) - set(onpage) - out_groups))

# ---- the reach test and the ranking built on it, recomputed here from the inputs
if REACHM and A.reach and A.signals and A.as_of:
    REACH_IN, SIG_IN = J(A.reach), J(A.signals)
    today = datetime.date.fromisoformat(A.as_of); now = today.year * 12 + today.month - 1
    CLS = {'decision': 1.0, 'mandate': 0.75, 'tech-lead': 0.6, 'leader': 0.3, 'growth': 0.15}
    check(REACHM['classes'] == CLS and REACHM['frozen'] == 0.15 and REACHM['family'] == 15 and REACHM['shares'] == {'research': 60, 'fire': 40}, 'the signal classes, the shares and the two additions are the documented ones', REACHM['classes'])
    check(REACHM['as_of'] == A.as_of and REACHM['scored'] == len(scored), 'the page states the day the signals were read as of and how many companies were scored')
    up = lambda v: int(v + 0.5 + 1e-9)
    want_list = {'open': 'ranked', 'long': 'long', 'later': 'later', 'out': 'out'}
    where = {r['group']: k for k in ('ranked', 'long', 'later', 'out') for r in HB.get(k, [])}
    check(set(REACH_IN) == set(onpage), 'a reach call is on file for every company inside the ICP', sorted(set(REACH_IN) ^ set(onpage)))
    check(set(SIG_IN) <= set(onpage), 'every signal belongs to a company inside the ICP', sorted(set(SIG_IN) - set(onpage)))
    rescored = {}
    for g, r in onpage.items():
        rc = REACH_IN.get(g) or {}; sig = SIG_IN.get(g, [])
        check(rc.get('state') in want_list and where[g] == want_list.get(rc.get('state')), f'{g}: listed where its reach call puts it', (rc.get('state'), where[g]))
        check(r['reach'].get('state') == rc.get('state') and r['reach'].get('why') == rc.get('why') and r['reach'].get('again') == rc.get('again') and r['reach'].get('note') == rc.get('note'), f'{g}: the reach call on the page is the one on file')
        if rc.get('state') != 'open':
            check(bool(rc.get('why')) and len(rc['why']) <= 230, f'{g}: a company that is not ranked says why, in one line', rc.get('why'))
        if rc.get('state') == 'later':
            check(bool(re.fullmatch(r'20\d\d', rc.get('again') or '')), f'{g}: a company set aside for now says when to look again', rc.get('again'))
        check(r['signals'] == sig, f'{g}: the signals on the page are the signals on file')
        for s in sig:
            check(s.get('cls') in CLS or s.get('cls') == 'frozen', f'{g}: a signal has a known class', s.get('cls'))
            check(bool(re.fullmatch(r'20\d\d-(0[1-9]|1[0-2])', s.get('date') or '')), f'{g}: a signal is dated YYYY-MM', s.get('date'))
            check(bool(s.get('text')) and re.search(r'\d', s['text'][:40]) is not None, f'{g}: a signal starts with its date', s.get('text'))
            check(s.get('source') is None or re.match(r'https?://', s['source']), f'{g}: a signal\'s source is a link or is named in its text', s.get('source'))
        recs = groups[g]; lead = max(recs, key=lambda a: a['triangle']); e = POT[g]; x = scored[g]
        live = sorted((CLS[s['cls']] * (1.0 if -9 <= now - mi(s['date']) <= 9 else 0.5 if 9 < now - mi(s['date']) <= 12 else 0.0), s['cls']) for s in sig if s['cls'] in CLS)
        live = [v for v in reversed(live) if v[0] > 0]
        first_hand = min(1.0, (live[0][0] if live else 0) + (0.25 * live[1][0] if len(live) > 1 else 0) + (0.15 if any(s['cls'] == 'frozen' for s in sig) else 0))
        intent = lead['anatta_sub']['intent']; research_pts = 60 * first_hand; fire_pts = 40 * max(0, intent - 2) / 18; lift = pot.LIFT[e.get('shopPay', 'no')]
        opening = min(100, up(research_pts + fire_pts) + lift)
        fresh = [s['cls'] for s in sig if s['cls'] in CLS and -9 <= now - mi(s['date']) <= 9]       # a signal older than 9 months adds points and names nothing
        lead_cls = max(fresh, key=CLS.get) if fresh else None
        window = 'open' if lead_cls == 'decision' else 'changing' if lead_cls in ('mandate', 'tech-lead') else 'fire' if intent >= 10 else 'quiet'
        check(r['intent'] == intent and r['opening_parts'] == {'first_hand': round(research_pts, 1), 'fire': round(fire_pts, 1), 'shop_pay': lift}, f'{g}: the parts of the opening recompute', r['opening_parts'])
        check(r['window'] == window, f'{g}: what the opening rests on', (r['window'], window))
        trig = any(s['cls'] in ('decision', 'mandate', 'tech-lead', 'leader') and -9 <= now - mi(s['date']) <= 9 for s in sig)
        def mscore(m):
            own = bool(m.get('triggerDate')) and not (m.get('trigger') or '').startswith('FIRE logged')
            return len(set(m['motives'])) + (1 if m.get('live') else 0) + (1 if (abs(mi(m['triggerDate']) - now) <= 9 if own else trig) else 0)
        moves = EXTRAS.get(g, {}).get('moves', [])
        s3 = sorted((mscore(m) for m in moves), reverse=True) + [0, 0, 0]
        mo2 = round(100 * (0.6 * s3[0] + 0.25 * s3[1] + 0.15 * s3[2]) / 5)
        family = sorted({f['name'] for a in recs for f in (a.get('shopify_in_family') or [])})
        path = min(100, mo2 + (15 if family else 0))
        check(r['path_parts'] == {'motion': mo2, 'family': 15 if family else 0, 'trigger': trig} and r['family'] == family, f'{g}: the parts of the way in recompute', r['path_parts'])
        best = max(moves, key=mscore) if moves else None
        check((r['first'] or None) == ([best['partner'], mscore(best)] if best else None), f'{g}: partner to move first, under the first-hand trigger rule', r['first'])
        sc = min(100, (35 * path + 30 * x['fit'] + 20 * opening + 15 * x['potential'] + 50) // 100 + pot.bonus(e))
        rescored[g] = (sc, opening, path, x['fit'])
        if rc.get('state') in ('open', 'long'):
            check(r['timing'] == opening and r['motion'] == path, f'{g}: opening and way in recompute', ((r['timing'], opening), (r['motion'], path)))
            check(r['priority'] == sc, f'{g}: score recomputes, halves up', (r['priority'], sc))
        else:
            check(r.get('priority') is None and r.get('rank') is None, f'{g}: a company set aside carries no score and no rank')
    want_order = sorted((g for g in onpage if where[g] == 'ranked'), key=lambda g: tuple(-v for v in rescored[g]))
    check([r['group'] for r in HB['ranked']] == want_order, 'the ranking is in score order, ties by opening, then way in, then Anatta fit', [r['group'] for r in HB['ranked']][:5])
    in_reach = [g for g in onpage if where[g] == 'ranked']; bonus_of = {g: pot.bonus(POT[g]) for g in in_reach}
    sens = {}
    for wo in (20, 30, 40, 50):         # the same order reach_rank.py writes: the other three weights keep their proportions
        rest = (100 - wo) / 80
        def under(g, wo=wo, rest=rest):
            sc, opening, path, fit = rescored[g]
            if wo != 20:
                sc = min(100, up((35 * rest * path + 30 * rest * fit + wo * opening + 15 * rest * scored[g]['potential']) / 100) + bonus_of[g])
            return (-sc, -opening, -path, -fit)
        sens[str(wo)] = sorted(in_reach, key=under)[:10]
    check(REACHM['sensitivity'] == sens, 'the first ten under each weighting of the opening recompute', {k: v[:4] for k, v in sens.items()})
elif REACHM:
    fails.append('the page was built with the reach test, and this run was not given --reach, --signals and --as-of to check it')
check(not ISSUE.get('accounts') or all(a['name'] in onpage for a in ISSUE['accounts']), 'every account on the issue is on the list')

# partners: live where the partner facts say they are
if A.facts:
    F = J(A.facts)
    research = J(os.path.join(os.path.dirname(paths.BOOK), 'research.json')) if os.path.exists(os.path.join(os.path.dirname(paths.BOOK), 'research.json')) else {}
    info = set(research.get('info_rows', []))
    grp_of = {a['name']: (a.get('group') or a['name']) for a in book['accounts']}
    live_at = {}
    for x in F['accounts']:
        if x['name'] in info:
            continue
        for v in x['vendors']:
            if v['state'] in ('live', 'live (dns only)'):
                live_at.setdefault(grp_of.get(x['name'], x['name']), set()).add(v['vendor'])
    for g, r in onpage.items():
        for m in r['moves']:
            if m.get('live'):
                check(m['partner'] in live_at.get(g, set()), f'{g}: {m["partner"]} is called live and the partner facts show it live at a store the company runs')
else:
    notes.append('partner facts not given: live partners were not checked against the scans')

# ---- the insight layer, where the page has one: writing rules, and proof that traces to the Proof Genome
WORDS = dict(zip('one two three four five six seven eight nine ten eleven twelve'.split(), range(1, 13)))
flat = lambda t: re.sub(r'\b(' + '|'.join(WORDS) + r')\b', lambda m: str(WORDS[m.group(1).lower()]), t.replace('’', "'").replace(',', ''), flags=re.I)
STORY = {flat(s['name']): s for s in genome['stories']}
GEN = {k: flat(json.dumps(v, ensure_ascii=False)) for k, v in STORY.items()}
ALIAS = {flat(k): flat(v) for k, v in NAMING.get('aliases', {}).items()}
CLEARED = {flat(k) for k in NAMING.get('cleared', {})}
NAME_RE = re.compile(r'(?<![\w])(' + '|'.join(re.escape(n) for n in sorted(list(GEN) + list(ALIAS), key=len, reverse=True)) + r')(?![\w])')
client = lambda n: ALIAS.get(flat(n), flat(n))
nums = lambda t: re.findall(r'\d[\d.]*\d|\d', flat(t))
try:
    import proof as rollup
    PROOF, _ = rollup.compute()
except Exception as e:        # the roll-up tool is the Heartbeat Source's; without it, totals are checked against the file it wrote
    PROOF = J(os.path.join(A.source, 'shared', 'anatta.json')).get('proof', {})
    notes.append(f'proof roll-up read from shared/anatta.json ({type(e).__name__} running tools/proof.py)')
INS = HB.get('insights') or {}
caveats, used = {}, {}
proof_lines = []          # (where, text): every line that carries Anatta proof
for g, a in (INS.get('accounts') or {}).items():
    check(g in onpage, f'insight for {g}: the company is inside the ICP')
    for k in ('why', 'play', 'fitt', 'leadt'):
        v = a.get(k)
        if v is None:
            continue
        check(isinstance(v, list) and 0 < len(v) <= 4, f'{g}: "{k}" is one to four lines', v if not isinstance(v, list) else len(v))
        for line in v if isinstance(v, list) else []:
            check(len(line) <= 170, f'{g}: a "{k}" line is 170 characters or fewer', (len(line), line))
    for line in a.get('why') or []:
        check(re.search(r'\d', line[:60]), f'{g}: a "why" line starts with its date or its measure', line)
    for k in ('watch', 'q', 'read'):
        check(a.get(k) is None or (isinstance(a[k], str) and len(a[k]) <= 200), f'{g}: "{k}" is one line', a.get(k))
    for row in a.get('stories') or []:
        check(isinstance(row, list) and len(row) == 3 and row[0] in ('Twin', 'Peer', 'Safety'), f'{g}: a story is [Twin|Peer|Safety, client, line]', row)
        if isinstance(row, list) and len(row) == 3:
            check(client(row[1]) in GEN, f'{g}: story names a client in the Proof Genome', row[1])
            used[row[1]] = used.get(row[1], 0) + (1 if (onpage.get(g, {}).get('rank') or 99) <= 10 else 0)
            proof_lines.append((f'{g}, {row[0]}', f'{row[1]}: {row[2]}'))
    proof_lines += [(f'{g}, the move', x) for x in a.get('leadt') or []]
    proof_lines += [(f'{g}, where Anatta fits', x) for x in a.get('fitt') or []]
    proof_lines += [(f'{g}, the play', x) for x in a.get('play') or []]
check(all(v <= 2 for v in used.values()), 'no story used more than twice in the ten', {k: v for k, v in used.items() if v > 2})
for i, f in enumerate(INS.get('findings') or []):
    proof_lines.append((f'finding {i + 1}', ' '.join([f.get('title', ''), f.get('text', '')] + (f.get('lines') or []))))
for where, text in proof_lines:
    for k in re.findall(r'\{proof\.(\w+)\}', text):
        check(k in PROOF, f'{where}: {{proof.{k}}} is a roll-up tools/proof.py computes', k)
    typed = flat(re.sub(r'\{proof\.\w+\}', '', text))
    hits = list(NAME_RE.finditer(typed))
    if 'Track record:' in typed:
        loose = nums(typed.split('Track record:')[1].split('Closest:')[0])
        check(not loose, f'{where}: a total is typed by hand. Use a {{proof.x}} token', (loose, text))
    for k, m in enumerate(hits):
        c = client(m.group(1)); seg = typed[m.end():(hits[k + 1].start() if k + 1 < len(hits) else len(typed))]
        miss = [v for v in nums(seg) if v not in GEN[c]]
        check(not miss, f'{where}: every number after {STORY[c]["name"]} is in its Proof Genome entry', (miss, text))
        check(STORY[c]['published'] or c in CLEARED, f'{where}: {STORY[c]["name"]} is unpublished in the Proof Genome and not cleared in naming.json')
        if STORY[c].get('caveat'):
            caveats[STORY[c]['name']] = STORY[c]['caveat']
# an unpublished client is never named anywhere on the page unless cleared
everything = flat(' \n '.join(strings({k: v for k, v in D.items() if k != 'accounts'}) + strings([{k: a.get(k) for k in ('story', 'shopify_angle', 'anatta_angle')} for a in D['accounts']])))
for m in NAME_RE.finditer(everything):
    c = client(m.group(1))
    if not STORY[c]['published']:
        check(c in CLEARED, f'{STORY[c]["name"]} is unpublished in the Proof Genome and not cleared in naming.json', everything[max(0, m.start() - 60):m.end() + 60])

# subscription view: every program listed belongs to a company on the list, and live programs carry the bonus
SUBS = HB.get('subscriptions') or {}
for row in SUBS.get('rows') or []:
    g = row['group']
    known = g in onpage or g in {a.get('group') or a['name'] for a in book['accounts']}
    check(known, f'subscription view: {g} is on the list')
    if g in onpage:
        check((row['state'] == 'live') == bool(onpage[g]['bonus']), f'subscription view: {g} is live exactly when it carries the bonus', (row['state'], onpage[g]['bonus']))
        check(row.get('rank') == onpage[g]['rank'] and row.get('priority') == onpage[g]['priority'], f'subscription view: {g} shows its rank and score')
        aside = (onpage[g].get('reach') or {}).get('state', 'open') != 'open'
        check(aside == bool(row.get('why_not_ranked')) and (not aside or row.get('section') in ('aside', 'ended', 'noted', 'context')), f'subscription view: {g} is marked as set aside exactly when it is', (aside, row.get('why_not_ranked'), row.get('section')))
        check(row['state'] == POT[g].get('subscription', 'none'), f'subscription view: {g} state is the researched state', (row['state'], POT[g].get('subscription')))
        counted = any(p.get('counts') and p.get('status') == 'live' for p in row.get('programs') or [])
        check(not (row.get('programs') or []) or counted == (row['state'] == 'live'), f'subscription view: {g} is live exactly when a program that counts is live')
    else:
        check(row.get('rank') is None and bool(row.get('why_not_ranked')), f'subscription view: {g} is not ranked and says why')
    for p in row.get('programs') or []:
        check(bool(p.get('evidence')) and bool(p.get('read')) and re.match(r'https?://', p.get('url') or ''), f'subscription view: {g}, {p.get("name")}: names its evidence, its page and the date it was read')
        check(isinstance(p.get('counts'), bool) and (p['counts'] or bool(p.get('why_counts'))), f'subscription view: {g}, {p.get("name")}: a program that does not count says why')
if SUBS:
    check(sum(1 for r in SUBS['rows'] if r['state'] == 'live' and r['group'] in onpage) == live_bonus, 'subscription view lists every ranked company with the bonus', (sum(1 for r in SUBS['rows'] if r['state'] == 'live' and r['group'] in onpage), live_bonus))

# ---- the two editions, the CSVs, and nothing private
HS = DS.get('heartbeat') or {}
both = lambda H: [(k, r['group'], r.get('priority'), r.get('rank')) for k in ('ranked', 'long', 'later', 'out') for r in H.get(k, [])]
check(both(HS) == both(HB), 'both editions carry the same ranking and the same companies set aside')
check(D.get('internal') is True and DS.get('internal') is False, 'each file is the edition it says it is')
INTERNAL_ONLY = ('crm_note', 'in_sfdc')
check(not any(k in a for a in DS['accounts'] for k in INTERNAL_ONLY), 'the shareable edition carries no internal-only field')
check(len(D['accounts']) == len(book['accounts']) == D['summary']['accounts'], 'every account on the list is on the page', (len(D['accounts']), len(book['accounts'])))
tiers = {}
for a in D['accounts']:
    tiers[a['tier']] = tiers.get(a['tier'], 0) + 1
check(tiers == D['summary']['tiers'], 'tier counts in the summary match the accounts', (tiers, D['summary']['tiers']))
ids = set()
if A.ids_from:
    with open(A.ids_from, encoding='utf-8-sig', newline='') as fh:
        for row in csv.DictReader(fh):
            for k, v in row.items():
                if k and re.search(r'\bid\b', k, re.I) and v and re.fullmatch(r'[A-Za-z0-9]{15,24}', v.strip()):
                    ids.add(v.strip())
    check(len(ids) > 0, 'record ids were read from the export')
else:
    notes.append('no export given: record ids were not checked')
for path, html, data, edition in ((A.internal, html_i, D, 'internal'), (A.shareable, html_s, DS, 'shareable')):
    body = re.sub(r'data:[a-z]+/[^"\')\s]+', '', html)
    check(not re.search(r'[\w.+-]+@[\w-]+\.[a-z]{2,}', body), f'no email address in the {edition} file', (re.search(r'[\w.+-]+@[\w-]+\.[a-z]{2,}', body) or [''])[0])
    check('deal_size' not in html and '"band"' not in html, f'no deal size in the {edition} file')
    check(not re.search(r'<script[^>]+src=', html) and not re.search(r'<link[^>]+href="https?:', html), f'{edition} file is standalone: no outside scripts or styles')
    leaked = [i for i in ids if i in html]
    check(not leaked, f'no CRM record id in the {edition} file', leaked[:3])
    hb_text = re.sub(r'\{proof\.\w+\}', '0', '\n'.join(strings(data.get('heartbeat') or {})))     # totals are tokens in the data; the page checks see them filled
    scan(hb_text, f'the {edition} Heartbeat data', strict=True)
    scan('\n'.join(strings({k: v for k, v in data.items() if k != 'heartbeat'})), f'the {edition} triangulation data', strict=False)
    no_firms('\n'.join(strings(data)), f'the {edition} data')
for path, edition in ((A.csv_internal, 'internal'), (A.csv_shareable, 'shareable')):
    if not path:
        continue
    with open(path, encoding='utf-8-sig', newline='') as fh:
        rows = list(csv.DictReader(fh))
    raw = open(path, encoding='utf-8-sig').read()
    check(len(rows) == len(book['accounts']), f'{edition} CSV has every account', len(rows))
    check(not [i for i in ids if i in raw], f'no CRM record id in the {edition} CSV')
    check(not re.search(r'[\w.+-]+@[\w-]+\.[a-z]{2,}', raw), f'no email address in the {edition} CSV')
    if edition == 'shareable':
        check('in_salesforce' not in rows[0] and 'crm_note' not in rows[0], 'the shareable CSV carries no internal-only column')
    gated = {a['name'] for a in book['accounts'] if a.get('gate')}
    in_group = {n: r for r in HB['ranked'] + ASIDE for n in r['rows'] if n not in gated}
    RANK_COL = 'rank' if REACHM else 'heartbeat_rank'
    bad = []
    for row in rows:
        r = in_group.get(row['name'])
        if r is None:
            if row.get(RANK_COL):
                bad.append((row['name'], 'has a rank but is not ranked'))
            continue
        s = lambda v: '' if v is None else str(v)
        if REACHM:
            ranked_row = r['reach']['state'] in ('open', 'long')
            want = {'reach': {'open': 'in reach', 'long': 'long odds', 'later': 'not now', 'out': 'out of reach'}[r['reach']['state']], 'rank': s(r['rank']), 'score': s(r['priority']),
                    'way_in': s(r['motion']) if ranked_row else '', 'opening': s(r['timing']) if ranked_row else '', 'anatta_icp_fit': s(r['fit']), 'potential': s(r['potential']),
                    'heartbeat_rank_alone': s(r['hb']['rank']), 'heartbeat_score_alone': s(r['hb']['priority'])}
            check(all(k in row for k in want), f'{edition} CSV carries the reach columns', [k for k in want if k not in row][:3])
        else:
            want = {'heartbeat_rank': str(r['rank']), 'heartbeat_score': str(r['priority']), 'heartbeat_segment': r['segment'], 'partner_motion': str(r['motion']),
                    'anatta_icp_fit': str(r['fit']), 'heartbeat_timing': str(r['timing']), 'potential': str(r['potential'])}
        diff = {k: (row.get(k), v) for k, v in want.items() if k in row and str(row.get(k)) != v}
        if diff:
            bad.append((row['name'], diff))
    check(not bad, f'{edition} CSV ranking columns match the page', bad[:3])

# ---------------------------------------------------------------- Part 2: the page
ran = False
if not A.no_page:
    js = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'qa_page.js')
    try:
        import tempfile
        res_path = os.path.join(tempfile.mkdtemp(), 'page.json')
        out = subprocess.run(['node', js, A.internal, A.shareable, res_path], capture_output=True, text=True, timeout=1500)
        res = J(res_path)
        ran = True
        passes += res['passes']
        fails += res['fails']
        notes += res.get('notes', [])
        for tag, where, text, strict in res.get('text', []):
            scan(text, f'{tag}: {where}', strict=strict)
            no_firms(text, f'{tag}: {where}')
    except Exception as e:
        fails.append(f'page checks did not run: {type(e).__name__}: {str(e)[:200]}' + (f' | {out.stderr[-400:]}' if 'out' in dir() else ''))

if caveats:
    print('Proof Genome caveats for the clients quoted on this page. Read each line against its caveat:')
    for nm, cav in sorted(caveats.items()):
        print(f'  {nm}: {cav}')
seen = set()
for n in notes:
    if n not in seen:
        seen.add(n); print('note:', n)
print(f'{passes} checks passed, {len(fails)} failed' + ('' if ran else ' (data checks only)'))
for x in fails:
    print('FAIL', x)
sys.exit(1 if fails else 0)
