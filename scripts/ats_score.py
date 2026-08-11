"""Simulate ATS scoring of a CV against a job description."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_client, MODEL

_SYSTEM = (
    "You are an ATS (Applicant Tracking System) expert. Simulate how enterprise ATS software "
    "scores a CV. Return ONLY valid JSON — no markdown fences, no extra text."
)

_USER = """\
Simulate ATS scoring for this CV against the job below.

Job Title: {title}
Required Skills: {required_skills}
Keywords: {keywords}

--- CV TEXT ---
{cv_text}
--- END ---

Return exactly:
{{
  "ats_score": <integer 0-100>,
  "keyword_hits": ["keywords from the JD clearly present in the CV"],
  "keyword_misses": ["important JD keywords absent from the CV"],
  "formatting_flags": ["ATS-hostile formatting issues detected (tables, columns, graphics, special chars, etc.)"],
  "section_scores": {{
    "contact_info": <0-100>,
    "summary": <0-100>,
    "work_experience": <0-100>,
    "skills_section": <0-100>,
    "education": <0-100>
  }},
  "recommendations": ["3-5 specific, ordered-by-impact changes to improve ATS score"]
}}
"""


def _local_checks(cv_text: str) -> list[str]:
    """Fast regex checks for common ATS-hostile patterns."""
    flags = []
    if re.search(r"\|{2,}", cv_text):
        flags.append("Table-style formatting detected (pipe characters) — ATS may misread columns")
    if len(re.findall(r"[^\x00-\x7F]", cv_text)) > 10:
        flags.append("Non-ASCII/special characters detected — may be stripped by ATS")
    if re.search(r"(linkedin\.com|github\.com)", cv_text, re.I) and "@" not in cv_text:
        flags.append("Email address not found in CV — contact section may be incomplete")
    if len(cv_text) > 8000:
        flags.append("CV text is very long — consider condensing to improve ATS parse quality")
    return flags


def simulate_ats_score(cv_text: str, job_analysis: dict, api_key: str = "") -> dict:
    local_flags = _local_checks(cv_text)
    client = get_client(api_key)
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": _USER.format(
                title=job_analysis.get("title", ""),
                required_skills=", ".join(job_analysis.get("required_skills", [])),
                keywords=", ".join(job_analysis.get("keywords", [])),
                cv_text=cv_text[:4500],
            )},
        ],
        max_tokens=1024,
        temperature=0.1,
    )
    raw = resp.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    result = json.loads(raw)
    # Merge local regex flags with LLM flags
    result["formatting_flags"] = local_flags + result.get("formatting_flags", [])
    return result
