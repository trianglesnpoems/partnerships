#!/usr/bin/env node
// Read one page the way a shopper's browser does, for research. A plain fetch misses what scripts draw and is refused
// by many stores; this loads the page in Chromium, waits, and prints what a reader would see.
//
//   node read_page.js <url> [--find "regex"] [--links "regex"] [--max 6000] [--click "text"]
//
//   --find   print only the passages around each match (300 characters either side), up to 12
//   --links  also list links whose text or address matches
//   --max    how much page text to print when --find is not given (default 6000 characters)
//   --click  click the first button or link with this text before reading (a tab, an accordion, "Subscribe")
//
// It prints the status, the final address, the title, any subscription engine the page called, then the text.
// A bot wall is reported as a wall. It is never evidence that something is absent.
const { chromium } = require('playwright');
const args = process.argv.slice(2); const url = args[0];
const opt = k => { const i = args.indexOf(k); return i > 0 ? args[i + 1] : null; };
if (!url) { console.error('usage: node read_page.js <url> [--find "regex"] [--links "regex"] [--max 6000] [--click "text"]'); process.exit(2); }
const ENGINES = { 'Recharge': /rechargepayments|rechargeapps|rechargecdn/i, 'Skio': /skio\.com/i, 'Stay.ai': /stay\.ai|retextion/i, 'Ordergroove': /ordergroove/i, 'Recurly': /recurly/i, 'Smartrr': /smartrr/i,
  'Bold Subscriptions': /sub\.boldapps\.net|ro\.boldapps\.net|bold[-_]?subscriptions/i, 'Loop Subscriptions': /loopwork\.co/i, 'Appstle': /appstle/i, 'Seal Subscriptions': /sealsubscriptions/i, 'Chargebee': /chargebee/i, 'Zuora': /zuora/i,
  'Subscribe Pro': /subscribepro/i, 'ebbo (Clarus)': /claruscommerce|ebbo\.com/i, 'Commerce7': /commerce7/i, 'WineDirect': /winedirect|vin65/i, 'Yotpo': /yotpo/i, 'Klaviyo': /klaviyo/i, 'Attentive': /attn\.tv|attentive/i };
const WALL = /access denied|pardon our interruption|are you a robot|verify you are human|captcha|attention required|request blocked|unusual traffic|just a moment|security check/i;
(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ userAgent: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36', viewport: { width: 1280, height: 1000 }, locale: 'en-US' });
  const p = await ctx.newPage(); const seen = new Set();
  p.on('request', q => { for (const [k, re] of Object.entries(ENGINES)) if (re.test(q.url())) seen.add(k); });
  try {
    const res = await p.goto(/^https?:/.test(url) ? url : 'https://' + url, { waitUntil: 'domcontentloaded', timeout: 40000 });
    await p.waitForTimeout(5000); await p.mouse.wheel(0, 6000).catch(() => {}); await p.waitForTimeout(1500);
    const click = opt('--click');
    if (click) { try { await p.getByText(click, { exact: false }).first().click({ timeout: 4000 }); await p.waitForTimeout(2500); } catch (e) { console.log('(could not click "' + click + '")'); } }
    const title = await p.title().catch(() => ''); const text = (await p.evaluate(() => document.body ? document.body.innerText : '').catch(() => '')).replace(/[ \t]+/g, ' ').replace(/\n{3,}/g, '\n\n');
    const status = res ? res.status() : 0;
    console.log(`status: ${status}\nfinal: ${p.url()}\ntitle: ${title}\nengines called: ${[...seen].join(', ') || 'none seen'}\ntext length: ${text.length}`);
    if (status >= 400 || WALL.test(title) || (text.length < 500 && WALL.test(text))) console.log('WALL: this looks like a block page. Treat the page as not read.');
    const find = opt('--find');
    if (find) {
      const re = new RegExp(find, 'gi'); let m, n = 0; console.log(`\n--- passages matching /${find}/`);
      while ((m = re.exec(text)) && n < 12) { console.log(`[${++n}] …${text.slice(Math.max(0, m.index - 300), m.index + m[0].length + 300).replace(/\s+/g, ' ')}…`); re.lastIndex = m.index + m[0].length + 300; }
      if (!n) console.log('(no match in the page text)');
    } else console.log('\n--- text\n' + text.slice(0, +(opt('--max') || 6000)));
    const lk = opt('--links');
    if (lk) {
      const re = new RegExp(lk, 'i'); const links = await p.evaluate(() => [...document.querySelectorAll('a[href]')].map(a => [(a.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 80), a.href]));
      const hit = links.filter(([t, h]) => re.test(t) || re.test(h)); console.log(`\n--- links matching /${lk}/ (${hit.length})`); for (const [t, h] of hit.slice(0, 30)) console.log(`${t} -> ${h}`);
    }
  } catch (e) { console.log('ERROR: ' + String(e.message || e).slice(0, 200) + '\nTreat the page as not read.'); }
  await browser.close(); process.exit(0);
})();
