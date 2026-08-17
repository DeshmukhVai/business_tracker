"""
Business-logic calculations.

Kept separate from routes so the numbers shown on the dashboard, reports
and payments pages are always computed the same way, straight from the
database, rather than re-derived (and potentially getting out of sync)
in multiple templates.
"""

from datetime import date, timedelta

from extensions import db
from models.sale import Sale, DELIVERY_STATUS_DELIVERED
from models.expense import Expense
from models.customer import Customer


def get_date_range(period, start=None, end=None):
    """Translate a named period (or explicit custom range) into (start, end)."""
    today = date.today()
    if period == "today":
        return today, today
    if period == "week":
        start_of_week = today - timedelta(days=today.weekday())
        return start_of_week, today
    if period == "month":
        return today.replace(day=1), today
    if period == "year":
        return today.replace(month=1, day=1), today
    if period == "custom" and start and end:
        return start, end
    # Default: all time.
    return None, None


def deliveries_due(days_ahead=7):
    """Undelivered orders that are overdue, due today, or due soon.

    Deliberately ignores the dashboard's period filter: what still has to
    go out is about today, not about whichever reporting window is being
    looked at. Overdue orders come first, then the nearest date.
    """
    today = date.today()
    return (
        Sale.query.filter(
            Sale.delivery_status != DELIVERY_STATUS_DELIVERED,
            Sale.delivery_date.isnot(None),
            Sale.delivery_date <= today + timedelta(days=days_ahead),
        )
        .order_by(Sale.delivery_date)
        .all()
    )


def sales_query(start=None, end=None):
    query = Sale.query
    if start:
        query = query.filter(Sale.order_date >= start)
    if end:
        query = query.filter(Sale.order_date <= end)
    return query


def expenses_query(start=None, end=None):
    query = Expense.query
    if start:
        query = query.filter(Expense.expense_date >= start)
    if end:
        query = query.filter(Expense.expense_date <= end)
    return query


def dashboard_summary(start=None, end=None):
    sales = sales_query(start, end).all()
    expenses = expenses_query(start, end).all()

    total_sales = sum(float(s.total_amount) for s in sales)
    total_received = sum(float(s.amount_paid) for s in sales)
    total_pending = total_sales - total_received
    total_expenses = sum(float(e.amount) for e in expenses)
    total_profit = total_sales - total_expenses

    return {
        "total_sales": total_sales,
        "total_expenses": total_expenses,
        "total_profit": total_profit,
        "amount_received": total_received,
        "amount_pending": total_pending,
        "num_customers": Customer.query.count(),
        "num_orders": len(sales),
    }


def sales_vs_expenses_series(start=None, end=None):
    """Daily totals suitable for a line/bar chart."""
    sales = sales_query(start, end).order_by(Sale.order_date).all()
    expenses = expenses_query(start, end).order_by(Expense.expense_date).all()

    by_date = {}
    for s in sales:
        d = s.order_date.isoformat()
        by_date.setdefault(d, {"sales": 0.0, "expenses": 0.0})
        by_date[d]["sales"] += float(s.total_amount)
    for e in expenses:
        d = e.expense_date.isoformat()
        by_date.setdefault(d, {"sales": 0.0, "expenses": 0.0})
        by_date[d]["expenses"] += float(e.amount)

    labels = sorted(by_date.keys())
    return {
        "labels": labels,
        "sales": [by_date[d]["sales"] for d in labels],
        "expenses": [by_date[d]["expenses"] for d in labels],
    }


def sales_by_product(start=None, end=None):
    from models.sale import OrderItem

    items = OrderItem.query.join(Sale).filter(Sale.id == OrderItem.order_id)
    if start:
        items = items.filter(Sale.order_date >= start)
    if end:
        items = items.filter(Sale.order_date <= end)

    totals = {}
    for item in items.all():
        name = item.product.name if item.product else "Unknown"
        totals.setdefault(name, 0.0)
        totals[name] += float(item.subtotal)

    sorted_items = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    return {
        "labels": [k for k, _ in sorted_items],
        "values": [v for _, v in sorted_items],
    }


def payment_status_breakdown(start=None, end=None):
    sales = sales_query(start, end).all()
    counts = {"Paid": 0, "Partially Paid": 0, "Pending": 0}
    for s in sales:
        counts[s.payment_status] = counts.get(s.payment_status, 0) + 1
    return counts
