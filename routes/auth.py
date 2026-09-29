"""Sign in / sign out, and first-run account creation.

Uses Flask's signed session cookie rather than an extra login library —
one small guard (see app.py) covers every page, which is easier to check
than a decorator that could be forgotten on a new route.
"""

from urllib.parse import urlparse

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    current_app,
)
from werkzeug.security import generate_password_hash

from extensions import db
from models.user import User, MIN_PASSWORD_LENGTH
from utils.validators import parse_required_text

auth_bp = Blueprint("auth", __name__)

# Endpoints reachable without signing in. Everything else is guarded.
PUBLIC_ENDPOINTS = {"auth.login", "auth.setup", "static"}


def current_user():
    """The signed-in user, or None. Cheap enough to call per request."""
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.session.get(User, user_id)


def any_user_exists():
    return db.session.query(User.id).first() is not None


def _safe_next(target):
    """Only allow redirects back into this site.

    Without this, /login?next=https://evil.example would bounce a
    freshly-signed-in owner straight off to someone else's page.
    """
    if not target:
        return None
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc:
        return None
    if not target.startswith("/") or target.startswith("//"):
        return None
    return target


def _start_session(user):
    # Clear first so a session handed to the browser before signing in
    # cannot be reused afterwards (session fixation).
    session.clear()
    session["user_id"] = user.id
    session.permanent = True


@auth_bp.route("/setup", methods=["GET", "POST"])
def setup():
    """Create the first account. Closed as soon as one exists."""
    if any_user_exists():
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        try:
            username = parse_required_text(request.form.get("username"), "Username", 80)
            password = request.form.get("password") or ""
            confirm = request.form.get("confirm_password") or ""

            if len(password) < MIN_PASSWORD_LENGTH:
                raise ValueError(
                    f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
                )
            if password != confirm:
                raise ValueError("The two passwords do not match.")

            user = User(username=username)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()

            _start_session(user)
            flash("Account created. Now create your first business.", "success")
            return redirect(url_for("businesses.select"))
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "error")

    return render_template("auth/setup.html", min_length=MIN_PASSWORD_LENGTH)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if not any_user_exists():
        return redirect(url_for("auth.setup"))

    if session.get("user_id"):
        return redirect(url_for("dashboard.index"))

    next_url = _safe_next(request.args.get("next"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = User.query.filter_by(username=username).first()

        if user and user.is_locked:
            flash(
                f"Too many failed attempts. Try again in {user.lock_minutes_left} minute(s).",
                "error",
            )
        elif user and user.check_password(password):
            user.register_success()
            db.session.commit()
            _start_session(user)
            return redirect(_safe_next(request.form.get("next")) or url_for("dashboard.index"))
        else:
            if user:
                user.register_failure()
                db.session.commit()
            else:
                # Hash anyway so a missing username does not answer faster
                # than a wrong password and reveal which names exist.
                generate_password_hash(password or "x")
            # Deliberately vague: never say which half was wrong.
            flash("Incorrect username or password.", "error")

    return render_template("auth/login.html", next_url=next_url)


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Signed out.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/change-password", methods=["POST"])
def change_password():
    user = current_user()
    if not user:
        return redirect(url_for("auth.login"))

    try:
        current = request.form.get("current_password") or ""
        new = request.form.get("new_password") or ""
        confirm = request.form.get("confirm_password") or ""

        if not user.check_password(current):
            raise ValueError("Your current password is not correct.")
        if len(new) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"New password must be at least {MIN_PASSWORD_LENGTH} characters.")
        if new != confirm:
            raise ValueError("The two new passwords do not match.")

        user.set_password(new)
        db.session.commit()

        # Keep this browser signed in, but on a brand new session id.
        _start_session(user)
        flash("Password changed.", "success")
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "error")

    return redirect(url_for("settings.index"))
