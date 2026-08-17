"""Expense categories.

These used to be a fixed list in config.py, which meant adding one needed
a code change. They now live in the database so they can be added from the
expense form itself. The config list survives as the set seeded on first
run, so an existing tracker keeps exactly the categories it had.
"""

from datetime import datetime

from extensions import db


class ExpenseCategory(db.Model):
    __tablename__ = "expense_categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @staticmethod
    def names():
        return [c.name for c in ExpenseCategory.query.order_by(ExpenseCategory.name).all()]

    @staticmethod
    def find_by_name(name):
        """Case-insensitive lookup, so "tape" and "Tape" are not two rows."""
        return ExpenseCategory.query.filter(
            db.func.lower(ExpenseCategory.name) == (name or "").strip().lower()
        ).first()

    @staticmethod
    def seed_defaults(default_names):
        """Insert the starting categories, once, on an empty table.

        Also runs for a database created before categories were stored,
        so nothing that was previously offered goes missing.
        """
        if db.session.query(ExpenseCategory.id).first() is not None:
            return []
        added = []
        for name in default_names:
            db.session.add(ExpenseCategory(name=name))
            added.append(name)
        db.session.commit()
        return added

    def __repr__(self):
        return f"<ExpenseCategory {self.name}>"
