"""
Application factory for the Business Tracker.

PythonAnywhere's WSGI file imports `app` from this module (see wsgi.py /
README.md for the exact snippet), and `flask run` / `python app.py` both
work for local development too.
"""

import os

from flask import Flask

from config import config_by_name, INSTANCE_DIR, DEFAULT_SECRET_KEY
from extensions import db


def check_secret_key(app):
    """Refuse to serve real data with the placeholder signing key.

    The login session is a signed cookie, so a publicly-known key means
    anyone can forge one and skip the login page entirely. Failing at
    startup is noisy, but far better than looking secure and not being.
    """
    if app.config.get("DEBUG"):
        return
    if app.config.get("SECRET_KEY") != DEFAULT_SECRET_KEY:
        return
    raise RuntimeError(
        "SECRET_KEY is still the placeholder value, which would let anyone "
        "forge a login cookie. Set a real one before serving:\n"
        '  python -c "import secrets; print(secrets.token_hex(32))"\n'
        "then put it in the environment as SECRET_KEY (see README).\n"
        "For local development run with FLASK_ENV=development instead."
    )


def create_app(config_name=None):
    config_name = config_name or os.environ.get("FLASK_ENV", "production")
    config_name = config_name if config_name in config_by_name else "production"

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_by_name[config_name])
    check_secret_key(app)

    # Make sure the instance folder (holds the SQLite file) always exists,
    # both locally and on PythonAnywhere.
    os.makedirs(INSTANCE_DIR, exist_ok=True)

    db.init_app(app)

    register_auth(app)
    register_blueprints(app)
    register_template_helpers(app)
    register_cli_commands(app)
    register_error_handlers(app)

    with app.app_context():
        # Safe to call on every startup: create_all only creates tables
        # that do not already exist, so existing data is never touched.
        db.create_all()

        # create_all does not add columns to tables that already exist, so
        # top those up separately for databases created before a feature
        # shipped. Also a no-op once the columns are present.
        from utils.schema import (
            ensure_columns,
            migrate_expense_categories_table,
            ensure_default_business,
        )

        # Must run before ensure_columns()/ensure_default_business() touch
        # expense_categories: it rebuilds the table itself (see docstring).
        migrate_expense_categories_table(db)

        added = ensure_columns(db)
        if added:
            app.logger.info("Added missing database columns: %s", ", ".join(added))

        # Multi-business support: give any pre-existing data (recorded
        # before businesses existed) a home so it is not orphaned.
        default_business_name = ensure_default_business(db)
        if default_business_name:
            app.logger.info(
                "Created '%s' to hold pre-existing data", default_business_name
            )

    return app


def register_auth(app):
    """Require a signed-in user, with an active business chosen, for every
    page except the sign-in and business-selection ones.

    Deliberately a global guard rather than a per-route decorator: a new
    route added later is protected by default instead of only when
    somebody remembers the decorator.
    """
    from flask import request, redirect, url_for, g, flash
    from routes.auth import PUBLIC_ENDPOINTS, current_user, any_user_exists
    from routes.businesses import BUSINESS_EXEMPT_ENDPOINTS, resolve_current_business

    @app.before_request
    def require_login():
        endpoint = request.endpoint
        if endpoint is None or endpoint in PUBLIC_ENDPOINTS:
            return None

        g.user = current_user()
        if not g.user:
            # No accounts yet: send the owner to create the first one.
            if not any_user_exists():
                return redirect(url_for("auth.setup"))
            # Come back to the requested page after signing in.
            return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))

        g.business = resolve_current_business(g.user)
        if g.business is None and endpoint not in BUSINESS_EXEMPT_ENDPOINTS:
            # Without this message, bouncing back to the same page you just
            # tried to leave looks like the link is simply broken rather
            # than "you partner in more than one business — pick one first".
            flash("Choose a business to continue.", "error")
            return redirect(url_for("businesses.select"))

        return None

    @app.context_processor
    def inject_user():
        from flask import g as ctx_g

        return {
            "current_user": getattr(ctx_g, "user", None),
            "current_business": getattr(ctx_g, "business", None),
            "current_partnership": getattr(ctx_g, "partnership", None),
            "user_businesses": getattr(ctx_g, "businesses", None) or [],
        }


def register_blueprints(app):
    from routes.dashboard import dashboard_bp
    from routes.customers import customers_bp
    from routes.products import products_bp
    from routes.sales import sales_bp
    from routes.expenses import expenses_bp
    from routes.payments import payments_bp
    from routes.reports import reports_bp
    from routes.settings import settings_bp
    from routes.auth import auth_bp
    from routes.businesses import businesses_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(businesses_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(customers_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(sales_bp)
    app.register_blueprint(expenses_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(settings_bp)


def register_template_helpers(app):
    @app.template_filter("currency")
    def currency_filter(value):
        """Format a number as ₹1,234.56 for use in templates."""
        try:
            value = float(value or 0)
        except (TypeError, ValueError):
            value = 0.0
        symbol = app.config.get("CURRENCY_SYMBOL", "₹")
        return f"{symbol}{value:,.2f}"

    @app.context_processor
    def inject_globals():
        from datetime import date

        return {"current_year": date.today().year}


def register_error_handlers(app):
    from flask import render_template

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(error):
        # Roll back any half-finished database transaction so a failed
        # request never leaves the session in a broken state for the
        # next request (important on PythonAnywhere's long-lived workers).
        db.session.rollback()
        app.logger.exception(error)
        return render_template("errors/500.html"), 500


def register_cli_commands(app):
    @app.cli.command("init-db")
    def init_db():
        """Create all database tables (flask init-db)."""
        with app.app_context():
            db.create_all()
        print("Database initialized.")

    @app.cli.command("reset-password")
    def reset_password():
        """Set a user's password from a console (flask reset-password).

        The way back in when the password is forgotten — there is no
        email reset, since the app sends no email.
        """
        import getpass

        from models.user import User, MIN_PASSWORD_LENGTH

        with app.app_context():
            users = User.query.order_by(User.username).all()
            if not users:
                print("No accounts yet — open the app and it will offer to create one.")
                return

            print("Accounts:", ", ".join(u.username for u in users))
            username = input("Username to reset: ").strip()
            user = User.query.filter_by(username=username).first()
            if not user:
                print(f"No account called {username!r}.")
                return

            password = getpass.getpass("New password: ")
            if len(password) < MIN_PASSWORD_LENGTH:
                print(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
                return
            if password != getpass.getpass("Confirm new password: "):
                print("The two passwords do not match.")
                return

            user.set_password(password)
            user.failed_attempts = 0
            user.locked_until = None
            db.session.commit()
            print(f"Password updated for {user.username}.")


# Module-level `app` object — this is what PythonAnywhere's WSGI file
# and `flask run` both look for.
#
# Running this file directly (`python app.py`) means local development, so
# it defaults to the development config; imported by a WSGI server it
# defaults to production, where the placeholder SECRET_KEY is refused.
# An explicit FLASK_ENV always wins.
_default_env = "development" if __name__ == "__main__" else "production"
app = create_app(os.environ.get("FLASK_ENV", _default_env))


if __name__ == "__main__":
    # Local development only. On PythonAnywhere the app is served through
    # the WSGI configuration described in README.md, not this block.
    #
    # Port comes from the environment because macOS hands port 5000 to
    # AirPlay Receiver, which answers with 403 and looks like the app
    # refusing you. Run `PORT=5001 python app.py` to step around it.
    app.run(debug=True, host="127.0.0.1", port=int(os.environ.get("PORT", 5000)))
