# Job Application Toolkit

Takes one job posting through six steps and keeps everything in one folder per application.

| Step | Who does it | Output |
| --- | --- | --- |
| 1. Review job | Claude (`/job-apply`) or you | `job.md`, `job-review.md`, fit score |
| 2. Review resume | Claude or you, helped by `match` | `resume-review.md`, `match.json` |
| 3. Tailor resume | Claude or you, guarded by `check` | `resume.tailored.json` → `.docx` + `.pdf` |
| 4. Proof-of-work deck | Claude or you | `deck.json` → `.pptx` |
| 5. Apply | You submit; the tool assembles the packet | `application.md` |
| 6. Track | Automatic at each step | `tracker.xlsx` |

There are two parts:

- **`jobapp.py`** — a script for the mechanical work: fetching the posting, rendering files, updating the spreadsheet. It makes no AI calls and needs no API key.
- **The `job-apply` skill** (`.claude/skills/job-apply/SKILL.md`) — instructions Claude Code follows to do the judgement steps and drive the script. In a Claude Code session in this repository, say "apply to this job: <url>" or run `/job-apply`.

You can use the script without Claude by writing the JSON files yourself.

## Setup

```bash
pip install -r tools/job-application/requirements.txt
python3 tools/job-application/jobapp.py init
```

`init` creates `tools/job-application/workspace/` with an example `resume.json`. Replace it with your real resume, keeping the same shape. Make the master resume complete rather than short — tailoring cuts from it.

**The workspace is gitignored.** This repository is public and the workspace holds your resume, so it is never committed. That also means a Claude Code cloud session loses it when the session ends. Run the tool locally, or set `JOBAPP_HOME` to a folder that persists (a private repository checkout, a synced drive).

## Commands

```bash
J="python3 tools/job-application/jobapp.py"

$J fetch https://boards.greenhouse.io/acme/jobs/12345      # 1. save the posting, add a tracker row
$J fetch --file posting.txt --url <url> --company Acme --title "Partner Manager"   # if the fetch fails

$J match acme --master      # 2. which recurring job terms the resume contains
$J check acme               # 3. tailored resume adds nothing that is not in the master
$J resume acme              # 3. render resume.tailored.json to .docx and .pdf
$J deck acme                # 4. render deck.json to .pptx
$J apply acme               # 5. list the packet, set status to Ready
$J apply acme --submitted   # 6. record the submission date
$J track set acme --status Interviewing --next "Prep for panel" --due 2026-12-03
$J track list
```

An application is named `<company>-<role>`; any unique part of the name works (`acme`).

### Fetching postings

Greenhouse, Lever and Ashby URLs are read through those boards' public JSON APIs. Any other URL is read as a web page: schema.org `JobPosting` data when the page has it, otherwise the visible text. Pages behind a login or rendered by JavaScript (LinkedIn, Workday) usually come back thin — paste the posting into a text file and use `--file`.

### The fabrication check

`check` compares `resume.tailored.json` with the master `resume.json` and fails if the tailored copy contains:

- an employer, title or date range that does not match a master entry exactly
- a degree or project that is not in the master
- any number that appears nowhere in the master

A skill that is not found verbatim in the master is a warning. `resume` runs the check and refuses to render on failure. If the master is what is out of date, update the master. The check cannot judge wording, so a reworded bullet that overstates still needs a human read.

### The keyword match

`match` lists words and two-word phrases the posting uses at least twice and whether the resume contains them. It is a word match with crude stemming, useful for spotting vocabulary gaps ("co-selling" vs "joint selling"), and nothing more.

### Applying

The tool does not submit applications. Greenhouse, Lever and Ashby only accept submissions through the employer's form (their submission APIs need the employer's key), and an application is sent in your name. `apply` confirms the packet is complete and prints the URL and files; you submit, then record it with `--submitted`. In a Claude Code session with browser or email tools, the skill has Claude fill the form or draft the email and stop for your go-ahead.

### The tracker

`tracker.xlsx` has one row per application: company, role, location, status, fit score, URL, dates found and applied, next action and its date, contact, resume and deck filenames, notes. The Status column has a dropdown. You can edit the file by hand; keep the `ID` column unchanged so the script can find its rows, and close the file before running commands that write to it.

## File formats

- Resume: `templates/resume.example.json`
- Deck: `templates/deck.example.json`. Slide types are `title`, `bullets`, `case` (problem / action / result), `metrics` (up to four figures), `plan` (up to four columns) and `closing`. `notes` on any slide becomes speaker notes. `theme` takes `accent`, `ink`, `muted`, `paper`, `panel` hex colours and `font`.

## Try it with the sample data

```bash
export JOBAPP_HOME=/tmp/jobapp-demo
$J init
$J fetch --file tools/job-application/templates/sample-job.txt --company Fabrikam --title "Senior Partnerships Manager"
A=$JOBAPP_HOME/applications/fabrikam-senior-partnerships-manager
cp $JOBAPP_HOME/resume.json $A/resume.tailored.json
cp tools/job-application/templates/deck.example.json $A/deck.json
$J match fabrikam && $J resume fabrikam && $J deck fabrikam && $J apply fabrikam && $J track list
```

## Limits

- The Greenhouse, Lever and Ashby fetchers were written against those APIs' documented response shapes and tested on synthetic payloads only; the session that built this could not reach those hosts. If one misreads a live posting, use `--file`.
- Resume layout is a single-column, ATS-safe design. There is one template.
- Deck text shrinks to fit long content but can still overflow a box; look at the rendered deck before sending it.
