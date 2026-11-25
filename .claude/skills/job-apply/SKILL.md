---
name: job-apply
description: Run a job application end to end - review the job, review the resume against it, tailor the resume, build a proof-of-work deck, prepare the application, and log it in the tracker spreadsheet. Use when the user shares a job posting or URL and wants to apply, asks to tailor their resume to a job, asks for a proof-of-work deck, or asks about the status of their applications.
---

# Job application

Six steps, one folder per application. The script `tools/job-application/jobapp.py`
does the mechanical work (fetching, rendering, tracking); you do the judgement.
Run it as `python3 tools/job-application/jobapp.py <command>`; `--help` lists commands.

Files live in `tools/job-application/workspace/` (or `$JOBAPP_HOME`):

```
resume.json                      master resume - the only source of facts
tracker.xlsx                     one row per application
applications/<company>-<role>/
  job.json, job.md               the posting
  job-review.md                  step 1
  resume-review.md               step 2
  resume.tailored.json           step 3, rendered to .docx and .pdf
  deck.json                      step 4, rendered to .pptx
  application.md                 step 5: answers, cover note, where to submit
```

The workspace is gitignored because this repository is public. Never commit it,
and never paste resume contents into anything that leaves the session without
the user asking.

## Before you start

Run `jobapp.py init` if the workspace does not exist. If `resume.json` is still
the Alex Rivera example, stop and ask the user for their real resume (file,
pasted text, or a link they can export). Transcribe it into the JSON shape in
`templates/resume.example.json` faithfully: every role, date and figure as
written, nothing improved. Ask about anything illegible instead of guessing.
The master resume should be long - keep every bullet; tailoring cuts later.

## 1. Review the job

`jobapp.py fetch <url>` reads Greenhouse, Lever and Ashby postings through their
public APIs and other pages through their HTML. If the fetch fails or the text
is thin (login wall, JavaScript page, blocked host), ask the user to paste the
posting and use `fetch --file posting.txt --url <url> --company .. --title ..`.

Write `job-review.md`:

- **The job in one sentence** - what this person is hired to make happen.
- **Must-haves** - the 4 to 6 requirements that would screen someone out, in the
  posting's own words. Separate these from nice-to-haves.
- **What they will weigh most** - infer from repetition, order and the title.
- **Unknowns and flags** - pay, level, location or visa limits, vague scope,
  anything worth asking a recruiter. Say "not stated" rather than guessing.
- **Fit score, 0 to 100, with the reasoning** - how many must-haves the master
  resume clearly evidences. Below roughly 50, tell the user plainly that this is
  a long shot and ask whether to continue before doing the remaining steps.

Record it: `jobapp.py track set <app> --fit <score>`.

## 2. Review the resume against the job

Run `jobapp.py match <app> --master` for a word-level coverage list. It is a
crude prompt, not a score to optimise: a "missing" term matters only if the user
actually has that experience and the resume fails to say so.

Write `resume-review.md`:

- For each must-have: the strongest evidence in the master resume (quote the
  bullet), or "no evidence".
- Gaps: must-haves with no evidence. For each, ask the user whether they have
  experience the resume omits. If they do, add it to `resume.json` first - the
  master is the source of truth, so new facts go there, never straight into a
  tailored copy.
- Weak bullets worth fixing regardless of this job: no outcome, no number,
  duty-shaped rather than result-shaped.

## 3. Tailor the resume

Copy `resume.json` to `applications/<app>/resume.tailored.json` and edit:

- Rewrite the headline and summary for this role.
- Reorder bullets so the evidence for the must-haves leads each role.
- Cut bullets that do not serve this job. Aim for one page; two at most.
- Use the posting's wording where it truthfully describes the same thing
  ("co-selling" for "joint selling").
- Reorder skills; drop irrelevant ones.

Hard rule: tailoring selects, orders and rewords. It never adds an employer,
title, date, degree, figure or skill the user has not claimed. `jobapp.py check
<app>` enforces the checkable part (employers, titles, dates, degrees, projects
and every number must exist in the master) and `resume` refuses to render if it
fails. Do not use `--force` to get past a real mismatch.

Render with `jobapp.py resume <app>`, then tell the user what changed and what
you cut.

## 4. Proof-of-work deck

The deck argues one thing: this person has already done the job's hardest part
and has started thinking about this company's version of it. Six to nine slides.
Write `deck.json` (shape and slide types in `templates/deck.example.json`:
`title`, `bullets`, `case`, `metrics`, `plan`, `closing`) and run
`jobapp.py deck <app>`.

1. `title` - a claim about what they would do for the company, not "Application".
2. `bullets` - what the role needs, as read from the posting and public sources.
3. One to three `case` slides - one per top must-have: problem, action, result.
4. `metrics` - three or four figures, all from the master resume.
5. `bullets` or `case` - a piece of real work for this company: a teardown, an
   audit, a prioritised list of ideas. Base it only on public material and say
   what it is based on. This slide is what makes it proof of work; if you cannot
   research the company, tell the user and draft it with them.
6. `plan` - first 30/60/90 days.
7. `closing` - the ask and contact details.

Every slide title is a full claim the slide then supports. Same fabrication rule
as the resume: figures and results come from `resume.json` or from the user.
Mark anything about the company you inferred rather than read. Open the rendered
deck (or convert to images) and check for overflowing text before calling it done.

## 5. Apply

Write `application.md`: where to submit, answers to the form's screening
questions, a short cover note (under 150 words, specific to the must-haves), and
anything the user must supply themselves (salary expectation, work
authorisation, references, demographic questions - never answer those for them).

Run `jobapp.py apply <app>` to confirm the packet is complete; it sets the
tracker to Ready.

Submitting is the user's action. Do not submit a form or send an email on their
behalf unless they tell you to for this specific application, after seeing the
packet. Then, depending on what is available:

- Browser tools: fill the form, attach the files, stop before the submit button
  and show the user the filled form.
- Email applications: create a draft with the attachments; let the user send it.
- Otherwise: hand over the URL and the file paths.

## 6. Track

Once the user confirms it went in: `jobapp.py apply <app> --submitted`, then set
a follow-up: `jobapp.py track set <app> --next "Follow up" --due <date a week out>`.

Later updates: `jobapp.py track set <app> --status Interviewing --note "..."`.
Statuses: Reviewing, Ready, Applied, Interviewing, Offer, Rejected, Withdrawn,
Skipped. `jobapp.py track list` shows everything; when the user asks how the
search is going, lead with overdue next actions.

If the user decides against a job at any step, set it to Skipped with a one-line
reason rather than deleting the folder.
