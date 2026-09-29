"""Dashboard blueprint: the landing page with summary cards and charts."""

from flask import Blueprint, render_template, request, g
from datetime import date, datetime

from utils.calculations import (
    get_date_range,
    dashboard_summary,
    deliveries_due,
    sales_vs_expenses_series,
    sales_by_product,
    payment_status_breakdown,
)

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def index():
    period = request.args.get("period", "all")
    start_raw = request.args.get("start")
    end_raw = request.args.get("end")

    start = end = None
    if period == "custom" and start_raw and end_raw:
        try:
            start = datetime.strptime(start_raw, "%Y-%m-%d").date()
            end = datetime.strptime(end_raw, "%Y-%m-%d").date()
        except ValueError:
            period = "month"

    if period != "custom":
        start, end = get_date_range(period)

    business_id = g.business.id
    summary = dashboard_summary(business_id, start, end)
    chart_series = sales_vs_expenses_series(business_id, start, end)
    product_chart = sales_by_product(business_id, start, end)
    status_chart = payment_status_breakdown(business_id, start, end)

    return render_template(
        "dashboard.html",
        summary=summary,
        due_deliveries=deliveries_due(business_id),
        chart_series=chart_series,
        product_chart=product_chart,
        status_chart=status_chart,
        period=period,
        start=start,
        end=end,
        today=date.today(),
    )
