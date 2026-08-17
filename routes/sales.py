"""Sales / order tracking.

An order can contain one or more line items (products). The add/edit
form defaults to a single row for speed, but the UI allows adding more
rows via JavaScript for orders with several products.
"""

from datetime import datetime, date

from flask import Blueprint, render_template, request, redirect, url_for, flash

from extensions import db
from models.sale import (
    Sale,
    OrderItem,
    DISCOUNT_TYPE_AMOUNT,
    DISCOUNT_TYPE_PERCENT,
    DISCOUNT_TYPES,
    DELIVERY_STATUS_PENDING,
    DELIVERY_STATUS_DELIVERED,
    DELIVERY_STATUSES,
)
from models.customer import Customer
from models.product import Product
from utils.validators import (
    parse_amount,
    parse_percent,
    parse_positive_int,
    parse_optional_text,
    parse_date,
    parse_optional_date,
)

sales_bp = Blueprint("sales", __name__, url_prefix="/sales")


@sales_bp.route("/")
def list_sales():
    search = request.args.get("q", "").strip()
    customer_id = request.args.get("customer_id", type=int)
    product_id = request.args.get("product_id", type=int)
    status = request.args.get("status", "")
    delivery = request.args.get("delivery", "")
    start_raw = request.args.get("start")
    end_raw = request.args.get("end")

    query = Sale.query
    if customer_id:
        query = query.filter(Sale.customer_id == customer_id)
    if status:
        query = query.filter(Sale.payment_status == status)
    if delivery == "overdue":
        # Undelivered and the promised date has already gone by.
        query = query.filter(
            Sale.delivery_status != DELIVERY_STATUS_DELIVERED,
            Sale.delivery_date.isnot(None),
            Sale.delivery_date < date.today(),
        )
    elif delivery in DELIVERY_STATUSES:
        query = query.filter(Sale.delivery_status == delivery)
    if start_raw:
        try:
            query = query.filter(Sale.order_date >= datetime.strptime(start_raw, "%Y-%m-%d").date())
        except ValueError:
            pass
    if end_raw:
        try:
            query = query.filter(Sale.order_date <= datetime.strptime(end_raw, "%Y-%m-%d").date())
        except ValueError:
            pass
    if product_id:
        query = query.join(OrderItem).filter(OrderItem.product_id == product_id)
    if search:
        like = f"%{search}%"
        query = query.join(Customer).filter(Customer.name.ilike(like))

    sales = query.order_by(Sale.order_date.desc(), Sale.id.desc()).all()
    customers = Customer.query.order_by(Customer.name).all()
    products = Product.query.order_by(Product.name).all()

    return render_template(
        "sales/list.html",
        sales=sales,
        customers=customers,
        products=products,
        search=search,
        customer_id=customer_id,
        product_id=product_id,
        status=status,
        delivery=delivery,
        start=start_raw,
        end=end_raw,
    )


def _picker_options(customers, products):
    """Flatten customers/products into the shape the picker macro wants.

    Labels and prices are formatted here rather than in the template so the
    dropdown text matches what the quick-add endpoints return.
    """
    customer_options = [
        {
            "id": c.id,
            "label": f"{c.name} ({c.phone})" if c.phone else c.name,
            "price": None,
        }
        for c in customers
    ]
    product_options = [
        {"id": p.id, "label": p.name, "price": f"{p.selling_price:.2f}"} for p in products
    ]
    return customer_options, product_options


def _parse_delivery(form):
    """Read the delivery date and status from the form."""
    delivery_date = parse_optional_date(form.get("delivery_date"), "Delivery date")
    delivery_status = (form.get("delivery_status") or DELIVERY_STATUS_PENDING).strip()
    if delivery_status not in DELIVERY_STATUSES:
        raise ValueError("Choose a valid delivery status.")
    return delivery_date, delivery_status


def _parse_discount(form):
    """Read the discount as either a flat amount or a percentage.

    Returns (discount_type, discount_value); the rupee figure is worked
    out by Sale.recompute_total once the line items are known.
    """
    discount_type = (form.get("discount_type") or DISCOUNT_TYPE_AMOUNT).strip()
    if discount_type not in DISCOUNT_TYPES:
        raise ValueError("Choose a valid discount type.")

    raw_value = form.get("discount_value") or 0
    if discount_type == DISCOUNT_TYPE_PERCENT:
        value = parse_percent(raw_value, "Discount percentage")
    else:
        value = parse_amount(raw_value, "Discount")
    return discount_type, value


def _apply_discount(sale, form, items):
    """Store the entered discount on the sale, rejecting impossible ones."""
    discount_type, value = _parse_discount(form)
    items_total = round(sum(float(item.subtotal) for item in items), 2)
    if discount_type == DISCOUNT_TYPE_AMOUNT and value > items_total:
        raise ValueError(
            f"Discount of {value:,.2f} is more than the order value of {items_total:,.2f}."
        )
    sale.discount_type = discount_type
    sale.discount_value = value


def _build_order_items(sale, form):
    """Parse the (possibly multi-row) product line items from the form."""
    product_ids = form.getlist("product_id[]")
    quantities = form.getlist("quantity[]")
    prices = form.getlist("selling_price[]")

    if not product_ids:
        raise ValueError("Add at least one product to the order.")

    items = []
    for idx, pid in enumerate(product_ids):
        if not pid:
            continue
        product = Product.query.get(int(pid))
        if not product:
            raise ValueError("Selected product could not be found.")
        quantity = parse_positive_int(quantities[idx] if idx < len(quantities) else None, "Quantity")
        raw_price = prices[idx] if idx < len(prices) and prices[idx] not in (None, "") else product.selling_price
        selling_price = parse_amount(raw_price, "Selling price")

        item = OrderItem(
            product_id=product.id,
            quantity=quantity,
            selling_price=selling_price,
            cost_price=product.cost_price,
        )
        item.compute_subtotal()
        items.append(item)

    if not items:
        raise ValueError("Add at least one product to the order.")
    return items


@sales_bp.route("/add", methods=["GET", "POST"])
def add_sale():
    customers = Customer.query.order_by(Customer.name).all()
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()

    if request.method == "POST":
        try:
            customer_id = request.form.get("customer_id", type=int)
            if not customer_id:
                raise ValueError("Please select a customer.")

            order_date = parse_date(request.form.get("order_date"), "Order date")
            amount_paid = parse_amount(request.form.get("amount_paid") or 0, "Amount paid")
            payment_method = parse_optional_text(request.form.get("payment_method"), 30)
            notes = parse_optional_text(request.form.get("notes"))

            delivery_date, delivery_status = _parse_delivery(request.form)

            sale = Sale(
                customer_id=customer_id,
                order_date=order_date,
                delivery_date=delivery_date,
                delivery_status=delivery_status,
                payment_method=payment_method,
                notes=notes,
            )
            items = _build_order_items(sale, request.form)
            for item in items:
                sale.items.append(item)
            _apply_discount(sale, request.form, items)
            sale.recompute_total(items)

            if amount_paid > sale.total_amount:
                raise ValueError("Amount paid cannot be more than the total amount.")
            sale.amount_paid = amount_paid
            sale.recompute_payment_status()

            db.session.add(sale)
            db.session.commit()
            flash("Sale recorded.", "success")
            return redirect(url_for("sales.list_sales"))
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "error")

    customer_options, product_options = _picker_options(customers, products)
    return render_template(
        "sales/form.html",
        sale=None,
        customer_options=customer_options,
        product_options=product_options,
        today=date.today(),
    )


@sales_bp.route("/<int:sale_id>/edit", methods=["GET", "POST"])
def edit_sale(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    customers = Customer.query.order_by(Customer.name).all()
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()

    if request.method == "POST":
        try:
            customer_id = request.form.get("customer_id", type=int)
            if not customer_id:
                raise ValueError("Please select a customer.")

            sale.customer_id = customer_id
            sale.order_date = parse_date(request.form.get("order_date"), "Order date")
            sale.delivery_date, sale.delivery_status = _parse_delivery(request.form)
            sale.payment_method = parse_optional_text(request.form.get("payment_method"), 30)
            sale.notes = parse_optional_text(request.form.get("notes"))

            # Replace line items entirely with the submitted set.
            for item in list(sale.items):
                db.session.delete(item)
            new_items = _build_order_items(sale, request.form)
            for item in new_items:
                sale.items.append(item)
            _apply_discount(sale, request.form, new_items)
            sale.recompute_total(new_items)

            amount_paid = parse_amount(request.form.get("amount_paid") or 0, "Amount paid")
            if amount_paid > sale.total_amount:
                raise ValueError("Amount paid cannot be more than the total amount.")
            sale.amount_paid = amount_paid
            sale.recompute_payment_status()

            db.session.commit()
            flash("Sale updated.", "success")
            return redirect(url_for("sales.list_sales"))
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "error")

    customer_options, product_options = _picker_options(customers, products)
    return render_template(
        "sales/form.html",
        sale=sale,
        customer_options=customer_options,
        product_options=product_options,
        today=date.today(),
    )


@sales_bp.route("/<int:sale_id>/delete", methods=["POST"])
def delete_sale(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    db.session.delete(sale)
    db.session.commit()
    flash("Sale deleted.", "success")
    return redirect(url_for("sales.list_sales"))


@sales_bp.route("/<int:sale_id>")
def view_sale(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    return render_template("sales/detail.html", sale=sale)


@sales_bp.route("/<int:sale_id>/mark-delivered", methods=["POST"])
def mark_delivered(sale_id):
    """Quick action from the sales list to tick an order off as delivered."""
    sale = Sale.query.get_or_404(sale_id)
    sale.delivery_status = DELIVERY_STATUS_DELIVERED
    if not sale.delivery_date:
        # Nothing was promised in advance, so record today as the day it went.
        sale.delivery_date = date.today()
    db.session.commit()
    flash(f"Order #{sale.id} marked as delivered.", "success")
    return redirect(request.referrer or url_for("sales.list_sales"))


@sales_bp.route("/<int:sale_id>/record-payment", methods=["POST"])
def record_payment(sale_id):
    """Quick action from the Pending Payments page to log an additional payment."""
    sale = Sale.query.get_or_404(sale_id)
    try:
        extra_payment = parse_amount(request.form.get("amount"), "Payment amount", allow_zero=False)
        new_total_paid = float(sale.amount_paid) + extra_payment
        if new_total_paid > float(sale.total_amount):
            raise ValueError("This payment would exceed the order total.")
        sale.amount_paid = new_total_paid
        sale.recompute_payment_status()
        db.session.commit()
        flash("Payment recorded.", "success")
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "error")
    return redirect(request.referrer or url_for("payments.list_pending"))
