"""PayFast billing — checkout redirect, ITN webhook, plan/usage status.

PayFast has no hosted customer portal the way Stripe does, so "Manage
billing" becomes a direct cancel action against the Subscriptions API
(see payfast.py) rather than a redirect to a provider-hosted page.

Plan state (`User.plan`) only ever changes from the ITN webhook handler,
never from a frontend success callback -- a browser landing back on
`return_url` after PayFast checkout proves the user's browser was
redirected there, not that the payment actually completed.
"""
import json
import os
from datetime import date

from flask import Blueprint, Response, jsonify, request
from flask_login import current_user, login_required

import payfast
from config import FREE_MONTHLY_GENERATIONS
from models import Application, User, db

PRO_PRICE_ZAR = os.environ.get("PAYFAST_PRO_PRICE_ZAR", "99.00")

billing_bp = Blueprint("billing", __name__, url_prefix="/api/billing")
webhook_bp = Blueprint("payfast_webhook", __name__)


def init_billing(app):
    app.register_blueprint(billing_bp)
    app.register_blueprint(webhook_bp)


def generations_used_this_month(user_id: int) -> int:
    start_of_month = date.today().replace(day=1).isoformat()
    return Application.query.filter(
        Application.user_id == user_id,
        Application.date_applied >= start_of_month,
    ).count()


def check_generation_quota(user: User) -> str | None:
    """Return an error message if `user` can't generate right now, else None."""
    if user.plan == "pro":
        return None
    used = generations_used_this_month(user.id)
    if used >= FREE_MONTHLY_GENERATIONS:
        return (f"Free plan limit reached ({FREE_MONTHLY_GENERATIONS}/month). "
                f"Upgrade to Pro for unlimited generations.")
    return None


def check_bulk_apply_allowed(user: User) -> str | None:
    if user.plan != "pro":
        return "Bulk Apply is a Pro feature. Upgrade to use it."
    return None


def _request_scheme() -> str:
    """Render's edge is Cloudflare-fronted and doesn't set the standard
    X-Forwarded-Proto header ProxyFix looks for -- confirmed directly via
    a temporary debug route, not assumed. It sends `Cf-Visitor:
    {"scheme":"https"}` instead, so that's what actually needs reading to
    get return_url/notify_url right for PayFast behind Render's edge."""
    cf_visitor = request.headers.get("Cf-Visitor")
    if cf_visitor:
        try:
            scheme = json.loads(cf_visitor).get("scheme")
            if scheme:
                return scheme
        except (ValueError, AttributeError):
            pass
    return request.scheme


def _origin() -> str:
    if request.headers.get("Origin"):
        return request.headers["Origin"]
    host = request.headers.get("Host", request.host)
    return f"{_request_scheme()}://{host}"


@billing_bp.route("/status")
@login_required
def status():
    used = generations_used_this_month(current_user.id)
    return jsonify({
        "plan": current_user.plan,
        "subscription_status": current_user.subscription_status,
        "generations_used": used,
        "generations_limit": None if current_user.plan == "pro" else FREE_MONTHLY_GENERATIONS,
    })


@billing_bp.route("/create-checkout-session", methods=["POST"])
@login_required
def create_checkout_session():
    if not payfast.MERCHANT_ID or not payfast.MERCHANT_KEY:
        return jsonify({"error": "Billing is not configured yet"}), 500
    if not current_user.email_verified:
        return jsonify({"error": "Please verify your email before upgrading"}), 403
    # The actual signed form POST happens when the browser is sent to this
    # route (below) -- PayFast requires POSTed form fields, not a redirect
    # URL with query params, so there's no single "checkout URL" to hand
    # back the way Stripe's Checkout Session has.
    return jsonify({"url": "/api/billing/payfast-checkout"})


@billing_bp.route("/payfast-checkout")
@login_required
def payfast_checkout():
    origin = _origin()
    # PAYFAST_TEST_BUYER_EMAIL: sandbox-testing-only override. PayFast
    # blocks a checkout whose email_address matches the merchant
    # account's own registered email ("Merchant is unable to receive
    # payments from the same account") -- confirmed directly against the
    # sandbox, not assumed. When the same person owns both the PayFast
    # account and the only verified CVMatch test account, this override
    # lets that account still exercise the full checkout/webhook flow by
    # sending a different (non-deliverable, doesn't need to be) email to
    # PayFast specifically, without touching what CVMatch itself thinks
    # the user's email is. Unset in production -- current_user.email is
    # correct there, a real customer's email won't collide with the
    # merchant's.
    buyer_email = os.environ.get("PAYFAST_TEST_BUYER_EMAIL") or current_user.email
    fields = payfast.build_subscription_checkout_fields(
        user_id=current_user.id,
        email=buyer_email,
        name_first=current_user.name or "",
        amount_zar=PRO_PRICE_ZAR,
        item_name="CVMatch Pro (monthly)",
        return_url=f"{origin}/?billing=success",
        cancel_url=f"{origin}/?billing=cancel",
        notify_url=f"{origin}/webhook/payfast",
    )
    inputs = "\n".join(
        f'<input type="hidden" name="{key}" value="{str(value).replace(chr(34), "&quot;")}">'
        for key, value in fields.items()
    )
    # Auto-submitting form -- the standard PayFast "Custom Integration"
    # pattern. No styling needed, this page is on screen for a fraction of
    # a second before the redirect fires.
    html = f"""<!DOCTYPE html><html><body>
<form id="pfForm" action="{payfast.PROCESS_URL}" method="post">{inputs}</form>
<script>document.getElementById('pfForm').submit();</script>
Redirecting to PayFast...
</body></html>"""
    return Response(html, mimetype="text/html")


@billing_bp.route("/cancel-subscription", methods=["POST"])
@login_required
def cancel_subscription_route():
    if not current_user.payfast_token:
        return jsonify({"error": "No active subscription to cancel"}), 400
    ok = payfast.cancel_subscription(current_user.payfast_token)
    if not ok:
        return jsonify({"error": "Could not reach PayFast to cancel. Try again shortly."}), 502
    # Plan itself flips to "free" only once the cancellation ITN arrives
    # (see the webhook handler) -- this just records that a cancel request
    # was sent, so the UI can show "Cancelling..." in the meantime.
    current_user.subscription_status = "cancelling"
    db.session.commit()
    return jsonify({"ok": True})


@webhook_bp.route("/webhook/payfast", methods=["POST"])
def payfast_webhook():
    raw_body = request.get_data()
    fields = request.form.to_dict()

    # Four required checks (see payfast.py's module docstring for why each
    # one matters) -- any hard failure rejects the ITN outright.
    if not payfast.verify_itn_signature(fields):
        return jsonify({"error": "Invalid signature"}), 400

    # Same Cloudflare-fronted-edge situation as _request_scheme(): no
    # X-Forwarded-For either, the real client IP is in Cf-Connecting-Ip.
    # request.remote_addr alone would be Render's internal proxy address,
    # not PayFast's, making this check meaningless behind this edge.
    source_ip = request.headers.get("Cf-Connecting-Ip") or request.remote_addr or ""
    host_check = payfast.verify_source_host(source_ip)
    if host_check is False:
        return jsonify({"error": "Untrusted source"}), 400
    # host_check is None (inconclusive) falls through deliberately -- the
    # signature and validate-endpoint checks carry the real weight here.

    if not payfast.validate_with_payfast(raw_body):
        return jsonify({"error": "PayFast validation failed"}), 400

    user_id = fields.get("custom_str1")
    user = db.session.get(User, int(user_id)) if user_id else None
    if not user:
        return jsonify({"error": "Unknown user"}), 400

    expected_amount = float(PRO_PRICE_ZAR)
    posted_amount = float(fields.get("amount_gross", 0) or 0)
    payment_status = fields.get("payment_status", "")

    if payment_status == "COMPLETE":
        if abs(posted_amount - expected_amount) > 0.01:
            # Amount mismatch on an otherwise-valid, PayFast-confirmed ITN
            # -- don't silently grant Pro at the wrong price.
            return jsonify({"error": "Amount mismatch"}), 400
        user.plan = "pro"
        user.subscription_status = "active"
        token = fields.get("token")
        if token:
            user.payfast_token = token
        db.session.commit()
    elif payment_status == "CANCELLED":
        user.plan = "free"
        user.subscription_status = "cancelled"
        db.session.commit()
    elif payment_status == "FAILED":
        # A single failed recurring charge isn't necessarily the end of the
        # subscription (PayFast retries) -- record it, don't downgrade yet.
        user.subscription_status = "past_due"
        db.session.commit()

    return jsonify({"ok": True})
