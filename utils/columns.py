"""Optional table columns.

List pages show a small default set of columns and offer the rest from a
Columns menu, so a table stays readable on a phone. The choice travels in
the query string next to the filters, which keeps it bookmarkable and
means the server renders exactly what was asked for.
"""

from flask import request


def selected_columns(optional_columns):
    """The valid column keys asked for in ?cols=...

    Anything not in `optional_columns` is dropped rather than trusted.
    """
    allowed = {key for key, _ in optional_columns}
    return [c for c in request.args.getlist("cols") if c in allowed]
