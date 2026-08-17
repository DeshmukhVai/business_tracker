"""Sale (order) and OrderItem models."""

from datetime import datetime, date

from extensions import db

PAYMENT_STATUS_PAID = "Paid"
PAYMENT_STATUS_PARTIAL = "Partially Paid"
PAYMENT_STATUS_PENDING = "Pending"

# A discount is entered either as a flat rupee amount off, or as a
# percentage of the items total. Whichever way it was typed, `discount`
# always stores the resolved rupee figure so every existing report,
# invoice and total keeps reading one field.
DISCOUNT_TYPE_AMOUNT = "amount"
DISCOUNT_TYPE_PERCENT = "percent"
DISCOUNT_TYPES = (DISCOUNT_TYPE_AMOUNT, DISCOUNT_TYPE_PERCENT)

# Delivery is tracked separately from payment — an order can be paid but
# not yet delivered, or delivered but not yet paid. Unlike payment status
# this cannot be derived from anything, so it is set by hand.
DELIVERY_STATUS_PENDING = "Pending"
DELIVERY_STATUS_DELIVERED = "Delivered"
DELIVERY_STATUSES = (DELIVERY_STATUS_PENDING, DELIVERY_STATUS_DELIVERED)


class Sale(db.Model):
    __tablename__ = "sales"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    order_date = db.Column(db.Date, nullable=False, default=date.today)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    # Resolved rupee discount — always derived, never set directly by the UI.
    discount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    # What the user actually typed, kept so the edit form can show "10%"
    # rather than the rupee figure it worked out to.
    discount_type = db.Column(db.String(10), nullable=False, default=DISCOUNT_TYPE_AMOUNT)
    discount_value = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    amount_paid = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    payment_status = db.Column(db.String(20), nullable=False, default=PAYMENT_STATUS_PENDING)
    # When the order is due to reach the customer. Optional — plenty of
    # orders are handed over on the spot.
    delivery_date = db.Column(db.Date, nullable=True)
    delivery_status = db.Column(
        db.String(20), nullable=False, default=DELIVERY_STATUS_PENDING
    )
    payment_method = db.Column(db.String(30), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    customer = db.relationship("Customer", back_populates="sales")
    items = db.relationship(
        "OrderItem", back_populates="sale", cascade="all, delete-orphan", lazy="dynamic"
    )

    @property
    def remaining_amount(self):
        return float(self.total_amount) - float(self.amount_paid)

    @property
    def estimated_profit(self):
        return sum(
            (float(item.selling_price) - float(item.cost_price)) * item.quantity
            for item in self.items
        )

    def recompute_payment_status(self):
        """Derive payment_status from total_amount / amount_paid.

        Always call this after changing amount_paid or total_amount, then
        commit — the status is never set directly by the UI.
        """
        paid = float(self.amount_paid or 0)
        total = float(self.total_amount or 0)
        if total <= 0:
            # Nothing left to collect — e.g. an order given away at a 100%
            # discount. Without this it would sit on the Pending Payments
            # page forever, reporting that ₹0 is owed.
            self.payment_status = PAYMENT_STATUS_PAID
        elif paid <= 0:
            self.payment_status = PAYMENT_STATUS_PENDING
        elif paid >= total:
            self.payment_status = PAYMENT_STATUS_PAID
        else:
            self.payment_status = PAYMENT_STATUS_PARTIAL

    @property
    def is_delivered(self):
        return self.delivery_status == DELIVERY_STATUS_DELIVERED

    @property
    def is_delivery_overdue(self):
        """Still undelivered with its delivery date already past.

        Derived on read rather than stored, so an order becomes overdue on
        its own as the date passes — nothing has to run overnight.
        """
        if self.is_delivered or not self.delivery_date:
            return False
        return self.delivery_date < date.today()

    @property
    def days_until_delivery(self):
        """Negative when overdue, 0 for today, None when no date is set."""
        if not self.delivery_date:
            return None
        return (self.delivery_date - date.today()).days

    @property
    def items_subtotal(self):
        """Order value before any discount."""
        return round(sum(float(item.subtotal) for item in self.items), 2)

    @property
    def discount_label(self):
        """How the discount reads on screen, e.g. '10%' or 'flat'."""
        if self.discount_type == DISCOUNT_TYPE_PERCENT:
            value = float(self.discount_value or 0)
            # Trim a trailing .0 so 10% does not render as 10.0%.
            return f"{value:g}%"
        return "flat"

    def compute_discount(self, items_total):
        """Resolve the entered discount into rupees.

        Capped at the items total so a 120% or oversized flat discount can
        never produce a negative order.
        """
        value = float(self.discount_value or 0)
        if self.discount_type == DISCOUNT_TYPE_PERCENT:
            amount = items_total * value / 100.0
        else:
            amount = value
        return round(min(max(amount, 0.0), items_total), 2)

    def recompute_total(self, items=None):
        """Recompute discount and total_amount from the line items.

        `items` may be passed explicitly so this works before a new sale
        has been flushed to the database.
        """
        rows = list(self.items) if items is None else list(items)
        items_total = round(sum(float(item.subtotal) for item in rows), 2)
        self.discount = self.compute_discount(items_total)
        self.total_amount = round(max(items_total - float(self.discount), 0), 2)

    def __repr__(self):
        return f"<Sale #{self.id} customer={self.customer_id}>"


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("sales.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    # selling_price / cost_price are snapshotted at time of sale so that
    # later edits to a product's prices do not rewrite historical orders.
    selling_price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    cost_price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    sale = db.relationship("Sale", back_populates="items")
    product = db.relationship("Product", back_populates="order_items")

    def compute_subtotal(self):
        self.subtotal = float(self.selling_price) * int(self.quantity)

    def __repr__(self):
        return f"<OrderItem order={self.order_id} product={self.product_id}>"
