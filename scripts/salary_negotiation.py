"""Generate salary negotiation scripts for a job offer."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_client, MODEL

_SYSTEM = """\
You are an expert salary negotiation coach. Generate specific, confident, word-for-word negotiation scripts.
Be assertive without being aggressive. Use real numbers when provided.
Structure your output with these exact section headers on their own lines:
### OPENING EMAIL
### PHONE COUNTER SCRIPT
### HANDLING PUSHBACK
### NON-SALARY ITEMS TO NEGOTIATE
### WALK-AWAY SCRIPT
### MARKET POSITIONING
"""

_USER = """\
Generate a salary negotiation pack for this offer.

Role: {title}
Company: {company}
Offered Salary: {offered}
Target Salary: {target}
Currency: {currency}
Current Benefits: {benefits}
Location/Remote: {location}
Offer Deadline: {deadline}
Seniority: {seniority}
Key Strengths to Leverage: {strengths}
"""


def generate_negotiation_scripts(
    job_title: str,
    company: str,
    offered_salary: str = "not disclosed",
    target_salary: str = "market rate",
    currency: str = "USD",
    benefits: str = "standard",
    location: str = "on-site",
    deadline: str = "not specified",
    seniority: str = "",
    strengths: str = "",
    api_key: str = "",
) -> str:
    client = get_client(api_key)
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": _USER.format(
                title=job_title,
                company=company,
                offered=offered_salary,
                target=target_salary,
                currency=currency,
                benefits=benefits,
                location=location,
                deadline=deadline,
                seniority=seniority or "not specified",
                strengths=strengths or "strong relevant experience and track record",
            )},
        ],
        max_tokens=1500,
        temperature=0.4,
    )
    return resp.choices[0].message.content.strip()
