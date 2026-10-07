# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

from odoo import fields, models

# The public EasyOCR service, so a fresh company only has to add its key.
DEFAULT_AI_URL = 'https://app.easyocr.es'
DEFAULT_AI_TIMEOUT = 120


class ResCompany(models.Model):
    """Extraction settings, one set per company.

    They live on the company and not in ir.config_parameter because the service
    and its key are per company: a group with several companies can point each
    one at its own service, and the settings screen writes straight to the
    company the user is working in.
    """

    _inherit = 'res.company'

    easyocr_ai_enabled = fields.Boolean(
        string='AI Extraction',
        help='Send documents to the EasyOCR service to read them. Off by default: '
             'nothing leaves the server until this is on.',
    )
    easyocr_ai_url = fields.Char(
        string='Service URL',
        default=DEFAULT_AI_URL,
        help='Base address of the EasyOCR service. The endpoint is added on top.',
    )
    easyocr_ai_apikey = fields.Char(
        string='API Key',
        help='Key sent as the X-API-Key header. Requested from the service provider.',
    )
    easyocr_ai_timeout = fields.Integer(
        string='Timeout (seconds)',
        default=DEFAULT_AI_TIMEOUT,
        help='How long to wait for the service before giving up. A scanned page '
             'can take a while, so keep it generous.',
    )

    # Tells the service who is reading the document, so it does not hand our own
    # company back as the vendor. Off by default: it is the only setting that
    # changes what is sent, and the guard in _resolve_partner() catches the bad
    # case on its own.
    easyocr_ai_receiver_context = fields.Boolean(
        string='Tell the service who we are',
        help='Add our own name and tax number to the request, so the service can '
             'tell the two parties apart on the document.',
    )

    # --------------------------------------------------------------
    # What a document becomes
    # --------------------------------------------------------------
    easyocr_bill_post = fields.Boolean(
        string='Confirm the bill automatically',
        help='Post the supplier bill as soon as it is created, instead of leaving '
             'it in draft for review. Off by default: posting books the bill and '
             'gives it a number.',
    )
    easyocr_autocreate_product = fields.Boolean(
        string='Create products that do not exist',
        help='When a line carries a supplier reference no product matches, create '
             'the product instead of leaving the line without one.',
    )
    easyocr_allow_self_vendor = fields.Boolean(
        string='Accept our own company as vendor',
        help='Book a document whose tax number is ours. Off by default: it is '
             'almost always a document that was read the wrong way round.',
    )
    easyocr_duplicate_check = fields.Boolean(
        string='Refuse a document already read',
        default=True,
        help='Before sending a file to the service, look for a document with the '
             'same content that has already been read. Reading it again would cost '
             'the same and change nothing.',
    )
    easyocr_duplicate_window_days = fields.Integer(
        string='Duplicate window (days)',
        default=0,
        help='How far back that check looks. 0 means no limit. Useful for a vendor '
             'whose monthly document is exactly the same file every month.',
    )
