"""Optimize LinkedIn profile sections for a specific target role."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_client, MODEL

_SYSTEM = (
    "You are a LinkedIn optimization expert and personal branding coach. "
    "Rewrite profile sections to attract recruiters for a specific role. "
    "Headlines must be under 220 characters. About must be under 2000 characters. "
    "Return ONLY valid JSON — no markdown fences, no extra text."
)

_USER = """\
Optimize these LinkedIn sections for the target role below.

Target Role: {title}
Company Type / Industry: {industry}
Required Skills: {required_skills}
ATS Keywords to Include: {keywords}

--- CURRENT LINKEDIN CONTENT ---
Headline: {headline}
About/Summary:
{about}
--- END ---

Return:
{{
  "headline_options": [
    {{"text": "headline option 1 (≤220 chars)", "angle": "what positioning angle this takes"}},
    {{"text": "headline option 2", "angle": "angle"}},
    {{"text": "headline option 3", "angle": "angle"}}
  ],
  "about_section": "Full rewritten About/Summary (≤2000 chars, first-person, keyword-rich, ends with call to action)",
  "skills_to_add": ["up to 10 skills to add to the Skills section for this role"],
  "skills_to_pin": ["top 3 to feature/pin"],
  "keyword_injection_tips": ["specific phrases to weave into existing experience bullets"],
  "quick_profile_wins": ["4 other quick profile improvements (photo, banner, URL, featured section, etc.)"]
}}
"""


def optimize_linkedin_profile(
    headline: str,
    about: str,
    job_analysis: dict,
    api_key: str = "",
) -> dict:
    client = get_client(api_key)
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": _USER.format(
                title=job_analysis.get("title", ""),
                industry=job_analysis.get("industry", "not specified"),
                required_skills=", ".join(job_analysis.get("required_skills", [])),
                keywords=", ".join(job_analysis.get("keywords", [])),
                headline=headline or "(not provided — write a strong default)",
                about=about or "(not provided — write from scratch)",
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
