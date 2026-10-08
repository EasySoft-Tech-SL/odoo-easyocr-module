# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

import json

from odoo import _, api, fields, models


class EasyocrReadingResult(models.TransientModel):
    """Everything the service answered, in one screen.

    The document keeps what becomes an entry, which is a handful of fields, and
    the rest of the answer used to go nowhere: the vendor's address, its town,
    its phone and its email were read and dropped on the floor. The module this
    is a port of shows all of it when a reading finishes, and so does this: one
    dialog, right after the reading, with what was read and how sure the service
    was of it.

    Every value here is read back from the answer the service gave, which is
    kept whole in ``last_extraction``, so nothing had to be stored twice for
    this screen to have something to show.
    """

    _name = 'easyocr.reading.result'
    _description = 'What the reading found'

    document_id = fields.Many2one(
        'easyocr.document',
        string='Document',
        required=True,
        ondelete='cascade',
        readonly=True,
    )
    partner_name = fields.Char(related='document_id.partner_name')
    partner_vat = fields.Char(related='document_id.partner_vat')
    ref = fields.Char(related='document_id.ref')
    document_date = fields.Date(related='document_id.document_date')
    due_date = fields.Date(related='document_id.due_date')
    amount_untaxed = fields.Monetary(
        related='document_id.amount_untaxed', currency_field='currency_id',
    )
    amount_total = fields.Monetary(
        related='document_id.amount_total', currency_field='currency_id',
    )
    currency_id = fields.Many2one(related='document_id.currency_id')
    is_refund = fields.Boolean(related='document_id.is_refund')
    line_count = fields.Integer(related='document_id.line_count')

    meta = fields.Char(
        string='The reading',
        compute='_compute_summaries',
    )
    extras = fields.Text(
        string='What else came back',
        compute='_compute_summaries',
    )

    @api.depends('document_id')
    def _compute_summaries(self):
        for wizard in self:
            answer = wizard._answer()
            wizard.meta = wizard._meta(answer)
            wizard.extras = wizard._extras(answer)

    def _answer(self):
        """The answer the service gave, as it was stored."""
        self.ensure_one()
        try:
            return json.loads(self.document_id.last_extraction or '{}')
        except (ValueError, TypeError):
            return {}

    def _structured(self, answer):
        return answer.get('structured_data') or {}

    def _meta(self, answer):
        """How sure the service was, and what the reading cost.

        Nothing invented: what the service did not say is left out instead of
        shown as a zero, which is the difference between a reading that was
        unsure and a reading nobody measured.
        """
        self.ensure_one()
        pieces = []
        confidence = answer.get('confidence')
        if confidence is not None:
            pieces.append(_("Confidence %s%%", round(float(confidence) * 100)))
        milliseconds = answer.get('processing_time_ms')
        if milliseconds:
            pieces.append(_("Read in %s s", round(float(milliseconds) / 1000, 1)))
        tokens = (answer.get('tokens') or {}).get('total')
        if tokens:
            pieces.append(_("Tokens: %s", tokens))
        pages = ((self._structured(answer).get('metadata') or {}).get('page_count'))
        if pages:
            pieces.append(_("Pages: %s", pages))
        return ' · '.join(str(piece) for piece in pieces)

    def _extras(self, answer):
        """The rest of the answer, which is where the vendor's details live.

        The document has fields for the name and the tax number and for nothing
        else, so this is the only place these are shown at all. They are not
        written onto the contact on their own: that is a change to somebody's
        address book and it is not a reading's place to make it.
        """
        self.ensure_one()
        data = self._structured(answer)
        supplier = data.get('supplier') or {}
        payment = data.get('payment') or {}

        lines = []
        document_type = data.get('document_type')
        if document_type:
            lines.append('%s: %s' % (_("Type"), document_type))
        if data.get('currency'):
            lines.append('%s: %s' % (_("Currency"), data['currency']))

        for key, label in (
            ('address', _("Address")),
            ('city', _("City")),
            ('postal_code', _("Postal code")),
            ('country', _("Country")),
            ('phone', _("Phone")),
            ('email', _("Email")),
        ):
            if supplier.get(key):
                lines.append('%s: %s' % (label, supplier[key]))

        if payment.get('method'):
            lines.append('%s: %s' % (_("Payment method"), payment['method']))
        if payment.get('reference'):
            lines.append('%s: %s' % (_("Payment reference"), payment['reference']))

        return '\n'.join(lines) if lines else _(
            "The service answered with the fields of the document and nothing else."
        )

    def action_open_document(self):
        """Back to the document, which is where the entry is made from."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'easyocr.document',
            'res_id': self.document_id.id,
            'views': [(False, 'form')],
            'view_mode': 'form',
            'target': 'current',
        }
