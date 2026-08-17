"""Expense tracking.

An expense is either a single typed amount (an electricity bill) or a
list of raw-material rows that add up to the total (a materials run that
bought pipe cleaners, sticks and tape in one go).
"""

from datetime import datetime

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
)
from sqlalchemy import or_

from extensions import db
from models.expense import Expense, ExpenseItem
from models.expense_category import ExpenseCategory
from utils.columns import selected_columns
from utils.validators import (
    parse_amount,
    parse_quantity,
    parse_required_text,
    parse_optional_text,
    parse_date,
)

expenses_bp = Blueprint("expenses", __name__, url_prefix="/expenses")

# The list shows date, description, amount and actions. Everything else is
# opt-in from the Columns menu, so the default table stays readable on a
# phone. Chosen columns travel in the query string, like the filters do.
FIXED_COLUMNS = ["Date", "Description", "Amount", "Actions"]
OPTIONAL_COLUMNS = [
    ("category", "Category"),
    ("payment_method", "Payment Method"),
]


@expenses_bp.route("/")
def list_expenses():
    search = request.args.get("q", "").strip()
    category = request.args.get("category", "")
    start_raw = request.args.get("start")
    end_raw = request.args.get("end")

    query = Expense.query
    if search:
        # Match the description or any raw-material row, so searching
        # "tape" finds the materials run that included tape.
        like = f"%{search}%"
        query = (
            query.outerjoin(ExpenseItem)
            .filter(or_(Expense.description.ilike(like), ExpenseItem.name.ilike(like)))
            .distinct()
        )
    if category:
        query = query.filter(Expense.category == category)
    if start_raw:
        try:
            query = query.filter(Expense.expense_date >= datetime.strptime(start_raw, "%Y-%m-%d").date())
        except ValueError:
            pass
    if end_raw:
        try:
            query = query.filter(Expense.expense_date <= datetime.strptime(end_raw, "%Y-%m-%d").date())
        except ValueError:
            pass

    expenses = query.order_by(Expense.expense_date.desc(), Expense.id.desc()).all()
    total = sum(float(e.amount) for e in expenses)

    return render_template(
        "expenses/list.html",
        expenses=expenses,
        total=total,
        search=search,
        category=category,
        start=start_raw,
        end=end_raw,
        categories=ExpenseCategory.names(),
        fixed_columns=FIXED_COLUMNS,
        optional_columns=OPTIONAL_COLUMNS,
        shown_columns=selected_columns(OPTIONAL_COLUMNS),
    )


def _category_options():
    """Categories shaped for the picker macro."""
    categories = ExpenseCategory.query.order_by(ExpenseCategory.name).all()
    return [{"id": c.name, "label": c.name, "price": None} for c in categories]


@expenses_bp.route("/categories/quick-add", methods=["POST"])
def quick_add_category():
    """Create a category from the expense form without leaving the page."""
    try:
        name = parse_required_text(request.form.get("name"), "Category name", 50)
        existing = ExpenseCategory.find_by_name(name)
        if existing:
            raise ValueError(f"'{existing.name}' is already a category.")
        category = ExpenseCategory(name=name)
        db.session.add(category)
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(exc)}), 400

    # The picker keys categories by name, which is what the expense stores.
    return jsonify({"ok": True, "category": {"id": category.name, "name": category.name}})


def _build_expense_items(form):
    """Parse the optional raw-material rows from the form.

    Returns an empty list when the user did not itemise the expense —
    that is a valid expense, not an error. Rows left completely blank are
    skipped so an unused spare row never blocks a save.
    """
    names = form.getlist("item_name[]")
    quantities = form.getlist("item_quantity[]")
    prices = form.getlist("item_unit_price[]")

    items = []
    for idx, raw_name in enumerate(names):
        name = (raw_name or "").strip()
        raw_qty = quantities[idx].strip() if idx < len(quantities) and quantities[idx] else ""
        raw_price = prices[idx].strip() if idx < len(prices) and prices[idx] else ""

        if not name and not raw_price:
            continue
        if not name:
            raise ValueError(f"Item {idx + 1}: please enter a name for the material.")
        if not raw_price:
            raise ValueError(f"Item {idx + 1} ({name}): please enter a price.")

        item = ExpenseItem(
            name=parse_required_text(name, f"Item {idx + 1} name", 120),
            # A blank quantity means "one of these", which is the common case.
            quantity=parse_quantity(raw_qty or 1, f"Item {idx + 1} ({name}) quantity"),
            unit_price=parse_amount(raw_price, f"Item {idx + 1} ({name}) price"),
        )
        item.compute_subtotal()
        items.append(item)

    return items


@expenses_bp.route("/add", methods=["GET", "POST"])
def add_expense():
    if request.method == "POST":
        try:
            items = _build_expense_items(request.form)
            expense = Expense(
                expense_date=parse_date(request.form.get("expense_date"), "Date"),
                category=parse_required_text(request.form.get("category"), "Category", 50),
                description=parse_optional_text(request.form.get("description"), 255),
                amount=parse_amount(request.form.get("amount"), "Total amount", allow_zero=False),
                payment_method=parse_optional_text(request.form.get("payment_method"), 30),
                notes=parse_optional_text(request.form.get("notes")),
            )
            for item in items:
                expense.items.append(item)
            db.session.add(expense)
            db.session.commit()
            flash("Expense added.", "success")
            return redirect(url_for("expenses.list_expenses"))
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "error")
    return render_template(
        "expenses/form.html", expense=None, category_options=_category_options()
    )


@expenses_bp.route("/<int:expense_id>/edit", methods=["GET", "POST"])
def edit_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    if request.method == "POST":
        try:
            items = _build_expense_items(request.form)
            expense.expense_date = parse_date(request.form.get("expense_date"), "Date")
            expense.category = parse_required_text(request.form.get("category"), "Category", 50)
            expense.description = parse_optional_text(request.form.get("description"), 255)
            expense.amount = parse_amount(
                request.form.get("amount"), "Total amount", allow_zero=False
            )
            expense.payment_method = parse_optional_text(request.form.get("payment_method"), 30)
            expense.notes = parse_optional_text(request.form.get("notes"))

            # Replace the item rows entirely with the submitted set, the
            # same way an order's line items are handled.
            for old_item in list(expense.items):
                db.session.delete(old_item)
            for item in items:
                expense.items.append(item)

            db.session.commit()
            flash("Expense updated.", "success")
            return redirect(url_for("expenses.list_expenses"))
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "error")
    return render_template(
        "expenses/form.html", expense=expense, category_options=_category_options()
    )


@expenses_bp.route("/<int:expense_id>")
def view_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    return render_template("expenses/detail.html", expense=expense)


@expenses_bp.route("/<int:expense_id>/delete", methods=["POST"])
def delete_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    db.session.delete(expense)
    db.session.commit()
    flash("Expense deleted.", "success")
    return redirect(url_for("expenses.list_expenses"))
