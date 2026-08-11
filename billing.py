"""Stripe billing — checkout, billing portal, webhook, plan/usage status."""
import os
from datetime import date

import stripe
from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from config import FREE_MONTHLY_GENERATIONS
from models import Application, User, db

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
_PRICE_ID = os.environ.get("STRIPE_PRICE_ID", "")
_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

_ACTIVE_STATUSES = {"active", "trialing"}

billing_bp = Blueprint("billing", __name__, url_prefix="/api/billing")
webhook_bp = Blueprint("stripe_webhook", __name__)


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


def _origin() -> str:
    return request.headers.get("Origin") or request.url_root.rstrip("/")


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
    if not _PRICE_ID:
        return jsonify({"error": "Billing is not configured yet"}), 500
    try:
        if not current_user.stripe_customer_id:
            customer = stripe.Customer.create(email=current_user.email, name=current_user.name or None)
            current_user.stripe_customer_id = customer.id
            db.session.commit()

        origin = _origin()
        checkout_session = stripe.checkout.Session.create(
            mode="subscription",
            customer=current_user.stripe_customer_id,
            client_reference_id=str(current_user.id),
            line_items=[{"price": _PRICE_ID, "quantity": 1}],
            success_url=f"{origin}/?billing=success",
            cancel_url=f"{origin}/?billing=cancel",
        )
        return jsonify({"url": checkout_session.url})
    except stripe.error.StripeError as e:
        return jsonify({"error": str(e)}), 500


@billing_bp.route("/create-portal-session", methods=["POST"])
@login_required
def create_portal_session():
    if not current_user.stripe_customer_id:
        return jsonify({"error": "No billing account yet"}), 400
    try:
        portal_session = stripe.billing_portal.Session.create(
            customer=current_user.stripe_customer_id,
            return_url=f"{_origin()}/",
        )
        return jsonify({"url": portal_session.url})
    except stripe.error.StripeError as e:
        return jsonify({"error": str(e)}), 500


def _find_user(client_reference_id, stripe_customer_id) -> User | None:
    if client_reference_id:
        user = db.session.get(User, int(client_reference_id))
        if user:
            return user
    if stripe_customer_id:
        return User.query.filter_by(stripe_customer_id=stripe_customer_id).first()
    return None


@webhook_bp.route("/webhook/stripe", methods=["POST"])
def stripe_webhook():
    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, _WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError):
        return jsonify({"error": "Invalid signature"}), 400

    obj = event["data"]["object"]
    etype = event["type"]

    if etype == "checkout.session.completed":
        user = _find_user(obj.get("client_reference_id"), obj.get("customer"))
        if user:
            user.stripe_customer_id = obj.get("customer") or user.stripe_customer_id
            user.stripe_subscription_id = obj.get("subscription")
            user.plan = "pro"
            user.subscription_status = "active"
            db.session.commit()

    elif etype == "customer.subscription.updated":
        user = User.query.filter_by(stripe_customer_id=obj.get("customer")).first()
        if user:
            sub_status = obj.get("status")
            user.subscription_status = sub_status
            user.plan = "pro" if sub_status in _ACTIVE_STATUSES else "free"
            db.session.commit()

    elif etype == "customer.subscription.deleted":
        user = User.query.filter_by(stripe_customer_id=obj.get("customer")).first()
        if user:
            user.plan = "free"
            user.subscription_status = "canceled"
            db.session.commit()

    return jsonify({"ok": True})
