"""Settings page.

Minimal for the MVP: shows app info and the categories/payment methods
currently configured. Kept as its own blueprint so future settings
(business name, invoice numbering, backup/export, etc.) have an obvious
home without restructuring the app.
"""

from flask import Blueprint, render_template, current_app, g

from models.expense_category import ExpenseCategory
from models.user import MIN_PASSWORD_LENGTH

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")


@settings_bp.route("/")
def index():
    return render_template(
        "settings/index.html",
        categories=ExpenseCategory.names(g.business.id),
        payment_methods=current_app.config["PAYMENT_METHODS"],
        min_password_length=MIN_PASSWORD_LENGTH,
    )
