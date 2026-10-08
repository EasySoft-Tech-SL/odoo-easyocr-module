# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    """The EasyOCR block of the settings screen.

    Each field mirrors a field on res.company through a writable related field,
    so saving the screen updates the company that is being configured and the
    value is read back from it next time.
    """

    _inherit = 'res.config.settings'

    easyocr_ai_enabled = fields.Boolean(
        related='company_id.easyocr_ai_enabled',
        readonly=False,
    )
    easyocr_ai_url = fields.Char(
        related='company_id.easyocr_ai_url',
        readonly=False,
    )
    easyocr_ai_apikey = fields.Char(
        related='company_id.easyocr_ai_apikey',
        readonly=False,
    )
    easyocr_ai_timeout = fields.Integer(
        related='company_id.easyocr_ai_timeout',
        readonly=False,
    )
    easyocr_ai_receiver_context = fields.Boolean(
        related='company_id.easyocr_ai_receiver_context',
        readonly=False,
    )
    easyocr_bill_post = fields.Boolean(
        related='company_id.easyocr_bill_post',
        readonly=False,
    )
    easyocr_autocreate_product = fields.Boolean(
        related='company_id.easyocr_autocreate_product',
        readonly=False,
    )
    easyocr_allow_self_vendor = fields.Boolean(
        related='company_id.easyocr_allow_self_vendor',
        readonly=False,
    )
    easyocr_duplicate_check = fields.Boolean(
        related='company_id.easyocr_duplicate_check',
        readonly=False,
    )
    easyocr_duplicate_window_days = fields.Integer(
        related='company_id.easyocr_duplicate_window_days',
        readonly=False,
    )
    easyocr_expense_target = fields.Selection(
        related='company_id.easyocr_expense_target',
        readonly=False,
    )
    easyocr_expense_allow_validate = fields.Boolean(
        related='company_id.easyocr_expense_allow_validate',
        readonly=False,
    )
    easyocr_webhook_create_bill = fields.Boolean(
        related='company_id.easyocr_webhook_create_bill',
        readonly=False,
    )
    easyocr_webhook_mark_paid = fields.Boolean(
        related='company_id.easyocr_webhook_mark_paid',
        readonly=False,
    )
    easyocr_webhook_journal_id = fields.Many2one(
        related='company_id.easyocr_webhook_journal_id',
        readonly=False,
    )
    easyocr_webhook_payment_method_line_id = fields.Many2one(
        related='company_id.easyocr_webhook_payment_method_line_id',
        readonly=False,
    )
