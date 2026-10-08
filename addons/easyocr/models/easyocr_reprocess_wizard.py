# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

from odoo import _, api, fields, models
from odoo.tools import format_datetime


class EasyocrReprocessWizard(models.TransientModel):
    """The question asked before reading a file that has already been read.

    A reading costs the same the second time and usually answers the same
    thing, so it is never automatic. It is still the reader's call, because a
    fixed monthly charge really is the same file every month and a fingerprint
    cannot tell the difference. The module this is a port of asks the same
    question with the same two answers, and this is that dialog in Odoo: the
    server refuses nothing, it asks.
    """

    _name = 'easyocr.reprocess.wizard'
    _description = 'Read a document again'

    document_id = fields.Many2one(
        'easyocr.document',
        string='Document',
        required=True,
        ondelete='cascade',
        readonly=True,
    )
    duplicate_id = fields.Many2one(
        'easyocr.document',
        string='Already read as',
        readonly=True,
    )
    message = fields.Text(
        string='What was found',
        compute='_compute_message',
        readonly=True,
    )

    @api.depends('duplicate_id')
    def _compute_message(self):
        for wizard in self:
            wizard.message = wizard._compose_message()

    def _compose_message(self):
        """What the reader needs to decide, in sentences and not in a template.

        Each piece is its own term, so a translator gets whole sentences to
        work with, and the pieces that have nothing to say are left out
        instead of leaving a gap in the middle of the text.
        """
        self.ensure_one()
        duplicate = self.duplicate_id
        if not duplicate:
            return ''

        pieces = [_(
            "This file has already been read: %(document)s.",
            document=duplicate.display_name,
        )]
        if duplicate.extraction_date:
            pieces.append(_(
                "It was read on %s.",
                format_datetime(self.env, duplicate.extraction_date),
            ))
        if duplicate.move_id:
            pieces.append(_("It became %s.", duplicate.move_id.display_name))
        return ' '.join(pieces)

    def action_read_again(self):
        """Read it, this time without asking."""
        self.ensure_one()
        result = self.document_id.action_extract(force=True)
        # The reading says what happened, and the dialog goes away by itself
        # afterwards. A dialog that stayed would hide the answer.
        return result or {'type': 'ir.actions.act_window_close'}

    def action_cancel(self):
        return {'type': 'ir.actions.act_window_close'}
