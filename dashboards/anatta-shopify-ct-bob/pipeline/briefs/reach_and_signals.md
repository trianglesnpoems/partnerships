# Reach and signals: two things every research record settles

Add this to the brief of the research pass that writes a company's dated events. The ranking reads these fields
directly. A conclusion that lives only in a sentence of prose never reaches the score: that is how a company once
ranked first while its own record said not to pitch it.

Do not tell a researcher that "another step handles" a judgment unless that step exists and its output is checked.

## 1. `reach`: can this company's store move in the next 18 months?

```json
"reach": {"state": "open | later | out", "kind": "...", "why": "<one sentence: the fact, with its date>",
          "source": "https://...", "decided": "YYYY-MM"}
```

| `state` | When | `kind` |
|---|---|---|
| `out` | It builds and runs its own commerce platform with an in-house engineering team, at national scale | `builds its own platform` |
| `out` | It does not run its own store: an outside operator, a licensee or a marketplace does | `no store of its own` |
| `later` | It finished a replatform or a rebuild, or chose a platform, inside the last 24 months, or one is under way on another vendor's platform. Give the month in `decided` | `just decided` |
| `open` | None of the above | |

- Answer only whether the store can move. Do not weigh size, fit or how attractive the account is.
- Do not use `out` because a company is large. Size is checked by rule against the list the score was built on.
- If you cannot tell, say `open` and put the doubt in `why`.
- The same fact is never keyed two ways. An in-house platform at national scale is `out` here, whatever a fit table
  says about custom builds.

## 2. `events`: each one dated, classed and marked first-hand or not

```json
{"date": "YYYY-MM", "text": "<one fact, with its day where known>", "source": "https://...", "kind": "...",
 "signal": "decision | mandate | tech-lead | leader | growth | frozen | rebuilding | staffing | none", "first_hand": true, "read": "YYYY-MM-DD"}
```

| `signal` | What it is |
|---|---|
| `decision` | The company or its owner has said a platform or IT decision is open: a review, a search, a tender, a posting whose stated job is to choose the platform |
| `mandate` | A new owner, or a new chief executive or chair |
| `tech-lead` | The technology or e-commerce chief's seat is open, newly filled or about to change |
| `leader` | Another senior change |
| `growth` | New stores, markets or lines on the platform it has |
| `frozen` | The store runs software its vendor has stopped building on, read on the store itself |
| `rebuilding` | Evidence against: a rebuild or a replatform is in flight, seen on the store itself or said by the company. The company is set aside as "not now" |
| `staffing` | Evidence against: it is hiring, or has just hired, people to build on the platform it has. When this is as recent as the signal the opening rests on, the research share of the opening is halved |
| `none` | Dated and true, and not a reason to re-open a platform choice. A move that has finished belongs in `reach`, not here |

- A posting counts for the seat it fills, not for the duties it lists. A Chief Technology Officer posting is
  `tech-lead`. It is `decision` only when the posting itself says a platform is being chosen.
- `first_hand` is true when the source is the company's own word or record: a filing, an earnings call, a release, its
  own posting, a page of its own site that you read. It is false for a vendor's, an integrator's or an analyst's account.
- A third-party claim about a date (a product's end of life, a contract's end) needs the primary source, or two
  independent sources written after the claim. Without them, class it `none` and say what is missing. Vendors change
  their plans: check the newest source, not the first one found.
- A reading from an intent tool is not an event. It is counted separately, once.

## 3. Look for what argues the other way, every time

A score that only counts evidence for a move ranks hope. Before a record is done, open the company's own job board (or a
dated copy of it) and the store's page source, and record what argues against as events with the two classes above:

- `staffing`: a posting for engineers, architects or managers to build on or run the platform it has. Give the date it
  was posted and whether it is still open.
- `rebuilding`: a new front end being rolled out, a migration in progress, a company statement that a rebuild has begun.
  Class by what the source shows: a posting for developers is `staffing`, and it is `rebuilding` only when the rebuild
  itself is in evidence.

Anything else that argues against (a vendor deal renewed, a sale or a court case that freezes decisions, another
programme that everything waits for) goes in `"against": [{"date", "text", "source"}]`. It is shown on the record.
When this was first checked on a ranking's first ten, 8 of the 10 had such evidence and none of it had been recorded.

## What happens to these fields

`reach_infer.py` derives the same calls by rule from the rest of the record and compares. Where the research and the
rules disagree, a person settles it in the overrides file, with a reason. `reach_rank.py` ranks the companies that can
move. `qa.py` stops a release in which a ranked company's own record argues that it cannot move.
