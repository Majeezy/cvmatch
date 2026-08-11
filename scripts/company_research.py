"""Generate a company research brief for interview preparation."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_client, MODEL

_SYSTEM = (
    "You are a business analyst helping a job seeker prepare for an interview. "
    "Generate a comprehensive company research brief from your training knowledge. "
    "Be honest when information may be outdated or uncertain. "
    "Return ONLY valid JSON — no markdown fences, no extra text."
)

_USER = """\
Generate a research brief for a job interview at this company.

Company: {company}
Role: {title}
Industry: {industry}
Seniority: {seniority}

Return:
{{
  "overview": "2-3 sentence company description (size, stage, mission)",
  "business_model": "How the company makes money",
  "key_products": ["main products or services — be specific"],
  "tech_stack": ["known technologies/tools they use, if relevant to this role"],
  "culture_signals": ["3-4 culture/values notes relevant to working there"],
  "recent_news": ["2-3 notable developments — prefix uncertain items with [VERIFY]"],
  "interview_tips": ["3-4 role-specific preparation tips"],
  "talking_points": ["3 things to mention in the interview to impress"],
  "questions_to_ask": ["4 smart, specific questions for the interviewer"],
  "concerns": ["any publicly known concerns worth researching — layoffs, culture issues, etc."],
  "disclaimer": "One sentence noting data is from model training and should be verified"
}}
"""


def research_company(company: str, job_title: str, industry: str = "", seniority: str = "", api_key: str = "") -> dict:
    client = get_client(api_key)
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": _USER.format(
                company=company or "Unknown Company",
                title=job_title,
                industry=industry or "not specified",
                seniority=seniority or "not specified",
            )},
        ],
        max_tokens=1500,
        temperature=0.3,
    )
    raw = resp.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    return json.loads(raw)
