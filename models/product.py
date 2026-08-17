"""Product model."""

from datetime import datetime

from extensions import db


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(80), nullable=True)
    selling_price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    cost_price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    order_items = db.relationship("OrderItem", back_populates="product", lazy="dynamic")

    @property
    def profit_per_item(self):
        return float(self.selling_price) - float(self.cost_price)

    def units_sold(self):
        return sum(item.quantity for item in self.order_items) or 0

    def total_revenue(self):
        return sum(item.subtotal for item in self.order_items) or 0

    def estimated_profit(self):
        return sum(
            (float(item.selling_price) - float(item.cost_price)) * item.quantity
            for item in self.order_items
        )

    def __repr__(self):
        return f"<Product {self.name}>"
