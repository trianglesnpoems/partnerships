#!/usr/bin/env python3
"""Contacts layer for one rep's book: dedupe, join to accounts, classify, geocode, cluster into metro hubs.
Single source of truth for every contact and hub number on the dashboard. Ported from the Oct 2026 build.

Usage: build_hubs.py <contacts_csv> <scored_json> <book_json> <out_json>
Needs the `geonamescache` package (GeoNames cities with population >= 500, bundled).

book.json keys used (all optional):
  contact_company_alias   {"Company name in the contacts export": "Account name in the accounts export"}
  contacts_wrong_company  {"Account name": "why contacts exported under it are not this account's people"}  -> left out, counted
"""
import csv, json, math, re, sys, collections
import geonamescache

CONTACTS, SCORED, BOOK, OUT = sys.argv[1:5]
RADIUS_KM = 120
book = json.load(open(BOOK))
ALIAS = book.get("contact_company_alias", {})
WRONG = book.get("contacts_wrong_company", {})
accounts = {a["name"]: a for a in json.load(open(SCORED))["accounts"]}
g = lambda r, k: (r.get(k) or "").strip()
norm = lambda s: re.sub(r"[^a-z0-9]+", " ", s.replace("®", "").lower()).strip()
by_norm = {norm(n): n for n in accounts}

# ---------- load + dedupe (email -> LinkedIn URL -> name + company) ----------
rows = list(csv.DictReader(open(CONTACTS, newline="", encoding="utf-8-sig")))
def ckey(r):
    g2 = lambda k: g(r, k).lower()
    return g2("Email") or g2("Person Linkedin Url") or (g2("First Name") + "|" + g2("Last Name") + "|" + g2("Company Name"))
uniq = {}
for r in rows:
    k = ckey(r)
    if k.strip("|") and k not in uniq: uniq[k] = r
RAW, UNIQ = len(rows), len(uniq)

# ---------- join to accounts ----------
def account_of(company):
    name = ALIAS.get(company) or by_norm.get(norm(company))
    return name if name in accounts else None
unjoined = sorted({g(r, "Company Name") for r in uniq.values() if not account_of(g(r, "Company Name"))})
assert not unjoined, f"contact companies with no account row (add to contact_company_alias in book.json): {unjoined}"
assert all(n in accounts for n in WRONG), "contacts_wrong_company names an account that is not in the book"

# ---------- geocode ----------
gc = geonamescache.GeonamesCache(min_city_population=500)
CC = {c["name"]: c["iso"] for c in gc.get_countries().values()}
CC.update({"United States": "US", "South Korea": "KR", "Taiwan": "TW", "Hong Kong": "HK", "Iran": "IR", "Venezuela": "VE", "Czech Republic": "CZ", "Russia": "RU", "Vietnam": "VN"})
NA = {"US", "CA", "MX"}
US = {s["name"]: s["code"] for s in gc.get_us_states().values()}
CA = {"Alberta": "01", "British Columbia": "02", "Manitoba": "03", "New Brunswick": "04", "Newfoundland and Labrador": "05", "Nova Scotia": "07",
      "Ontario": "08", "Prince Edward Island": "09", "Quebec": "10", "Saskatchewan": "11", "Yukon": "12", "Northwest Territories": "13", "Nunavut": "14"}
CA_AB = {"Alberta": "AB", "British Columbia": "BC", "Manitoba": "MB", "New Brunswick": "NB", "Newfoundland and Labrador": "NL", "Nova Scotia": "NS", "Ontario": "ON",
         "Prince Edward Island": "PE", "Quebec": "QC", "Saskatchewan": "SK", "Yukon": "YT", "Northwest Territories": "NT", "Nunavut": "NU"}
idx = collections.defaultdict(list)
for c in gc.get_cities().values():
    for n in {c["name"].lower()} | {a.lower() for a in c.get("alternatenames", [])}:
        idx[(n, c["countrycode"])].append(c)
# Places the gazetteer does not carry, keyed (city, state) -> (lat, lng). Add a place here only with coordinates from a source.
OVERRIDES = {}

def geocode(city, state, country):
    if not city: return None, "no-city"
    if (city, state) in OVERRIDES: return OVERRIDES[(city, state)], "override"
    cc = CC.get(country)
    if not cc: return None, "unresolved"
    a = (US if cc == "US" else CA if cc == "CA" else {}).get(state)
    c0 = city.lower()
    for v in (c0, re.sub(r"\b(charter township of|charter township|township of|township|air force base|afb|village of|town of|city of|regional municipality)\b", "", c0).strip(),
              re.sub(r"^saint\b", "st.", c0), re.sub(r"^st\.?\s", "saint ", c0), re.sub(r"^fort\b", "ft.", c0), re.sub(r"^mount\b", "mt.", c0)):
        cands = [c for c in idx.get((v, cc), []) if not a or c["admin1code"] == a]
        if cands:
            c = max(cands, key=lambda c: c["population"])
            return (c["latitude"], c["longitude"]), "geonames"
    return None, "unresolved"

# ---------- classify ----------
C_SUITE = r"\b(ceo|cfo|coo|cmo|cio|cto|cro|cso|cpo|cdo|cao|chro|ciso|cco)\b|chief [\w ,&/.'-]*?(officer|executive)\b|chief executive"
def seniority(title):
    """Read a level off the job title. A first sort, not a fact."""
    t = title.lower()
    # an assistant or administrator "to" an executive is staff, whatever titles follow the "to"
    if re.search(r"\b(assistant|asst\.?|administrator|coordinator|secretary)\b[^,;/]*\bto\b", t) and not re.search(r"\bassistant (vice|vp|professor|director|dean)\b", t): return "Manager / Staff"
    t = re.split(r",?\s*office of\b", t)[0]                                                    # "Program Director ..., Office of the EVP & COO"
    if re.search(r"\b(associate|deputy|assistant) (chief|c[a-z]{1,3}o)\b", t): return "VP"     # one step below the chief
    if re.search(C_SUITE, t): return "C-level"
    if re.search(r"\b(founder|owner|co-owner|franchisee?|chairman|chairwoman|chair of the board|executive chair|managing partner|principal|operating partner)\b", t) \
       or (re.search(r"\bpresident\b", t) and not re.search(r"\bvice[- ]president\b|\bv\.?p\b", t)): return "Founder / Owner"
    if re.search(r"\b(vp|svp|evp|avp|vice president|vice-president|vice chancellor|vice provost|head of|chief of staff)\b", t) or "v.p." in t: return "VP"
    if re.search(r"director|directrice|directeur|\bhead\b|\bdean\b|\bchief\b", t): return "Director"
    if re.search(r"\b(manager|lead|specialist|partner|assistant|coordinator|analyst)\b", t): return "Manager / Staff"
    return "Other"

def function(title):
    t = title.lower()
    if re.search(r"e-?commerce|\bdigital\b|\bomni-?channel\b|\bdtc\b|\bd2c\b|direct[- ]to[- ]consumer", t): return "Ecommerce / Digital"
    if re.search(r"market|brand|communications|public relations|advertising|growth|demand|creative|design|art director|media|social", t): return "Marketing / Brand"
    if re.search(r"\b(cfo|finance|financial|accounting|controller|legal|counsel|procurement|treasur|audit|tax)", t): return "Finance / Legal"
    if re.search(r"\b(cio|cto|technology|information|it\b|engineering|software|architect|cloud|data|bi\b|technical|systems|cybersecurity|infrastructure)", t): return "Technology"
    if re.search(r"\b(ceo|coo|president|founder|owner|franchise|chairman|chair|managing|general manager|operating partner|executive officer|principal)\b", t): return "Executive / Owner"
    if re.search(r"\b(sales|revenue|cro|channel|partner|retail|commercial|category|customer|store)", t): return "Sales / Retail / CX"
    if re.search(r"\b(product|innovation|merchandis|publish|editorial|production|culinary|development)", t): return "Product / Merchandising"
    if re.search(r"\b(people|human|hr\b|talent|chro)", t): return "People / HR"
    if re.search(r"\b(operations|operating|ops|supply|facilities|strategy|pmo|program|project|logistics)", t): return "Operations / Strategy"
    return "Other"

# ---------- build contact records ----------
contacts, excluded = [], collections.Counter()
for r in uniq.values():
    acct = account_of(g(r, "Company Name"))
    if acct in WRONG: excluded[acct] += 1; continue
    city, state, country = g(r, "City"), g(r, "State"), g(r, "Country")
    email = g(r, "Email").lower()
    if email.endswith(".invalid"): email = ""          # Apollo's marker for an address it has invalidated
    ll, how = geocode(city, state, country)
    a = accounts[acct]
    contacts.append({"id": len(contacts), "first": g(r, "First Name"), "last": g(r, "Last Name"), "title": g(r, "Title"),
                     "company": a.get("display") or acct, "acct": acct, "email": email, "linkedin": g(r, "Person Linkedin Url"),
                     "city": city, "state": state, "country": country, "seniority": seniority(g(r, "Title")), "func": function(g(r, "Title")),
                     "geo": how, "lat": ll[0] if ll else None, "lng": ll[1] if ll else None, "hub": None,
                     "region": "NA" if CC.get(country) in NA else "INTL" if country else "?"})

# ---------- cluster: deterministic greedy radius, nearest seed wins ----------
def hav(a, b):
    p1, p2 = math.radians(a[0]), math.radians(b[0]); dp, dl = p2 - p1, math.radians(b[1] - a[1])
    return 2 * 6371.0 * math.asin(math.sqrt(math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2))
groups = collections.defaultdict(list)
for c in contacts:
    if c["lat"] is not None: groups[(c["city"], c["state"], c["country"], c["lat"], c["lng"])].append(c)
ordered = sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0][0], kv[0][1]))
HUB_NAMES = {  # seed "City, ST" -> metro name; anything not listed keeps its seed name
 "New York, NY": "New York Metro", "Chicago, IL": "Chicago Metro", "San Francisco, CA": "SF Bay Area", "Austin, TX": "Austin", "Toronto, ON": "Toronto / GTA",
 "Nashville, TN": "Nashville", "Calgary, AB": "Calgary", "Saskatoon, SK": "Saskatoon", "Los Angeles, CA": "Greater Los Angeles", "Atlanta, GA": "Atlanta Metro",
 "Ottawa, ON": "Ottawa–Gatineau", "Dallas, TX": "Dallas–Fort Worth", "Milwaukee, WI": "Milwaukee", "Minneapolis, MN": "Minneapolis–St. Paul", "San Diego, CA": "San Diego",
 "Houston, TX": "Greater Houston", "Montreal, QC": "Montréal", "Edmonton, AB": "Edmonton", "Indianapolis, IN": "Indianapolis", "Salt Lake City, UT": "Salt Lake / Wasatch Front",
 "Phoenix, AZ": "Phoenix Metro", "Boston, MA": "Greater Boston", "Portland, OR": "Portland", "Seattle, WA": "Seattle / Puget Sound", "Miami, FL": "South Florida",
 "Tampa, FL": "Tampa Bay", "Orlando, FL": "Orlando", "Charlotte, NC": "Charlotte", "Cleveland, OH": "Cleveland", "Kansas City, MO": "Kansas City Metro",
 "Charlottesville, VA": "Charlottesville / Central Virginia", "Columbia, MO": "Columbia, MO", "Denver, CO": "Denver / Front Range", "Washington, DC": "Washington DC Metro",
 "Philadelphia, PA": "Greater Philadelphia", "Detroit, MI": "Detroit Metro", "St. Louis, MO": "St. Louis", "Vancouver, BC": "Vancouver", "Quebec, QC": "Québec City",
 "Mexico City, Mexico City": "Mexico City", "Irvine, CA": "Orange County", "San Jose, CA": "SF Bay Area (South)", "Pittsburgh, PA": "Pittsburgh", "Columbus, OH": "Columbus",
 "Fort Lauderdale, FL": "South Florida", "Clermont, FL": "Orlando / Tampa", "Baltimore, MD": "Baltimore / Washington DC",
 "Hamilton, ON": "Toronto / Hamilton", "Martinsville, VA": "Piedmont Triad / Martinsville", "Monterrey, Nuevo Leon": "Monterrey",
}
ab = lambda state: US.get(state) or CA_AB.get(state) or state
hubs = []
for (city, state, country, lat, lng), members in ordered:
    near = [(d, h) for d, h in ((hav((lat, lng), (h["lat"], h["lng"])), h) for h in hubs) if d <= RADIUS_KM]
    if near:
        h = min(near, key=lambda x: x[0])[1]; h["members"] += members; h["cities"].append(f"{city}, {ab(state)}" if state else city)
    else:
        hubs.append({"seed": city, "state": state, "country": country, "lat": lat, "lng": lng, "members": list(members), "cities": [f"{city}, {ab(state)}" if state else city]})
hubs.sort(key=lambda h: (-len(h["members"]), h["seed"]))
out_hubs = []
for hi, h in enumerate(hubs):
    region = "NA" if CC.get(h["country"]) in NA else "INTL"
    seed = f'{h["seed"]}, {ab(h["state"])}' if region == "NA" and h["state"] else f'{h["seed"]}, {h["country"]}'
    for m in h["members"]: m["hub"] = hi
    out_hubs.append({"id": hi, "name": HUB_NAMES.get(seed, seed), "seed": seed, "lat": round(h["lat"], 4), "lng": round(h["lng"], 4), "country": h["country"],
                     "inset": "HI" if h["state"] == "Hawaii" else "AK" if h["state"] == "Alaska" else "MX" if h["country"] == "Mexico" else None, "region": region,
                     "n": len(h["members"]), "accounts": len({m["acct"] for m in h["members"]}), "cities": sorted(set(h["cities"])), "contacts": [m["id"] for m in h["members"]]})

# ---------- assertions (one source of truth) ----------
mapped = [c for c in contacts if c["hub"] is not None]; unmapped = [c for c in contacts if c["hub"] is None]
assert len(contacts) + sum(excluded.values()) == UNIQ, "kept + left out must equal unique contacts"
assert sum(h["n"] for h in out_hubs) == len(mapped), "hub counts must sum to mapped contacts"
assert all(c["geo"] in ("no-city", "unresolved") for c in unmapped)
blob = json.dumps(contacts)
assert not re.search(r"\b00[13Q][A-Za-z0-9]{12}(?:[A-Za-z0-9]{3})?\b", blob), "a Salesforce record ID is in the contact data"
unresolved = collections.Counter((c["city"], c["state"], c["country"]) for c in contacts if c["geo"] == "unresolved")
for c in contacts: c.pop("lat"); c.pop("lng")          # the page needs the hub, not a person's coordinates
per_acct = collections.Counter(c["acct"] for c in contacts)
summary = {"raw_rows": RAW, "unique_contacts": UNIQ, "kept": len(contacts), "left_out": dict(excluded), "left_out_reason": {k: WRONG[k] for k in excluded},
           "with_email": sum(1 for c in contacts if c["email"]), "mapped": len(mapped), "unmapped": len(unmapped),
           "unmapped_no_city": sum(1 for c in contacts if c["geo"] == "no-city"), "unresolved": sum(unresolved.values()),
           "unresolved_places": [f"{k[0]}, {k[1] or k[2]}" for k in unresolved], "hubs": len(out_hubs), "radius_km": RADIUS_KM,
           "intl_contacts": sum(1 for c in contacts if c["region"] == "INTL"), "override_count": sum(1 for c in contacts if c["geo"] == "override"),
           "accounts_with_contacts": len(per_acct), "accounts_without_contacts": sorted(n for n in accounts if n not in per_acct and n not in excluded),
           "company_aliases": len({g(r, "Company Name") for r in uniq.values() if g(r, "Company Name") in ALIAS})}
json.dump({"summary": summary, "hubs": out_hubs, "contacts": contacts}, open(OUT, "w"), indent=0, ensure_ascii=False)
print(json.dumps({k: v for k, v in summary.items() if k not in ("accounts_without_contacts", "left_out_reason")}, indent=1))
print("\nHUBS (top 30):")
for h in out_hubs[:30]: print(f'{h["n"]:3d} people {h["accounts"]:2d} accounts  {h["name"][:30]:30s} seed={h["seed"][:28]:28s} cities={len(h["cities"])} {h["region"]} {h["inset"] or ""}')
print("\nSENIORITY:", collections.Counter(c["seniority"] for c in contacts).most_common())
print("FUNCTION:", collections.Counter(c["func"] for c in contacts).most_common())
print("UNMAPPED by reason:", collections.Counter(c["geo"] for c in unmapped).most_common(), "| unresolved places:", unresolved.most_common(40))
