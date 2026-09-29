"""
Optional helper to load a few sample records so you can see the app in
action before entering your own data.

Run with:  python seed_data.py

Safe to run multiple times — it checks for existing data first and does
nothing if any customers already exist, so it will never duplicate or
overwrite real business records.
"""

from datetime import date, timedelta

from app import create_app
from extensions import db
from models.business import Business
from models.customer import Customer
from models.product import Product
from models.sale import Sale, OrderItem
from models.expense import Expense

app = create_app()

with app.app_context():
    business = Business.query.order_by(Business.id).first()
    if business is None:
        print(
            "No business exists yet — open the app, create your account, and create "
            "your first business, then run this again."
        )
    elif Customer.query.filter_by(business_id=business.id).count() > 0:
        print(
            f"'{business.name}' already has data — skipping sample data "
            "(nothing was changed)."
        )
    else:
        bid = business.id
        priya = Customer(business_id=bid, name="Priya Sharma", phone="9876543210", email="priya@example.com")
        rahul = Customer(business_id=bid, name="Rahul Verma", phone="9123456780")
        db.session.add_all([priya, rahul])

        bouquet = Product(business_id=bid, name="Custom Bouquet", category="Flowers", selling_price=1200, cost_price=700)
        cake = Product(business_id=bid, name="Chocolate Cake", category="Bakery", selling_price=800, cost_price=350)
        db.session.add_all([bouquet, cake])
        db.session.flush()

        sale1 = Sale(business_id=bid, customer_id=priya.id, order_date=date.today() - timedelta(days=2), payment_method="UPI")
        item1 = OrderItem(product_id=bouquet.id, quantity=2, selling_price=bouquet.selling_price, cost_price=bouquet.cost_price)
        item1.compute_subtotal()
        sale1.items.append(item1)
        sale1.recompute_total()
        sale1.amount_paid = 1500
        sale1.recompute_payment_status()

        sale2 = Sale(business_id=bid, customer_id=rahul.id, order_date=date.today() - timedelta(days=1), payment_method="Cash")
        item2 = OrderItem(product_id=cake.id, quantity=1, selling_price=cake.selling_price, cost_price=cake.cost_price)
        item2.compute_subtotal()
        sale2.items.append(item2)
        sale2.recompute_total()
        sale2.amount_paid = 0
        sale2.recompute_payment_status()

        db.session.add_all([sale1, sale2])

        expense1 = Expense(business_id=bid, expense_date=date.today() - timedelta(days=3), category="Raw Materials",
                            description="Bought flowers and wrapping material", amount=850, payment_method="UPI")
        expense2 = Expense(business_id=bid, expense_date=date.today() - timedelta(days=1), category="Delivery",
                            description="Local delivery charges", amount=150, payment_method="Cash")
        db.session.add_all([expense1, expense2])

        db.session.commit()
        print(f"Sample data added to '{business.name}': 2 customers, 2 products, 2 sales, 2 expenses.")
