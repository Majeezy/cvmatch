"""Export tailored CV and cover letter as PDF using fpdf2."""
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import TAILORED_CVS_DIR, COVER_LETTERS_DIR


def _slug(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", text or "").strip("_")


def export_cv_pdf(cv_text: str, job_title: str, company: str, output_dir: Path | None = None) -> Path:
    """Convert structured CV plain text (## / ### / bullet) to a formatted PDF."""
    from fpdf import FPDF

    class _PDF(FPDF):
        pass

    pdf = _PDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(20, 18, 20)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    for line in cv_text.splitlines():
        s = line.strip()
        if not s:
            pdf.ln(2)
            continue

        if s.startswith("## "):
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(31, 73, 125)
            pdf.ln(3)
            pdf.cell(0, 7, s[3:].upper(), ln=True)
            pdf.set_draw_color(31, 73, 125)
            pdf.set_line_width(0.4)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
            pdf.ln(2)
            pdf.set_text_color(30, 30, 30)

        elif s.startswith("### "):
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(40, 40, 40)
            pdf.ln(1)
            pdf.cell(0, 6, s[4:], ln=True)

        elif s.startswith(("- ", "• ")):
            pdf.set_font("Helvetica", "", 9.5)
            pdf.set_text_color(55, 55, 55)
            pdf.cell(5, 5.5, chr(149))  # bullet
            pdf.multi_cell(0, 5.5, s.lstrip("-• "), ln=True)

        else:
            pdf.set_font("Helvetica", "", 9.5)
            pdf.set_text_color(55, 55, 55)
            pdf.multi_cell(0, 5.5, s, ln=True)

    today = date.today().strftime("%Y%m%d")
    fname = f"{_slug(company)}_{_slug(job_title)}_{today}.pdf"
    out_dir = output_dir or TAILORED_CVS_DIR
    out = out_dir / fname
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out))
    return out


def export_cl_pdf(cl_text: str, job_title: str, company: str, applicant_name: str = "", output_dir: Path | None = None) -> Path:
    """Export cover letter text as a clean PDF."""
    from fpdf import FPDF

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(25, 22, 25)
    pdf.set_auto_page_break(auto=True, margin=22)
    pdf.add_page()
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(40, 40, 40)

    for para in cl_text.split("\n\n"):
        para = para.strip()
        if para:
            pdf.multi_cell(0, 6.5, para, ln=True)
            pdf.ln(4)

    today = date.today().strftime("%Y%m%d")
    fname = f"CoverLetter_{_slug(company)}_{_slug(job_title)}_{today}.pdf"
    out = COVER_LETTERS_DIR / fname
    COVER_LETTERS_DIR.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out))
    return out
