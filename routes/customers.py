"""Customer management: list, add, edit, delete, purchase history."""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, g

from extensions import db
from models.customer import Customer
from utils.validators import parse_required_text, parse_optional_text

customers_bp = Blueprint("customers", __name__, url_prefix="/customers")


@customers_bp.route("/")
def list_customers():
    search = request.args.get("q", "").strip()
    query = Customer.query.filter_by(business_id=g.business.id)
    if search:
        like = f"%{search}%"
        query = query.filter(
            db.or_(Customer.name.ilike(like), Customer.phone.ilike(like))
        )
    customers = query.order_by(Customer.name).all()
    return render_template("customers/list.html", customers=customers, search=search)


@customers_bp.route("/add", methods=["GET", "POST"])
def add_customer():
    if request.method == "POST":
        try:
            customer = Customer(
                business_id=g.business.id,
                name=parse_required_text(request.form.get("name"), "Customer name", 120),
                phone=parse_optional_text(request.form.get("phone"), 20),
                email=parse_optional_text(request.form.get("email"), 120),
                address=parse_optional_text(request.form.get("address"), 255),
                notes=parse_optional_text(request.form.get("notes")),
            )
            db.session.add(customer)
            db.session.commit()
            flash(f"Customer '{customer.name}' added.", "success")
            return redirect(url_for("customers.list_customers"))
        except ValueError as exc:
            flash(str(exc), "error")
    return render_template("customers/form.html", customer=None)


@customers_bp.route("/quick-add", methods=["POST"])
def quick_add_customer():
    """Create a customer from the Add Sale form without leaving the page.

    Returns JSON rather than redirecting, so the half-filled order on
    screen is not lost. Uses the same validators as the full form.
    """
    try:
        customer = Customer(
            business_id=g.business.id,
            name=parse_required_text(request.form.get("name"), "Customer name", 120),
            phone=parse_optional_text(request.form.get("phone"), 20),
        )
        db.session.add(customer)
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(exc)}), 400

    return jsonify(
        {
            "ok": True,
            "customer": {"id": customer.id, "name": customer.name, "phone": customer.phone},
        }
    )


@customers_bp.route("/<int:customer_id>/edit", methods=["GET", "POST"])
def edit_customer(customer_id):
    customer = Customer.query.filter_by(id=customer_id, business_id=g.business.id).first_or_404()
    if request.method == "POST":
        try:
            customer.name = parse_required_text(request.form.get("name"), "Customer name", 120)
            customer.phone = parse_optional_text(request.form.get("phone"), 20)
            customer.email = parse_optional_text(request.form.get("email"), 120)
            customer.address = parse_optional_text(request.form.get("address"), 255)
            customer.notes = parse_optional_text(request.form.get("notes"))
            db.session.commit()
            flash("Customer updated.", "success")
            return redirect(url_for("customers.list_customers"))
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "error")
    return render_template("customers/form.html", customer=customer)


@customers_bp.route("/<int:customer_id>/delete", methods=["POST"])
def delete_customer(customer_id):
    customer = Customer.query.filter_by(id=customer_id, business_id=g.business.id).first_or_404()
    if customer.total_orders() > 0:
        flash(
            "This customer has existing orders and cannot be deleted. "
            "Consider keeping the record for history.",
            "error",
        )
        return redirect(url_for("customers.list_customers"))
    db.session.delete(customer)
    db.session.commit()
    flash("Customer deleted.", "success")
    return redirect(url_for("customers.list_customers"))


@customers_bp.route("/<int:customer_id>")
def view_customer(customer_id):
    customer = Customer.query.filter_by(id=customer_id, business_id=g.business.id).first_or_404()
    orders = customer.sales.order_by(db.desc("order_date")).all()
    return render_template("customers/detail.html", customer=customer, orders=orders)
