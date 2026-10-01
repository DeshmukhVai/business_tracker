"""Partner settlements: who owes whom for expenses paid personally.

When a partner pays for an expense out of their own pocket instead of
business funds, every other partner's equal share of it (see
routes/expenses.py: _apply_expense_shares) is tracked here until they
pay it back.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, g

from extensions import db
from models.expense import Expense
from models.expense_share import ExpenseShare

settlements_bp = Blueprint("settlements", __name__, url_prefix="/settlements")


def _business_shares(business_id, include_settled):
    query = ExpenseShare.query.join(Expense).filter(Expense.business_id == business_id)
    if not include_settled:
        query = query.filter(ExpenseShare.is_settled.is_(False))
    return query.order_by(Expense.expense_date.desc(), Expense.id.desc()).all()


def _find_share(share_id):
    """The share, scoped to the active business — or None if it isn't here."""
    return (
        ExpenseShare.query.join(Expense)
        .filter(ExpenseShare.id == share_id, Expense.business_id == g.business.id)
        .first()
    )


@settlements_bp.route("/")
def index():
    show_settled = request.args.get("show_settled") == "1"
    shares = _business_shares(g.business.id, include_settled=show_settled)

    # Net balances per pair of people, not per direction: if Disha owes
    # Vaibhavi 2500 from one expense and Vaibhavi owes Disha 1000 from
    # another, that's one person owing the other 1500 — not two separate
    # debts sitting there looking unrelated.
    pair_totals = {}
    people = {}
    for share in shares:
        if share.is_settled:
            continue
        payer = share.expense.paid_by
        ower = share.owed_by
        if not payer or not ower or payer.id == ower.id:
            continue
        people[payer.id] = payer
        people[ower.id] = ower

        totals = pair_totals.setdefault(frozenset((payer.id, ower.id)), {})
        totals[ower.id] = totals.get(ower.id, 0.0) + float(share.amount)

    balances = []
    for pair, totals in pair_totals.items():
        id1, id2 = tuple(pair)
        net = round(totals.get(id1, 0.0) - totals.get(id2, 0.0), 2)
        if net == 0:
            continue  # what they owe each other cancels out exactly
        ower_id, payer_id = (id1, id2) if net > 0 else (id2, id1)
        balances.append(
            {"ower": people[ower_id], "payer": people[payer_id], "amount": abs(net)}
        )

    balances.sort(key=lambda r: r["amount"], reverse=True)
    total_outstanding = sum(r["amount"] for r in balances)

    return render_template(
        "settlements/index.html",
        shares=shares,
        balances=balances,
        total_outstanding=total_outstanding,
        show_settled=show_settled,
    )


@settlements_bp.route("/<int:share_id>/settle", methods=["POST"])
def settle(share_id):
    share = _find_share(share_id)
    if not share:
        flash("That settlement could not be found.", "error")
        return redirect(url_for("settlements.index"))

    share.mark_settled()
    db.session.commit()
    flash(f"Marked {share.owed_by.username}'s share as settled.", "success")
    return redirect(request.referrer or url_for("settlements.index"))


@settlements_bp.route("/<int:share_id>/unsettle", methods=["POST"])
def unsettle(share_id):
    share = _find_share(share_id)
    if not share:
        flash("That settlement could not be found.", "error")
        return redirect(url_for("settlements.index"))

    share.mark_unsettled()
    db.session.commit()
    flash("Marked as not yet settled.", "success")
    return redirect(request.referrer or url_for("settlements.index"))
