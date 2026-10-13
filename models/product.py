"""Product model."""

from datetime import datetime

from extensions import db


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(80), nullable=True)
    selling_price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    cost_price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    # Units currently on hand. A new sale deducts from this automatically
    # (see routes/sales.py); whatever it can't cover is tracked per order
    # line as OrderItem.pending_quantity instead of blocking the sale.
    stock_quantity = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    order_items = db.relationship("OrderItem", back_populates="product", lazy="dynamic")

    @property
    def pending_stock_quantity(self):
        """Units currently owed across every not-yet-delivered order.

        Once an order is marked Delivered it drops out of this total —
        by then it must have been fulfilled somehow, whether that meant
        restocking or producing more, so it no longer counts as owed.
        """
        from models.sale import Sale, OrderItem, DELIVERY_STATUS_DELIVERED

        total = (
            db.session.query(db.func.sum(OrderItem.pending_quantity))
            .join(Sale, Sale.id == OrderItem.order_id)
            .filter(OrderItem.product_id == self.id, Sale.delivery_status != DELIVERY_STATUS_DELIVERED)
            .scalar()
        )
        return total or 0

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
