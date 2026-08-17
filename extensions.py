"""
Shared extension instances.

Kept in their own module (rather than inside app.py) so that model
files can `from extensions import db` without causing circular imports.
"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
