"""Analyze a job application rejection and provide actionable feedback."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_client, MODEL

_SYSTEM = (
    "You are a compassionate but direct career coach. "
    "Help job seekers learn from rejections with honest, specific, actionable advice. "
    "Return ONLY valid JSON — no markdown fences, no extra text."
)

_USER = """\
Analyze this job rejection and give the candidate actionable feedback.

Role: {title}
Company: {company}
Date Applied: {date}
Stage Reached: {stage}
Rejection Feedback (if any): {feedback}

--- CANDIDATE CONTEXT ---
{cv_context}
--- END ---

Return:
{{
  "likely_reasons": [
    {{"reason": "description", "probability": "high | medium | low", "evidence": "what in the context suggests this"}}
  ],
  "cv_improvements": [
    {{"issue": "specific problem", "fix": "exact change to make", "example": "before -> after example if possible"}}
  ],
  "strategy_improvements": ["changes to the application approach for next time"],
  "positive_takeaways": ["what the candidate did well in this application"],
  "reapply_recommendation": "yes | no | wait_6_months",
  "reapply_reasoning": "why",
  "next_steps": ["3-5 prioritised concrete actions"],
  "similar_roles": ["2-3 alternative role titles that might be a better fit"],
  "encouragement": "One genuine, specific encouraging sentence"
}}
"""


def analyze_rejection(
    job_title: str,
    company: str,
    feedback: str = "",
    stage: str = "initial screening",
    date_applied: str = "",
    cv_context: str = "",
    api_key: str = "",
) -> dict:
    client = get_client(api_key)
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": _USER.format(
                title=job_title,
                company=company,
                date=date_applied or "not specified",
                stage=stage,
                feedback=feedback or "No feedback provided",
                cv_context=cv_context[:2000] or "No CV context available",
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
