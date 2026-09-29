"""Expense and ExpenseItem models.

`amount` is what was spent, and it is the only figure the dashboard and
reports read. The item rows are a free-standing note of what things cost
— "pink pipe cleaner, ₹120 each" — kept purely for reference. They are
never added up and have no bearing on `amount`.
"""

from datetime import datetime, date

from extensions import db


class Expense(db.Model):
    __tablename__ = "expenses"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False)
    expense_date = db.Column(db.Date, nullable=False, default=date.today)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    payment_method = db.Column(db.String(30), nullable=True)
    # Which partner of the business actually paid this — a dropdown of
    # partners rather than free text, so it can't drift into names that
    # aren't really part of the business. Nullable: expenses recorded
    # before this existed have no one on file, and that's fine.
    paid_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    # The alternative to paid_by_user_id: this came straight out of the
    # business's own funds/profit rather than a partner's pocket, so
    # there's no one to reimburse. Mutually exclusive with paid_by_user_id
    # — the form only ever sets one of the two.
    paid_from_business = db.Column(db.Boolean, nullable=False, default=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    paid_by = db.relationship("User")

    @property
    def paid_by_label(self):
        """How "who paid" reads on screen, or None if never recorded."""
        if self.paid_from_business:
            return "Business (Profit)"
        if self.paid_by:
            return self.paid_by.username
        return None

    items = db.relationship(
        "ExpenseItem", back_populates="expense", cascade="all, delete-orphan", lazy="dynamic"
    )

    @property
    def item_list(self):
        """Items ordered the way they were entered on the form."""
        return self.items.order_by(ExpenseItem.id).all()

    @property
    def item_count(self):
        return self.items.count()


    def __repr__(self):
        return f"<Expense {self.category} {self.amount}>"


class ExpenseItem(db.Model):
    __tablename__ = "expense_items"

    id = db.Column(db.Integer, primary_key=True)
    expense_id = db.Column(db.Integer, db.ForeignKey("expenses.id"), nullable=False)
    # Free text rather than a foreign key: raw materials are bought ad hoc
    # and do not need to exist in the product catalogue first.
    name = db.Column(db.String(120), nullable=False)
    # Numeric, not Integer — 0.5 kg or 2.5 m of something is legitimate.
    quantity = db.Column(db.Numeric(10, 2), nullable=False, default=1)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    expense = db.relationship("Expense", back_populates="items")

    def compute_subtotal(self):
        self.subtotal = round(float(self.quantity) * float(self.unit_price), 2)

    def __repr__(self):
        return f"<ExpenseItem {self.name} {self.subtotal}>"
