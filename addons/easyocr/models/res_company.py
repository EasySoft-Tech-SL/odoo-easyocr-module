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
    easyocr_invoice_draft = fields.Boolean(
        string='Create invoices as draft',
        help='When on, the invoices the module creates are left in draft instead '
             'of being posted automatically, so a person confirms them.',
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
        string='Ask before reading a document already read',
        default=True,
        help='Before sending a file to the service, look for a document with the '
             'same content that has already been read, and ask. Reading it again '
             'costs a reading; leaving the question alone costs nothing.',
    )
    easyocr_duplicate_window_days = fields.Integer(
        string='Duplicate window (days)',
        default=0,
        help='How far back that check looks. 0 means no limit. Useful for a vendor '
             'whose monthly document is exactly the same file every month.',
    )

    # --------------------------------------------------------------
    # What a photographed receipt becomes
    # --------------------------------------------------------------
    easyocr_expense_target = fields.Selection(
        selection=[
            ('bill', 'Supplier bill'),
            ('expense', 'Employee expense'),
        ],
        string='A photographed receipt becomes',
        default='bill',
        help='Where a receipt photographed from a phone ends up. A supplier bill '
             'needs a vendor; a ticket from a petrol station is not one, so the '
             'employee expense is usually the better fit when the person taking '
             'the photo is the one who paid.',
    )
    easyocr_expense_allow_validate = fields.Boolean(
        string='Let the phone send the expense',
        help='Let whoever took the photo put the expense forward for approval at '
             'the same time, instead of leaving it in draft until they open Odoo.',
    )

    # --------------------------------------------------------------
    # What a webhook is allowed to do on its own
    # --------------------------------------------------------------
    easyocr_webhook_create_bill = fields.Boolean(
        string='Create the bill from a webhook',
        help='When the service says it has finished reading a document, make the '
             'supplier bill from it without waiting for anyone. Off by default: a '
             'webhook is a message from outside, and a bill is an accounting entry.',
    )
    easyocr_webhook_mark_paid = fields.Boolean(
        string='Mark the bill as paid',
        help='Register the payment on the bills a webhook creates, as if the money '
             'had already gone out. It only applies to a bill that is confirmed, '
             'because a bill in draft has nothing to pay against.',
    )
    easyocr_webhook_journal_id = fields.Many2one(
        comodel_name='account.journal',
        string='Bank account',
        domain="[('type', 'in', ('bank', 'cash')), ('company_id', '=', id)]",
        help='Where the payment of a webhook bill is recorded.',
    )
    easyocr_webhook_payment_method_line_id = fields.Many2one(
        comodel_name='account.payment.method.line',
        string='Payment method',
        help='How the payment is recorded on that bank account. Left empty, Odoo '
             'takes the one the account has by default.',
    )
