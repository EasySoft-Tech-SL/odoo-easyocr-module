# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

from odoo import models


class AccountMove(models.Model):
    """A bill deleted takes with it the copy of the call that made it.

    The webhook log keeps the body of a call that needed a person, and that
    body is the whole reading: names, tax numbers, addresses. Once the bill it
    was kept for is gone there is nothing left to review, and the copy is
    personal data with no purpose. The line of the log stays, without it.
    """

    _inherit = 'account.move'

    def unlink(self):
        documents = self.env['easyocr.document'].sudo().search([('move_id', 'in', self.ids)])
        result = super().unlink()
        if documents:
            self.env['easyocr.webhook.log'].sudo().search([
                ('document_id', 'in', documents.ids),
                ('payload', '!=', False),
            ]).write({'payload': False})
        return result
