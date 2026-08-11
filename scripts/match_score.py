"""Calculate CV-to-job match score using Groq."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_client, MODEL

SYSTEM = (
    "You are a recruitment expert and ATS specialist. "
    "Analyze the match between a CV and job description. "
    "Return ONLY valid JSON — no markdown fences, no extra text."
)

USER_TEMPLATE = """\
Score how well this CV matches the job below. Be realistic — honest gaps are useful.

Job Title: {title}
Seniority: {seniority}
Required Skills: {required_skills}
Key Keywords: {keywords}
Key Responsibilities:
{responsibilities}

--- CV ---
{cv_text}
--- END ---

Return exactly this JSON structure:
{{
  "overall_score": <integer 0-100>,
  "breakdown": {{
    "skills_match": <integer 0-100>,
    "experience_match": <integer 0-100>,
    "keywords_coverage": <integer 0-100>,
    "seniority_match": <integer 0-100>
  }},
  "matched_skills": ["skills from required list clearly present in CV"],
  "missing_skills": ["required skills NOT found in CV"],
  "strengths": ["2-3 key strengths relevant to this specific role"],
  "gaps": ["2-3 concrete gaps the candidate should address or emphasize differently"]
}}
"""


def calculate_match_score(cv_text: str, job_analysis: dict, api_key: str = "") -> dict:
    client = get_client(api_key)
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": USER_TEMPLATE.format(
                title=job_analysis.get("title", ""),
                seniority=job_analysis.get("seniority_level", ""),
                required_skills=", ".join(job_analysis.get("required_skills", [])),
                keywords=", ".join(job_analysis.get("keywords", [])),
                responsibilities="\n".join(
                    f"- {r}" for r in job_analysis.get("responsibilities", [])
                ),
                cv_text=cv_text[:4000],
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
    return json.loads(raw)
