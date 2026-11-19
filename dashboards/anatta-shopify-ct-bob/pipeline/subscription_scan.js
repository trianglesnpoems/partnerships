#!/usr/bin/env node
// Subscription scan: look for recurring purchase at each store the way a shopper's browser would find it.
//
//   node subscription_scan.js <stores.json> <out.json> [concurrency]
//
// stores.json is [{"name": "...", "domain": "store.com", "groups": ["Company"]}, ...]. For each store the scan
//   1. loads the home page and collects every link whose text or address reads like recurring purchase,
//   2. asks the store, from inside the page, for the addresses programs usually live at (/subscriptions, /autoship, ...),
//   3. reads the sitemap for addresses that name a subscription, auto-ship, club, membership or rental,
//   4. runs the store's own search for "subscription",
//   5. on a Shopify store, reads product records for selling plans (how Shopify stores a subscription offer),
//   6. opens the three most promising pages and keeps the sentences around each match,
// and records every subscription engine the browser called on the way.
//
// What comes out is a list of leads with the words found and where. It is not a verdict: "subscribe" is also what a
// newsletter box says, and a club can be a golf club. A person or a research pass reads the leads and decides.
// A bot wall or a failed load is recorded as not read. It is never read as "no program here".
const fs = require('fs');
const { chromium } = require('playwright');
const [storesPath, outPath, conc] = process.argv.slice(2);
if (!storesPath || !outPath) { console.error('usage: node subscription_scan.js <stores.json> <out.json> [concurrency]'); process.exit(2); }

// The engines that run subscriptions, memberships and wine clubs. Matched against every request and each page's source.
const ENGINES = {
  'Recharge': /rechargepayments|rechargeapps|rechargecdn|rechargeassets/i, 'Skio': /skio\.com/i, 'Stay.ai': /stay\.ai|retextion/i, 'Ordergroove': /ordergroove/i,
  'Recurly': /recurly/i, 'Smartrr': /smartrr/i, 'Bold Subscriptions': /sub\.boldapps\.net|ro\.boldapps\.net|bold[-_]?subscriptions/i, 'Loop Subscriptions': /loopwork\.co/i,
  'Appstle': /appstle/i, 'Seal Subscriptions': /sealsubscriptions/i, 'PayWhirl': /paywhirl/i, 'Chargebee': /chargebee/i, 'Zuora': /zuora/i, 'sticky.io': /sticky\.io/i,
  'Subbly': /subbly/i, 'Awtomic': /awtomic|bundlesubscriptions/i, 'Prive': /tryprive|prive\.co/i, 'Subscribe Pro': /subscribepro/i, 'QPilot': /qpilot/i,
  'WooCommerce Subscriptions': /woocommerce-subscriptions|wcs-|wc-subscriptions/i, 'Maxio': /chargify|maxio/i, 'Rebilly': /rebilly/i, 'Yotpo Subscriptions': /subscriptions\.yotpo/i,
  'ebbo (Clarus)': /claruscommerce|ebbo\.com/i, 'Commerce7': /commerce7/i, 'WineDirect': /winedirect|vin65/i, 'Vinoshipper': /vinoshipper/i,
};
// Words that can mean recurring purchase, by kind. "member" and "rental" are weak on their own.
const CATS = [
  ['sub', 'subscri(?:be|bed|ber|bers|ption|ptions)'],
  ['auto', 'auto[\\s-]?(?:ship|deliver|replenish|renew|refill|reorder)\\w*|autoship\\w*|autorenew\\w*'],
  ['replen', 'replenish\\w*|recurring (?:order|deliver|shipment|purchase|billing|charge)\\w*|repeat deliver\\w*|scheduled deliver\\w*|easy refills?'],
  ['club', '\\b(?:wine|beer|coffee|tea|candy|book|box|snack|sock|cheese|plant|science)[\\s-]?club\\b|\\w+ of the month|monthly box|subscription box'],
  ['member', 'paid membership|membership fee|annual (?:fee|membership)|\\bmemberships?\\b|become a member|join the club|\\bclub\\b'],
  ['rental', '\\brent(?:al|als)?\\b|rent[\\s-]to[\\s-]own|\\blease(?:s|d)?\\b'],
];
const URLKEY = 'subscri|auto-?(?:ship|deliver|replen|renew)|autoship|replenish|membership|member-|[-/_]club|rental|refill|of-the-month';
const PATHS = ['/subscriptions', '/subscription', '/subscribe', '/subscribe-and-save', '/pages/subscribe', '/pages/subscription', '/pages/subscriptions', '/pages/subscribe-and-save',
  '/auto-ship', '/autoship', '/auto-delivery', '/autodelivery', '/auto-replenish', '/auto-replenishment', '/replenishment', '/membership', '/memberships', '/club', '/wine-club', '/rentals', '/rent'];
const WALL = /access denied|pardon our interruption|are you a robot|verify you are human|captcha|attention required|request blocked|bot or not|unusual traffic|just a moment|security check/i;
const NEWS = 'newsletter|e-?mail|\\bsms\\b|text (?:alert|message|me)|inbox|sign up for|\\bupdates\\b|unsubscribe|mailing list|notif|youtube|channel|podcast|rss|stay (?:up to date|in touch|in the know|connected)|(?:special|exclusive) offers|latest news|be the first';
// Selling plans that are not subscriptions: a pre-order or a deposit is stored the same way.
const NOT_A_SUB = 'pre-?order|back-?order|try before|deposit|layaway|made to order';

// Runs inside the page. Everything it needs arrives as plain data, and only compact results cross back.
const IN_PAGE = async ({ job, CATS, URLKEY, PATHS, NEWS, NOT_A_SUB, shown }) => {
  const KW = new RegExp(CATS.map(c => c[1]).join('|'), 'gi'), newsRe = new RegExp(NEWS, 'i'), urlRe = new RegExp(URLKEY, 'i'), old = new Set(shown || []);
  const pathOf = u => { try { return new URL(u, location.href).pathname; } catch (e) { return ''; } };
  const catOf = w => (CATS.find(c => new RegExp('^(?:' + c[1] + ')$', 'i').test(w)) || ['other'])[0];
  const snips = (text, max) => {
    const out = [], counts = {}, seen = new Set(); KW.lastIndex = 0; let m, n = 0;
    while ((m = KW.exec(text)) && n++ < 400) {
      const cat = catOf(m[0]);
      const news = cat === 'sub' && newsRe.test(text.slice(Math.max(0, m.index - 90), m.index + m[0].length + 90));
      const k = news ? 'newsletter' : cat; counts[k] = (counts[k] || 0) + 1;
      if (out.length >= 30) continue;
      const s = text.slice(Math.max(0, m.index - 140), Math.min(text.length, m.index + m[0].length + 200)).replace(/\s+/g, ' ').trim();
      const key = text.slice(Math.max(0, m.index - 40), m.index + m[0].length + 40).replace(/\s+/g, ' ').trim(); if (seen.has(key) || old.has(key)) continue; seen.add(key);
      out.push({ cat, news, s, key }); KW.lastIndex = m.index + m[0].length + 150;
    }
    const rank = x => x.news ? 9 : ({ auto: 0, sub: 1, replen: 2, club: 3, member: 5, rental: 6 }[x.cat] ?? 7);
    return { counts, snips: out.sort((a, b) => rank(a) - rank(b)).slice(0, max) };
  };
  const textOf = html => { const d = new DOMParser().parseFromString(html, 'text/html'); d.querySelectorAll('script,style,noscript,svg,template').forEach(e => e.remove()); return { title: (d.title || '').trim().slice(0, 140), text: (d.body ? d.body.textContent : '').replace(/\s+/g, ' ') }; };
  const get = async (url, ms) => { const c = new AbortController(), t = setTimeout(() => c.abort(), ms || 9000); try { const r = await fetch(url, { redirect: 'follow', credentials: 'include', signal: c.signal }); return r; } finally { clearTimeout(t); } };
  const body = async r => { if (/\.gz($|\?)/.test(r.url)) { try { return await new Response(r.body.pipeThrough(new DecompressionStream('gzip'))).text(); } catch (e) { return ''; } } return await r.text(); };

  if (job === 'page') {           // the page that is open now
    const text = (document.body ? document.body.innerText : '').replace(/[ \t]+/g, ' ');
    const links = [], seen = new Set();
    for (const a of document.querySelectorAll('a[href]')) {
      const t = (a.innerText || a.getAttribute('aria-label') || a.title || '').replace(/\s+/g, ' ').trim().slice(0, 90); let href = a.href || '';
      if (!/^https?:/.test(href) || seen.has(href)) continue;
      href = href.split('#')[0]; if (seen.has(href) || href.split('?')[0] === location.href.split('#')[0].split('?')[0]) continue;
      if (/log-?in|sign-?in|\/account|unsubscribe|wish-?list|privacy|terms/i.test(pathOf(href))) continue;
      KW.lastIndex = 0; const mt = KW.exec(t); const mu = urlRe.exec(pathOf(href));
      if (!mt && !mu) continue;
      if (mt && catOf(mt[0]) === 'sub' && newsRe.test(t) && !mu) continue;
      seen.add(href); links.push({ text: t, href: href.slice(0, 220), cat: mt ? catOf(mt[0]) : 'url' }); if (links.length >= 40) break;
    }
    const h = [...document.querySelectorAll('h1,h2')].map(e => e.innerText.replace(/\s+/g, ' ').trim()).filter(Boolean).slice(0, 6).join(' | ').slice(0, 300);
    return { title: document.title.slice(0, 140), head: h, links, chars: text.length, shopify: !!(window.Shopify && (window.Shopify.shop || window.Shopify.theme)), ...snips(text, 8) };
  }
  if (job === 'probe') {          // the addresses a program usually lives at
    const home = textOf(document.documentElement.outerHTML).title; const out = [];
    const one = async p => {
      try {
        const r = await get(p, 7000); const html = (await r.text()).slice(0, 900000); const { title, text } = textOf(html); const f = new URL(r.url);
        const soft = r.status >= 400 || f.pathname === '/' || title === home || /log-?in|sign-?in|\/account/i.test(f.pathname) || /not found|404|can.?t find|couldn.?t find|no longer available|page missing|oops/i.test(title + ' ' + text.slice(0, 400));
        const x = { path: p, status: r.status, final: f.pathname.slice(0, 120) + (f.host !== location.host ? ' @' + f.host : ''), title, soft };
        if (!soft) Object.assign(x, snips(text, 4)); out.push(x);
      } catch (e) { out.push({ path: p, status: 0, error: String(e).slice(0, 60) }); }
    };
    for (let i = 0; i < PATHS.length; i += 11) await Promise.all(PATHS.slice(i, i + 11).map(one));
    return out;
  }
  if (job === 'sitemap') {        // addresses in the sitemap that name a program
    const res = { found: false, read: 0, locs: 0, urls: [], skipped: 0 }; let roots = [];
    try { const r = await get('/robots.txt', 7000); if (r.ok) roots = [...(await r.text()).matchAll(/^\s*sitemap:\s*(\S+)/gim)].map(m => m[1]).slice(0, 4); } catch (e) {}
    if (!roots.length) roots = ['/sitemap.xml'];
    const queue = roots.slice(), done = new Set(); const hits = new Set();
    while (queue.length && res.read < 6) {
      const u = queue.shift(); if (done.has(u)) continue; done.add(u);
      try {
        if (new URL(u, location.href).host !== location.host) { res.skipped++; continue; }
        const r = await get(u, 8000); if (!r.ok) continue; const xml = (await body(r)).slice(0, 6000000); if (!/<(urlset|sitemapindex)/i.test(xml)) continue;
        res.found = true; res.read++;
        const locs = [...xml.matchAll(/<loc>\s*(?:<!\[CDATA\[)?([^<\]]+)/gi)].map(m => m[1].trim());
        if (/<sitemapindex/i.test(xml)) { const pref = locs.filter(l => /page|content|static|landing|cms|categor|collection|misc|other|info|folder/i.test(l)); for (const l of [...pref, ...locs.filter(l => !pref.includes(l))].slice(0, 7)) queue.push(l); }
        else { res.locs += locs.length; for (const l of locs) if (urlRe.test(pathOf(l)) && !/unsubscribe/i.test(l)) hits.add(l.slice(0, 200)); }
      } catch (e) { res.skipped++; }
    }
    res.urls = [...hits].sort((a, b) => a.length - b.length).slice(0, 30); res.hits = hits.size; return res;
  }
  if (job === 'shopify') {        // selling plans on product records: how Shopify stores a subscription offer
    const res = { products: 0, sampled: 0, with_plans: 0, with_sub_plans: 0, plans: [], example: '' }; const notSub = new RegExp(NOT_A_SUB, 'i');
    try {
      const r = await get('/products.json?limit=250', 12000); if (!r.ok) return res; const j = await r.json(); const ps = j.products || []; res.products = ps.length;
      const hint = ps.filter(p => /subscri|refill|replen|auto/i.test((p.title || '') + ' ' + (p.tags || []).join(' ') + ' ' + (p.product_type || '')));
      const pick = [...new Set([...hint.slice(0, 6), ...ps.slice(0, 6), ...ps.slice(-3)])].slice(0, 14);
      for (const p of pick) {
        try { const q = await get('/products/' + p.handle + '.js', 8000); if (!q.ok) continue; const d = await q.json(); res.sampled++; const g = d.selling_plan_groups || [];
          const subs = g.filter(x => !notSub.test(String(x.name) + ' ' + (x.selling_plans || []).map(y => y.name).join(' ')));
          if (subs.length) { res.with_sub_plans++; if (!res.example) res.example = '/products/' + p.handle; }
          if (g.length) { res.with_plans++; for (const x of g) if (res.plans.length < 6 && !res.plans.includes(x.name)) res.plans.push(String(x.name).slice(0, 80)); } } catch (e) {}
      }
    } catch (e) {}
    return res;
  }
};

const stores = JSON.parse(fs.readFileSync(storesPath, 'utf8'));
const out = {};
const within = (p, ms, fallback) => Promise.race([p, new Promise(r => setTimeout(() => r(fallback), ms))]);
async function scan(browser, s, hold) {
  const ctx = hold.ctx = await browser.newContext({ userAgent: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36', viewport: { width: 1280, height: 900 }, locale: 'en-US' });
  const p = await ctx.newPage(); const engines = {}; let phase = 'home';
  const r = { domain: s.domain, read: false, status: '', final_url: '', engines, links: [], probes: [], pages: [] };
  const note = (u, how) => { for (const [k, re] of Object.entries(ENGINES)) if (re.test(u)) engines[k] = engines[k] || how; };
  p.on('request', q => { try { const u = new URL(q.url()); note(u.hostname + u.pathname.slice(0, 80), 'called on ' + phase); } catch (e) {} });
  const shown = []; const t0 = Date.now();
  const inPage = (job, ms) => within(p.evaluate(IN_PAGE, { job, CATS, URLKEY, PATHS, NEWS, NOT_A_SUB, shown }).catch(e => ({ error: String(e.message || e).slice(0, 80) })), ms, { error: 'timed out' });
  const keep = x => { for (const s of (x && x.snips) || []) { if (s.key) shown.push(s.key); delete s.key; } return x; };
  const source = async where => { const html = await within(p.content().catch(() => ''), 8000, ''); for (const [k, re] of Object.entries(ENGINES)) if (!engines[k] && re.test(html)) engines[k] = 'in the page source of ' + where; };
  try {
    // Some stores answer only at www, and a busy server is not a wall: try the address as given, then www, before calling it unread.
    const open = async host => { try { return await p.goto('https://' + host + '/', { waitUntil: 'domcontentloaded', timeout: 35000 }); } catch (e) { return null; } };
    let res = await open(s.domain);
    if ((!res || res.status() >= 400) && !/^www\./.test(s.domain) && s.domain.split('.').length <= 3) { const again = await open('www.' + s.domain); if (again && (!res || again.status() < res.status())) res = again; }
    if (!res) throw new Error('did not load');
    r.status = res ? res.status() : ''; await p.waitForTimeout(4500);
    const title = await p.title().catch(() => ''), body = await p.evaluate(() => document.body ? document.body.innerText.slice(0, 600) : '').catch(() => '');
    r.final_url = p.url();
    if ((res && res.status() >= 400) || WALL.test(title) || (body.length < 400 && WALL.test(body))) { r.wall = true; r.wall_title = title.slice(0, 80); await ctx.close(); return r; }
    r.read = true;
    await p.mouse.wheel(0, 20000).catch(() => {}); await p.waitForTimeout(1500);
    const home = keep(await inPage('page', 12000)); r.home = { title: home.title, chars: home.chars, counts: home.counts, snips: home.snips }; r.links = home.links || []; await source('the home page');
    r.probes = await inPage('probe', 30000); if (!Array.isArray(r.probes)) r.probes = []; for (const x of r.probes) keep(x);
    r.sitemap = await inPage('sitemap', 40000);
    if (home.shopify) r.shopify = await inPage('shopify', 40000);
    // the store's own search
    phase = 'the search'; let searched = false;
    for (const sel of ['input[type="search"]', 'input[name="q"]', 'input[name="search"]', 'input[name="Ntt"]', 'input[placeholder*="earch" i]', 'input[aria-label*="earch" i]']) {
      const box = p.locator(sel).first();
      if (await box.count().catch(() => 0) && await box.isVisible().catch(() => false)) {
        try { await box.fill('subscription', { timeout: 3000 }); await p.waitForTimeout(1200); await box.press('Enter', { timeout: 3000 }); await p.waitForTimeout(5000); searched = true; break; } catch (e) {}
      }
    }
    if (!searched) { try { const q = await p.goto(new URL('/search?q=subscription', r.final_url).href, { waitUntil: 'domcontentloaded', timeout: 25000 }); if (q && q.status() < 400) { await p.waitForTimeout(4000); searched = true; } } catch (e) {} }
    if (searched && !WALL.test(await p.title().catch(() => ''))) {
      const sp = keep(await inPage('page', 12000)); await source('the search results');
      r.search = { url: p.url().slice(0, 200), title: sp.title, counts: sp.counts, snips: (sp.snips || []).slice(0, 5), links: (sp.links || []).filter(l => !r.links.some(k => k.href === l.href)).slice(0, 10) };
    }
    // the most promising pages, opened for real
    const origin = new URL(r.final_url).origin, cand = [];
    const push = (u, why, w) => { try { const a = new URL(u, origin).href.split('#')[0]; if (new URL(a).pathname === '/') return; const had = cand.find(c => c.url === a); if (had) { if (w < had.w) { had.w = w; had.why = why; } } else cand.push({ url: a, why, w }); } catch (e) {} };
    const W = { auto: 0, sub: 1, replen: 2, club: 3, url: 4, member: 6, rental: 7 };
    for (const l of r.links) push(l.href, 'link: ' + l.text, /^\s*subscribe\s*$/i.test(l.text) ? 7.5 : (W[l.cat] ?? 8));
    for (const l of (r.search && r.search.links) || []) push(l.href, 'search link: ' + l.text, (W[l.cat] ?? 8) + 0.5);
    for (const x of r.probes) if (x.status === 200 && !x.soft && x.counts && ((x.counts.sub || 0) + (x.counts.auto || 0) + (x.counts.replen || 0) + (x.counts.club || 0) > 0)) push(x.final.split(' @')[0], 'address answered: ' + x.path, 1.5);
    for (const u of (r.sitemap && r.sitemap.urls) || []) push(u, 'in the sitemap', /subscri|auto|replen/i.test(u) ? 2.5 : 6.5);
    cand.sort((a, b) => a.w - b.w);
    for (const c of cand.filter(c => new URL(c.url).host.replace(/^www\./, '').endsWith(s.domain.replace(/^www\./, '').split('.').slice(-2).join('.'))).slice(0, 3)) {
      phase = c.url.replace(origin, '').slice(0, 60);
      try {
        const q = await p.goto(c.url, { waitUntil: 'domcontentloaded', timeout: 25000 }); await p.waitForTimeout(3500);
        const pg = keep(await inPage('page', 12000)); await source(phase);
        r.pages.push({ url: c.url.slice(0, 220), why: c.why.slice(0, 110), status: q ? q.status() : '', final: p.url().slice(0, 220), title: pg.title, head: pg.head, counts: pg.counts, snips: (pg.snips || []).slice(0, 8), wall: WALL.test(pg.title || '') });
      } catch (e) { r.pages.push({ url: c.url.slice(0, 220), why: c.why.slice(0, 110), error: String(e.message || e).slice(0, 80) }); }
    }
    r.candidates = cand.length; r.secs = Math.round((Date.now() - t0) / 1000);
  } catch (e) { r.error = String(e.message || e).slice(0, 90); }
  await ctx.close().catch(() => {}); return r;
}
// What the scan found, in one word, so a reader can sort the leads. Still a lead, not a verdict.
function lead(r) {
  if (!r.read) return 'not read';
  const strong = c => c && ((c.auto || 0) + (c.replen || 0) + (c.sub || 0) + (c.club || 0)) > 0;
  const pages = (r.pages || []).filter(x => !x.wall && !x.error);
  if ((r.shopify && r.shopify.with_sub_plans) || Object.keys(r.engines).length) return 'engine or selling plan seen';
  if (pages.some(x => strong(x.counts)) || (r.probes || []).some(x => !x.soft && strong(x.counts))) return 'program wording on a page';
  if (strong(r.home && r.home.counts) || strong(r.search && r.search.counts) || ((r.sitemap && r.sitemap.hits) || 0) > 0) return 'wording seen, no page opened';
  if (pages.some(x => x.counts && (x.counts.member || x.counts.rental)) || ((r.home && r.home.counts && (r.home.counts.member || 0)) > 0)) return 'membership or rental wording only';
  return 'nothing seen';
}
(async () => {
  const browser = await chromium.launch(); const queue = stores.slice(); let done = 0;
  const worker = async () => {
    while (queue.length) {
      const s = queue.shift(), hold = {};
      const r = await within(scan(browser, s, hold).catch(e => ({ domain: s.domain, read: false, error: String(e.message || e).slice(0, 90), engines: {} })), 170000, null);
      if (!r) { if (hold.ctx) await hold.ctx.close().catch(() => {}); out[s.domain] = { domain: s.domain, read: false, error: 'timed out', engines: {} }; } else out[s.domain] = r;
      out[s.domain].lead = lead(out[s.domain]);
      if (++done % 10 === 0) { console.log(`${done} of ${stores.length}`); fs.writeFileSync(outPath, JSON.stringify({ scanned: new Date().toISOString().slice(0, 10), partial: true, stores: out }, null, 1)); }
    }
  };
  await Promise.all(Array.from({ length: +(conc || 6) }, worker));
  await browser.close();
  fs.writeFileSync(outPath, JSON.stringify({ scanned: new Date().toISOString().slice(0, 10), stores: out }, null, 1));
  const v = Object.values(out), n = {}; for (const x of v) n[x.lead] = (n[x.lead] || 0) + 1;
  console.log(`${v.length} stores | read ${v.filter(x => x.read).length} | walled ${v.filter(x => x.wall).length} | failed ${v.filter(x => x.error).length}`);
  console.log(Object.entries(n).map(([k, c]) => `${k}: ${c}`).join(' | '));
  process.exit(0);   // timers from the per-step time limits would otherwise hold the process open
})();
