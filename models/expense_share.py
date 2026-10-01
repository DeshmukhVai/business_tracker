"""ExpenseShare — reimbursement owed between partners.

When a partner pays for an expense out of their own pocket (see
Expense.paid_by_user_id) rather than it coming out of business funds,
every other partner owes an equal share of it back to whoever paid. One
row per owing partner per expense, created when the expense is saved and
settled individually as each partner pays their share back.
"""

from datetime import datetime

from extensions import db


class ExpenseShare(db.Model):
    __tablename__ = "expense_shares"

    id = db.Column(db.Integer, primary_key=True)
    expense_id = db.Column(db.Integer, db.ForeignKey("expenses.id"), nullable=False)
    owed_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    is_settled = db.Column(db.Boolean, nullable=False, default=False)
    settled_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    expense = db.relationship("Expense", back_populates="shares")
    owed_by = db.relationship("User")

    def mark_settled(self):
        self.is_settled = True
        self.settled_at = datetime.utcnow()

    def mark_unsettled(self):
        self.is_settled = False
        self.settled_at = None

    def __repr__(self):
        return f"<ExpenseShare expense={self.expense_id} owed_by={self.owed_by_user_id} amount={self.amount}>"
