"""Transactional email via Resend — verification emails only, for now.

Mirrors the lazy-client pattern used elsewhere in this project (Groq
client built per-call, not at import time): a missing RESEND_API_KEY
should only break the actual send, not importing this module or anything
that imports it.
"""
import os

import requests

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
EMAIL_FROM = os.environ.get("EMAIL_FROM", "ORBITAL Careers <onboarding@resend.dev>")


def send_verification_email(to: str, name: str, verify_url: str) -> bool:
    """Returns True if Resend accepted the send, False otherwise (including
    when RESEND_API_KEY isn't set) -- callers should never let a failed
    send block signup itself, the same way the hospital-platform project's
    password-reset email isn't allowed to block the reset it's for."""
    if not RESEND_API_KEY:
        return False
    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
            json={
                "from": EMAIL_FROM,
                "to": to,
                "subject": "Verify your ORBITAL Careers account",
                "text": (
                    f"Hi {name or 'there'},\n\n"
                    f"Confirm your email to finish setting up your ORBITAL Careers "
                    f"account:\n\n{verify_url}\n\n"
                    f"If you didn't create this account, you can ignore this email.\n"
                ),
            },
            timeout=10,
        )
        return resp.status_code < 300
    except requests.RequestException:
        return False
