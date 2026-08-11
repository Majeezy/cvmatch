"""Authentication — signup/login/logout, backed by Flask-Login + the User model."""
import re

from flask import Blueprint, jsonify, request
from flask_login import LoginManager, current_user, login_required, login_user, logout_user

from models import User, db

login_manager = LoginManager()
auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def init_auth(app):
    login_manager.init_app(app)
    login_manager.login_view = None  # API-only; no redirect, routes return 401

    @login_manager.unauthorized_handler
    def _unauthorized():
        return jsonify({"error": "Not authenticated"}), 401

    app.register_blueprint(auth_bp)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def _user_dict(user: User) -> dict:
    return {"id": user.id, "email": user.email, "name": user.name or ""}


@auth_bp.route("/signup", methods=["POST"])
def signup():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    name = data.get("name", "").strip()

    if not _EMAIL_RE.match(email):
        return jsonify({"error": "Enter a valid email address"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "An account with that email already exists"}), 409

    user = User(email=email, name=name)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    login_user(user)
    return jsonify(_user_dict(user))


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid email or password"}), 401

    login_user(user, remember=True)
    return jsonify(_user_dict(user))


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return jsonify({"ok": True})


@auth_bp.route("/me")
def me():
    if not current_user.is_authenticated:
        return jsonify({"error": "Not authenticated"}), 401
    return jsonify(_user_dict(current_user))


@auth_bp.route("/change-password", methods=["POST"])
@login_required
def change_password():
    data = request.get_json(silent=True) or {}
    current_password = data.get("current_password", "")
    new_password = data.get("new_password", "")

    if not current_user.check_password(current_password):
        return jsonify({"error": "Current password is incorrect"}), 401
    if len(new_password) < 8:
        return jsonify({"error": "New password must be at least 8 characters"}), 400

    current_user.set_password(new_password)
    db.session.commit()
    return jsonify({"ok": True})
