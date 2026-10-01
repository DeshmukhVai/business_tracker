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
    g,
)
from sqlalchemy import or_

from extensions import db
from models.business_partner import BusinessPartner
from models.expense import Expense, ExpenseItem
from models.expense_category import ExpenseCategory
from models.expense_share import ExpenseShare
from models.user import User
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
    ("paid_by", "Paid By"),
]


def _partner_users():
    """Users who partner in the active business, for the "Paid By" dropdown.

    A dropdown rather than free text so an expense can only ever be
    attributed to someone who actually has access to this business.
    """
    return (
        User.query.join(BusinessPartner, BusinessPartner.user_id == User.id)
        .filter(BusinessPartner.business_id == g.business.id)
        .order_by(User.username)
        .all()
    )


def _parse_payment_split(form, total_amount):
    """Read how an expense was paid into (paid_by_user_id, business_amount).

    Any mix is allowed: fully personal (business_amount left at 0), fully
    business-funded (business_amount equal to the total, no partner
    needed), or split between the two — a partner covering part of it out
    of pocket while the rest came from business funds.

    Rejects a business_amount bigger than the total, a partner id that
    isn't actually a partner here, and a personal remainder with no one
    assigned to it — each is either an impossible input or a tampered
    form field, not something the picker itself would ever produce.
    """
    raw_business = form.get("business_amount")
    business_amount = parse_amount(raw_business or 0, "Amount from business profit")
    if business_amount > total_amount:
        raise ValueError("Amount from business profit can't be more than the total amount.")

    raw_partner = (form.get("paid_by") or "").strip()
    paid_by_user_id = int(raw_partner) if raw_partner else None
    if paid_by_user_id is not None and not BusinessPartner.query.filter_by(
        business_id=g.business.id, user_id=paid_by_user_id
    ).first():
        raise ValueError("Selected person is not a partner of this business.")

    personal_amount = round(total_amount - business_amount, 2)
    if personal_amount > 0 and paid_by_user_id is None:
        raise ValueError(
            f"Select who personally paid the remaining {personal_amount:,.2f} "
            "not covered by business profit."
        )
    if personal_amount <= 0:
        paid_by_user_id = None  # nothing personal left to attribute to anyone

    return paid_by_user_id, business_amount


def _apply_expense_shares(expense):
    """(Re)create the reimbursement rows owed to whoever paid personally.

    Replaces any existing shares entirely — same pattern as the item
    rows — so an edited amount or payment split always leaves the split
    correct. Only the personal portion (amount minus business_amount) is
    ever split; a fully business-funded expense, or the business-funded
    part of a mixed one, needs no reimbursement from anyone.

    The personal portion is split equally across every partner the
    business currently has, excluding whoever paid (they already fronted
    their own share by paying it). Two partners means the other owes
    exactly half of that portion, which is the common case; it
    generalises the same way to more.
    """
    for old_share in list(expense.shares):
        db.session.delete(old_share)

    personal_amount = round(float(expense.amount or 0) - float(expense.business_amount or 0), 2)
    if not expense.paid_by_user_id or personal_amount <= 0:
        return

    partner_user_ids = [
        row[0]
        for row in db.session.query(BusinessPartner.user_id)
        .filter_by(business_id=expense.business_id)
        .all()
    ]
    owing_user_ids = [uid for uid in partner_user_ids if uid != expense.paid_by_user_id]
    if not owing_user_ids:
        return  # solo business, or no other partner to split with

    share_amount = round(personal_amount / len(partner_user_ids), 2)
    for uid in owing_user_ids:
        db.session.add(
            ExpenseShare(expense_id=expense.id, owed_by_user_id=uid, amount=share_amount)
        )


@expenses_bp.route("/")
def list_expenses():
    search = request.args.get("q", "").strip()
    category = request.args.get("category", "")
    start_raw = request.args.get("start")
    end_raw = request.args.get("end")

    query = Expense.query.filter_by(business_id=g.business.id)
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
        categories=ExpenseCategory.names(g.business.id),
        fixed_columns=FIXED_COLUMNS,
        optional_columns=OPTIONAL_COLUMNS,
        shown_columns=selected_columns(OPTIONAL_COLUMNS),
    )


def _category_options():
    """Categories shaped for the picker macro."""
    categories = (
        ExpenseCategory.query.filter_by(business_id=g.business.id)
        .order_by(ExpenseCategory.name)
        .all()
    )
    return [{"id": c.name, "label": c.name, "price": None} for c in categories]


@expenses_bp.route("/categories/quick-add", methods=["POST"])
def quick_add_category():
    """Create a category from the expense form without leaving the page."""
    try:
        name = parse_required_text(request.form.get("name"), "Category name", 50)
        existing = ExpenseCategory.find_by_name(g.business.id, name)
        if existing:
            raise ValueError(f"'{existing.name}' is already a category.")
        category = ExpenseCategory(business_id=g.business.id, name=name)
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
            amount = parse_amount(request.form.get("amount"), "Total amount", allow_zero=False)
            paid_by_user_id, business_amount = _parse_payment_split(request.form, amount)
            expense = Expense(
                business_id=g.business.id,
                expense_date=parse_date(request.form.get("expense_date"), "Date"),
                category=parse_required_text(request.form.get("category"), "Category", 50),
                description=parse_optional_text(request.form.get("description"), 255),
                amount=amount,
                payment_method=parse_optional_text(request.form.get("payment_method"), 30),
                paid_by_user_id=paid_by_user_id,
                business_amount=business_amount,
                notes=parse_optional_text(request.form.get("notes")),
            )
            for item in items:
                expense.items.append(item)
            db.session.add(expense)
            db.session.flush()  # assigns expense.id, needed by the shares below
            _apply_expense_shares(expense)
            db.session.commit()
            flash("Expense added.", "success")
            return redirect(url_for("expenses.list_expenses"))
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "error")
    return render_template(
        "expenses/form.html",
        expense=None,
        category_options=_category_options(),
        partner_users=_partner_users(),
    )


@expenses_bp.route("/<int:expense_id>/edit", methods=["GET", "POST"])
def edit_expense(expense_id):
    expense = Expense.query.filter_by(id=expense_id, business_id=g.business.id).first_or_404()
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
            expense.paid_by_user_id, expense.business_amount = _parse_payment_split(
                request.form, float(expense.amount)
            )
            expense.notes = parse_optional_text(request.form.get("notes"))

            # Replace the item rows entirely with the submitted set, the
            # same way an order's line items are handled.
            for old_item in list(expense.items):
                db.session.delete(old_item)
            for item in items:
                expense.items.append(item)

            _apply_expense_shares(expense)
            db.session.commit()
            flash("Expense updated.", "success")
            return redirect(url_for("expenses.list_expenses"))
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "error")
    return render_template(
        "expenses/form.html",
        expense=expense,
        category_options=_category_options(),
        partner_users=_partner_users(),
    )


@expenses_bp.route("/<int:expense_id>")
def view_expense(expense_id):
    expense = Expense.query.filter_by(id=expense_id, business_id=g.business.id).first_or_404()
    return render_template("expenses/detail.html", expense=expense)


@expenses_bp.route("/<int:expense_id>/delete", methods=["POST"])
def delete_expense(expense_id):
    expense = Expense.query.filter_by(id=expense_id, business_id=g.business.id).first_or_404()
    db.session.delete(expense)
    db.session.commit()
    flash("Expense deleted.", "success")
    return redirect(url_for("expenses.list_expenses"))
