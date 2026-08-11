"""Generate a personalized cover letter using Groq and save as DOCX."""
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_client, MODEL, COVER_LETTERS_DIR

_SYSTEM_BASE = """\
You are a professional cover letter writer.
Rules:
- Write in first person.
- Base the letter ONLY on facts present in the CV — never fabricate experience or skills.
- Structure: opening paragraph (role + enthusiasm), middle paragraph (top 2-3 relevant achievements/skills), closing paragraph (call to action).
- Total length: 3 paragraphs, 250-350 words.
- Output only the 3 body paragraphs separated by blank lines. No subject line, no date, no greeting, no sign-off.
"""

_TONE_ADDENDA = {
    "formal":    "Tone: formal, professional, precise. Use full sentences. Avoid contractions.",
    "confident": "Tone: confident, assertive, achievement-forward. Lead with impact. Use active voice throughout.",
    "creative":  "Tone: engaging, distinctive, personality-forward. One vivid metaphor or hook is encouraged.",
}

SYSTEM = _SYSTEM_BASE + _TONE_ADDENDA["formal"]

USER_TEMPLATE = """\
Write a cover letter for this application.

Role: {title}
Company: {company}
Key requirements: {required_skills}
Keywords to incorporate: {keywords}

--- APPLICANT'S CV ---
{cv_text}
--- END CV ---
"""


def generate_cover_letter(cv_text: str, job_analysis: dict, api_key: str = "", tone: str = "formal") -> str:
    """Return cover letter body text (3 paragraphs)."""
    system = _SYSTEM_BASE + _TONE_ADDENDA.get(tone, _TONE_ADDENDA["formal"])
    client = get_client(api_key)
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": USER_TEMPLATE.format(
                title=job_analysis.get("title", ""),
                company=job_analysis.get("company", ""),
                required_skills=", ".join(job_analysis.get("required_skills", [])),
                keywords=", ".join(job_analysis.get("keywords", [])),
                cv_text=cv_text,
            )},
        ],
        max_tokens=1024,
        temperature=0.4,
    )
    return response.choices[0].message.content.strip()


def _slug(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_")


def save_cover_letter(letter_text: str, job_title: str, company: str, applicant_name: str = "", output_dir: Path | None = None) -> Path:
    """Save cover letter as a clean DOCX file."""
    from docx import Document
    from docx.shared import Pt

    doc = Document()

    for section in doc.sections:
        section.top_margin = Pt(72)
        section.bottom_margin = Pt(72)
        section.left_margin = Pt(72)
        section.right_margin = Pt(72)

    for para in doc.paragraphs:
        para._element.getparent().remove(para._element)

    def add_para(text, bold=False):
        para = doc.add_paragraph()
        run = para.add_run(text)
        run.font.size = Pt(11)
        run.bold = bold
        para.paragraph_format.space_after = Pt(8)

    today_str = date.today().strftime("%B %d, %Y")
    add_para(today_str)
    add_para("Hiring Manager")
    add_para(company)
    doc.add_paragraph()
    add_para(f"Re: Application for {job_title}", bold=True)
    doc.add_paragraph()
    add_para("Dear Hiring Manager,")
    doc.add_paragraph()

    for paragraph in letter_text.split("\n\n"):
        paragraph = paragraph.strip()
        if paragraph:
            add_para(paragraph)
            doc.add_paragraph()

    add_para("Sincerely,")
    doc.add_paragraph()
    if applicant_name:
        add_para(applicant_name, bold=True)

    today = date.today().strftime("%Y%m%d")
    filename = f"CoverLetter_{_slug(company)}_{_slug(job_title)}_{today}.docx"
    output_path = (output_dir or COVER_LETTERS_DIR) / filename
    doc.save(output_path)
    return output_path
