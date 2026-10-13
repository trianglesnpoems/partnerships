#!/usr/bin/env python3
"""Build geo-hub data for the Nicole hub map.

Single source of truth for: contact dedupe, geocoding, hub clustering, account join.
Usage: build_hubs.py <data_dir> <out_json>
"""
import csv, glob, json, math, re, sys, collections, os
import geonamescache

DATA, OUT = sys.argv[1], sys.argv[2]
EXTRA_CONTACT_FILES = sys.argv[3:]   # additional contact CSVs beyond DATA/*contacts*.csv
RADIUS_KM = 120

# ---------- load ----------
rows = []
for f in sorted(glob.glob(DATA + "/*contacts*.csv")) + EXTRA_CONTACT_FILES:
    with open(f, newline='', encoding='utf-8-sig') as fh:
        rows += list(csv.DictReader(fh))
def ckey(r):
    g2 = lambda k: (r.get(k) or "").strip().lower()
    return g2("Email") or g2("Person Linkedin Url") or (g2("First Name") + "|" + g2("Last Name") + "|" + g2("Company Name"))
contacts = {}
for r in rows:
    k = ckey(r)
    if k.strip("|") and k not in contacts:
        contacts[k] = r
RAW, UNIQ = len(rows), len(contacts)

accounts = {}
def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", s.replace("®", "").lower()).strip()
ALIAS = {"federated co operatives ltd": "co op"}  # FCL's account row is "Co-op" (co-op.crs)
for f in glob.glob(DATA + "/*accounts*.csv"):
    with open(f, newline='', encoding='utf-8') as fh:
        for a in csv.DictReader(fh):
            accounts[norm(a["Company Name"])] = a

# ---------- geocode ----------
gc = geonamescache.GeonamesCache()
CC = {c['name']: c['iso'] for c in gc.get_countries().values()}
CC.update({"United States": "US", "South Korea": "KR", "Taiwan": "TW", "Hong Kong": "HK", "Iran": "IR", "Venezuela": "VE", "Czech Republic": "CZ", "Russia": "RU", "Vietnam": "VN"})
NA = {"US", "CA", "MX"}
US = {s['name']: s['code'] for s in gc.get_us_states().values()}
CA = {"Alberta": "01", "British Columbia": "02", "Manitoba": "03", "New Brunswick": "04",
      "Newfoundland and Labrador": "05", "Nova Scotia": "07", "Ontario": "08",
      "Prince Edward Island": "09", "Quebec": "10", "Saskatchewan": "11"}
MX = {"Mexico City": "09", "State of Mexico": "15"}
idx = collections.defaultdict(list)
for c in gc.get_cities().values():
    names = {c['name'].lower()} | {a.lower() for a in c.get('alternatenames', [])}
    for n in names:
        idx[(n, c['countrycode'])].append(c)

# Places geonames' cities15000 set doesn't carry. (lat, lng)
OVERRIDES = {
 ("Halifax Regional Municipality","Nova Scotia"):(44.6488,-63.5752), ("Dillon","Colorado"):(39.6303,-106.0434),
 ("Laurel","Delaware"):(38.5565,-75.5713), ("Kennett Square","Pennsylvania"):(39.8468,-75.7116),
 ("Montville","New Jersey"):(40.9129,-74.3657), ("Cottonwood","California"):(40.3857,-122.2808),
 ("Maxville","Ontario"):(45.2833,-74.8500), ("Monument","Colorado"):(39.0917,-104.8725),
 ("East Aurora","New York"):(42.7679,-78.6134), ("Fairmont Hot Springs","British Columbia"):(50.3367,-115.8556),
 ("Prospect","Kentucky"):(38.3451,-85.6097), ("Grandora","Saskatchewan"):(52.1667,-106.9333),
 ("Flourtown","Pennsylvania"):(40.1037,-75.2121), ("Russell","Kansas"):(38.8950,-98.8598),
 ("Ucluelet","British Columbia"):(48.9419,-125.5464), ("Spicewood","Texas"):(30.4763,-98.1548),
 ("Oradell","New Jersey"):(40.9587,-74.0371), ("Allenhurst","Georgia"):(31.7788,-81.6079),
 ("Mechanicsburg","Pennsylvania"):(40.2143,-77.0086), ("Wading River","New York"):(40.9507,-72.8429),
 ("Boonton","New Jersey"):(40.9026,-74.4071), ("Jenkintown","Pennsylvania"):(40.0959,-75.1252),
 ("Kensington","Prince Edward Island"):(46.4333,-63.6333), ("Iowa Park","Texas"):(33.9515,-98.6687),
 ("Mount Uniacke","Nova Scotia"):(44.9000,-63.8333), ("Ellenwood","Georgia"):(33.6301,-84.2896),
 ("Summerside","Prince Edward Island"):(46.3950,-63.7871), ("West Monroe","Louisiana"):(32.5185,-92.1476),
 ("Morris Plains","New Jersey"):(40.8215,-74.4810), ("Foxborough","Massachusetts"):(42.0654,-71.2478),
 ("Peru","Indiana"):(40.7537,-86.0689), ("Wabash","Indiana"):(40.7978,-85.8205),
 ("Davenport","Florida"):(28.1614,-81.6017), ("San Anselmo","California"):(37.9746,-122.5616),
 ("Hawthorne","New York"):(41.1073,-73.7957), ("Nemo","Texas"):(32.2735,-97.6600),
 ("Fort Lee","Virginia"):(37.2468,-77.3350), ("Potwin","Kansas"):(37.9386,-97.0186),
 ("Woodbridge","Virginia"):(38.6582,-77.2497), ("Caldwell","New Jersey"):(40.8398,-74.2765),
 ("Destrehan","Louisiana"):(29.9630,-90.3534), ("Courtice","Ontario"):(43.9122,-78.7811),
 ("Glenshaw","Pennsylvania"):(40.5325,-79.9661), ("Dexter","Michigan"):(42.3384,-83.8894),
 ("Gibsons","British Columbia"):(49.4027,-123.5050), ("West Dundee","Illinois"):(42.0981,-88.2829),
 ("Gibbsboro","New Jersey"):(39.8382,-74.9654), ("Panorama","British Columbia"):(50.4600,-116.2400),
 ("Corte Madera","California"):(37.9255,-122.5275), ("Aldie","Virginia"):(38.9757,-77.6411),
 ("Princeton","Texas"):(33.1801,-96.4980), ("Argyle","Texas"):(33.1212,-97.1836),
 ("Buford","Georgia"):(34.1207,-84.0044), ("Smithfield","Utah"):(41.8383,-111.8327),
 ("Atholville","New Brunswick"):(47.9833,-66.7167), ("Thorndale","Texas"):(30.6138,-97.2061),
 ("Winfield","Illinois"):(41.8617,-88.1609), ("Chester","New Jersey"):(40.7843,-74.6968),
 ("Greenville","Wisconsin"):(44.2975,-88.5384), ("Mount Forest","Ontario"):(43.9833,-80.7333), ("Puslinch","Ontario"):(43.4500,-80.1667),
 ("Penn Laird","Virginia"):(38.3843,-78.8008), ("Southampton","Pennsylvania"):(40.1912,-75.0066), ("Sunset Prairie","British Columbia"):(55.9500,-120.9000),
 ("Georgetown Township","Michigan"):(42.8900,-85.8900), ("Goodfellow Air Force Base","Texas"):(31.4350,-100.4000), ("Valencia","Pennsylvania"):(40.6753,-79.9892),
 ("Clavet","Saskatchewan"):(52.0167,-106.3667), ("Sunrise Beach","Missouri"):(38.1750,-92.7760), ("Lyme","Connecticut"):(41.3990,-72.3480),
 ("Andover Township","New Jersey"):(41.0100,-74.7400), ("Kinkora","Prince Edward Island"):(46.3167,-63.6000),
 ("Chatham-Kent","Ontario"):(42.4048,-82.1910), ("Lake Winola","Pennsylvania"):(41.5095,-75.8546), ("Meadowbank","Prince Edward Island"):(46.2000,-63.2500),
 ("Neosho","Wisconsin"):(43.3078,-88.5234), ("Fort Riley","Kansas"):(39.0553,-96.7920), ("McClellan Park","California"):(38.6677,-121.4005),
 ("Arborg","Manitoba"):(50.9078,-97.0834), ("Antelias","Mount Lebanon Governorate"):(33.9150,35.5944), ("Hubert","North Carolina"):(34.6974,-77.2244),
}

# Fallback gazetteer: GeoNames cities1000 (population >= 1000) with admin1 codes, from the cities.json npm package.
C1000 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "build", "cities.json-1.1.6", "cities1000.txt")
idx1000 = collections.defaultdict(list)
with open(C1000, encoding="utf-8") as fh:
    for line in fh:
        f = line.rstrip("\n").split("\t")
        if len(f) < 15: continue
        rec = {"name": f[1], "lat": float(f[4]), "lng": float(f[5]), "cc": f[8], "admin1": f[10], "pop": int(f[14] or 0)}
        names = {f[1].lower(), f[2].lower()} | {a.lower() for a in f[3].split(",") if a}
        for n in names: idx1000[(n, f[8])].append(rec)
def geocode1000(city, state, cc):
    a = (US if cc == "US" else CA if cc == "CA" else MX if cc == "MX" else {}).get(state)
    c = city.lower()
    variants = [c, re.sub(r"\b(charter township|township|air force base|afb|village of|town of|city of)\b", "", c).strip()]
    for v in variants:
        cands = [r for r in idx1000.get((v, cc), []) if not a or r["admin1"] == a]
        if cands:
            r = max(cands, key=lambda r: r["pop"]); return (r["lat"], r["lng"])
    return None

def geocode(city, state, country):
    if not city:
        return None, "no-city"
    if (city, state) in OVERRIDES:
        return OVERRIDES[(city, state)], "override"
    cc = CC.get(country)
    if not cc:
        return None, "unresolved"
    a = (US if cc == "US" else CA if cc == "CA" else MX if cc == "MX" else {}).get(state)
    cands = [c for c in idx.get((city.lower(), cc), []) if not a or c['admin1code'] == a]
    if not cands:
        ll = geocode1000(city, state, cc)
        return (ll, "cities1000") if ll else (None, "unresolved")
    c = max(cands, key=lambda c: c['population'])
    return (c['latitude'], c['longitude']), "geonames"

# ---------- classify ----------
def seniority(title, company):
    t = title.lower()
    if "commissary" in company.lower() and re.search(r"\bcao\b", t):
        return "Staff"           # DeCA "CAO" = Computer Assisted Ordering, not an exec
    if re.search(r"\b(ceo|cfo|coo|cmo|cio|cto|cro|cso|cpo|cdo|cao|chro|cspo|chief)\b", t) or "co-ceo" in t or "chief" in t:
        return "C-level"
    if re.search(r"\b(founder|owner|franchise|franchisee|chairman|chair|president|managing partner|principal|operating partner|partner -|co-owner)\b", t):
        return "Founder / Owner"
    if re.search(r"\b(vp|svp|evp|vice president|vice-president|head of)\b", t):
        return "VP"
    if "director" in t:
        return "Director"
    if re.search(r"\b(manager|lead|specialist|partner|assistant|owner)\b", t):
        return "Manager / Staff"
    return "Other"

def function(title):
    t = title.lower()
    if re.search(r"market|brand|communications|public relations|advertising|growth|demand|creative|design|art director|media|social", t): return "Marketing / Brand"
    if re.search(r"\b(cfo|finance|financial|accounting|controller|legal|counsel|procurement)\b", t): return "Finance / Legal"
    if re.search(r"\b(cio|cto|technology|information|it\b|engineering|software|architect|cloud|digital|data|bi\b|technical|systems|cybersecurity|infrastructure)", t): return "Technology / Digital"
    if re.search(r"\b(ceo|coo|president|founder|owner|franchise|chairman|chair|managing|general manager|operating partner|executive officer|principal)\b", t): return "Executive / Owner"
    if re.search(r"\b(sales|revenue|cro|channel|partner|retail|commercial|category|ecommerce|e-commerce|customer)\b", t): return "Sales / Revenue / CX"
    if re.search(r"\b(product|innovation|merchandis|publish|editorial|production|culinary|development)\b", t): return "Product / Merchandising"
    if re.search(r"\b(people|human|hr\b|talent|chro)\b", t): return "People / HR"
    if re.search(r"\b(operations|operating|ops|supply|facilities|strategy|pmo|program|project)\b", t): return "Operations / Strategy"
    return "Other"

# ---------- build contact records ----------
out_contacts, unmapped = [], []
for i, (email, r) in enumerate(contacts.items()):
    city, state, country = r["City"].strip(), r["State"].strip(), r["Country"].strip()
    company = r["Company Name"].strip() or "(no company listed)"
    acct = accounts.get(ALIAS.get(norm(company), norm(company)), {})
    ll, how = geocode(city, state, country)
    rec = {
        "id": i, "first": r["First Name"].strip(), "last": r["Last Name"].strip(),
        "title": r["Title"].strip(), "company": company, "email": r["Email"].strip().lower(),
        "linkedin": r["Person Linkedin Url"].strip(), "city": city, "state": state, "country": country,
        "seniority": seniority(r["Title"], company), "func": function(r["Title"]),
        "intent": acct.get("FIRE_Intent") or "", "fire": acct.get("FIRE_Score_Total") or "",
        "inmarket": acct.get("In-market") == "true", "website": acct.get("Website", ""),
        "geo": how, "lat": ll[0] if ll else None, "lng": ll[1] if ll else None, "hub": None,
        "region": "NA" if CC.get(country) in NA else "INTL",
    }
    out_contacts.append(rec)
    if not ll:
        unmapped.append(rec)

# ---------- cluster ----------
def hav(a, b):
    R = 6371.0
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(h))

groups = collections.defaultdict(list)
for c in out_contacts:
    if c["lat"] is not None:
        groups[(c["city"], c["state"], c["country"], c["lat"], c["lng"])].append(c)
ordered = sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0][0]))

HUB_NAMES = {  # keyed by seed "City, ST" -> metro name
 "New York, NY":"New York Metro", "Chicago, IL":"Chicago Metro", "San Francisco, CA":"SF Bay Area", "Austin, TX":"Austin",
 "Toronto, ON":"Toronto / GTA", "Nashville, TN":"Nashville", "Calgary, AB":"Calgary", "Saskatoon, SK":"Saskatoon",
 "Los Angeles, CA":"Greater Los Angeles", "Atlanta, GA":"Atlanta Metro", "Ottawa, ON":"Ottawa–Gatineau",
 "Dallas, TX":"Dallas–Fort Worth", "Milwaukee, WI":"Milwaukee", "Boca Raton, FL":"South Florida",
 "Kennett Square, PA":"Greater Philadelphia", "Halifax Regional Municipality, NS":"Halifax",
 "Minneapolis, MN":"Minneapolis–St. Paul", "Dillon, CO":"Denver / Front Range", "Colorado Springs, CO":"Colorado Springs",
 "San Diego, CA":"San Diego", "Houston, TX":"Greater Houston", "Montreal, QC":"Montréal", "Edmonton, AB":"Edmonton",
 "Honolulu, HI":"Hawaiʻi (Oʻahu)", "Indianapolis, IN":"Indianapolis", "Salt Lake City, UT":"Salt Lake / Wasatch Front",
 "Phoenix, AZ":"Phoenix Metro", "Charlottetown, PE":"Prince Edward Island", "Durham, NC":"Research Triangle",
 "Boston, MA":"Greater Boston", "Fresno, CA":"Fresno / Central Valley", "Madison, WI":"Madison",
 "Chester, VA":"Richmond / Central Virginia", "Aldie, VA":"Washington DC Metro", "Portland, OR":"Portland",
 "Laurel, DE":"Delmarva (Laurel, DE)", "East Aurora, NY":"Buffalo", "Mexico City, Mexico City":"Mexico City",
 "Idaho Falls, ID":"Idaho Falls", "Henderson, NV":"Las Vegas", "Regina, SK":"Regina", "Victoria, BC":"Vancouver / Victoria",
 "Chesterfield, MO":"St. Louis", "Memphis, TN":"Memphis", "Tampa, FL":"Tampa Bay", "Orlando, FL":"Orlando",
 "Savannah, GA":"Savannah / Coastal Georgia", "Winnipeg, MB":"Winnipeg", "Cottonwood, CA":"Chico / Redding",
 "Destrehan, LA":"New Orleans", "Ankeny, IA":"Des Moines", "Charter Township of Clinton, MI":"Detroit Metro",
 "Fairmont Hot Springs, BC":"Panorama / Kootenays", "Stillwater, OK":"Stillwater, OK", "Charlotte, NC":"Charlotte", "Carlisle, PA":"Harrisburg / Central PA",
 "Miami, FL":"South Florida", "Fort Lee, VA":"Richmond / Central Virginia", "Seattle, WA":"Seattle / Puget Sound", "Bellingham, WA":"Vancouver / Bellingham",
 "Potosi, MO":"St. Louis / Potosi", "Waterford, CT":"Southeast Connecticut", "Stafford, VA":"Washington DC Metro", "Birmingham, MI":"Detroit Metro",
 "Roseville, CA":"Sacramento", "Eagle, ID":"Boise", "Charlemont, MA":"Western Massachusetts", "Summerside, PE":"Prince Edward Island",
 "Glenshaw, PA":"Pittsburgh", "Holland, MI":"Grand Rapids / Holland", "Fort Myers, FL":"Fort Myers / SW Florida", "Cleveland, OH":"Cleveland",
 "New Orleans, LA":"New Orleans", "Albuquerque, NM":"Albuquerque", "Hilo, HI":"Hawaiʻi (Big Island)", "Shirur, Maharashtra":"Pune / Shirur",
}
hubs = []
for (city, state, country, lat, lng), members in ordered:
    # join the NEAREST existing seed within the radius (not the first one found),
    # so a Philadelphia suburb inside both the NYC and Philly radii lands in Philly
    near = [(hav((lat, lng), (h["lat"], h["lng"])), h) for h in hubs]
    near = [(d, h) for d, h in near if d <= RADIUS_KM]
    if near:
        h = min(near, key=lambda x: x[0])[1]
        h["members"] += members; h["cities"].append(f"{city}, {state}")
    else:
        hubs.append({"seed": city, "state": state, "country": country, "lat": lat, "lng": lng,
                     "members": list(members), "cities": [f"{city}, {state}"]})
hubs.sort(key=lambda h: (-len(h["members"]), h["seed"]))
ABBR = {**{v: k for k, v in US.items()}}
US_AB = {s['name']: s['code'] for s in gc.get_us_states().values()}
CA_AB = {"Alberta":"AB","British Columbia":"BC","Manitoba":"MB","New Brunswick":"NB","Nova Scotia":"NS","Ontario":"ON","Prince Edward Island":"PE","Quebec":"QC","Saskatchewan":"SK"}
def ab(state, country):
    return US_AB.get(state) or CA_AB.get(state) or state
out_hubs = []
for hi, h in enumerate(hubs):
    seed_str = f'{h["seed"]}, {ab(h["state"], h["country"])}'
    region = "NA" if CC.get(h["country"]) in NA else "INTL"
    if region == "INTL":
        seed_str = f'{h["seed"]}, {h["country"]}'
    name = HUB_NAMES.get(seed_str, seed_str)
    inset = "HI" if h["state"] == "Hawaii" else "MX" if h["country"] == "Mexico" else None
    region = "NA" if CC.get(h["country"]) in NA else "INTL"
    for m in h["members"]:
        m["hub"] = hi
    out_hubs.append({"id": hi, "name": name, "seed": f'{h["seed"]}, {ab(h["state"], h["country"])}',
                     "lat": h["lat"], "lng": h["lng"], "country": h["country"], "inset": inset, "region": region,
                     "n": len(h["members"]), "accounts": len({m["company"] for m in h["members"]}),
                     "cities": h["cities"], "contacts": [m["id"] for m in h["members"]]})

# ---------- assertions (one source of truth) ----------
mapped = [c for c in out_contacts if c["hub"] is not None]
assert len(mapped) + len(unmapped) == UNIQ, "mapped + unmapped must equal unique contacts"
assert sum(h["n"] for h in out_hubs) == len(mapped), "hub counts must sum to mapped contacts"
unresolved = collections.Counter((c["city"], c["state"], c["country"]) for c in out_contacts if c["geo"] == "unresolved")
if unresolved:
    print("UNRESOLVED (add to OVERRIDES):"); [print(" ", k, n) for k, n in unresolved.most_common()]
    raise SystemExit("unresolved geocodes")

acct_hit = sum(1 for c in out_contacts if c["website"])
summary = {
    "generated": "2026-10-13", "raw_rows": RAW, "intl_contacts": sum(1 for c in out_contacts if c["region"] == "INTL"), "unique_contacts": UNIQ, "mapped": len(mapped),
    "unmapped": len(unmapped), "hubs": len(out_hubs), "radius_km": RADIUS_KM,
    "accounts_in_contacts": len({c["company"] for c in out_contacts}),
    "contacts_with_account_signal": acct_hit,
    "accounts_file_rows": len(accounts),
    "accounts_without_contacts": sorted(a["Company Name"] for k, a in accounts.items()
                                        if k not in {norm(c["company"]) for c in out_contacts}),
}
json.dump({"summary": summary, "hubs": out_hubs, "contacts": out_contacts}, open(OUT, "w"), indent=0)
print(json.dumps(summary, indent=1))
print("\nHUBS:")
for h in out_hubs:
    print(f'{h["n"]:3d} {h["accounts"]:3d}  {h["name"]:30s} seed={h["seed"]:28s} cities={len(h["cities"])} inset={h["inset"]}')
print("\nUNMAPPED by state:", collections.Counter((c["state"] or "—", c["country"]) for c in unmapped).most_common())
print("\nSENIORITY:", collections.Counter(c["seniority"] for c in out_contacts).most_common())
print("FUNCTION:", collections.Counter(c["func"] for c in out_contacts).most_common())
