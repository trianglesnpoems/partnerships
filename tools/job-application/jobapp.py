#!/usr/bin/env python3
"""jobapp - job application toolkit.

One folder per application, one master resume, one tracker spreadsheet.

  init                     create the workspace and a resume template
  fetch <url>|--file F     save a job posting           -> job.json, job.md
  match <app>              keyword coverage, resume vs job -> match.json
  check <app>              verify the tailored resume invents nothing
  resume <app>|--master    render resume JSON           -> .docx + .pdf
  deck <app>               render deck.json             -> .pptx
  apply <app>              show the application packet; --submitted records it
  track list|set           read / update tracker.xlsx

The judgement steps (reviewing the job, reviewing and tailoring the resume,
writing the deck) are done by a person or by Claude via the `job-apply` skill;
this script does the deterministic parts and keeps the files in one place.
"""
import argparse
import datetime as dt
import json
import os
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOME = Path(os.environ.get("JOBAPP_HOME") or HERE / "workspace")
APPS = HOME / "applications"
MASTER = HOME / "resume.json"
TRACKER = HOME / "tracker.xlsx"
TODAY = dt.date.today().isoformat()

STATUSES = ["Reviewing", "Ready", "Applied", "Interviewing", "Offer",
            "Rejected", "Withdrawn", "Skipped"]
COLUMNS = ["ID", "Company", "Role", "Location", "Status", "Fit", "Job URL",
           "Found", "Applied", "Next action", "Next action date", "Contact",
           "Resume", "Deck", "Notes"]
WIDTHS = [30, 20, 30, 18, 13, 6, 40, 12, 12, 30, 16, 22, 34, 34, 50]


def die(msg):
    sys.exit(f"error: {msg}")


def slugify(*parts):
    s = "-".join(p for p in parts if p).lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:70]


def load(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        die(f"{path} not found")
    except json.JSONDecodeError as e:
        die(f"{path} is not valid JSON: {e}")


def save(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                          encoding="utf-8")


def app_dir(ref):
    """Resolve an application by exact folder name or unique substring."""
    if not APPS.exists():
        die(f"no applications yet in {APPS} - run `fetch` first")
    names = sorted(p.name for p in APPS.iterdir() if p.is_dir())
    if ref in names:
        return APPS / ref
    hits = [n for n in names if ref.lower() in n]
    if len(hits) == 1:
        return APPS / hits[0]
    die(f"'{ref}' matches {hits or 'nothing'}; applications: {names}")


# ---------------------------------------------------------------- fetch

def html_to_text(html):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "header"]):
        tag.decompose()
    for li in soup.find_all("li"):
        li.insert_before("\n- ")
    for tag in soup.find_all(["p", "div", "br", "h1", "h2", "h3", "h4", "ul", "ol", "tr"]):
        tag.insert_before("\n")
    text = soup.get_text()
    lines = [re.sub(r"[ \t\xa0]+", " ", ln).strip() for ln in text.splitlines()]
    out = []
    for ln in lines:                      # collapse runs of blank lines
        if ln or (out and out[-1]):
            out.append(ln)
    return "\n".join(out).strip()


def http_get(url, as_json=False):
    import requests
    r = requests.get(url, timeout=30, headers={
        "User-Agent": "Mozilla/5.0 (compatible; jobapp/1.0)",
        "Accept": "application/json" if as_json else "text/html,*/*"})
    r.raise_for_status()
    return r.json() if as_json else r.text


def parse_greenhouse(d):
    import html as _html
    return {"company": d.get("company_name", ""), "title": d.get("title", ""),
            "location": (d.get("location") or {}).get("name", ""),
            "description": html_to_text(_html.unescape(d.get("content", "")))}


def parse_lever(d):
    parts = [d.get("descriptionPlain") or html_to_text(d.get("description", ""))]
    for sec in d.get("lists", []):
        parts.append(f"\n{sec.get('text', '')}\n{html_to_text(sec.get('content', ''))}")
    parts.append(d.get("additionalPlain") or html_to_text(d.get("additional", "")))
    cat = d.get("categories") or {}
    return {"company": "", "title": d.get("text", ""),
            "location": cat.get("location", ""),
            "description": "\n".join(p for p in parts if p).strip()}


def parse_ashby(board, job_id):
    for j in board.get("jobs", []):
        if j.get("id") == job_id or job_id in (j.get("jobUrl") or ""):
            return {"company": "", "title": j.get("title", ""),
                    "location": j.get("location", ""),
                    "description": j.get("descriptionPlain")
                    or html_to_text(j.get("descriptionHtml", ""))}
    raise ValueError("job id not found on Ashby board")


def parse_generic(html):
    """schema.org JobPosting JSON-LD if present, else the page's visible text."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except ValueError:
            continue
        nodes = data if isinstance(data, list) else data.get("@graph", [data])
        for n in nodes:
            if isinstance(n, dict) and n.get("@type") == "JobPosting":
                org = n.get("hiringOrganization") or {}
                loc = n.get("jobLocation") or {}
                loc = loc[0] if isinstance(loc, list) and loc else loc
                addr = loc.get("address", {}) if isinstance(loc, dict) else {}
                place = ", ".join(x for x in [addr.get("addressLocality"),
                                              addr.get("addressRegion")] if x) \
                    if isinstance(addr, dict) else str(addr)
                return {"company": org.get("name", "") if isinstance(org, dict) else str(org),
                        "title": n.get("title", ""), "location": place,
                        "description": html_to_text(n.get("description", ""))}
    title = soup.title.get_text(strip=True) if soup.title else ""
    return {"company": "", "title": title, "location": "",
            "description": html_to_text(html)}


def fetch_url(url):
    m = re.search(r"greenhouse\.io/(?:embed/job_app\?for=)?([\w-]+)/jobs/(\d+)", url)
    if m:
        api = f"https://boards-api.greenhouse.io/v1/boards/{m[1]}/jobs/{m[2]}"
        job = parse_greenhouse(http_get(api, as_json=True))
        return {**job, "company": job["company"] or m[1], "source": "greenhouse"}
    m = re.search(r"jobs\.lever\.co/([\w-]+)/([0-9a-f-]{36})", url)
    if m:
        api = f"https://api.lever.co/v0/postings/{m[1]}/{m[2]}"
        return {**parse_lever(http_get(api, as_json=True)), "company": m[1], "source": "lever"}
    m = re.search(r"jobs\.ashbyhq\.com/([\w.-]+)/([0-9a-f-]{36})", url)
    if m:
        api = f"https://api.ashbyhq.com/posting-api/job-board/{m[1]}"
        return {**parse_ashby(http_get(api, as_json=True), m[2]), "company": m[1], "source": "ashby"}
    return {**parse_generic(http_get(url)), "source": "web"}


def cmd_fetch(a):
    if a.file:
        raw = sys.stdin.read() if a.file == "-" else Path(a.file).read_text(encoding="utf-8")
        job = {"company": "", "title": "", "location": "", "source": "pasted",
               "description": html_to_text(raw) if "</" in raw else raw.strip()}
    elif a.url:
        try:
            job = fetch_url(a.url)
        except Exception as e:
            die(f"could not fetch {a.url}: {e}\n"
                "Paste the posting into a text file and rerun with "
                "--file posting.txt --url <url> --company ... --title ...")
    else:
        die("give a URL or --file")
    job["company"] = a.company or job["company"]
    job["title"] = a.title or job["title"]
    job["location"] = a.location or job["location"]
    job["url"] = a.url or ""
    job["fetched"] = TODAY
    if not job["company"] or not job["title"]:
        die("could not determine company/title - pass --company and --title")
    if len(job["description"]) < 200:
        print("warning: description is very short; the page may need a login or "
              "JavaScript. Consider --file with the pasted posting.", file=sys.stderr)
    d = APPS / slugify(job["company"], job["title"])
    d.mkdir(parents=True, exist_ok=True)
    save(d / "job.json", job)
    (d / "job.md").write_text(
        f"# {job['title']} - {job['company']}\n\n"
        f"- Location: {job['location'] or 'n/a'}\n- URL: {job['url'] or 'n/a'}\n"
        f"- Saved: {TODAY}\n\n{job['description']}\n", encoding="utf-8")
    track_upsert(d.name, {"Company": job["company"], "Role": job["title"],
                          "Location": job["location"], "Job URL": job["url"],
                          "Found": TODAY}, default_status="Reviewing")
    print(f"saved {d}\ntracked as Reviewing in {TRACKER}")


# ---------------------------------------------------------------- match

STOP = set("""a about above across after all also an and any are as at be been being both but by can
could day do does each etc every for from have has having help how if in including into is it its
job join like looking make may more most must need new not of on one or other our out over own per
plus role roles should so such team teams than that the their them these they this those through to
under up us using we well what when where which while who will with within work working would year
years you your yours ability able strong experience experienced preferred required requirements
responsibilities qualifications skills company candidate ideal excellent great opportunity
opportunities position based people ensure provide environment equal employer benefits apply
build building drive driving develop developing manage managing support supporting best high
key including across within etc time full part""".split())


def tokens(text):
    return re.findall(r"[a-z][a-z0-9+#]*(?:[./-][a-z0-9+#]+)*", text.lower())


def stem(w):
    for suf in ("ing", "ies", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[: -len(suf)]
    return w


def resume_text(r):
    """All human-readable text in a resume JSON, flattened."""
    out = []

    def walk(x):
        if isinstance(x, str):
            out.append(x)
        elif isinstance(x, list):
            for i in x:
                walk(i)
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
    walk(r)
    return "\n".join(out)


def job_terms(desc, top=40):
    """Words and two-word phrases the posting repeats, most frequent first."""
    uni, bi, shown = Counter(), Counter(), {}
    for line in re.split(r"[\n.;:]+", desc):          # phrases do not span lines
        toks = [t for t in tokens(line)]
        for t in toks:
            if t not in STOP and len(t) > 2:
                uni[stem(t)] += 1
                shown.setdefault(stem(t), t)
        for a, b in zip(toks, toks[1:]):
            if a not in STOP and b not in STOP and len(a) > 2 and len(b) > 2:
                key = f"{stem(a)} {stem(b)}"
                bi[key] += 1
                shown.setdefault(key, f"{a} {b}")
    picked = [(t, c) for t, c in bi.items() if c >= 2]
    inside = {w for t, _ in picked for w in t.split()}
    picked += [(t, c) for t, c in uni.items() if c >= 2 and t not in inside]
    picked.sort(key=lambda x: (-x[1], x[0]))
    return [(shown[t], c) for t, c in picked[:top]]


def cmd_match(a):
    d = app_dir(a.app)
    job = load(d / "job.json")
    src = d / "resume.tailored.json"
    src = src if src.exists() and not a.master else MASTER
    have = {stem(t) for t in tokens(resume_text(load(src)))}
    rows = []
    for term, count in job_terms(job["description"]):
        rows.append({"term": term, "mentions": count,
                     "in_resume": all(stem(w) in have for w in term.split())})
    hit = [r for r in rows if r["in_resume"]]
    cov = round(100 * len(hit) / len(rows)) if rows else 0
    save(d / "match.json", {"resume": src.name, "coverage_pct": cov, "terms": rows})
    print(f"{src.name} vs {d.name}: {cov}% of {len(rows)} recurring job terms present")
    print("  present: " + ", ".join(r["term"] for r in hit))
    print("  missing: " + ", ".join(r["term"] for r in rows if not r["in_resume"]))
    print("(heuristic word match - a missing term is a prompt to check, not a verdict)")


# ---------------------------------------------------------------- check

def norm(s):
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


def numbers(text):
    found = re.findall(r"\d[\d,]*(?:\.\d+)?", text)
    return {n.replace(",", "").rstrip(".") for n in found}


def check_resume(tailored, master):
    """Return (errors, warnings). A tailored resume may reorder, cut and reword;
    it may not add employers, titles, dates, degrees or figures."""
    errors, warnings = [], []
    if norm(tailored.get("name")) != norm(master.get("name")):
        errors.append("name differs from master resume")
    if tailored.get("contact") != master.get("contact"):
        warnings.append("contact block differs from master resume")
    jobs = {(norm(e.get("company")), norm(e.get("title")), norm(e.get("start")),
             norm(e.get("end"))) for e in master.get("experience", [])}
    for e in tailored.get("experience", []):
        key = (norm(e.get("company")), norm(e.get("title")), norm(e.get("start")), norm(e.get("end")))
        if key not in jobs:
            errors.append(f"experience not in master (company/title/dates must match exactly): "
                          f"{e.get('title')} at {e.get('company')}, {e.get('start')}-{e.get('end')}")
    schools = {(norm(e.get("school")), norm(e.get("degree"))) for e in master.get("education", [])}
    for e in tailored.get("education", []):
        if (norm(e.get("school")), norm(e.get("degree"))) not in schools:
            errors.append(f"education not in master: {e.get('degree')} at {e.get('school')}")
    projects = {norm(p.get("name")) for p in master.get("projects", [])}
    for p in tailored.get("projects", []):
        if norm(p.get("name")) not in projects:
            errors.append(f"project not in master: {p.get('name')}")
    master_text = norm(resume_text(master))
    new_nums = numbers(resume_text(tailored)) - numbers(resume_text(master))
    if new_nums:
        errors.append("figures that do not appear anywhere in the master resume: "
                      + ", ".join(sorted(new_nums)))
    for g in tailored.get("skills", []):
        for item in g.get("items", []):
            if norm(item) not in master_text:
                warnings.append(f"skill not found verbatim in master: {item}")
    return errors, warnings


def run_check(d):
    errors, warnings = check_resume(load(d / "resume.tailored.json"), load(MASTER))
    for w in warnings:
        print(f"  warning: {w}")
    for e in errors:
        print(f"  ERROR: {e}")
    return errors


def cmd_check(a):
    d = app_dir(a.app)
    if run_check(d):
        sys.exit(1)
    print(f"ok: {d.name}/resume.tailored.json adds no employers, dates, degrees or figures")


# ---------------------------------------------------------------- resume

def date_range(e):
    return " - ".join(x for x in [e.get("start"), e.get("end")] if x)


def contact_line(r):
    c = r.get("contact", {})
    return "  |  ".join(x for x in [c.get("location"), c.get("email"), c.get("phone"),
                                    *c.get("links", [])] if x)


def resume_docx(r, path):
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Inches, Pt, RGBColor

    doc = Document()
    sec = doc.sections[0]
    sec.left_margin = sec.right_margin = Inches(0.75)
    sec.top_margin = sec.bottom_margin = Inches(0.6)
    width = sec.page_width - sec.left_margin - sec.right_margin
    base = doc.styles["Normal"]
    base.font.name, base.font.size = "Calibri", Pt(10.5)
    base.paragraph_format.space_after = Pt(0)

    def para(text="", bold=False, size=None, after=0, before=0, align=None, style=None):
        p = doc.add_paragraph(style=style)
        if text:
            run = p.add_run(text)
            run.bold = bold
            if size:
                run.font.size = Pt(size)
        p.paragraph_format.space_after = Pt(after)
        p.paragraph_format.space_before = Pt(before)
        if align:
            p.alignment = align
        return p

    def heading(text):
        p = para(text.upper(), bold=True, size=10.5, before=9, after=3)
        p.runs[0].font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)
        border = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        for k, v in (("val", "single"), ("sz", "6"), ("space", "1"), ("color", "1F3A5F")):
            bottom.set(qn(f"w:{k}"), v)
        border.append(bottom)
        p._p.get_or_add_pPr().append(border)

    def split_line(left, right, bold_left=True, before=5):
        p = para(before=before)
        p.paragraph_format.tab_stops.add_tab_stop(width, WD_TAB_ALIGNMENT.RIGHT)
        p.add_run(left).bold = bold_left
        if right:
            p.add_run("\t" + right)
        return p

    def bullets(items):
        for b in items or []:
            p = para(b, style="List Bullet")
            p.paragraph_format.left_indent = Inches(0.2)

    para(r.get("name", ""), bold=True, size=20, align=WD_ALIGN_PARAGRAPH.CENTER)
    if r.get("headline"):
        para(r["headline"], size=11, align=WD_ALIGN_PARAGRAPH.CENTER)
    para(contact_line(r), size=9.5, align=WD_ALIGN_PARAGRAPH.CENTER)
    if r.get("summary"):
        heading("Summary")
        para(r["summary"])
    if r.get("experience"):
        heading("Experience")
        for e in r["experience"]:
            split_line(f"{e.get('title', '')}, {e.get('company', '')}", date_range(e))
            if e.get("location"):
                para(e["location"]).runs[0].italic = True
            bullets(e.get("bullets"))
    if r.get("projects"):
        heading("Projects")
        for pr in r["projects"]:
            split_line(pr.get("name", ""), pr.get("link", ""))
            bullets(pr.get("bullets"))
    if r.get("skills"):
        heading("Skills")
        for g in r["skills"]:
            p = para()
            if g.get("group"):
                p.add_run(g["group"] + ": ").bold = True
            p.add_run(", ".join(g.get("items", [])))
    if r.get("education"):
        heading("Education")
        for e in r["education"]:
            split_line(f"{e.get('degree', '')}, {e.get('school', '')}", str(e.get("year", "")),
                       before=2)
    doc.save(path)


def resume_pdf(r, path):
    from xml.sax.saxutils import escape
    from reportlab.lib.colors import HexColor
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Table, TableStyle

    reg, bold = "Helvetica", "Helvetica-Bold"
    for folder in ("/usr/share/fonts/truetype/dejavu", "/Library/Fonts",
                   "/System/Library/Fonts/Supplemental", "C:/Windows/Fonts"):
        for rname, bname in (("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"),
                             ("Arial.ttf", "Arial Bold.ttf"), ("arial.ttf", "arialbd.ttf")):
            if reg == "Helvetica" and (Path(folder) / rname).exists() \
                    and (Path(folder) / bname).exists():
                pdfmetrics.registerFont(TTFont("Body", str(Path(folder) / rname)))
                pdfmetrics.registerFont(TTFont("Body-Bold", str(Path(folder) / bname)))
                reg, bold = "Body", "Body-Bold"

    def t(s):  # the built-in PDF fonts only cover Latin-1
        s = str(s or "")
        if reg == "Helvetica":
            for a, b in (("\u2192", "->"), ("\u2013", "-"), ("\u2014", "-"), ("\u2022", "-"),
                         ("\u2018", "'"), ("\u2019", "'"), ("\u201c", '"'), ("\u201d", '"')):
                s = s.replace(a, b)
            s = s.encode("latin-1", "replace").decode("latin-1")
        return escape(s)

    navy = HexColor("#1F3A5F")
    body = ParagraphStyle("body", fontName=reg, fontSize=9.6, leading=12.4)
    center = ParagraphStyle("center", parent=body, alignment=TA_CENTER)
    name = ParagraphStyle("name", parent=center, fontName=bold, fontSize=19, leading=24)
    head = ParagraphStyle("head", parent=body, fontName=bold, textColor=navy, spaceBefore=9)
    bullet = ParagraphStyle("bullet", parent=body, leftIndent=12, bulletIndent=2)
    right = ParagraphStyle("right", parent=body, alignment=2)
    doc = SimpleDocTemplate(str(path), pagesize=LETTER, leftMargin=0.75 * inch,
                            rightMargin=0.75 * inch, topMargin=0.55 * inch,
                            bottomMargin=0.55 * inch, title=f"{r.get('name', '')} - Resume",
                            author=r.get("name", ""))
    flow = []

    def heading(text):
        flow.append(Paragraph(t(text.upper()), head))
        flow.append(HRFlowable(width="100%", thickness=0.7, color=navy, spaceAfter=3))

    def split_line(left, rightside):
        tbl = Table([[Paragraph(f'<font name="{bold}">{t(left)}</font>', body),
                      Paragraph(t(rightside), right)]],
                    colWidths=[doc.width * 0.62, doc.width * 0.38])
        tbl.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0),
                                 ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                 ("TOPPADDING", (0, 0), (-1, -1), 5),
                                 ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                                 ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        flow.append(tbl)

    def bullets(items):
        for b in items or []:
            flow.append(Paragraph(t(b), bullet, bulletText="\u2022" if reg == "Body" else "-"))

    flow.append(Paragraph(t(r.get("name")), name))
    if r.get("headline"):
        flow.append(Paragraph(t(r["headline"]), center))
    flow.append(Paragraph(t(contact_line(r)), center))
    if r.get("summary"):
        heading("Summary")
        flow.append(Paragraph(t(r["summary"]), body))
    if r.get("experience"):
        heading("Experience")
        for e in r["experience"]:
            split_line(f"{e.get('title', '')}, {e.get('company', '')}", date_range(e))
            if e.get("location"):
                flow.append(Paragraph(f"<i>{t(e['location'])}</i>", body))
            bullets(e.get("bullets"))
    if r.get("projects"):
        heading("Projects")
        for pr in r["projects"]:
            split_line(pr.get("name", ""), pr.get("link", ""))
            bullets(pr.get("bullets"))
    if r.get("skills"):
        heading("Skills")
        for g in r["skills"]:
            label = f'<font name="{bold}">{t(g["group"])}: </font>' if g.get("group") else ""
            flow.append(Paragraph(label + t(", ".join(g.get("items", []))), body))
    if r.get("education"):
        heading("Education")
        for e in r["education"]:
            split_line(f"{e.get('degree', '')}, {e.get('school', '')}", str(e.get("year", "")))
    doc.build(flow)
    return doc.page


def cmd_resume(a):
    if a.master:
        src, out_dir, label = MASTER, HOME, "Master"
    else:
        if not a.app:
            die("give an application or --master")
        out_dir = app_dir(a.app)
        src = out_dir / "resume.tailored.json"
        if not src.exists():
            die(f"{src} not found - write the tailored resume first (copy resume.json and edit)")
        label = load(out_dir / "job.json")["company"]
        if run_check(out_dir) and not a.force:
            die("tailored resume failed the fabrication check; fix it, or --force if the "
                "master resume is what is out of date")
    r = load(src)
    stem_ = re.sub(r"[^\w .-]", "", f"{r.get('name', 'Resume')} - Resume - {label}")
    docx_path, pdf_path = out_dir / f"{stem_}.docx", out_dir / f"{stem_}.pdf"
    resume_docx(r, docx_path)
    pages = resume_pdf(r, pdf_path)
    print(f"wrote {docx_path}\nwrote {pdf_path} ({pages} page{'s' if pages != 1 else ''})")
    if pages > 2:
        print("warning: over 2 pages - cut bullets that do not serve this job")
    if not a.master:
        track_upsert(out_dir.name, {"Resume": pdf_path.name})


# ---------------------------------------------------------------- deck

def cmd_deck(a):
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import MSO_ANCHOR
    from pptx.util import Inches, Pt

    d = app_dir(a.app)
    spec = load(d / "deck.json")
    theme = spec.get("theme", {})

    def rgb(key, default):
        return RGBColor.from_string(theme.get(key, default).lstrip("#").upper())

    ink, muted = rgb("ink", "#14213D"), rgb("muted", "#5C677D")
    accent, paper, panel = rgb("accent", "#E07A1F"), rgb("paper", "#FBFAF7"), rgb("panel", "#F0EDE6")
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    W, M = 13.333, 0.8
    total = len(spec.get("slides", []))

    def fit(text, size, chars):
        """Step the font size down when the text is long for its box."""
        n = len(text)
        return size if n <= chars else max(size * 0.62, size * (chars / n) ** 0.5)

    def box(slide, x, y, w, h, text="", size=18, bold=False, color=None, anchor=None):
        tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = 0
        if anchor:
            tf.vertical_anchor = anchor
        lines = text if isinstance(text, list) else [text]
        for i, line in enumerate(lines):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            run = p.add_run()
            run.text = str(line)
            run.font.size, run.font.bold = Pt(size), bold
            run.font.color.rgb = color or ink
            run.font.name = theme.get("font", "Calibri")
            p.space_after = Pt(size * 0.45)
        return tb

    def rect(slide, x, y, w, h, fill):
        s = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
        s.fill.solid()
        s.fill.fore_color.rgb = fill
        s.line.fill.background()
        s.shadow.inherit = False
        return s

    def base(s, n, title=None):
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        bg = slide.background.fill
        bg.solid()
        bg.fore_color.rgb = paper
        if title:
            rect(slide, M, 0.75, 0.6, 0.07, accent)
            box(slide, M, 0.9, W - 2 * M, 1.1, title, size=fit(title, 32, 60), bold=True)
            box(slide, M, 6.85, 8, 0.3, spec.get("footer", spec.get("author", "")), 10, color=muted)
            box(slide, W - M - 1, 6.85, 1, 0.3, f"{n} / {total}", 10, color=muted)
        if s.get("notes"):
            slide.notes_slide.notes_text_frame.text = s["notes"]
        return slide

    def bullet_lines(items):
        return [f"\u2022  {b}" for b in items or []]

    for n, s in enumerate(spec.get("slides", []), 1):
        kind = s.get("type", "bullets")
        if kind in ("title", "closing"):
            slide = base(s, n)
            rect(slide, 0, 0, 0.35, 7.5, accent)
            box(slide, 1.2, 2.2, 10.8, 2.0, s.get("title", ""), fit(s.get("title", ""), 44, 55),
                bold=True, anchor=MSO_ANCHOR.BOTTOM)
            sub = [x for x in [s.get("subtitle") or s.get("body")] if x]
            box(slide, 1.2, 4.4, 10.8, 1.3, sub, 20, color=muted)
            foot = s.get("contact") or spec.get("author", "")
            box(slide, 1.2, 6.3, 10.8, 0.4, foot, 14, color=ink)
        elif kind == "metrics":
            slide = base(s, n, s.get("title"))
            items = s.get("metrics", [])[:4]
            gap = 0.3
            w = (W - 2 * M - gap * (len(items) - 1)) / max(len(items), 1)
            for i, m in enumerate(items):
                x = M + i * (w + gap)
                rect(slide, x, 2.4, w, 3.0, panel)
                box(slide, x + 0.3, 2.6, w - 0.6, 1.4, m.get("value", ""),
                    fit(str(m.get("value", "")), 46, 7 if len(items) > 3 else 9),
                    bold=True, color=accent, anchor=MSO_ANCHOR.BOTTOM)
                box(slide, x + 0.3, 4.1, w - 0.6, 1.2, m.get("label", ""),
                    fit(m.get("label", ""), 15, 70), color=ink)
            if s.get("note"):
                box(slide, M, 5.7, W - 2 * M, 0.8, s["note"], 14, color=muted)
        elif kind in ("case", "plan"):
            slide = base(s, n, s.get("title"))
            if kind == "case":
                cols = [{"heading": h, "text": s.get(k, "")} for h, k in
                        (("Problem", "problem"), ("What I did", "action"), ("Result", "result"))]
            else:
                cols = s.get("columns", [])[:4]
            gap = 0.3
            w = (W - 2 * M - gap * (len(cols) - 1)) / max(len(cols), 1)
            for i, c in enumerate(cols):
                x = M + i * (w + gap)
                rect(slide, x, 2.3, w, 0.06, accent)
                box(slide, x, 2.45, w, 0.5, c.get("heading", ""), 16, bold=True, color=accent)
                body = bullet_lines(c.get("bullets")) if c.get("bullets") else [c.get("text", "")]
                box(slide, x, 3.0, w, 3.0, body, fit(" ".join(body), 16, 230))
            if s.get("proof"):
                box(slide, M, 6.2, W - 2 * M, 0.4, f"Proof: {s['proof']}", 12, color=muted)
        else:  # bullets
            slide = base(s, n, s.get("title"))
            body = bullet_lines(s.get("bullets"))
            box(slide, M, 2.3, W - 2 * M, 3.6, body, fit(" ".join(body), 22, 420))
            if s.get("note"):
                box(slide, M, 6.1, W - 2 * M, 0.6, s["note"], 14, color=muted)

    job = load(d / "job.json")
    out = d / re.sub(r"[^\w .-]", "", f"{spec.get('author', 'Deck')} - Proof of Work - "
                                      f"{job['company']}.pptx")
    prs.save(out)
    print(f"wrote {out} ({total} slides)")
    track_upsert(d.name, {"Deck": out.name})


# ---------------------------------------------------------------- tracker

def tracker_open():
    from openpyxl import Workbook, load_workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation
    if TRACKER.exists():
        wb = load_workbook(TRACKER)
        return wb, wb["Applications"]
    HOME.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "Applications"
    ws.append(COLUMNS)
    for i, w in enumerate(WIDTHS, 1):
        cell = ws.cell(row=1, column=i)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F3A5F")
        cell.alignment = Alignment(vertical="center")
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(COLUMNS))}1"
    dv = DataValidation(type="list", formula1='"' + ",".join(STATUSES) + '"', allow_blank=True)
    dv.add("E2:E2000")
    ws.add_data_validation(dv)
    return wb, ws


def track_upsert(app_id, fields, default_status=None):
    try:
        wb, ws = tracker_open()
    except PermissionError:
        die(f"{TRACKER} is open in another program - close it and retry")
    head = [c.value for c in ws[1]]
    row = next((r for r in range(2, ws.max_row + 1) if ws.cell(r, 1).value == app_id), None)
    if row is None:
        row = ws.max_row + 1
        ws.cell(row, 1, app_id)
        if default_status:
            ws.cell(row, head.index("Status") + 1, default_status)
    for k, v in fields.items():
        if v is not None and v != "":
            ws.cell(row, head.index(k) + 1, v)
    ws.auto_filter.ref = ws.dimensions
    try:
        wb.save(TRACKER)
    except PermissionError:
        die(f"{TRACKER} is open in another program - close it and retry")


def cmd_track(a):
    if a.action == "set":
        if not a.app:
            die("track set needs an application")
        d = app_dir(a.app)
        fields = {"Status": a.status, "Fit": a.fit, "Next action": a.next,
                  "Next action date": a.due, "Contact": a.contact, "Notes": a.note}
        if a.status == "Applied":
            fields["Applied"] = a.date or TODAY
        if not any(v not in (None, "") for v in fields.values()):
            die("nothing to set - pass --status, --fit, --next, --due, --contact or --note")
        track_upsert(d.name, fields)
        print(f"updated {d.name}")
        return
    if not TRACKER.exists():
        die(f"no tracker yet at {TRACKER}")
    _, ws = tracker_open()
    rows = [dict(zip(COLUMNS, r)) for r in ws.iter_rows(min_row=2, values_only=True) if r[0]]
    print(f"{len(rows)} application(s) in {TRACKER}")
    for r in rows:
        nxt = f"  next: {r['Next action']} ({r['Next action date'] or 'no date'})" \
            if r["Next action"] else ""
        print(f"  [{r['Status'] or '?':<12}] {r['Company']} - {r['Role']}"
              f"  fit {r['Fit'] if r['Fit'] is not None else '-'}{nxt}")


# ---------------------------------------------------------------- apply

def cmd_apply(a):
    d = app_dir(a.app)
    job = load(d / "job.json")
    if a.submitted:
        track_upsert(d.name, {"Status": "Applied", "Applied": a.date or TODAY, "Notes": a.note})
        print(f"recorded: applied to {job['company']} on {a.date or TODAY}")
        return
    pdfs, decks = sorted(d.glob("*Resume*.pdf")), sorted(d.glob("*.pptx"))
    answers = d / "application.md"
    print(f"Application packet: {job['title']} - {job['company']}")
    print(f"  apply at : {job['url'] or '(no URL saved)'}")
    for label, found in (("resume   ", pdfs), ("deck     ", decks),
                         ("answers  ", [answers] if answers.exists() else [])):
        print(f"  {label}: {found[0] if found else 'MISSING'}")
    if not pdfs:
        die("no tailored resume PDF yet - run `resume` first")
    track_upsert(d.name, {"Status": "Ready"})
    print("Status set to Ready. Submit it yourself, then run:\n"
          f"  jobapp.py apply {d.name} --submitted")


# ---------------------------------------------------------------- init / cli

def cmd_init(a):
    APPS.mkdir(parents=True, exist_ok=True)
    if MASTER.exists():
        print(f"{MASTER} already exists - left untouched")
    else:
        shutil.copy(HERE / "templates" / "resume.example.json", MASTER)
        print(f"created {MASTER} - replace the example content with your real resume")
    tracker_open()[0].save(TRACKER)
    print(f"workspace ready at {HOME}")


def main():
    p = argparse.ArgumentParser(prog="jobapp.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init").set_defaults(fn=cmd_init)

    s = sub.add_parser("fetch", help="save a job posting")
    s.add_argument("url", nargs="?")
    s.add_argument("--url", dest="url_opt", help="posting URL when using --file")
    s.add_argument("--file", help="text or HTML file with the posting ('-' for stdin)")
    s.add_argument("--company")
    s.add_argument("--title")
    s.add_argument("--location")
    s.set_defaults(fn=cmd_fetch)

    s = sub.add_parser("match", help="keyword coverage of resume vs job")
    s.add_argument("app")
    s.add_argument("--master", action="store_true", help="score the master resume")
    s.set_defaults(fn=cmd_match)

    s = sub.add_parser("check", help="verify the tailored resume invents nothing")
    s.add_argument("app")
    s.set_defaults(fn=cmd_check)

    s = sub.add_parser("resume", help="render resume to .docx and .pdf")
    s.add_argument("app", nargs="?")
    s.add_argument("--master", action="store_true")
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_resume)

    s = sub.add_parser("deck", help="render deck.json to .pptx")
    s.add_argument("app")
    s.set_defaults(fn=cmd_deck)

    s = sub.add_parser("apply", help="show the packet, or record a submission")
    s.add_argument("app")
    s.add_argument("--submitted", action="store_true")
    s.add_argument("--date")
    s.add_argument("--note")
    s.set_defaults(fn=cmd_apply)

    s = sub.add_parser("track", help="list or update the tracker")
    s.add_argument("action", choices=["list", "set"])
    s.add_argument("app", nargs="?")
    s.add_argument("--status", choices=STATUSES)
    s.add_argument("--fit", type=int, help="fit score 0-100")
    s.add_argument("--next", help="next action")
    s.add_argument("--due", help="next action date, YYYY-MM-DD")
    s.add_argument("--contact")
    s.add_argument("--note")
    s.add_argument("--date", help="applied date, default today")
    s.set_defaults(fn=cmd_track)

    a = p.parse_args()
    if a.cmd == "fetch":
        a.url = a.url or a.url_opt
    a.fn(a)


if __name__ == "__main__":
    main()
