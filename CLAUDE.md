# Working in this repository

This repository holds the pipeline that ranks account lists for Anatta and a partner. Account data, list
configuration and generated pages never go in it.

## Before any ranking is shown

A ranking once put a national retailer first while its own research note said "do not pitch". Every step had done its
job and no step owned the question: the research wrote the conclusion in prose, the brief for the next pass said
another step would handle it, the score never read it, and QA checked the arithmetic. The full account is in
`dashboards/anatta-shopify-ct-bob/README.md`, under "A list nobody pre-qualified: reach first".

Seven rules came out of it. They apply to every list and every score, not only that one.

1. **A conclusion lives in a field the ranking reads.** Prose may explain it. Prose may not be the only place it lives.
2. **A brief never says another step handles a judgment** unless that step exists and its output is checked.
3. **One fact, one key.** The same evidence is not scored up in one pass and down in another.
4. **A score is used inside the range it was built on.** Compare the list with the list the score was built on before
   trusting the score on it.
5. **A signal is the company's own dated word**, or it is marked third-party. An intent reading is counted once. A third
   party's claim about a date is re-read against the newest source before it is used.
6. **A contradiction between the research and the rank stops the release.** It is never a footnote. Tell the person
   whose list it is, with the evidence.
7. **The first ten are challenged by a reader who did not build them**, before anyone else sees them.

## In practice

- Research briefs include `pipeline/briefs/reach_and_signals.md`.
- `reach_infer.py`, then `reach_rank.py`, come before `assemble.py`. A difference between the research and the rules is
  settled in the overrides file with a reason, not by picking one silently.
- The first ten go to independent readers with `pipeline/briefs/challenge.md`; `validate_challenge.py` checks what
  comes back.
- `qa.py` must pass with `--reference` and `--challenge`. A failure is fixed. It is not explained in a note on the page.
- After changing `reach_infer.py` or `reach_rank.py`, run `python3 dashboards/anatta-shopify-ct-bob/pipeline/selftest_reach.py`.
- Running someone's model "unchanged" does not mean accepting a result the evidence contradicts. Say so, show the
  evidence, and offer the fix.
