"""
Configuration for the Business Tracker application.

Uses environment variables where possible so the same codebase works
unchanged both locally and on PythonAnywhere. No local machine paths
are hard-coded anywhere in this file.
"""

import os
from datetime import timedelta

# BASE_DIR points at the project root regardless of where the app is
# actually deployed (local machine, PythonAnywhere, etc).
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Signing key used for the login session cookie. Anyone who knows it can
# mint a cookie and walk past the login page, so production refuses to
# start while it is still this placeholder (see app.py).
DEFAULT_SECRET_KEY = "dev-secret-key-change-me"

# The SQLite database lives inside an "instance" folder next to the
# code. Flask automatically treats this folder as instance-relative
# and it is safe to write to on PythonAnywhere.
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
DEFAULT_DB_PATH = os.path.join(INSTANCE_DIR, "business_tracker.db")


class Config:
    """Base configuration shared by all environments."""

    # Read the secret key from the environment when available (recommended
    # for production / PythonAnywhere). Falls back to a development-only
    # value so the app still runs out of the box locally.
    SECRET_KEY = os.environ.get("SECRET_KEY", DEFAULT_SECRET_KEY)

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Login session cookie. HttpOnly keeps it away from JavaScript, and
    # SameSite=Lax stops another site posting to the app as the owner.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(days=14)

    # Currency used throughout the UI.
    CURRENCY_SYMBOL = "₹"  # Rupee sign

    # Starting expense categories. These are seeded into the
    # expense_categories table the first time the app runs; after that the
    # database is the source of truth and new ones are added from the
    # expense form, not from here.
    EXPENSE_CATEGORIES = [
        "Raw Materials",
        "Packaging",
        "Delivery",
        "Marketing",
        "Electricity",
        "Equipment",
        "Transportation",
        "Other",
    ]

    PAYMENT_METHODS = ["Cash", "UPI", "Bank Transfer", "Card", "Other"]


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    # PythonAnywhere serves over HTTPS, so the cookie need never travel
    # in the clear.
    SESSION_COOKIE_SECURE = True


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}
