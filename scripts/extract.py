"""Text extraction from PDF and DOCX files."""
from pathlib import Path


def extract_pdf(path: str | Path) -> str:
    """Extract text from a PDF file using pdfplumber."""
    import pdfplumber

    text_parts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n".join(text_parts)


def extract_docx(path: str | Path) -> str:
    """Extract text from a DOCX file using python-docx."""
    from docx import Document

    doc = Document(path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


def extract_text(path: str | Path) -> str:
    """Auto-detect file type and extract text."""
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return extract_pdf(path)
    elif suffix in (".docx", ".doc"):
        return extract_docx(path)
    elif suffix == ".txt":
        return path.read_text(encoding="utf-8", errors="ignore")
    else:
        raise ValueError(f"Unsupported file type: {suffix}. Use .pdf, .docx, or .txt")
