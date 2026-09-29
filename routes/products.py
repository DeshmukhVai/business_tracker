"""Product management: list, add, edit, activate/deactivate, delete."""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, g

from extensions import db
from models.product import Product
from utils.columns import selected_columns
from utils.validators import parse_amount, parse_required_text, parse_optional_text

products_bp = Blueprint("products", __name__, url_prefix="/products")

# Name, selling price, status and actions are what the list is for at a
# glance; the costing detail is opt-in from the Columns menu.
FIXED_COLUMNS = ["Name", "Selling Price", "Status", "Actions"]
OPTIONAL_COLUMNS = [
    ("category", "Category"),
    ("cost_price", "Cost Price"),
    ("profit", "Profit/Item"),
]


@products_bp.route("/")
def list_products():
    search = request.args.get("q", "").strip()
    show_inactive = request.args.get("show_inactive") == "1"

    query = Product.query.filter_by(business_id=g.business.id)
    if not show_inactive:
        query = query.filter(Product.is_active.is_(True))
    if search:
        query = query.filter(Product.name.ilike(f"%{search}%"))
    products = query.order_by(Product.name).all()
    return render_template(
        "products/list.html",
        products=products,
        search=search,
        show_inactive=show_inactive,
        fixed_columns=FIXED_COLUMNS,
        optional_columns=OPTIONAL_COLUMNS,
        shown_columns=selected_columns(OPTIONAL_COLUMNS),
    )


@products_bp.route("/add", methods=["GET", "POST"])
def add_product():
    if request.method == "POST":
        try:
            selling_price = parse_amount(request.form.get("selling_price"), "Selling price")
            cost_price = parse_amount(request.form.get("cost_price"), "Cost price")
            product = Product(
                business_id=g.business.id,
                name=parse_required_text(request.form.get("name"), "Product name", 120),
                category=parse_optional_text(request.form.get("category"), 80),
                selling_price=selling_price,
                cost_price=cost_price,
                description=parse_optional_text(request.form.get("description")),
                is_active=True,
            )
            db.session.add(product)
            db.session.commit()
            flash(f"Product '{product.name}' added.", "success")
            return redirect(url_for("products.list_products"))
        except ValueError as exc:
            flash(str(exc), "error")
    return render_template("products/form.html", product=None)


@products_bp.route("/quick-add", methods=["POST"])
def quick_add_product():
    """Create a product from the Add Sale form without leaving the page.

    Returns JSON rather than redirecting, so the half-filled order on
    screen is not lost. Uses the same validators as the full form.
    """
    try:
        product = Product(
            business_id=g.business.id,
            name=parse_required_text(request.form.get("name"), "Product name", 120),
            category=parse_optional_text(request.form.get("category"), 80),
            selling_price=parse_amount(request.form.get("selling_price"), "Selling price"),
            cost_price=parse_amount(request.form.get("cost_price"), "Cost price"),
            is_active=True,
        )
        db.session.add(product)
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(exc)}), 400

    return jsonify(
        {
            "ok": True,
            "product": {
                "id": product.id,
                "name": product.name,
                # Formatted to two decimals so the option's data-price
                # matches the server-rendered ones exactly.
                "selling_price": f"{product.selling_price:.2f}",
            },
        }
    )


@products_bp.route("/<int:product_id>/edit", methods=["GET", "POST"])
def edit_product(product_id):
    product = Product.query.filter_by(id=product_id, business_id=g.business.id).first_or_404()
    if request.method == "POST":
        try:
            product.name = parse_required_text(request.form.get("name"), "Product name", 120)
            product.category = parse_optional_text(request.form.get("category"), 80)
            product.selling_price = parse_amount(request.form.get("selling_price"), "Selling price")
            product.cost_price = parse_amount(request.form.get("cost_price"), "Cost price")
            product.description = parse_optional_text(request.form.get("description"))
            product.is_active = request.form.get("is_active") == "on"
            db.session.commit()
            flash("Product updated.", "success")
            return redirect(url_for("products.list_products"))
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "error")
    return render_template("products/form.html", product=product)


@products_bp.route("/<int:product_id>/toggle-active", methods=["POST"])
def toggle_active(product_id):
    product = Product.query.filter_by(id=product_id, business_id=g.business.id).first_or_404()
    product.is_active = not product.is_active
    db.session.commit()
    state = "activated" if product.is_active else "deactivated"
    flash(f"Product '{product.name}' {state}.", "success")
    return redirect(url_for("products.list_products"))


@products_bp.route("/<int:product_id>/delete", methods=["POST"])
def delete_product(product_id):
    product = Product.query.filter_by(id=product_id, business_id=g.business.id).first_or_404()
    if product.order_items.count() > 0:
        flash(
            "This product has past sales and cannot be deleted. "
            "You can deactivate it instead.",
            "error",
        )
        return redirect(url_for("products.list_products"))
    db.session.delete(product)
    db.session.commit()
    flash("Product deleted.", "success")
    return redirect(url_for("products.list_products"))
