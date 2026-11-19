#!/usr/bin/env python3
"""Load each storefront once and read the commerce platform off the page itself.

A third-party detector (BuiltWith, Store Leads) reports what it saw on some host at some date. This step reads the
live page on the day of the build, so the research starts from "what answers at this address today":
the final URL after redirects, the platform fingerprints found in the HTML, headers and cookies, the Shopify theme
object when there is one, and whether a bot wall answered instead of the site (which is NOT evidence of no store).

It never guesses: a host with no fingerprint is reported as "no platform fingerprint", and a blocked or failed fetch
is reported as such.

Usage: live_check.py <hosts.txt> <out.json>      (one host per line; stdlib only)
Behind a TLS-intercepting proxy set LIVE_CHECK_CA_BUNDLE=/path/to/ca.pem."""
import concurrent.futures as cf
import gzip, json, os, re, ssl, sys, urllib.error, urllib.request, datetime, http.cookiejar

CA = os.environ.get("LIVE_CHECK_CA_BUNDLE") or ("/root/.ccr/ca-bundle.crt" if os.path.exists("/root/.ccr/ca-bundle.crt") else None)
CTX = ssl.create_default_context(cafile=CA) if CA else ssl.create_default_context()
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0.0.0 Safari/537.36")
HDRS = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9", "Accept-Encoding": "gzip"}
MAX = 3_000_000

# (platform, where it is looked for, pattern). "html" = page source, "hdr" = response headers, "ck" = cookie names.
# Patterns are deliberately specific: a bare vendor name in a script URL is not a platform.
FP = [
    ("Shopify", "html", r"cdn\.shopify\.com|/cdn/shop/|Shopify\.theme\s*=|Shopify\.shop\s*=|myshopify\.com"),
    ("Shopify", "hdr", r"^x-shopid|^x-shopify-stage|^x-sorting-hat-shopid|^powered-by: *shopify|^x-shopify-"),
    ("Shopify (Hydrogen / Oxygen)", "html", r"shopify\.com/oxygen|cdn\.shopify\.com/oxygen|Shopify/Hydrogen|@shopify/hydrogen"),
    ("Shopify (Hydrogen / Oxygen)", "hdr", r"^powered-by: *shopify, *(hydrogen|oxygen)|^server: *oxygen|^oxygen-"),
    ("Salesforce Commerce Cloud", "html", r"demandware\.static|/on/demandware\.store/|demandware\.edgesuite|dw/shop/v\d|\bdwstatic\b|/dw/image/v2/"),
    ("Salesforce Commerce Cloud", "ck", r"^dwsid$|^dwanonymous_|^dwac_|^sid$.*dw|^__cq_dnt$|^dw_dnt$"),
    ("Salesforce Commerce Cloud (PWA Kit / headless)", "html", r"mobify|commerce-sdk-react|/mobify/bundle/|__PRELOADED_STATE__.{0,2000}?\bcommerceAPI\b"),
    ("SAP Commerce Cloud (Hybris)", "html", r"/_ui/(responsive|desktop|addons|shared)/|\bACC\.config\b|/medias/[^\"' ]+\?context=|\byCMS\b|cx-storefront|/occ/v2/|spartacus"),
    ("HCL Commerce (WebSphere)", "html", r"/wcsstore/|/webapp/wcs/stores/|/wcs/resources/store/|\bWCParamJS\b|/hclstore/|\bwcsstore\b"),
    ("HCL Commerce (WebSphere)", "ck", r"^WC_(SESSION_ESTABLISHED|PERSISTENT|ACTIVEPOINTER|USERACTIVITY)|^WC_"),
    ("Oracle Commerce (ATG / Commerce Cloud)", "html", r"/ccstoreui/|/ccstore/v1/|oracle commerce cloud|\b_DARGS\b|/atg/|atg\.commerce|\bATGSvcs\b|_dyncharset"),
    ("Oracle Commerce (ATG / Commerce Cloud)", "ck", r"^DYN_USER_ID$|^DYN_USER_CONFIRM$|^ATG_SESSION_ID$"),
    ("Adobe Commerce / Magento", "html", r"/static/version\d+/|/static/frontend/|Magento_[A-Z][A-Za-z]+/|\bmage/cookies\b|mage-cache-storage|text/x-magento-init|/pub/static/|/media/catalog/product/|Mage\.Cookies|/skin/frontend/"),
    ("Adobe Commerce / Magento", "hdr", r"^x-magento-"),
    ("Adobe Commerce (Edge Delivery / PWA)", "html", r"magento-venia|@magento/(pwa|venia)|pwa-studio|commerce\.adobe\.io|catalog-service\.adobe\.io"),
    ("BigCommerce", "html", r"cdn\d*\.bigcommerce\.com|bigcommerce\.com/s-[a-z0-9]+|\bstencil-utils\b|data-stencil|BCData\s*="),
    ("WooCommerce", "html", r"wp-content/plugins/woocommerce|\bwoocommerce-(page|js|no-js)\b|wc-ajax=|wc_add_to_cart_params|class=\"[^\"]*\bwoocommerce\b"),
    ("commercetools", "html", r"commercetools\.(com|io)|\bctp[_-]project|commercetools-frontend"),
    ("VTEX", "html", r"vteximg\.com|vtexassets\.com|\.vtex\.com/|vtex\.render|__RUNTIME__"),
    ("Kibo Commerce", "html", r"kibocommerce|mozu\.com|cdn-(sb|tp\d)\.mozu\.com"),
    ("Miva Merchant", "html", r"/mm5/|Miva Merchant|\bmivajs\b|mvga\.js"),
    ("NetSuite SuiteCommerce", "html", r"suitecommerce|/sca-(src|dev)-|\bSC\.ENVIRONMENT\b|netsuite\.com/c\.\d+|/c\.\d+/[a-z0-9-]*sca"),
    ("Optimizely Commerce (Episerver)", "html", r"/episerver/|EPiServer|epi-(cms|commerce)|optimizely commerce"),
    ("Sitecore", "html", r"/-/media/|/sitecore/|scItemsPath|sc_site"),
    ("Znode", "html", r"\bznode\b"),
    ("Unilog", "html", r"unilog(corp)?\.com|\bcimm2\b"),
    ("Salesforce B2B / Experience Cloud", "html", r"/s/sfsites/|\bccrz__|[a-z0-9-]\.(?:my\.site|force)\.com/|LightningOutApp|siteforce:"),
    ("Insite / Optimizely B2B", "html", r"insitecommerce|insite\.(core|js)|/systemresources/"),
    ("Instacart Storefront", "html", r"instacart\.com/(store|assets|image-server)|instacart-idp|powered by instacart|instacartcdn|\bIC_STOREFRONT\b"),
    ("Fanatics platform", "html", r"frgimages\.com|fanatics\.frgimages|images\.footballfanatics\.com|fanaticsinc\.com/(?!$)|\bfanatics-web\b"),
    ("WineDirect / vinSUITE", "html", r"vinsuite|winedirect\.com|vin65\.com|assetss?\.vin65"),
    ("Commerce7", "html", r"commerce7\.com|cdn\.commerce7"),
    ("Squarespace", "html", r"static1\.squarespace\.com|squarespace-cdn\.com|Static\.SQUARESPACE_CONTEXT"),
    ("Webflow", "html", r"assets\.website-files\.com|data-wf-site|webflow\.(js|css)"),
    ("Wix", "html", r"static\.wixstatic\.com|wix-warmup-data|_wixCIDX"),
    ("WordPress", "html", r"/wp-content/|/wp-includes/|wp-json"),
    ("Drupal", "html", r"Drupal\.settings|drupal-settings-json|/sites/default/files/"),
    ("Adobe Experience Manager", "html", r"/etc\.clientlibs/|/etc/designs/|/content/dam/|cq:template"),
    ("Contentful", "html", r"ctfassets\.net|contentful\.com"),
    ("Contentstack", "html", r"contentstack\.(io|com)"),
    ("Amplience", "html", r"amplience\.(net|com)|a\.static\.amplience|cdn\.media\.amplience"),
    ("Next.js (custom / headless front end)", "html", r"__NEXT_DATA__|/_next/static/"),
    ("Nuxt (custom / headless front end)", "html", r"__NUXT__|/_nuxt/"),
    ("Angular (custom front end)", "html", r"ng-version=\"\d+"),
]
FP = [(n, w, re.compile(p, re.I | (re.M if w == "hdr" else 0))) for n, w, p in FP]
# things that are not a platform but matter for the Shopify-ecosystem read
APPS = [("Klaviyo", r"klaviyo\.com|static\.klaviyo|_learnq"), ("Yotpo", r"yotpo\.com|staticw2\.yotpo"), ("Recharge", r"rechargeapps|rechargecdn|rechargepayments"),
        ("Gorgias", r"gorgias\.(chat|io|com)"), ("Okendo", r"okendo\.io"), ("Attentive", r"attn\.tv|attentivemobile"), ("Global-e", r"global-e\.com|globale\."),
        ("Shop Pay", r"shop-pay|shopify-pay|shop\.app/pay|shop_pay"), ("Afterpay", r"afterpay"), ("Klarna", r"klarna"), ("Affirm", r"affirm\.com"),
        ("Loop Returns", r"loopreturns"), ("Rebuy", r"rebuyengine"), ("Nosto", r"nosto\.com"), ("Bazaarvoice", r"bazaarvoice|bvapi"), ("PowerReviews", r"powerreviews"),
        ("Dynamic Yield", r"dynamicyield|dy-api"), ("Bloomreach", r"bloomreach|brxcdn|exponea"), ("Algolia", r"algolia(net)?\.com|algolianet"),
        ("Constructor", r"cnstrc\.com"), ("Salesforce Marketing Cloud", r"exacttarget|igodigital|evergage|mc\.s\d+\.exacttarget"), ("Einstein (CQuotient)", r"cquotient"),
        ("Adobe Analytics / Target", r"omtrdc\.net|adobedtm|tt\.omtrdc|assets\.adobedtm"), ("Tealium", r"tiqcdn\.com"), ("Braze", r"braze\.(com|eu)|appboy"),
        ("Signifyd", r"signifyd"), ("Narvar", r"narvar"), ("Elevar", r"elevar"), ("Triple Whale", r"triplewhale|triplepixel"), ("Northbeam", r"northbeam")]
APPS = [(n, re.compile(p, re.I)) for n, p in APPS]
WALLS = [("Akamai", r"errors\.edgesuite\.net|<title>Access Denied</title>|akamai.{0,40}(bot|denied)"), ("PerimeterX / HUMAN", r"px-captcha|_pxAppId|perimeterx|Press &amp; Hold|human\.security"),
         ("Vercel checkpoint", r"Vercel Security Checkpoint"),
         ("Cloudflare challenge", r"cf-chl-|Just a moment\.\.\.|challenge-platform|cf-turnstile|Attention Required! \| Cloudflare"), ("Imperva / Incapsula", r"_Incapsula_Resource|incapsula incident"),
         ("DataDome", r"datadome|geo\.captcha-delivery\.com"), ("Kasada", r"KPSDK|kasada"), ("Queue-it", r"queue-it\.net"), ("Radware", r"radware|validate\.perfdrive\.com")]
WALLS = [(n, re.compile(p, re.I | re.S)) for n, p in WALLS]
RE_THEME = re.compile(r"Shopify\.theme\s*=\s*(\{.*?\})\s*;", re.S)
RE_SHOP = re.compile(r"Shopify\.shop\s*=\s*\"([a-z0-9][a-z0-9-]*\.myshopify\.com)\"", re.I)

def fetch(url, timeout=25):
    jar = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPSHandler(context=CTX), urllib.request.HTTPCookieProcessor(jar))
    req = urllib.request.Request(url, headers=HDRS)
    try:
        r = op.open(req, timeout=timeout); code = r.status
    except urllib.error.HTTPError as e:
        r, code = e, e.code     # error pages still carry fingerprints (a Shopify password page, a bot wall)
    raw = r.read(MAX)
    if raw[:2] == b"\x1f\x8b":
        try: raw = gzip.decompress(raw)
        except Exception: pass
    return code, r.geturl(), [(k.lower(), v) for k, v in r.headers.items()], raw.decode("utf-8", "replace"), sorted({c.name for c in jar})

def read(host):
    out = {"host": host, "checked": datetime.date.today().isoformat(), "status": None, "final_url": "", "error": "", "title": "",
           "platforms": [], "evidence": {}, "apps": [], "bot_wall": "", "shopify": None, "bytes": 0}
    cands = [f"https://{host}/"] + ([f"https://www.{host}/"] if host.count(".") == 1 and not host.startswith("www.") else [])
    got, err = None, ""
    for url in cands:
        try:
            got = fetch(url); break
        except Exception as e:
            err = f"{type(e).__name__}: {str(e)[:120]}"
    if not got:
        out["error"] = err or "unreachable"; return out
    code, final, hdrs, html, cookies = got
    out.update(status=code, final_url=final, bytes=len(html))
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    out["title"] = re.sub(r"\s+", " ", m.group(1)).strip()[:140] if m else ""
    hdr_text = "\n".join(f"{k}: {v}" for k, v in hdrs)
    blocked = code in (401, 403, 405, 406, 429, 503)
    for name, pat in WALLS:
        if pat.search(html[:60000]) and (blocked or len(html) < 20000):
            out["bot_wall"] = name; break
    if blocked and not out["bot_wall"] and len(html) < 20000 and code != 401:
        out["bot_wall"] = f"refused (HTTP {code})"     # an unnamed refusal is still a refusal, not an empty site
    for name, where, pat in FP:
        if where == "ck":
            hit = next((c for c in cookies if pat.search(c)), None)
            ev = f"cookie {hit}" if hit else None
        else:
            m = pat.search(html if where == "html" else hdr_text)
            ev = (("page: " if where == "html" else "header: ") + re.sub(r"\s+", " ", m.group(0))[:60]) if m else None
        if ev and name not in out["evidence"]:
            out["evidence"][name] = ev; out["platforms"].append(name)
    out["apps"] = [n for n, pat in APPS if pat.search(html)]
    if "Shopify" in out["evidence"]:
        sh = {}
        m = RE_THEME.search(html)
        if m:
            try: t = json.loads(m.group(1))
            except Exception: t = {k: (re.search(r'"%s"\s*:\s*"([^"]*)"' % k, m.group(1)) or [None, ""])[1] for k in ("name", "schema_name")}
            sh["theme_name"], sh["theme_schema"] = str(t.get("name") or ""), str(t.get("schema_name") or "")
            sh["theme_store_id"] = t.get("theme_store_id")
        m = RE_SHOP.search(html)
        if m: sh["shop"] = m.group(1)
        out["shopify"] = sh
    return out

def main():
    hosts = sorted({h.strip().lower() for h in open(sys.argv[1], encoding="utf-8") if h.strip() and not h.startswith("#")})
    res = {}
    with cf.ThreadPoolExecutor(max_workers=16) as ex:
        for i, r in enumerate(ex.map(read, hosts), 1):
            res[r["host"]] = r
            if i % 25 == 0: print(f"  {i}/{len(hosts)}", file=sys.stderr)
    json.dump(res, open(sys.argv[2], "w"), indent=0, ensure_ascii=False)
    ok = [r for r in res.values() if r["status"]]
    print("hosts", len(hosts), "| answered", len(ok), "| HTTP 200", sum(1 for r in ok if r["status"] == 200), "| bot wall", sum(1 for r in ok if r["bot_wall"]),
          "| failed", len(hosts) - len(ok), "| with a platform fingerprint", sum(1 for r in ok if r["platforms"]))

if __name__ == "__main__":
    main()
