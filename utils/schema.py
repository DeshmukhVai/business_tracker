"""Tiny forward-only schema top-up for columns added after launch.

`db.create_all()` creates missing *tables* but never adds a missing
*column* to a table that already exists, so a database created before a
feature shipped would raise "no such column" on the next query.

Each entry below is applied only when the column is absent, which makes
this safe to run on every startup — including on PythonAnywhere, where
there is no migration step and existing business data must survive.
"""

from sqlalchemy import text

# table -> column -> (DDL type + default, backfill SQL or None)
ADDED_COLUMNS = {
    "sales": {
        # Discounts used to be a flat rupee amount only. Older orders are
        # backfilled as flat discounts of the amount they already had, so
        # their totals stay exactly as recorded.
        "discount_type": (
            "VARCHAR(10) NOT NULL DEFAULT 'amount'",
            "UPDATE sales SET discount_type = 'amount' WHERE discount_type IS NULL",
        ),
        "discount_value": (
            "NUMERIC(10, 2) NOT NULL DEFAULT 0",
            "UPDATE sales SET discount_value = COALESCE(discount, 0)",
        ),
        # Orders recorded before delivery tracking existed have no date.
        "delivery_date": ("DATE", None),
        # They are left as Pending rather than assumed delivered: a wrong
        # "Pending" is visible and easy to correct, whereas a wrong
        # "Delivered" would silently hide an order still owed to someone.
        "delivery_status": (
            "VARCHAR(20) NOT NULL DEFAULT 'Pending'",
            "UPDATE sales SET delivery_status = 'Pending' WHERE delivery_status IS NULL",
        ),
        "business_id": ("INTEGER", None),
    },
    # Multi-business support: every business-owned table gets a nullable
    # business_id column added here, then backfilled onto a "Default
    # Business" by ensure_default_business() below — a real NOT NULL
    # constraint isn't added since SQLite can't do that without rebuilding
    # the table, and application code always sets it on new rows anyway.
    "customers": {"business_id": ("INTEGER", None)},
    "products": {"business_id": ("INTEGER", None)},
    "expenses": {
        "business_id": ("INTEGER", None),
        # Which partner paid — see models/expense.py for why this is a
        # user reference rather than free text.
        "paid_by_user_id": ("INTEGER", None),
        # Replaces the old all-or-nothing paid_from_business flag with a
        # split amount, so an expense can be partly business-funded and
        # partly personal. Expenses that had the flag set are backfilled
        # as fully business-funded, matching what that flag used to mean;
        # everything else defaults to 0 (fully personal, or unspecified).
        "business_amount": (
            "NUMERIC(10, 2) NOT NULL DEFAULT 0",
            "UPDATE expenses SET business_amount = amount WHERE paid_from_business = 1",
        ),
    },
}


def _existing_columns(connection, table_name):
    rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return {row[1] for row in rows}


def _table_exists(connection, table_name):
    row = connection.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),
        {"name": table_name},
    ).fetchone()
    return row is not None


def ensure_columns(db):
    """Add any columns that this version of the code expects but the
    database does not have yet. Returns the list of columns added."""
    # PRAGMA/ALTER syntax here is SQLite-specific; skip on anything else
    # rather than emitting statements another engine would reject.
    if db.engine.dialect.name != "sqlite":
        return []

    added = []
    with db.engine.begin() as connection:
        for table_name, columns in ADDED_COLUMNS.items():
            if not _table_exists(connection, table_name):
                continue  # create_all() will build it complete
            present = _existing_columns(connection, table_name)
            for column_name, (ddl, backfill) in columns.items():
                if column_name in present:
                    continue
                connection.execute(
                    text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}")
                )
                if backfill:
                    connection.execute(text(backfill))
                added.append(f"{table_name}.{column_name}")
    return added


def migrate_expense_categories_table(db):
    """Rebuild expense_categories with a per-business unique constraint.

    Its name column used to be globally unique. Multi-business support
    needs "Packaging" to exist once per business rather than once total,
    and SQLite cannot alter a unique constraint in place, so the table is
    rebuilt: a new table with the right constraint, the old rows copied
    across, then the old table swapped out. `business_id` comes along as
    plain NULL for now; ensure_default_business() backfills it afterwards.

    A no-op once the table already has a business_id column (including on
    every fresh install, where create_all() already built it correctly).
    """
    if db.engine.dialect.name != "sqlite":
        return False

    with db.engine.begin() as connection:
        if not _table_exists(connection, "expense_categories"):
            return False
        if "business_id" in _existing_columns(connection, "expense_categories"):
            return False

        connection.execute(
            text(
                "CREATE TABLE expense_categories_new ("
                "id INTEGER PRIMARY KEY, "
                "business_id INTEGER, "
                "name VARCHAR(50) NOT NULL, "
                "created_at DATETIME, "
                "UNIQUE (business_id, name))"
            )
        )
        connection.execute(
            text(
                "INSERT INTO expense_categories_new (id, name, created_at) "
                "SELECT id, name, created_at FROM expense_categories"
            )
        )
        connection.execute(text("DROP TABLE expense_categories"))
        connection.execute(
            text("ALTER TABLE expense_categories_new RENAME TO expense_categories")
        )
    return True


# Every table that now carries a business_id column, needing a value
# backfilled for rows that predate multi-business support.
BUSINESS_SCOPED_TABLES = ["customers", "products", "sales", "expenses", "expense_categories"]


def ensure_default_business(db):
    """Give pre-existing data a home: a "Default Business" owned by every
    user account that already existed.

    Runs once, only when there is a row with business_id still NULL — a
    brand new install never has one, since every row created after this
    feature shipped is created with a business already chosen. Returns
    the business name if one was created, else None.
    """
    with db.engine.connect() as connection:
        needs_backfill = False
        for table_name in BUSINESS_SCOPED_TABLES:
            if not _table_exists(connection, table_name):
                continue
            row = connection.execute(
                text(f"SELECT 1 FROM {table_name} WHERE business_id IS NULL LIMIT 1")
            ).fetchone()
            if row is not None:
                needs_backfill = True
                break
    if not needs_backfill:
        return None

    from models.business import Business
    from models.business_partner import BusinessPartner, ROLE_OWNER
    from models.user import User

    default_business = Business(name="My Business")
    db.session.add(default_business)
    db.session.flush()
    for user in User.query.all():
        db.session.add(
            BusinessPartner(business_id=default_business.id, user_id=user.id, role=ROLE_OWNER)
        )
    db.session.commit()

    with db.engine.begin() as connection:
        for table_name in BUSINESS_SCOPED_TABLES:
            if not _table_exists(connection, table_name):
                continue
            connection.execute(
                text(f"UPDATE {table_name} SET business_id = :bid WHERE business_id IS NULL"),
                {"bid": default_business.id},
            )

    return default_business.name
