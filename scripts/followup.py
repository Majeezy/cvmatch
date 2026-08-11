"""Generate a professional follow-up email for a job application."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_client, MODEL

SYSTEM = """\
You are a professional career coach. Write concise, confident follow-up emails for job applications.

Format your output exactly as:
Subject: <subject line>

<email body — 3 short paragraphs, formal but warm tone, under 150 words total>

Rules:
- Do not use placeholder text like [Your Name], [Date], [Company Name]
- Do not include a sign-off name line
- Do not include "Dear Hiring Manager" — start with the first paragraph directly
- Keep it short: hiring managers are busy
"""

USER_TEMPLATE = """\
Write a follow-up email for this application.

Role: {title}
Company: {company}
Applicant name: {name}
Days since applying: {days}
Current application status: {status}
Additional context: {context}
"""


def generate_followup_email(
    job_title: str,
    company: str,
    applicant_name: str = "",
    days_since: int = 7,
    status: str = "Applied",
    context: str = "",
    api_key: str = "",
) -> dict:
    client = get_client(api_key)
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": USER_TEMPLATE.format(
                title=job_title,
                company=company,
                name=applicant_name or "the applicant",
                days=days_since,
                status=status,
                context=context or "No additional context provided.",
            )},
        ],
        max_tokens=400,
        temperature=0.4,
    )
    text = resp.choices[0].message.content.strip()

    subject = ""
    body_lines = []
    in_body = False
    for line in text.split("\n"):
        if line.lower().startswith("subject:"):
            subject = line[8:].strip()
        elif subject and not in_body and line.strip() == "":
            in_body = True
        elif in_body:
            body_lines.append(line)

    body = "\n".join(body_lines).strip() or text
    return {"subject": subject, "body": body}
