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

import datetime


def to_float(value, default=0.0):
    """Read a number that may arrive as a string, without blowing up on junk."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def to_amount(text, default=None):
    """Read an amount as a person wrote it, or nothing at all.

    What comes out of a rectangle on a page is not a number: it is whatever the
    paper printed, which is "320,77 EUR" here and "1.234,56" as soon as the
    amount runs into the thousands. The separators decide, and they decide the
    way the last one written does: with both present the one on the right is the
    decimal. A lone dot with exactly three digits behind it is read as a
    thousands separator, which is what it is on a Spanish invoice.

    Anything with no digits in it is not an amount, and answers `default`: a
    rectangle drawn over the wrong part of the page must leave the field it was
    meant for alone, not fill it with zero.
    """
    if isinstance(text, (int, float)):
        return float(text)
    if not isinstance(text, str):
        return default
    limpio = ''.join(c for c in text if c.isdigit() or c in ',.-')
    if not any(c.isdigit() for c in limpio):
        return default
    negativo = limpio.startswith('-')
    limpio = limpio.lstrip('-')
    if ',' in limpio and '.' in limpio:
        decimal = ',' if limpio.rfind(',') > limpio.rfind('.') else '.'
        millar = '.' if decimal == ',' else ','
        limpio = limpio.replace(millar, '').replace(decimal, '.')
    elif ',' in limpio:
        limpio = limpio.replace(',', '.')
    elif limpio.count('.') == 1:
        entero, _, cola = limpio.partition('.')
        if len(cola) == 3 and entero and len(entero) <= 3:
            # "1.234" y no "1,234": en un papel de aqui son mil doscientos
            # treinta y cuatro.
            limpio = entero + cola
    elif limpio.count('.') > 1:
        limpio = limpio.replace('.', '')
    try:
        amount = float(limpio)
    except ValueError:
        return default
    return -amount if negativo else amount


def to_date(text, default=None):
    """Read a date as a person wrote it, or nothing at all.

    Odoo reads ISO dates and little else, and a supplier prints 30/09/2026.
    """
    if not isinstance(text, str):
        return default
    limpio = text.strip()
    for formato in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y', '%d/%m/%y', '%Y/%m/%d'):
        try:
            return datetime.datetime.strptime(limpio, formato).date()
        except ValueError:
            continue
    return default



# Postgres codes of the errors a second try can get past: a lock that was not
# had in time, a write refused because another transaction got there first, and
# a deadlock. Read from the error itself, so psycopg2 and psycopg 3 both work.
CONCURRENCY_ERROR_CODES = ('55P03', '40001', '40P01')


def is_concurrency_error(error):
    """Whether the error is one that waiting and trying again would fix."""
    code = getattr(error, 'pgcode', None) or getattr(error, 'sqlstate', None)
    return code in CONCURRENCY_ERROR_CODES


def param_value(env, key):
    """A system parameter as text, on every series.

    Odoo 20 reads every parameter as its own type and no longer offers the
    untyped get_param; the series before it have only get_param.
    """
    parameters = env['ir.config_parameter'].sudo()
    getter = getattr(parameters, 'get_str', None) or parameters.get_param
    return getter(key) or ''


def set_param_value(env, key, value):
    """Write a system parameter as text, on every series."""
    parameters = env['ir.config_parameter'].sudo()
    setter = getattr(parameters, 'set_str', None) or parameters.set_param
    setter(key, value)
