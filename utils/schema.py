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
