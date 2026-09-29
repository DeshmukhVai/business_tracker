"""Expense categories.

These used to be a fixed list in config.py, which meant adding one needed
a code change. They now live in the database so they can be added from the
expense form itself. The config list is what a new business gets seeded
with, so it starts out with a sensible default set.

Categories are scoped per business (via `business_id`) rather than
global, so two businesses can each have their own "Packaging" without
colliding — hence the uniqueness is on (business_id, name), not name alone.
"""

from datetime import datetime

from extensions import db


class ExpenseCategory(db.Model):
    __tablename__ = "expense_categories"
    __table_args__ = (
        db.UniqueConstraint("business_id", "name", name="uq_expense_category_business_name"),
    )

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @staticmethod
    def names(business_id):
        return [
            c.name
            for c in ExpenseCategory.query.filter_by(business_id=business_id)
            .order_by(ExpenseCategory.name)
            .all()
        ]

    @staticmethod
    def find_by_name(business_id, name):
        """Case-insensitive lookup, so "tape" and "Tape" are not two rows."""
        return ExpenseCategory.query.filter(
            ExpenseCategory.business_id == business_id,
            db.func.lower(ExpenseCategory.name) == (name or "").strip().lower(),
        ).first()

    @staticmethod
    def seed_defaults(business_id, default_names):
        """Insert the starting categories, once, for a business with none yet.

        Called when a business is created, so every business starts out
        with the same default set as the original single-business tracker.
        """
        if ExpenseCategory.query.filter_by(business_id=business_id).first() is not None:
            return []
        added = []
        for name in default_names:
            db.session.add(ExpenseCategory(business_id=business_id, name=name))
            added.append(name)
        db.session.commit()
        return added

    def __repr__(self):
        return f"<ExpenseCategory {self.name}>"
