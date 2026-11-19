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
 "signal": "decision | mandate | tech-lead | leader | growth | frozen | none", "first_hand": true, "read": "YYYY-MM-DD"}
```

| `signal` | What it is |
|---|---|
| `decision` | The company or its owner has said a platform or IT decision is open: a review, a search, a tender, a posting whose stated job is to choose the platform |
| `mandate` | A new owner, or a new chief executive or chair |
| `tech-lead` | The technology or e-commerce chief's seat is open, newly filled or about to change |
| `leader` | Another senior change |
| `growth` | New stores, markets or lines on the platform it has |
| `frozen` | The store runs software its vendor has stopped building on, read on the store itself |
| `none` | Dated and true, and not a reason to re-open a platform choice. A move that has finished belongs in `reach`, not here |

- A posting counts for the seat it fills, not for the duties it lists. A Chief Technology Officer posting is
  `tech-lead`. It is `decision` only when the posting itself says a platform is being chosen.
- `first_hand` is true when the source is the company's own word or record: a filing, an earnings call, a release, its
  own posting, a page of its own site that you read. It is false for a vendor's, an integrator's or an analyst's account.
- A third-party claim about a date (a product's end of life, a contract's end) needs the primary source, or two
  independent sources written after the claim. Without them, class it `none` and say what is missing. Vendors change
  their plans: check the newest source, not the first one found.
- A reading from an intent tool is not an event. It is counted separately, once.

## 3. `against`: what argues the other way

```json
"against": [{"date": "YYYY-MM", "text": "...", "source": "https://..."}]
```

First-hand facts that argue against a move or an open decision: hiring engineers for the platform it has, a vendor deal
renewed, a rebuild in progress, a sale that freezes decisions. The challenge of the first ten will look for these. It
costs less to record them now.

## What happens to these fields

`reach_infer.py` derives the same calls by rule from the rest of the record and compares. Where the research and the
rules disagree, a person settles it in the overrides file, with a reason. `reach_rank.py` ranks the companies that can
move. `qa.py` stops a release in which a ranked company's own record argues that it cannot move.
