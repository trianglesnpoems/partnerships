#!/usr/bin/env node
// Browser scan for partner facts: load each storefront in a real browser, run a search, and record which vendors the
// page calls. A technology export can keep listing a tool long after a store stopped using it, and a static fetch of
// the HTML misses anything a tag manager loads, so this is the scan that says what a shopper's browser talks to today.
//
//   node browser_scan.js <stores.json> <out.json> [concurrency]
//
// stores.json is [{"name": "...", "domain": "store.com"}, ...]. For each store the scan loads the home page, runs a
// search (through the page's own search box when it finds one, else /search?q=), and matches every request and the final
// page against the vendor patterns below. Vendor names are the ones partner_facts.py uses, so the two files join.
// A bot wall or a failed load is recorded as not read. It is never read as "no tool here".
const fs = require('fs');
const { chromium } = require('playwright');
const [storesPath, outPath, conc] = process.argv.slice(2);
const V = {
  'Klaviyo': /klaviyo\.com/i, 'Attentive': /attn\.tv|attentivemobile/i, 'Bloomreach': /brxcdn|brcdn\.com|bloomreach|brsrvr|exponea|brtrk/i, 'Braze': /braze\.(com|eu)|appboy/i,
  'Iterable': /iterable\.com/i, 'Salesforce Marketing Cloud': /exacttarget|igodigital|marketingcloudapis|sfmc-/i, 'Listrak': /listrak/i, 'Zeta': /zetaglobal|rezync|boomtrain/i,
  'Sailthru': /sailthru/i, 'Emarsys': /emarsys|scarabresearch/i, 'Bronto': /bronto\.com/i, 'Oracle Responsys': /responsys|rsys\d?\.net/i, 'Acoustic': /silverpop|acoustic\.co/i,
  'Bluecore': /bluecore|triggeredmail/i, 'Wunderkind': /wunderkind|bounceexchange|bouncex/i, 'Cordial': /cordial\.io/i, 'Mailchimp': /chimpstatic|list-manage/i, 'Postscript': /postscript\.io/i,
  'Yotpo': /yotpo\.com/i, 'Okendo': /okendo/i, 'Bazaarvoice': /bazaarvoice|bvapi|curalate/i, 'PowerReviews': /powerreviews/i, 'Emplifi': /turnto\.com|pixlee|emplifi/i,
  'Olapic': /olapic|photorank/i, 'Shopper Approved': /shopperapproved/i, 'Judge.me': /judge\.me/i, 'Stamped': /stamped\.io/i, 'Trustpilot': /trustpilot/i,
  'Gorgias': /gorgias/i, 'Kustomer': /kustomer/i, 'Zendesk': /zendesk|zdassets|zopim/i, 'Salesforce Service Cloud': /salesforceliveagent|liveagent|salesforce-scrt|embeddedservice/i,
  'Freshdesk': /freshdesk|freshchat/i, 'LivePerson': /liveperson|lpsnmedia/i, 'Genesys': /genesys|mypurecloud/i, 'Gladly': /gladly\.com/i, 'Intercom': /intercom(cdn)?\.(io|com)/i,
  'Ada': /ada\.support|ada\.cx/i, 'iAdvize': /iadvize/i, 'Powerfront': /powerfront|inside-graph/i, 'LiveChat': /livechatinc/i, 'Olark': /olark/i, 'eGain': /egain/i,
  'Nuance': /nuance|touchcommerce/i, 'Sierra': /sierra\.(chat|ai)/i, 'Linc': /letslinc|linc\.global/i, 'Tidio': /tidio/i,
  'Algolia': /algolia(net)?\.(com|net)|algolia\.io/i, 'Constructor': /cnstrc\.com|constructor\.io/i, 'Fast Simon': /fastsimon|instantsearchplus/i, 'Oracle Endeca': /endeca/i,
  'Lucidworks': /lucidworks/i, 'Coveo': /coveo/i, 'Unbxd': /unbxd/i, 'Findify': /findify/i, 'Hawk Search': /hawksearch/i, 'Searchspring': /searchspring/i, 'Klevu': /klevu/i,
  'Nosto': /nosto\.com/i, 'GroupBy': /groupbycloud|groupby\.io/i, 'Reflektion': /reflektion|rfksrv/i, 'Attraqt': /attraqt|fredhopper/i,
  'Loop': /loopreturns/i, 'AfterShip': /aftership/i, 'Narvar': /narvar/i, 'Happy Returns': /happyreturns/i, 'Returnly': /returnly/i,
  'Global-e': /global-e\.com|globale|borderfree/i, 'ESW': /eshopworld/i, 'Zonos': /zonos\.com/i, 'FlavorCloud': /flavorcloud/i,
  'Recharge': /rechargepayments|rechargeapps|rechargecdn/i, 'Skio': /skio\.com/i, 'Stay.ai': /stay\.ai|retextion/i, 'Ordergroove': /ordergroove/i, 'Recurly': /recurly/i,
  'Smile.io': /smile\.io/i, 'Rivo': /rivo\.io/i, 'Friendbuy': /friendbuy/i, 'Talon.One': /talon\.one/i, 'Rokt': /rokt\.com/i, 'LoyaltyLion': /loyaltylion/i, 'Extole': /extole/i,
  'Dynamic Yield': /dynamicyield/i, 'Rebuy': /rebuyengine/i, 'Shoplift': /shoplift\.ai/i, 'Monetate': /monetate/i, 'Certona': /certona|res-x\.com/i, 'Adobe Target': /tt\.omtrdc|adobetarget/i,
  'Salesforce Personalization': /evergage|evgnet/i, 'Optimizely': /optimizely/i, 'AB Tasty': /abtasty/i, 'Granify': /granify/i,
  'Signifyd': /signifyd/i, 'Forter': /forter/i, 'NoFraud': /nofraud/i, 'Riskified': /riskified/i, 'Kount': /kount\.(com|net)|kaptcha/i, 'Sift': /siftscience|sift\.com/i, 'ThreatMetrix': /threatmetrix|online-metrix/i,
  'Yottaa': /yottaa/i, 'Noibu': /noibu/i, 'Elevar': /elevar/i, 'Triple Whale': /triplewhale|triplepixel/i, 'Tapcart': /tapcart/i,
};
const WALL = /access denied|pardon our interruption|are you a robot|verify you are human|captcha|attention required|request blocked|bot or not|unusual traffic/i;
const stores = JSON.parse(fs.readFileSync(storesPath, 'utf8'));
const out = {};
async function scan(browser, s) {
  const ctx = await browser.newContext({ userAgent: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36', viewport: { width: 1280, height: 900 }, locale: 'en-US' });
  const p = await ctx.newPage(); const seen = {}; const r = { domain: s.domain, read: false, search_read: false, status: '', final_url: '', seen };
  const note = (u, how) => { for (const [k, re] of Object.entries(V)) if (re.test(u)) seen[k] = seen[k] || how; };
  p.on('request', q => { try { note(new URL(q.url()).hostname + new URL(q.url()).pathname.slice(0, 60), 'call'); } catch (e) {} });
  try {
    const res = await p.goto('https://' + s.domain + '/', { waitUntil: 'domcontentloaded', timeout: 35000 });
    r.status = res ? res.status() : ''; await p.waitForTimeout(6000);
    const title = await p.title().catch(() => ''), body = (await p.evaluate(() => document.body ? document.body.innerText.slice(0, 600) : '').catch(() => ''));
    r.final_url = p.url();
    if ((res && res.status() >= 400) || WALL.test(title) || (body.length < 400 && WALL.test(body))) { r.wall = true; }
    else {
      r.read = true;
      await p.mouse.wheel(0, 1400).catch(() => {}); await p.waitForTimeout(1500);
      // a search, through the page's own box when there is one
      let searched = false;
      for (const sel of ['input[type="search"]', 'input[name="q"]', 'input[name="search"]', 'input[name="Ntt"]', 'input[placeholder*="earch" i]', 'input[aria-label*="earch" i]']) {
        const box = p.locator(sel).first();
        if (await box.count().catch(() => 0) && await box.isVisible().catch(() => false)) {
          try { await box.fill('gift', { timeout: 3000 }); await p.waitForTimeout(1800); await box.press('Enter', { timeout: 3000 }); await p.waitForTimeout(6000); searched = true; break; } catch (e) {}
        }
      }
      if (!searched) { try { const q = await p.goto(new URL('/search?q=gift', p.url()).href, { waitUntil: 'domcontentloaded', timeout: 25000 }); if (q && q.status() < 400) { await p.waitForTimeout(5000); searched = true; } } catch (e) {} }
      r.search_read = searched && !WALL.test(await p.title().catch(() => ''));
      r.search_url = p.url();
      const html = await p.content().catch(() => ''); for (const [k, re] of Object.entries(V)) if (!seen[k] && re.test(html)) seen[k] = 'page';
    }
  } catch (e) { r.error = String(e.message || e).slice(0, 90); }
  await ctx.close(); return r;
}
(async () => {
  const browser = await chromium.launch(); const queue = stores.slice(); let done = 0;
  const worker = async () => { while (queue.length) { const s = queue.shift(); out[s.domain] = await Promise.race([scan(browser, s), new Promise(res => setTimeout(() => res({ domain: s.domain, read: false, search_read: false, error: 'timed out', seen: {} }), 90000))]); if (++done % 10 === 0) console.log(`${done} of ${stores.length}`); } };
  await Promise.all(Array.from({ length: +(conc || 6) }, worker));
  await browser.close();
  fs.writeFileSync(outPath, JSON.stringify({ scanned: new Date().toISOString().slice(0, 10), stores: out }, null, 1));
  const v = Object.values(out);
  console.log(`${v.length} stores | read ${v.filter(x => x.read).length} | search page read ${v.filter(x => x.search_read).length} | walled ${v.filter(x => x.wall).length} | failed ${v.filter(x => x.error).length}`);
})();
