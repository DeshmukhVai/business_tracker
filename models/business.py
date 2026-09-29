"""Business model — the top-level entity all records belong to.

One tracker instance can run more than one business, each with its own
customers, products, sales and expenses. A business is shared with
whichever users partner in it (see BusinessPartner) rather than
belonging to a single owner.
"""

from datetime import datetime

from extensions import db


class Business(db.Model):
    __tablename__ = "businesses"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    partnerships = db.relationship(
        "BusinessPartner", back_populates="business", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Business {self.name}>"
