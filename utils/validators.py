"""
Small, dependency-free validation helpers used by every route module.

Each function raises ValueError with a human-readable message when the
input is invalid, so routes can do:

    try:
        amount = parse_positive_amount(request.form.get("amount"))
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(...)
"""

from datetime import datetime


def parse_amount(raw_value, field_name="Amount", allow_zero=True):
    """Parse a money value, rejecting negatives and non-numeric input."""
    if raw_value is None or str(raw_value).strip() == "":
        raise ValueError(f"{field_name} is required.")
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a valid number.")
    if value < 0:
        raise ValueError(f"{field_name} cannot be negative.")
    if not allow_zero and value == 0:
        raise ValueError(f"{field_name} must be greater than zero.")
    return round(value, 2)


def parse_positive_int(raw_value, field_name="Quantity", minimum=1):
    if raw_value is None or str(raw_value).strip() == "":
        raise ValueError(f"{field_name} is required.")
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a whole number.")
    if value < minimum:
        raise ValueError(f"{field_name} must be at least {minimum}.")
    return value


def parse_percent(raw_value, field_name="Percentage"):
    """Parse a 0-100 percentage."""
    if raw_value is None or str(raw_value).strip() == "":
        return 0.0
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a valid number.")
    if value < 0:
        raise ValueError(f"{field_name} cannot be negative.")
    if value > 100:
        raise ValueError(f"{field_name} cannot be more than 100%.")
    return round(value, 2)


def parse_quantity(raw_value, field_name="Quantity"):
    """Parse a decimal quantity — 0.5 kg or 2.5 m of a raw material is valid."""
    if raw_value is None or str(raw_value).strip() == "":
        raise ValueError(f"{field_name} is required.")
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a valid number.")
    if value <= 0:
        raise ValueError(f"{field_name} must be greater than zero.")
    return round(value, 2)


def parse_required_text(raw_value, field_name="This field", max_length=None):
    if raw_value is None or str(raw_value).strip() == "":
        raise ValueError(f"{field_name} is required.")
    text = str(raw_value).strip()
    if max_length and len(text) > max_length:
        raise ValueError(f"{field_name} must be {max_length} characters or fewer.")
    return text


def parse_date(raw_value, field_name="Date"):
    if raw_value is None or str(raw_value).strip() == "":
        raise ValueError(f"{field_name} is required.")
    try:
        return datetime.strptime(raw_value, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"{field_name} must be a valid date (YYYY-MM-DD).")


def parse_optional_date(raw_value, field_name="Date"):
    """Like parse_date, but an empty value is allowed and returns None."""
    if raw_value is None or str(raw_value).strip() == "":
        return None
    return parse_date(raw_value, field_name)


def parse_optional_text(raw_value, max_length=None):
    if raw_value is None:
        return None
    text = str(raw_value).strip()
    if not text:
        return None
    if max_length and len(text) > max_length:
        raise ValueError(f"Value must be {max_length} characters or fewer.")
    return text
