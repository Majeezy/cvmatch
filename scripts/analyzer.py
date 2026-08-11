"""Analyze a job description and extract structured requirements using Groq."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_client, MODEL

SYSTEM = (
    "You are a job requirements analyst. Extract structured information from job descriptions. "
    "Return ONLY valid JSON with no markdown fences or extra text. "
    "Extract only what is explicitly stated — do not infer or guess."
)

USER_TEMPLATE = """\
Extract the following from this job description and return as JSON:
{{
  "title": "job title as written",
  "company": "company name, or null if not found",
  "seniority_level": "junior/mid/senior/lead/principal or null",
  "required_skills": ["list of must-have technical and soft skills"],
  "nice_to_have": ["list of optional/preferred skills"],
  "responsibilities": ["key responsibilities, max 8"],
  "keywords": ["important ATS keywords: tools, technologies, methodologies, certifications"],
  "industry": "industry or sector, or null"
}}

Job Description:
{job_text}
"""


def analyze_job(job_text: str, api_key: str = "") -> dict:
    """Return structured job analysis as a dict."""
    client = get_client(api_key)
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": USER_TEMPLATE.format(job_text=job_text)},
        ],
        max_tokens=1024,
        temperature=0.1,
    )
    raw = response.choices[0].message.content.strip()

    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    return json.loads(raw)
