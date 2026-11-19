#!/usr/bin/env node
// Page checks for qa.py: both editions, at phone and desktop size, in a real browser.
//
//   node qa_page.js <internal.html> <shareable.html> <result.json>
//
// Prints progress and writes {passes, fails, notes, text} to result.json. `text` is what a reader can see at each
// stop, as [edition and size, where, the text, whether the Heartbeat wording rules apply in full]; qa.py scans it.
const path = require('path');
const fs = require('fs');
const { chromium } = require('playwright');
const resultPath = process.argv[4];
const files = process.argv.slice(2, 4).map(f => path.resolve(f));
const SIZES = [['phone', 390, 844, 'dark'], ['desktop', 1440, 900, 'light']];
let passes = 0; const fails = [], notes = [], text = [];
const check = (ok, what, detail) => { if (ok) passes++; else fails.push(what + (detail !== undefined && detail !== '' ? ': ' + (typeof detail === 'string' ? detail : JSON.stringify(detail)).slice(0, 300) : '')); };

(async () => {
  const browser = await chromium.launch();
  for (const [edition, file] of [['internal', files[0]], ['shareable', files[1]]]) {
    for (const [label, w, h, scheme] of SIZES) {
      const tag = `${edition} ${label}`;
      const ctx = await browser.newContext({ viewport: { width: w, height: h }, colorScheme: scheme, deviceScaleFactor: 1 });
      const outside = [];
      await ctx.route('**/*', r => { const u = r.request().url(); if (/^(file|data|blob|about):/.test(u)) return r.continue(); outside.push(u); return r.abort(); });
      const pg = await ctx.newPage(); const errs = [];
      pg.on('pageerror', e => errs.push(String(e.message || e)));
      pg.on('console', m => { if (m.type() === 'error' && !/ERR_FAILED|net::/.test(m.text())) errs.push(m.text()); });
      await pg.goto('file://' + file); await pg.waitForTimeout(900);
      const fits = () => pg.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1);
      const grab = async (where, strict, sel) => { const t = await pg.evaluate(s => { const el = s ? document.querySelector(s) : document.body; return el ? el.innerText : ''; }, sel || null); text.push([tag, where, t, !!strict]); return t; };
      // the same door a click uses: the page listens for clicks on anything that names an account
      const open = nm => pg.evaluate(n => { const el = [...document.querySelectorAll('[data-focus]')].find(e => e.dataset.focus === n); if (el) el.click(); return !!el; }, nm);
      const data = await pg.evaluate(() => JSON.parse(document.getElementById('data').textContent));
      const HB = data.heartbeat, ranked = HB.ranked, n = ranked.length;
      const REACH = HB.reach || null, ASIDE = [...(HB.long || []), ...(HB.later || []), ...(HB.out || [])];      // with the reach test: who is ranked, and who is set aside
      const WORD = {long: 'Long odds', later: 'Not now', out: 'Out of reach'};
      check(data.internal === (edition === 'internal'), `${tag}: the file is the ${edition} edition`);

      // overview: the ranking first, in score order, with the scores the data holds
      check(await fits(), `${tag}: the overview fits the screen width`);
      const rows = await pg.evaluate(() => [...document.querySelectorAll('#hb-top tbody tr.row:not(.readrow), #hb-rest tbody tr.row:not(.readrow)')].map(r => [+r.querySelector('.hbrank').textContent, r.querySelector('strong').textContent, +r.querySelector('td.num b').textContent, r.dataset.focus]));
      const want = REACH ? ranked.slice() : ranked.slice().sort((a, b) => b.priority - a.priority || b.motion - a.motion || b.fit - a.fit);     // qa.py recomputes the order of a reach ranking
      if (REACH) check(want.every((r, i) => !i || want[i - 1].priority >= r.priority), `${tag}: the ranking never steps up in score`);
      check(JSON.stringify(rows.map(r => r[1])) === JSON.stringify(want.map(r => r.display)), `${tag}: the ranking lists every company in score order`, rows.slice(0, 3));
      check(JSON.stringify(rows.map(r => r[2])) === JSON.stringify(want.map(r => r.priority)), `${tag}: the scores on the ranking match the data`);
      check(JSON.stringify(rows.map(r => r[0])) === JSON.stringify(want.map((r, i) => i + 1)), `${tag}: ranks run 1 to ${n}`);
      check(await pg.locator('#hb-top tbody tr.row:not(.readrow)').count() === Math.min(10, n), `${tag}: the first ten lead the page`);
      const eyebrow = (await pg.locator('#hb-eyebrow').innerText()).toLowerCase();
      check(eyebrow.includes('not for partners'), `${tag}: marked Not for partners`, eyebrow);
      check((await pg.locator('#ov-h1').innerText()).includes(String(data.accounts.length)), `${tag}: the headline counts every account`);
      check(await pg.locator('#hb-top .hbbar').count() === Math.min(10, n), `${tag}: every row in the ten shows where its score comes from`);
      if (REACH) {
        const shownAside = await pg.evaluate(() => [...document.querySelectorAll('#hb-aside [data-aside]')].map(e => e.dataset.aside));
        check(JSON.stringify(shownAside) === JSON.stringify(ASIDE.map(r => r.group)), `${tag}: every company set aside is listed with its reason, in order`, [shownAside.length, ASIDE.length]);
        check((await pg.locator('#ov-h1').innerText()).includes(String(n)), `${tag}: the headline says how many companies can move`);
      }
      const outsideRows = await pg.locator('#hb-outside tbody tr').count();
      check(outsideRows === HB.outside.length, `${tag}: every company outside the ICP is listed`, [outsideRows, HB.outside.length]);
      await pg.evaluate(() => document.querySelectorAll('#v-overview details').forEach(d => { d.open = true; }));
      await pg.waitForTimeout(150);
      check(await fits(), `${tag}: the overview with every fold open fits the screen width`);
      await grab('the Heartbeat ranking', true, '#hb-sec');
      await grab('the overview', false);

      // the insight layer and the subscription view, where the page has them
      const INS = HB.insights, SUBS = HB.subscriptions;
      if (INS && (INS.findings || []).length) {
        check(await pg.locator('#ins-findings .finding').count() === INS.findings.length, `${tag}: every finding is shown`, [await pg.locator('#ins-findings .finding').count(), INS.findings.length]);
        await grab('what the ranking says', true, '#ins-sec');
      }
      if (SUBS && (SUBS.rows || []).length) {
        const shown = await pg.evaluate(() => [...document.querySelectorAll('#subs-list [data-sub]')].map(e => e.dataset.sub));
        const expect = SUBS.rows.filter(r => r.section !== 'context').map(r => r.group);
        check(JSON.stringify(shown) === JSON.stringify(expect), `${tag}: the subscription view lists every program company, in order`, [shown.length, expect.length]);
        await grab('the subscription view', true, '#subs-sec');
      }

      // the first row by a real click; every other ranked company through the same door the click uses
      await pg.evaluate(() => { location.hash = '#overview'; }); await pg.waitForTimeout(120);
      await pg.locator('#hb-top tbody tr.row').first().click(); await pg.waitForTimeout(350);
      check((await pg.evaluate(() => location.hash)) === '#accounts', `${tag}: clicking a ranked row opens the account view`);
      for (const r of want) {
        await open(r.lead); await pg.waitForTimeout(90);
        const got = await pg.evaluate(() => { const row = document.querySelector('#tbody tr.row[aria-expanded="true"]'); const det = row && row.nextElementSibling; const hb = det && det.querySelector('.hbrec'); return row ? { name: row.dataset.n, all: det ? det.innerText : '', hb: hb ? hb.innerText : '', wide: det ? det.scrollWidth > det.clientWidth + 1 : false } : null; });
        check(got && got.name === r.lead, `${tag}: ${r.display} opens its record`, got && got.name);
        if (!got) continue;
        const t = (got.hb || got.all).toLowerCase(), has = x => t.includes(x.toLowerCase());     // headings are set in capitals by their style
        check(has(REACH ? `Score · ${r.priority} · rank ${r.rank} of ${n}` : `Heartbeat score · ${r.priority} · rank ${r.rank} of ${n}`), `${tag}: ${r.display} shows its score and rank`);
        check(has(REACH ? `Way in · ${r.motion}` : `Why a partner moves · ${r.motion}`) && has(`Anatta fit · ${r.fit}`) && has(REACH ? `Opening · ${r.timing}` : `Timing · ${r.timing}`) && has(`Potential · ${r.potential}`), `${tag}: ${r.display} shows four measures`);
        if (REACH) check(has(`The Heartbeat score alone gave ${r.hb.priority}, rank ${r.hb.rank} of ${REACH.scored}`), `${tag}: ${r.display} keeps the score the Heartbeat alone gave it`);
        if (REACH) check((r.signals || []).every(s => has(s.text)), `${tag}: ${r.display} lists the dated signals its opening rests on`);
        check(has('Shop Pay:'), `${tag}: ${r.display} has the Shop Pay wedge`);
        check(has('Subscription · +10') === !!r.bonus, `${tag}: ${r.display} subscription bonus line`);
        check(!got.wide && await fits(), `${tag}: ${r.display} record fits the screen width`);
        if (got.hb) text.push([tag, `${r.display} / Heartbeat record`, got.hb, true]);
        if (r.rank <= 12) text.push([tag, `${r.display} / full record`, got.all, false]);
      }
      for (const r of ASIDE) {       // set aside: the record says so, gives the reason and keeps the earlier score
        await open(r.lead); await pg.waitForTimeout(90);
        const got = await pg.evaluate(() => { const row = document.querySelector('#tbody tr.row[aria-expanded="true"]'); const det = row && row.nextElementSibling; const hb = det && det.querySelector('.hbrec'); return row ? { name: row.dataset.n, hb: hb ? hb.innerText : '', wide: det ? det.scrollWidth > det.clientWidth + 1 : false } : null; });
        check(got && got.name === r.lead, `${tag}: ${r.display} opens its record`, got && got.name);
        if (!got) continue;
        const t = got.hb.toLowerCase(), has = x => t.includes(x.toLowerCase()), st = r.reach.state;
        check(has(st === 'long' ? 'Listed apart · Long odds' : `Not ranked · ${WORD[st]}`) && has(r.reach.why), `${tag}: ${r.display} is shown as ${WORD[st].toLowerCase()}, with the reason`);
        check(has(`The Heartbeat score alone gave ${r.hb.priority}, rank ${r.hb.rank} of ${REACH.scored}`), `${tag}: ${r.display} keeps the score the Heartbeat alone gave it`);
        check(st === 'long' ? has(`Score · ${r.priority}`) : !has('Score · ') || has('The Heartbeat score alone'), `${tag}: ${r.display} shows a score only where one was computed`);
        check(!got.wide && await fits(), `${tag}: ${r.display} record fits the screen width`);
        text.push([tag, `${r.display} / record of a company set aside`, got.hb, true]);
      }
      for (const r of HB.outside) {
        await open(r.lead); await pg.waitForTimeout(80);
        const t = await pg.evaluate(() => { const row = document.querySelector('#tbody tr.row[aria-expanded="true"]'); return row && row.nextElementSibling ? row.nextElementSibling.innerText : ''; });
        check(t.includes("Outside Anatta's ICP"), `${tag}: ${r.display} is shown as outside the ICP`);
      }
      // the other views
      const views = await pg.evaluate(() => [...document.querySelectorAll('.tab')].filter(t => !t.hidden && getComputedStyle(t).display !== 'none').map(t => t.dataset.view));
      for (const v of views) {
        await pg.evaluate(x => { location.hash = '#' + x; }, v); await pg.waitForTimeout(450);
        check(await fits(), `${tag}: the ${v} view fits the screen width`);
        await grab(`the ${v} view`, false, '#v-' + v);
      }
      await grab('navigation', true, '.tabs, nav, header');
      // links open safely, and nothing is a mail link
      const links = await pg.evaluate(() => [...document.querySelectorAll('a[href]')].map(a => [a.getAttribute('href'), a.target, a.rel]));
      const bad = links.filter(([u, t, r]) => !(u.startsWith('#') || (/^https?:\/\//.test(u) && t === '_blank' && /noopener/.test(r))));
      check(!bad.length, `${tag}: every link is an https link opened safely`, bad.slice(0, 3));
      check(!outside.length, `${tag}: the file never reaches outside itself`, outside.slice(0, 3));
      check(!errs.length, `${tag}: no script errors`, errs.slice(0, 2));
      await ctx.close();
      console.log(`${tag}: done (${passes} passed, ${fails.length} failed so far)`);
    }
  }
  await browser.close();
  fs.writeFileSync(resultPath, JSON.stringify({ passes, fails, notes, text }));
  process.exit(0);
})().catch(e => { fs.writeFileSync(resultPath, JSON.stringify({ passes, fails: fails.concat(['page checks crashed: ' + String(e.message || e).slice(0, 300)]), notes, text })); process.exit(0); });
