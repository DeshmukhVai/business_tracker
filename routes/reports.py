"""Reports: monthly summary, expense breakdown, customer report, product report."""

from datetime import date
import calendar

from flask import Blueprint, render_template, request, g

from models.sale import Sale
from models.expense import Expense
from models.customer import Customer
from models.product import Product

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")


@reports_bp.route("/")
def index():
    today = date.today()
    year = request.args.get("year", type=int) or today.year
    month = request.args.get("month", type=int) or today.month

    month_start = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    month_end = date(year, month, last_day)

    business_id = g.business.id
    sales = Sale.query.filter(
        Sale.business_id == business_id, Sale.order_date.between(month_start, month_end)
    ).all()
    expenses = Expense.query.filter(
        Expense.business_id == business_id, Expense.expense_date.between(month_start, month_end)
    ).all()

    total_sales = sum(float(s.total_amount) for s in sales)
    total_received = sum(float(s.amount_paid) for s in sales)
    total_pending = total_sales - total_received
    total_expenses = sum(float(e.amount) for e in expenses)
    total_profit = total_sales - total_expenses

    monthly_summary = {
        "label": month_start.strftime("%B %Y"),
        "sales": total_sales,
        "expenses": total_expenses,
        "profit": total_profit,
        "received": total_received,
        "pending": total_pending,
    }

    # Expense breakdown by category (all time is more useful than a single
    # month for spotting where money habitually goes, so this section uses
    # the full history rather than being locked to the selected month).
    breakdown = {}
    for e in Expense.query.filter_by(business_id=business_id).all():
        breakdown.setdefault(e.category, 0.0)
        breakdown[e.category] += float(e.amount)
    expense_breakdown = sorted(breakdown.items(), key=lambda kv: kv[1], reverse=True)

    # Customer report.
    customer_rows = []
    for customer in Customer.query.filter_by(business_id=business_id).order_by(Customer.name).all():
        orders = customer.total_orders()
        if orders == 0:
            continue
        customer_rows.append(
            {
                "customer": customer,
                "orders": orders,
                "purchased": customer.total_purchased(),
                "paid": customer.total_paid(),
                "pending": customer.total_pending(),
            }
        )
    customer_rows.sort(key=lambda r: r["purchased"], reverse=True)

    # Product report.
    product_rows = []
    for product in Product.query.filter_by(business_id=business_id).order_by(Product.name).all():
        units = product.units_sold()
        if units == 0:
            continue
        product_rows.append(
            {
                "product": product,
                "units_sold": units,
                "revenue": product.total_revenue(),
                "profit": product.estimated_profit(),
            }
        )
    product_rows.sort(key=lambda r: r["revenue"], reverse=True)

    return render_template(
        "reports/index.html",
        monthly_summary=monthly_summary,
        expense_breakdown=expense_breakdown,
        customer_rows=customer_rows,
        product_rows=product_rows,
        year=year,
        month=month,
    )
