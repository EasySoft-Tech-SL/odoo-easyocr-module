# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

from odoo import _, fields, models

from .easyocr_extractor import EasyocrServiceError


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
    easyocr_invoice_draft = fields.Boolean(
        related='company_id.easyocr_invoice_draft',
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

    # ------------------------------------------------------------------
    # Checking the settings before anything is sent
    # ------------------------------------------------------------------
    def action_easyocr_test_connection(self):
        """Ask the service about the account, and say what it answers.

        The screen this button sits on is where a key gets typed, so it is where
        a key that does not work should be caught. Asking the service who the key
        belongs to costs nothing -- unlike a reading, which is paid for on the
        way out and comes back refused -- so the mistake is found here instead of
        in the middle of a document.

        It asks about the company the screen is being edited *for*, not the one
        the user happens to be working in: with the settings open for another
        company, that other company's key is the one being typed.
        """
        self.ensure_one()
        company = self.company_id or self.env.company
        try:
            account = self.env['easyocr.extractor'].account(company)
        except EasyocrServiceError as error:
            return self._easyocr_answer('warning', str(error))

        status = account.get('status') or {}
        if not status.get('can_process', True):
            return self._easyocr_answer(
                'warning',
                status.get('block_message')
                or _("The EasyOCR account cannot read documents right now."),
            )

        quota = account.get('quota') or {}
        answer = _(
            "The service answered. Account: %(account)s, plan: %(plan)s.",
            account=(account.get('account') or {}).get('name') or _("no name"),
            plan=(account.get('plan') or {}).get('name') or _("no plan"),
        )
        if quota.get('pages_remaining') is not None:
            answer = _(
                "%(answer)s %(pages)s pages left to read this month.",
                answer=answer,
                pages=quota['pages_remaining'],
            )
        return self._easyocr_answer('success', answer)

    def _easyocr_answer(self, kind, message):
        """Show the answer to the button and leave it there to be read.

        Sticky on purpose: it is the reply to something the reader just asked,
        and a reply that disappears on its own is one they have to ask for again.
        """
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': kind,
                'message': message,
                'sticky': True,
            },
        }
