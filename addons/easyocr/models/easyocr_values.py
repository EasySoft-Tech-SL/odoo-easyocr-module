# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

"""Reading the values the extraction service sends.

This file holds no model on purpose. The document and the service client both
need to read a number that arrives as a string, and neither may import the
other: importing one model module from inside another reorders the classes
Odoo registers, and the registry then refuses a _inherit whose base has not
been added yet ("Model 'easyocr.document' does not exist in registry"). A module
with no models in it cannot do that, so the reader lives here.
"""


def to_float(value, default=0.0):
    """Read a number that may arrive as a string, without blowing up on junk."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
