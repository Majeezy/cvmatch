"""Detect red flags and positive signals in a job description."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_client, MODEL

_SYSTEM = (
    "You are a senior recruiter and career coach who helps job seekers evaluate opportunities. "
    "Analyze job descriptions for concerning patterns AND genuine positives. Be balanced. "
    "Return ONLY valid JSON — no markdown fences, no extra text."
)

_USER = """\
Analyze this job description for red flags and positive signals.

Job Title: {title}
Company: {company}

--- JOB DESCRIPTION ---
{jd_text}
--- END ---

Return:
{{
  "overall_risk": "low | medium | high",
  "overall_verdict": "1-2 sentence balanced assessment",
  "red_flags": [
    {{
      "flag": "description of the concern",
      "category": "compensation | scope creep | culture | requirements | transparency | other",
      "severity": "low | medium | high",
      "quote": "exact excerpt from JD that raised this flag"
    }}
  ],
  "positive_signals": ["genuine good signs in the posting"],
  "vague_claims": ["claims that are suspiciously vague or unverifiable"],
  "questions_to_investigate": ["specific questions to ask in the interview to probe concerns"],
  "research_suggestions": ["things to search/verify before applying"]
}}
"""

_LOCAL_PATTERNS = [
    (r"unlimited\s+pto", "Unlimited PTO — often signals no real PTO culture", "medium", "compensation"),
    (r"wear\s+many\s+hats", "'Wear many hats' — may indicate understaffed team", "medium", "scope creep"),
    (r"competitive\s+salary", "Vague 'competitive salary' — no salary range disclosed", "medium", "compensation"),
    (r"fast[- ]paced\s+environment", "Fast-paced environment — can indicate high-pressure culture", "low", "culture"),
    (r"startup\s+(spirit|culture|mentality)", "Startup culture language — may mean long hours with startup pay", "low", "culture"),
    (r"(\d+)\+?\s+years.{0,30}(experience|exp).{0,50}(\d+)\s+years.{0,20}(old|ago|since\s+20)", "Years of experience may exceed tool's age", "high", "requirements"),
    (r"must\s+be\s+available\s+(24|any)", "24/7 availability requirement", "high", "scope creep"),
    (r"(unpaid|no\s+compensation|volunteer)", "Unpaid or volunteer position", "high", "compensation"),
    (r"confidential\s+(company|employer|client)", "Anonymous employer — inability to research company culture", "medium", "transparency"),
]


def _local_scan(jd_text: str) -> list[dict]:
    found = []
    lower = jd_text.lower()
    for pattern, flag, severity, category in _LOCAL_PATTERNS:
        m = re.search(pattern, lower)
        if m:
            start = max(0, m.start() - 20)
            end = min(len(jd_text), m.end() + 40)
            found.append({
                "flag": flag,
                "category": category,
                "severity": severity,
                "quote": jd_text[start:end].strip(),
            })
    return found


def detect_red_flags(jd_text: str, job_analysis: dict, api_key: str = "") -> dict:
    local_flags = _local_scan(jd_text)
    client = get_client(api_key)
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": _USER.format(
                title=job_analysis.get("title", ""),
                company=job_analysis.get("company", "Unknown"),
                jd_text=jd_text[:4000],
            )},
        ],
        max_tokens=1200,
        temperature=0.2,
    )
    raw = resp.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    result = json.loads(raw)
    # Prepend local regex flags (dedup by quote)
    existing_quotes = {f.get("quote", "")[:40] for f in result.get("red_flags", [])}
    for lf in local_flags:
        if lf["quote"][:40] not in existing_quotes:
            result.setdefault("red_flags", []).insert(0, lf)
    return result
