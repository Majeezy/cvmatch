"""Generate tailored interview questions using Groq."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_client, MODEL

SYSTEM = (
    "You are an expert interview coach. Generate targeted, role-specific interview questions "
    "tailored to both the job requirements and the candidate's actual background. "
    "Return ONLY valid JSON — no markdown fences, no extra text."
)

USER_TEMPLATE = """\
Generate interview questions for this candidate and role.

Job Title: {title}
Company: {company}
Seniority: {seniority}
Required Skills: {required_skills}

--- CANDIDATE CV (excerpt) ---
{cv_text}
--- END ---

Return this JSON:
{{
  "technical": [
    "4-5 technical/skills-based questions specific to the required skills and the candidate's background"
  ],
  "behavioral": [
    "3-4 STAR-format behavioral questions (Situation, Task, Action, Result) relevant to the role"
  ],
  "situational": [
    "2-3 hypothetical scenario questions the candidate should prepare for"
  ],
  "company_role": [
    "2 questions about this specific company or role context"
  ],
  "to_ask_interviewer": [
    "3 thoughtful, specific questions the candidate should ask the interviewer"
  ]
}}
"""


def generate_interview_questions(cv_text: str, job_analysis: dict, api_key: str = "") -> dict:
    client = get_client(api_key)
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": USER_TEMPLATE.format(
                title=job_analysis.get("title", ""),
                company=job_analysis.get("company", ""),
                seniority=job_analysis.get("seniority_level", ""),
                required_skills=", ".join(job_analysis.get("required_skills", [])),
                cv_text=cv_text[:3000],
            )},
        ],
        max_tokens=1500,
        temperature=0.4,
    )
    raw = resp.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    return json.loads(raw)
