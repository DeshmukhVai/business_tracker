"""Pending payments page: who still owes money."""

from flask import Blueprint, render_template, request, g

from models.sale import Sale, PAYMENT_STATUS_PAID
from models.customer import Customer

payments_bp = Blueprint("payments", __name__, url_prefix="/payments")


@payments_bp.route("/pending")
def list_pending():
    sort_by = request.args.get("sort", "highest")

    sales = Sale.query.filter(
        Sale.business_id == g.business.id, Sale.payment_status != PAYMENT_STATUS_PAID
    ).all()

    if sort_by == "oldest":
        sales.sort(key=lambda s: s.order_date)
    elif sort_by == "customer":
        sales.sort(key=lambda s: (s.customer.name if s.customer else "").lower())
    else:  # highest pending amount first
        sales.sort(key=lambda s: s.remaining_amount, reverse=True)

    total_pending = sum(s.remaining_amount for s in sales)

    # Customer-wise pending totals.
    by_customer = {}
    for s in sales:
        if not s.customer:
            continue
        by_customer.setdefault(s.customer.id, {"customer": s.customer, "pending": 0.0})
        by_customer[s.customer.id]["pending"] += s.remaining_amount
    customer_totals = sorted(by_customer.values(), key=lambda c: c["pending"], reverse=True)

    return render_template(
        "payments/list.html",
        sales=sales,
        total_pending=total_pending,
        sort_by=sort_by,
        customer_totals=customer_totals,
    )
