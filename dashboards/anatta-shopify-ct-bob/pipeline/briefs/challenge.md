# Challenge the first ten

You are checking someone else's work. A ranking of companies has been built for a Shopify agency and for Shopify. Each of the
companies in your file sits in the first ten. Your job is to try to prove each one does not belong there. You are not asked to
agree. A challenge that finds nothing is a valid result, and so is one that overturns a company.

Today is 2026-11-19. Your input file gives, per company: its stores, the claim that its store can move (`claim_reach`), and the
dated signals its place rests on (`claim_opening.signals`, each with a source).

## What to test, per company

1. **Each dated signal, at its source.** Open the source. Is the event real, is the date right, does the text say what the signal
   says? Is a job posting still open? Has something newer replaced it (a hire announced, a review concluded, a deal called off)?
   If the source will not open, find a second source. Mark the signal `confirmed`, `changed` (say how) or `not found`.
2. **Can the store move?** Look for first-hand evidence that it cannot, or will not soon:
   - a replatform, rebuild or relaunch that finished in the last 24 months, or one under way on another vendor's platform;
   - the company hiring engineers for the platform it has (a posting that names the current platform as the stack to build on);
   - an in-house platform team that builds the store itself;
   - a vendor deal announced or renewed (commerce platform, point of sale, order management) in 2025 or 2026;
   - a sale, merger or bankruptcy that freezes decisions.
3. **Anything first-hand that strengthens the case** and is not in the file: note it too, with its source.

## How to look

- Read a store or a page the way a browser does:
  `node pipeline/read_page.js <url> --find "regex"`
  It prints the status, the title and the text or the passages that match. A block page means "not read", never "absent".
- Use web search for filings, releases, earnings calls and job postings. Prefer the company's own pages, SEC filings, the job
  board that carries the posting, and trade press that quotes the company. A vendor's or an integrator's article is third-party:
  say so, and look for the primary source behind it.
- Spend your effort where a finding would change the verdict. About 6 to 10 look-ups per company is enough.
- Do not contact anyone, fill in forms or log in anywhere. Read only.

## What to return

Write one JSON file to the output path you were given, and nothing else there:

```json
{"batch": "A", "companies": [
  {"group": "<group, exactly as in the input>",
   "verdict": "holds | weaker | wrong",
   "summary": "<one or two plain sentences: what you found and what it does to the company's place>",
   "signals": [{"date": "<as in the input>", "status": "confirmed | changed | not found", "note": "<what the source says, with the date you read it>", "source": "<the link you read>"}],
   "against": [{"date": "YYYY-MM", "kind": "rebuilding | staffing | renewal | freeze | other", "text": "<a first-hand fact that argues against a move or an open decision>", "source": "https://..."}],
   "for": [{"date": "YYYY-MM", "text": "<a first-hand fact that strengthens the case, not already in the file>", "source": "https://..."}],
   "not_checked": ["<anything you could not read, and why>"]}
]}
```

- `holds`: every signal is confirmed and nothing first-hand argues against a move.
- `weaker`: a signal has changed or could not be found, or there is first-hand evidence against, but the place could still stand.
- `wrong`: the store cannot move, or the decision the place rests on is not open.
- `signals` has one entry for each signal in the input, in the same order.
- Every `against` and `for` entry needs a link you opened yourself and a date.
- Give each `against` entry its `kind`. `rebuilding`: a rebuild or a replatform is in flight, seen on the store itself or
  said by the company. `staffing`: the company is hiring, or has just hired, people to build on the platform it has.
  `renewal`: a vendor deal announced or renewed. `freeze`: a sale, a merger, a court case or another programme that holds
  decisions up. `other`: anything else. Class by what the source shows, not by what it suggests: a posting for developers
  on the current platform is `staffing`, and it is `rebuilding` only when the rebuild itself is in evidence.
- Plain words. One fact per sentence. Mark anything you could not verify as not verified. Do not name any firm that builds or
  runs stores for the company. No em dashes.

When the file is written, run: `python3 -I <validator path> <input file> <output file>` and fix anything it reports. Your final
message should be three or four lines: the verdict for each company, and anything you could not check.
