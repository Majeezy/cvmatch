"""Tailor a CV to a specific job description using Groq, then save as DOCX."""
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_client, MODEL, TAILORED_CVS_DIR

SYSTEM = """\
You are an expert CV writer and ATS optimization specialist.

Rules:
- NEVER invent, fabricate, or imply experience, skills, or qualifications not present in the original CV.
- Preserve all factual content: dates, job titles, company names, education, and achievements.
- Rewrite bullet points to use language and keywords from the job description wherever truthful and relevant.
- Keep tone professional and concise.
- Output must be ATS-safe: no special symbols, plain text with clear section headings.

Output format — use exactly these section headers (lines starting with ##):
## CONTACT
## SUMMARY
## EXPERIENCE
## SKILLS
## EDUCATION
## CERTIFICATIONS (omit section if none in original CV)

Under ## EXPERIENCE, use this sub-format for each role:
### Job Title | Company | Start Date - End Date
- bullet
- bullet
"""

USER_TEMPLATE = """\
Tailor the CV below for the following job.

Job Title: {title}
Company: {company}
Required Skills: {required_skills}
Key Keywords: {keywords}
Responsibilities:
{responsibilities}

--- ORIGINAL CV ---
{cv_text}
--- END CV ---

Produce the tailored CV now.
"""


def tailor_cv(cv_text: str, job_analysis: dict, api_key: str = "") -> str:
    """Return tailored CV as structured plain text."""
    client = get_client(api_key)
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": USER_TEMPLATE.format(
                title=job_analysis.get("title", ""),
                company=job_analysis.get("company", ""),
                required_skills=", ".join(job_analysis.get("required_skills", [])),
                keywords=", ".join(job_analysis.get("keywords", [])),
                responsibilities="\n".join(f"- {r}" for r in job_analysis.get("responsibilities", [])),
                cv_text=cv_text,
            )},
        ],
        max_tokens=4096,
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()


def _slug(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_")


def save_tailored_cv(tailored_text: str, job_title: str, company: str, output_dir: Path | None = None) -> Path:
    """Parse the structured tailored CV text and save as a clean DOCX file."""
    from docx import Document
    from docx.shared import Pt, RGBColor
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    doc = Document()

    for section in doc.sections:
        section.top_margin = Pt(72)
        section.bottom_margin = Pt(72)
        section.left_margin = Pt(72)
        section.right_margin = Pt(72)

    for para in doc.paragraphs:
        para._element.getparent().remove(para._element)

    def add_section_heading(text):
        para = doc.add_paragraph()
        run = para.add_run(text)
        run.bold = True
        run.font.size = Pt(13)
        run.font.color.rgb = RGBColor(0x1F, 0x49, 0x7D)
        para.paragraph_format.space_before = Pt(10)
        para.paragraph_format.space_after = Pt(2)
        pPr = para._p.get_or_add_pPr()
        pBdr = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        bottom.set(qn("w:val"), "single")
        bottom.set(qn("w:sz"), "6")
        bottom.set(qn("w:space"), "1")
        bottom.set(qn("w:color"), "1F497D")
        pBdr.append(bottom)
        pPr.append(pBdr)

    def add_role_heading(text):
        para = doc.add_paragraph()
        run = para.add_run(text)
        run.bold = True
        run.font.size = Pt(11)
        para.paragraph_format.space_before = Pt(6)
        para.paragraph_format.space_after = Pt(2)

    def add_body(text, bullet=False):
        para = doc.add_paragraph()
        if bullet:
            para.style = doc.styles["List Bullet"]
            run = para.add_run(text.lstrip("-• "))
        else:
            run = para.add_run(text)
        run.font.size = Pt(10.5)
        para.paragraph_format.space_before = Pt(0)
        para.paragraph_format.space_after = Pt(2)

    for line in tailored_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("## "):
            add_section_heading(stripped[3:].strip())
        elif stripped.startswith("### "):
            add_role_heading(stripped[4:].strip())
        elif stripped.startswith("- ") or stripped.startswith("• "):
            add_body(stripped, bullet=True)
        else:
            add_body(stripped)

    today = date.today().strftime("%Y%m%d")
    filename = f"{_slug(company)}_{_slug(job_title)}_{today}.docx"
    output_path = (output_dir or TAILORED_CVS_DIR) / filename
    doc.save(output_path)
    return output_path
