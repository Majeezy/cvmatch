"""Generate a learning roadmap to close the skills gap for a target role."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_client, MODEL

_SYSTEM = (
    "You are a senior career coach and tech educator. "
    "Create concrete, actionable learning roadmaps for job seekers. "
    "Use real platform names (Coursera, freeCodeCamp, official docs, YouTube, etc.). "
    "Return ONLY valid JSON — no markdown fences, no extra text."
)

_USER = """\
Create a skills gap roadmap for this candidate targeting this role.

Target Role: {title}
Seniority Target: {seniority}
Missing Skills: {missing_skills}
Current Skills (from CV): {current_skills}

Return:
{{
  "priority_order": ["skills in recommended learning order"],
  "quick_wins": ["skills learnable in under 2 weeks — tackle these first"],
  "roadmap": [
    {{
      "skill": "skill name",
      "priority": "critical | nice-to-have",
      "current_level": "none | beginner | intermediate",
      "target_level": "level needed for this role",
      "weeks_estimate": <integer>,
      "resources": [
        {{
          "name": "resource name",
          "platform": "Coursera / YouTube / docs / book / project",
          "type": "course | tutorial | documentation | project | certification",
          "free": true or false,
          "search_hint": "exact search term to find it"
        }}
      ],
      "week_one_action": "Specific thing to do in the first week"
    }}
  ],
  "total_weeks_estimate": <integer>,
  "immediate_actions": ["3 things to do this week to start"],
  "study_plan": "Brief suggested weekly schedule (e.g. 1hr/day, focus on X first)"
}}
"""


def generate_skills_roadmap(missing_skills: list, current_skills: list, job_analysis: dict, api_key: str = "") -> dict:
    if not missing_skills:
        return {
            "priority_order": [],
            "quick_wins": [],
            "roadmap": [],
            "total_weeks_estimate": 0,
            "immediate_actions": ["No missing skills identified — focus on tailoring your CV keywords"],
            "study_plan": "Your skills match this role well.",
        }
    client = get_client(api_key)
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": _USER.format(
                title=job_analysis.get("title", ""),
                seniority=job_analysis.get("seniority_level", ""),
                missing_skills=", ".join(missing_skills),
                current_skills=", ".join(current_skills) or "not specified",
            )},
        ],
        max_tokens=2000,
        temperature=0.3,
    )
    raw = resp.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    return json.loads(raw)
