"""Customer model."""

from datetime import datetime

from extensions import db


class Customer(db.Model):
    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # A customer can have many sales/orders. Deleting a customer is
    # blocked at the route layer if they have existing orders, so this
    # relationship does not cascade-delete by default.
    sales = db.relationship("Sale", back_populates="customer", lazy="dynamic")

    def total_orders(self):
        return self.sales.count()

    def total_purchased(self):
        return sum(s.total_amount for s in self.sales) or 0

    def total_paid(self):
        return sum(s.amount_paid for s in self.sales) or 0

    def total_pending(self):
        return self.total_purchased() - self.total_paid()

    def last_purchase_date(self):
        last_sale = self.sales.order_by(db.desc("order_date")).first()
        return last_sale.order_date if last_sale else None

    def __repr__(self):
        return f"<Customer {self.name}>"
