"""PayFast integration — signing, ITN (webhook) validation, and the
Subscriptions management API. No Flask dependency here on purpose: this is
the part of billing that most needs isolated testing, since a signature bug
fails silently (PayFast just rejects the request) rather than raising.

PayFast has two *different*, non-interchangeable signature schemes:
  - "Custom Integration" (the hosted payment form, and ITN webhooks that
    come from it): fields in the order PayFast's own attribute docs list
    them -- NOT alphabetical. PayFast's docs site is a JS app that
    wouldn't render for automated fetching while building this, so the
    field order below was reverse-engineered empirically: posted straight
    to sandbox.payfast.co.za/eng/process and iterated on the real error
    responses until accepted (confirmed via a real 302 redirect to a
    genuine PayFast payment page, both for a one-off payment and for the
    subscription flow `build_subscription_checkout_fields` actually
    builds). The one real bug this caught: `custom_str1` has to come
    *before* the subscription-specific
    fields, not after -- putting it last (the obvious place to add it)
    produced a signature mismatch that a less direct test would have
    missed entirely.
  - The REST Subscriptions API (pause/cancel/fetch on an existing
    subscription, in the second half of this file): alphabetically-sorted
    fields, header-based auth. Unlike the checkout flow above, this has
    NOT been verified against a live sandbox call -- doing so needs an
    actual active subscription token, which means completing a real
    sandbox payment with a test card first. Treat it as unverified until
    that happens.

Both schemes: MD5 hex digest of `key=value&key=value...` with each value
URL-encoded the way a web form encodes it -- spaces as `+`, via
urllib.parse.quote_plus, NOT quote()/%20. This is a well-documented
footgun; getting it wrong produces a signature that's wrong in a way
that's easy to not notice (it's still 32 hex chars, just the wrong ones).
"""
import hashlib
import os
import socket
import time
from urllib.parse import quote_plus

import requests

MERCHANT_ID = os.environ.get("PAYFAST_MERCHANT_ID", "")
MERCHANT_KEY = os.environ.get("PAYFAST_MERCHANT_KEY", "")
PASSPHRASE = os.environ.get("PAYFAST_PASSPHRASE", "")
SANDBOX = os.environ.get("PAYFAST_SANDBOX", "true").lower() == "true"

_HOST = "sandbox.payfast.co.za" if SANDBOX else "www.payfast.co.za"
PROCESS_URL = f"https://{_HOST}/eng/process"
VALIDATE_URL = f"https://{_HOST}/eng/query/validate"
SUBSCRIPTIONS_API = "https://api.payfast.co.za/v1"

# Documented frequency codes for the `frequency` field.
FREQUENCY_MONTHLY = 3

# Known PayFast ITN source ranges. Incomplete -- PayFast's own "Ports and
# IP addresses" doc page is the canonical list and wasn't fetchable while
# building this. Used as a soft signal (logged, not a hard reject) below,
# specifically because an incomplete list must never be the reason a real
# payment gets silently dropped.
_KNOWN_RANGE_PREFIX = "197.97.145."


def _encode_form_fields(fields: dict) -> str:
    """`key=value&key=value...`, values space-encoded as `+`, blanks
    dropped, in the exact order `fields` iterates -- caller is
    responsible for passing an already-ordered dict."""
    parts = [
        f"{key}={quote_plus(str(value).strip())}"
        for key, value in fields.items()
        if value not in (None, "")
    ]
    return "&".join(parts)


def _sign(fields: dict) -> str:
    encoded = _encode_form_fields(fields)
    if PASSPHRASE:
        encoded += f"&passphrase={quote_plus(PASSPHRASE)}"
    return hashlib.md5(encoded.encode("utf-8")).hexdigest()


def build_subscription_checkout_fields(
    *,
    user_id: int,
    email: str,
    name_first: str,
    amount_zar: str,
    item_name: str,
    return_url: str,
    cancel_url: str,
    notify_url: str,
) -> dict:
    """Fields for the auto-submitting checkout form (see templates/payfast_redirect.html).
    `amount_zar` is a decimal string like "99.00" -- PayFast takes major
    units, not cents.
    """
    fields = {
        "merchant_id": MERCHANT_ID,
        "merchant_key": MERCHANT_KEY,
        "return_url": return_url,
        "cancel_url": cancel_url,
        "notify_url": notify_url,
        "name_first": name_first or "",
        "email_address": email,
        "m_payment_id": f"user-{user_id}-{int(time.time())}",
        "amount": amount_zar,
        "item_name": item_name,
        "custom_str1": str(user_id),  # round-tripped on every ITN
        "subscription_type": 1,
        "recurring_amount": amount_zar,
        "frequency": FREQUENCY_MONTHLY,
        "cycles": 0,  # bills indefinitely until cancelled
    }
    fields["signature"] = _sign(fields)
    return fields


def verify_itn_signature(posted_fields: dict) -> bool:
    """`posted_fields` as received (e.g. request.form), including PayFast's
    own `signature` field, which is excluded from the recomputation and
    compared against."""
    their_signature = posted_fields.get("signature", "")
    ours = dict(posted_fields)
    ours.pop("signature", None)
    return _sign(ours) == their_signature


def verify_source_host(remote_addr: str) -> bool:
    """Best-effort: true if we're confident this is PayFast, False if we're
    confident it's NOT, None if inconclusive. An inconclusive result must
    not by itself reject a webhook -- see the four-step validation in
    billing.py, where the signature and validate-endpoint checks below
    carry the real weight."""
    if remote_addr.startswith(_KNOWN_RANGE_PREFIX):
        return True
    try:
        hostname = socket.gethostbyaddr(remote_addr)[0]
    except (socket.herror, socket.gaierror, OSError):
        return None
    return "payfast.co.za" in hostname


def validate_with_payfast(raw_body: bytes) -> bool:
    """POST the raw ITN body back to PayFast and require a literal `VALID`
    response -- the strongest of the four checks, since it means PayFast
    itself is vouching for this exact payload."""
    try:
        resp = requests.post(
            VALIDATE_URL,
            data=raw_body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
        return resp.text.strip() == "VALID"
    except requests.RequestException:
        return False


# ── Subscriptions management API (separate auth scheme — see module
# docstring) ─────────────────────────────────────────────────────────────

def _subscriptions_api_headers(request_body: str = "") -> dict:
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
    # Alphabetical per the REST variant of PayFast's signing scheme.
    to_sign = {
        "merchant-id": MERCHANT_ID,
        "timestamp": timestamp,
        "version": "v1",
    }
    if request_body:
        to_sign["request-body"] = request_body
    ordered = dict(sorted(to_sign.items()))
    signature = _sign(ordered)
    return {
        "merchant-id": MERCHANT_ID,
        "version": "v1",
        "timestamp": timestamp,
        "signature": signature,
    }


def cancel_subscription(token: str) -> bool:
    """Best-effort cancel via the Subscriptions API. Not yet verified
    against a live sandbox call (see module docstring) -- the webhook
    ('customer.subscription.deleted'-equivalent ITN) is the authoritative
    source of truth for plan state either way, this just asks PayFast to
    stop billing."""
    try:
        resp = requests.put(
            f"{SUBSCRIPTIONS_API}/subscriptions/{token}/cancel",
            headers=_subscriptions_api_headers(),
            timeout=10,
        )
        return resp.status_code == 200
    except requests.RequestException:
        return False


def fetch_subscription_status(token: str) -> dict | None:
    """Reconciliation path — lets `/api/billing/status` double-check
    against PayFast directly rather than trusting only webhook state,
    since there's no hosted customer portal to redirect users to for a
    live view the way Stripe's billing portal provides."""
    try:
        resp = requests.get(
            f"{SUBSCRIPTIONS_API}/subscriptions/{token}/fetch",
            headers=_subscriptions_api_headers(),
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json()
    except requests.RequestException:
        pass
    return None
