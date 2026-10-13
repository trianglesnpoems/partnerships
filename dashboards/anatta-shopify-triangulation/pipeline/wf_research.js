export const meta = {
  name: 'shopify-triangulation-research-lean',
  description: 'Research a group of account batches on Shopify-fit and Anatta-fit with sourced evidence; adversarially verify provisional T1 (two lenses), T2 (one lens) and gated-but-engaged accounts (one lens)',
  phases: [
    { title: 'Research', detail: 'batches of ~12 accounts, both legs scored with sourced evidence' },
    { title: 'Verify', detail: 'adversarial lenses on provisional T1/T2 and gated accounts with 10+ contacts' },
  ],
}

const { batches, accounts, rubric, out_dir, group } = args
const metaByName = Object.fromEntries(accounts.map(a => [a.name, a]))

const MODELS = ['DTC brand', 'Omni retailer', 'Grocery', 'B2B / wholesale', 'Restaurant / hospitality', 'Franchise services', 'Services', 'Education', 'Government', 'Media / publishing', 'Direct selling', 'Other']
const GATES = ['', 'already_plus', 'gov', 'distress', 'non_merchant', 'bad_record', 'restricted']
const I = (max) => ({ type: 'integer', minimum: 0, maximum: max })
const EV = { type: 'array', items: { type: 'object', properties: { claim: { type: 'string' }, source: { type: 'string' } }, required: ['claim', 'source'] } }
const ACCOUNT = {
  type: 'object',
  properties: {
    name: { type: 'string' }, domain: { type: 'string' }, category: { type: 'string' }, model: { type: 'string', enum: MODELS },
    size_est: { type: 'string' }, platform_confirmed: { type: 'string' }, hq: { type: 'string' }, ownership: { type: 'string' },
    shopify: { type: 'object', properties: { whitespace: I(25), scale: I(20), model_fit: I(20), unified: I(15), timing: I(10), ecosystem: I(10), penalties: { type: 'integer', minimum: -100, maximum: 0 }, penalty_reason: { type: 'string' } }, required: ['whitespace', 'scale', 'model_fit', 'unified', 'timing', 'ecosystem', 'penalties', 'penalty_reason'] },
    anatta: { type: 'object', properties: { brand_surface: I(20), modernization: I(20), scale: I(20), ltv: I(20) }, required: ['brand_surface', 'modernization', 'scale', 'ltv'] },
    gate: { type: 'string', enum: GATES }, gate_reason: { type: 'string' },
    story: { type: 'string' }, shopify_angle: { type: 'string' }, anatta_angle: { type: 'string' },
    evidence: EV, flags: { type: 'array', items: { type: 'string' } }, confidence: { type: 'string', enum: ['high', 'med', 'low'] },
  },
  required: ['name', 'domain', 'category', 'model', 'size_est', 'platform_confirmed', 'hq', 'ownership', 'shopify', 'anatta', 'gate', 'gate_reason', 'story', 'shopify_angle', 'anatta_angle', 'evidence', 'flags', 'confidence'],
}
const RESEARCH = { type: 'object', properties: { accounts: { type: 'array', items: ACCOUNT } }, required: ['accounts'] }
const VERDICT = {
  type: 'object',
  properties: {
    name: { type: 'string' }, verdict: { type: 'string', enum: ['confirmed', 'adjust', 'refute'] },
    shopify_fit_suggested: { type: ['integer', 'null'], minimum: 0, maximum: 100 }, anatta_fit_suggested: { type: ['integer', 'null'], minimum: 0, maximum: 100 },
    gate_suggested: { type: 'string', enum: ['keep', ...GATES] }, reason: { type: 'string' }, evidence: EV,
  },
  required: ['name', 'verdict', 'shopify_fit_suggested', 'anatta_fit_suggested', 'gate_suggested', 'reason', 'evidence'],
}

const TOOLING = `Tooling notes: WebFetch does NOT work in this environment (DNS is blocked) — do not call it. Use WebSearch: "standard" mode first, "extended" only when you need a specific fact (store counts, revenue, platform, ownership, distress). Budget: 2–4 searches per account; an obvious non-fit (no store, no scale, wrong business) deserves ONE search and a low score — do not go down rabbit holes on obscure companies. Read the rubric and your batch file with the Read tool. Your final text is not read by a human — return data only through the StructuredOutput tool.`

const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v))
function fireIntent(f) { let p = ({ High: 10, Medium: 7, Low: 3 })[f.intent] ?? 2; if (f.in_market) p += 5; const s = f.score === '' ? null : +f.score; if (s !== null) p += s >= 50 ? 5 : s >= 35 ? 3 : s > 0 ? 1 : 0; if (f.signals) p += 3; return Math.min(20, p) }
function bonus(f) { let b = 0; if (f.in_market) b += 3; if (f.intent === 'High') b += 3; if (/shopify/i.test(f.signals || '')) b += 4; return b }
function score(rec) {
  const m = metaByName[rec.name] || { fire: { intent: '', score: '', in_market: false, signals: '' }, contacts: 0 }
  const s = rec.shopify, a = rec.anatta
  const sf = clamp(s.whitespace + s.scale + s.model_fit + s.unified + s.timing + s.ecosystem + s.penalties, 0, 100)
  const af = clamp(a.brand_surface + a.modernization + a.scale + a.ltv + fireIntent(m.fire), 0, 100)
  const tri = Math.min(100, Math.round(0.55 * sf + 0.45 * af + bonus(m.fire)))
  const tier = rec.gate === 'already_plus' ? 'EXP' : rec.gate ? 'X' : (tri >= 62 && sf >= 63) ? 'T1' : tri >= 48 ? 'T2' : tri >= 36 ? 'T3' : 'T4'
  return { sf, af, tri, tier, contacts: m.contacts }
}

function researchPrompt(b) {
  return `You are scoring a batch of accounts for an Anatta × Shopify partner triangulation.
1. Read the rubric: ${rubric}
2. Read your batch (${b.names.length} accounts, JSON array with the Apollo/FIRE fields, the BuiltWith stack row and contact stats): ${b.file}
3. For EVERY account in the batch, research it on the web and score BOTH legs exactly per the rubric. Confirm what the storefront really runs on (the brand's own shop pages, "<brand> shopify", press about replatforms). Find scale (revenue, stores, headcount), business model, ownership/parent, distress, and timing signals. 3–5 evidence items with URLs per account that could matter; 1–2 for obvious non-fits. Write the story / shopify_angle / anatta_angle as a pitch, not a description.
4. Return {accounts:[...]} through StructuredOutput with one entry per account — all ${b.names.length} names, spelled exactly as in the batch file: ${JSON.stringify(b.names)}.
5. ALSO write the identical object as JSON to ${out_dir}/results/${b.id}.json with the Write tool before you finish.
${TOOLING}`
}

const SUBSCORE_HINT = 'The caller recomputes: shopify_fit = sum of the six Shopify subscores + penalties (clamped 0–100); anatta_fit = sum of the four Anatta subscores + a 20-point intent subscore from FIRE fields; triangle = 0.55×shopify + 0.45×anatta (+ small intent bonuses). T1 needs triangle ≥ 62 AND shopify_fit ≥ 63; T2 ≥ 48; T3 ≥ 36.'

function verifyPrompt(rec, sc, lens, i) {
  const lensText = lens === 'platform'
    ? `LENS: platform & scale skeptic. Try to REFUTE the researcher's platform_confirmed, whitespace and scale subscores. Check what the storefront actually runs on today (a separate shop subdomain? a headless build? already Shopify or Shopify Plus?), whether the BuiltWith row is stale, and whether revenue / traffic / store counts support the scale given. If the account is gated "already_plus", confirm Shopify Plus is really live and current.`
    : `LENS: business-model & gate skeptic. Try to REFUTE the business-model fit, unified-commerce surface, timing claims and the gate decision. Look for ownership changes, insolvency, government status, franchise structures, a parent that controls procurement, a product business hiding behind a services brand (or vice versa), or evidence the researcher missed (an online store that does exist, a wholesale catalogue, physical stores).`
  return `Adversarially verify one scored account for an Anatta × Shopify partner triangulation. Read the rubric first: ${rubric}
${lensText}
Default to verdict "confirmed" only when your own search supports the record. Use "adjust" when the evidence moves either fit score by 8+ points (give the full suggested 0–100 fit values, not subscores), and "refute" when the record is materially wrong (wrong platform, wrong business, should be gated / should not be gated — then set gate_suggested; otherwise "keep"). 2–4 evidence items with URLs. Budget: at most 4 searches. ${SUBSCORE_HINT}

RECORD (provisional: shopify_fit ${sc.sf}, anatta_fit ${sc.af}, triangle ${sc.tri}, tier ${sc.tier}, contacts in book ${sc.contacts}):
${JSON.stringify(rec)}

Return through StructuredOutput, and ALSO write the identical object to ${out_dir}/verify/${i}.json with the Write tool. ${TOOLING}`
}

function needsVerify(rec, sc) {
  if (sc.tier === 'T1') return ['platform', 'model']
  if (sc.tier === 'T2') return ['platform']
  if (rec.gate && sc.contacts >= 10) return [rec.gate === 'already_plus' ? 'platform' : 'model']
  return []
}

const results = await pipeline(
  batches,
  b => agent(researchPrompt(b), { label: `research:${b.id}`, phase: 'Research', schema: RESEARCH }),
  async (res, b) => {
    if (!res) { log(`${b.id}: research agent returned nothing`); return { batch: b.id, records: [], verdicts: [], missing: b.names } }
    const records = res.accounts.filter(Boolean)
    const missing = b.names.filter(n => !records.some(r => r.name === n))
    if (missing.length) log(`${b.id}: missing ${missing.length} accounts: ${missing.join(', ')}`)
    const jobs = []
    records.forEach((rec, k) => {
      const sc = score(rec)
      for (const lens of needsVerify(rec, sc)) jobs.push({ rec, sc, lens, id: `${b.id}__${String(k).padStart(2, '0')}__${lens}` })
    })
    log(`${b.id}: ${records.length} records → ${jobs.length} verification jobs`)
    const verdicts = (await parallel(jobs.map(j => () => agent(verifyPrompt(j.rec, j.sc, j.lens, j.id), { label: `verify:${j.rec.name.slice(0, 28)}:${j.lens}`, phase: 'Verify', schema: VERDICT }).then(v => v && ({ ...v, lens: j.lens, provisional: j.sc, file: j.id }))))).filter(Boolean)
    return { batch: b.id, records, verdicts, missing }
  }
)

const all = results.filter(Boolean)
const records = all.flatMap(r => r.records)
const tierCount = {}
records.forEach(r => { const t = score(r).tier; tierCount[t] = (tierCount[t] || 0) + 1 })
return {
  group,
  batches: all.map(r => r.batch),
  records: records.length,
  missing: all.flatMap(r => r.missing || []),
  provisional_tiers: tierCount,
  top: records.map(r => ({ name: r.name, ...score(r) })).filter(x => x.tier === 'T1' || x.tier === 'T2').sort((a, b) => b.tri - a.tri),
  verdicts: all.flatMap(r => r.verdicts).map(v => ({ name: v.name, lens: v.lens, verdict: v.verdict, sf: v.shopify_fit_suggested, af: v.anatta_fit_suggested, gate: v.gate_suggested, reason: v.reason.slice(0, 240) })),
}
