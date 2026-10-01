"""
Database models package.

Importing this package registers every model with SQLAlchemy so that
`db.create_all()` (see app.py) creates every table.
"""

from models.business import Business
from models.business_partner import BusinessPartner
from models.customer import Customer
from models.product import Product
from models.sale import Sale, OrderItem
from models.expense import Expense, ExpenseItem
from models.expense_category import ExpenseCategory
from models.expense_share import ExpenseShare
from models.user import User

__all__ = [
    "Business",
    "BusinessPartner",
    "Customer",
    "Product",
    "Sale",
    "OrderItem",
    "Expense",
    "ExpenseItem",
    "ExpenseCategory",
    "ExpenseShare",
    "User",
]
