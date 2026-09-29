"""Business selection, creation, and partner management.

A tracker instance can hold more than one business, and each one is
shared by whichever users partner in it — every partner has full access
to that business's data. A signed-in user sees only the businesses they
partner in; the active one for a browsing session is remembered in the
session cookie, alongside the signed-in user.
"""

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    current_app,
    g,
)

from extensions import db
from models.business import Business
from models.business_partner import BusinessPartner, ROLE_OWNER, ROLE_PARTNER, ROLES
from models.customer import Customer
from models.expense import Expense, ExpenseItem
from models.expense_category import ExpenseCategory
from models.product import Product
from models.sale import Sale, OrderItem
from models.user import User, MIN_PASSWORD_LENGTH
from utils.validators import parse_required_text

businesses_bp = Blueprint("businesses", __name__, url_prefix="/businesses")

# Reachable once signed in even with no active business chosen yet —
# picking or creating one is exactly what these pages are for.
BUSINESS_EXEMPT_ENDPOINTS = {
    "businesses.select",
    "businesses.create",
    "businesses.switch",
    "auth.logout",
    "auth.change_password",
}


def user_partnerships(user):
    """Every business this user partners in, alphabetically by name."""
    return (
        BusinessPartner.query.filter_by(user_id=user.id)
        .join(Business)
        .order_by(Business.name)
        .all()
    )


def resolve_current_business(user):
    """The active business for this session, or None if one still needs picking.

    Also stashes the user's full partnership list on `g` so templates
    (the nav switcher) don't need a second query.
    """
    partnerships = user_partnerships(user)
    g.partnerships = partnerships
    g.businesses = [p.business for p in partnerships]

    business_id = session.get("business_id")
    if business_id:
        match = next((p for p in partnerships if p.business_id == business_id), None)
        if match:
            g.partnership = match
            return match.business
        # Stale id left over from a removed partnership, or another
        # account's session — drop it rather than trust it again.
        session.pop("business_id", None)

    if len(partnerships) == 1:
        session["business_id"] = partnerships[0].business_id
        g.partnership = partnerships[0]
        return partnerships[0].business

    return None


def _can_create_business(user):
    """Whether this user is allowed to create a (further) business.

    A brand new account with no partnerships anywhere must still be able
    to create its first business — that's how anyone gets one at all —
    but once someone has at least one partnership, creating another is
    reserved for owners. A user who has only ever been invited in as a
    partner shouldn't be able to spin up their own separate businesses.
    """
    partnerships = user_partnerships(user)
    return not partnerships or any(p.is_owner for p in partnerships)


@businesses_bp.route("/", methods=["GET"])
def select():
    partnerships = user_partnerships(g.user)
    return render_template(
        "businesses/select.html",
        partnerships=partnerships,
        can_create=_can_create_business(g.user),
    )


@businesses_bp.route("/", methods=["POST"])
def create():
    if not _can_create_business(g.user):
        flash("Only an owner of an existing business can create another one.", "error")
        return redirect(url_for("businesses.select"))

    try:
        name = parse_required_text(request.form.get("name"), "Business name", 120)
        business = Business(name=name)
        db.session.add(business)
        db.session.flush()
        db.session.add(
            BusinessPartner(business_id=business.id, user_id=g.user.id, role=ROLE_OWNER)
        )
        ExpenseCategory.seed_defaults(business.id, current_app.config["EXPENSE_CATEGORIES"])
        db.session.commit()
        session["business_id"] = business.id
        flash(f"Created {business.name}.", "success")
        return redirect(url_for("dashboard.index"))
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "error")
        return redirect(url_for("businesses.select"))


@businesses_bp.route("/<int:business_id>/switch", methods=["POST"])
def switch(business_id):
    partnership = BusinessPartner.query.filter_by(
        business_id=business_id, user_id=g.user.id
    ).first()
    if not partnership:
        flash("You don't have access to that business.", "error")
        return redirect(url_for("businesses.select"))

    session["business_id"] = business_id
    flash(f"Switched to {partnership.business.name}.", "success")
    return redirect(url_for("dashboard.index"))


@businesses_bp.route("/partners", methods=["GET"])
def partners():
    partnerships = (
        BusinessPartner.query.filter_by(business_id=g.business.id)
        .join(User)
        .order_by(User.username)
        .all()
    )
    counts = {
        "customers": Customer.query.filter_by(business_id=g.business.id).count(),
        "products": Product.query.filter_by(business_id=g.business.id).count(),
        "sales": Sale.query.filter_by(business_id=g.business.id).count(),
        "expenses": Expense.query.filter_by(business_id=g.business.id).count(),
    }
    return render_template(
        "businesses/partners.html", partnerships=partnerships, roles=ROLES, counts=counts
    )


@businesses_bp.route("/partners", methods=["POST"])
def add_partner():
    if not g.partnership.is_owner:
        flash("Only an owner of this business can add partners.", "error")
        return redirect(url_for("businesses.partners"))

    try:
        username = parse_required_text(request.form.get("username"), "Username", 80)
        role = request.form.get("role") or ROLE_PARTNER
        if role not in ROLES:
            role = ROLE_PARTNER

        user = User.query.filter_by(username=username).first()
        if user is None:
            password = request.form.get("password") or ""
            if len(password) < MIN_PASSWORD_LENGTH:
                raise ValueError(
                    f"{username!r} doesn't have an account yet, so creating one needs a "
                    f"starting password of at least {MIN_PASSWORD_LENGTH} characters — "
                    "share it with them, they can change it once signed in."
                )
            user = User(username=username)
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
        elif BusinessPartner.query.filter_by(business_id=g.business.id, user_id=user.id).first():
            raise ValueError(f"{username} already partners in {g.business.name}.")

        db.session.add(BusinessPartner(business_id=g.business.id, user_id=user.id, role=role))
        db.session.commit()
        flash(f"Added {username} as a {role} of {g.business.name}.", "success")
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "error")

    return redirect(url_for("businesses.partners"))


@businesses_bp.route("/partners/<int:partnership_id>/role", methods=["POST"])
def update_role(partnership_id):
    if not g.partnership.is_owner:
        flash("Only an owner of this business can change partner roles.", "error")
        return redirect(url_for("businesses.partners"))

    target = BusinessPartner.query.filter_by(id=partnership_id, business_id=g.business.id).first()
    if not target:
        flash("That partner is no longer part of this business.", "error")
        return redirect(url_for("businesses.partners"))

    new_role = request.form.get("role")
    if new_role not in ROLES:
        flash("Choose a valid role.", "error")
        return redirect(url_for("businesses.partners"))

    if target.role != new_role and target.is_owner:
        # Losing this owner must still leave someone able to manage the
        # business — the same reasoning as the last-partner guard below,
        # just scoped to owners rather than to partners of any role.
        remaining_owners = BusinessPartner.query.filter_by(
            business_id=g.business.id, role=ROLE_OWNER
        ).count()
        if remaining_owners <= 1:
            flash("A business must keep at least one owner.", "error")
            return redirect(url_for("businesses.partners"))

    target.role = new_role
    db.session.commit()
    flash(f"{target.user.username} is now {'an' if new_role == ROLE_OWNER else 'a'} {new_role}.", "success")
    return redirect(url_for("businesses.partners"))


@businesses_bp.route("/partners/<int:partnership_id>/remove", methods=["POST"])
def remove_partner(partnership_id):
    if not g.partnership.is_owner:
        flash("Only an owner of this business can remove partners.", "error")
        return redirect(url_for("businesses.partners"))

    target = BusinessPartner.query.filter_by(id=partnership_id, business_id=g.business.id).first()
    if not target:
        flash("That partner is no longer part of this business.", "error")
        return redirect(url_for("businesses.partners"))

    remaining = BusinessPartner.query.filter_by(business_id=g.business.id).count()
    if remaining <= 1:
        flash("A business must keep at least one partner.", "error")
        return redirect(url_for("businesses.partners"))

    removing_self = target.user_id == g.user.id
    db.session.delete(target)
    db.session.commit()

    if removing_self:
        session.pop("business_id", None)
        flash("You left that business.", "success")
        return redirect(url_for("businesses.select"))

    flash("Partner removed.", "success")
    return redirect(url_for("businesses.partners"))


@businesses_bp.route("/rename", methods=["POST"])
def rename():
    if not g.partnership.is_owner:
        flash("Only an owner of this business can rename it.", "error")
        return redirect(url_for("businesses.partners"))

    try:
        g.business.name = parse_required_text(request.form.get("name"), "Business name", 120)
        db.session.commit()
        flash("Business renamed.", "success")
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "error")

    return redirect(url_for("businesses.partners"))


@businesses_bp.route("/delete", methods=["POST"])
def delete():
    """Permanently delete the active business and everything in it.

    Irreversible, so it asks the owner to type the business's exact name
    rather than just clicking a button — the same pattern GitHub uses for
    deleting a repository. There's no relationship-level cascade from
    Business to its records (only a plain business_id column), so each
    table is cleared explicitly, children before parents, in one
    transaction.
    """
    business = g.business
    if not g.partnership.is_owner:
        flash("Only an owner of this business can delete it.", "error")
        return redirect(url_for("businesses.partners"))

    typed_name = (request.form.get("confirm_name") or "").strip()
    if typed_name != business.name:
        flash("Type the business's exact name to confirm deletion.", "error")
        return redirect(url_for("businesses.partners"))

    business_id = business.id
    name = business.name

    OrderItem.query.filter(
        OrderItem.order_id.in_(db.session.query(Sale.id).filter_by(business_id=business_id))
    ).delete(synchronize_session=False)
    Sale.query.filter_by(business_id=business_id).delete(synchronize_session=False)

    ExpenseItem.query.filter(
        ExpenseItem.expense_id.in_(db.session.query(Expense.id).filter_by(business_id=business_id))
    ).delete(synchronize_session=False)
    Expense.query.filter_by(business_id=business_id).delete(synchronize_session=False)

    Customer.query.filter_by(business_id=business_id).delete(synchronize_session=False)
    Product.query.filter_by(business_id=business_id).delete(synchronize_session=False)
    ExpenseCategory.query.filter_by(business_id=business_id).delete(synchronize_session=False)
    BusinessPartner.query.filter_by(business_id=business_id).delete(synchronize_session=False)

    db.session.delete(business)
    db.session.commit()

    session.pop("business_id", None)
    flash(f"Deleted '{name}' and all its data.", "success")
    return redirect(url_for("businesses.select"))
