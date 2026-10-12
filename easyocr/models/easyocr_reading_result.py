# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

import json

from odoo import _, api, fields, models

from .easyocr_values import to_float


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

    def action_result_data(self):
        """Everything the result dialog draws, in one answer.

        Each card comes back as ``[key, label, value]`` rows, with the labels
        already in the reader's language: the key tells the screen which value
        it may hand back corrected, and the amounts travel as numbers so the
        screen writes them the way the reader's language does. The lines come
        back with the rates the service put on each one already picked out.
        The raw payload travels whole for the JSON button.
        """
        self.ensure_one()
        answer = self._answer()
        structured = self._structured(answer)
        document = structured.get('document') or {}
        supplier = structured.get('supplier') or {}
        customer = structured.get('customer') or {}
        totals = structured.get('totals') or {}
        payment = structured.get('payment') or {}
        company = self.document_id.company_id

        def rows(triples):
            return [
                [key, label, value] for key, label, value in triples
                if value not in (None, '')
            ]

        def doc(*keys):
            # The service puts these at the top of the answer; older answers
            # nest them under ``document``. Either is read.
            for key in keys:
                for source in (structured, document):
                    value = source.get(key)
                    if value not in (None, ''):
                        return value
            return None

        def amount(*keys):
            for key in keys:
                value = totals.get(key)
                if value not in (None, ''):
                    return to_float(value, None)
            return None

        return {
            'meta_pills': self._meta_pills(answer),
            'sections': {
                'document': rows([
                    ('document_type', _("Type"), self._document_type_label(doc('document_type'))),
                    ('document_number', _("Invoice number"), doc('document_number', 'invoice_number')),
                    ('issue_date', _("Date"), doc('issue_date', 'date')),
                    ('due_date', _("Due date"), doc('due_date')),
                    ('currency', _("Currency"), doc('currency')),
                ]),
                'supplier': rows([
                    ('name', _("Name"), supplier.get('name')),
                    ('tax_id', _("Tax ID"), supplier.get('tax_id')),
                    ('address', _("Address"), supplier.get('address')),
                    ('city', _("City"), supplier.get('city')),
                    ('postal_code', _("Postal code"), supplier.get('postal_code')),
                    ('country', _("Country"), supplier.get('country')),
                    ('phone', _("Phone"), supplier.get('phone')),
                    ('email', _("Email"), supplier.get('email')),
                ]),
                'customer': rows([
                    ('name', _("Name"), customer.get('name')),
                    ('tax_id', _("Tax ID"), customer.get('tax_id')),
                    ('address', _("Address"), customer.get('address')),
                    ('city', _("City"), customer.get('city')),
                    ('postal_code', _("Postal code"), customer.get('postal_code')),
                    ('country', _("Country"), customer.get('country')),
                ]),
                'totals': rows([
                    ('subtotal', _("Subtotal"), amount('net_subtotal', 'subtotal')),
                    ('tax', _("Tax"), amount('tax_total', 'tax')),
                    ('discount', _("Discount"), amount('discount_total', 'discount')),
                    ('surcharge', _("RE / Surcharge"), amount('surcharge_total')),
                    ('withholding', _("IRPF / Withholding"), amount('withholding_total')),
                    ('total', _("Total"), amount('total')),
                ]),
                'payment': rows([
                    ('method', _("Method"), payment.get('method')),
                    ('status', _("Status"), self._payment_status_label(payment.get('status'))),
                    ('bank_account', _("Bank account"), payment.get('bank_account')),
                    ('reference', _("Reference"), payment.get('reference')),
                ]),
            },
            'items': [self._dialog_item(item, totals) for item in structured.get('items') or []],
            'notes': structured.get('notes') or '',
            'supplier_match': self.document_id.action_check_supplier(
                supplier.get('tax_id') or '', supplier.get('name') or '',
            ),
            'invoice_draft': bool(company.easyocr_invoice_draft),
            'is_refund': bool(self.document_id.is_refund),
            'raw': answer,
        }

    def _document_type_label(self, value):
        """The kind of document, in words, for the types the service names."""
        labels = {
            'invoice': _("Invoice"),
            'credit_note': _("Credit note"),
            'receipt': _("Receipt"),
            'proforma': _("Pro forma"),
            'quote': _("Quote"),
        }
        return labels.get(str(value or '').lower(), value)

    def _payment_status_label(self, value):
        """Whether the paper says it was paid, in words."""
        labels = {
            'paid': _("Paid"),
            'unpaid': _("Unpaid"),
            'pending': _("Unpaid"),
            'partial': _("Partially paid"),
            'partially_paid': _("Partially paid"),
        }
        return labels.get(str(value or '').lower(), value)

    def _dialog_item(self, item, totals):
        """One line as the dialog edits it: the three rates picked out apart."""
        rates = {'tax_rate': 0.0, 're_rate': 0.0, 'irpf_rate': 0.0}
        for tax in item.get('taxes') if isinstance(item.get('taxes'), list) else []:
            if not isinstance(tax, dict):
                continue
            kind = str(tax.get('tax_type') or '').lower().strip()
            rate = to_float(tax.get('tax_rate'))
            if kind in ('tva', 'iva', 'vat') and rate:
                rates['tax_rate'] = rate
            elif kind == 're' and rate:
                rates['re_rate'] = rate
            elif kind in ('irpf', 'retencion', 'withholding') and rate:
                rates['irpf_rate'] = abs(rate)
        for key in rates:
            if not rates[key]:
                rates[key] = abs(to_float(item.get(key)))
        if not rates['tax_rate']:
            # The document's own VAT rate, for a line that came without one.
            for tax in totals.get('taxes') if isinstance(totals.get('taxes'), list) else []:
                if isinstance(tax, dict) and str(tax.get('tax_type') or '').lower() in ('tva', 'iva', 'vat'):
                    rates['tax_rate'] = to_float(tax.get('tax_rate'))
                    break
        quantity = to_float(item.get('quantity') or item.get('qty'), 1.0) or 1.0
        unit_price = to_float(item.get('unit_price') or item.get('price'))
        net = to_float(item.get('net_amount') or item.get('total') or item.get('line_total'), None)
        if not unit_price and net:
            unit_price = net / quantity
        return dict(
            rates,
            code=item.get('code') or item.get('product_code') or '',
            description=item.get('description') or item.get('label') or item.get('name') or '',
            item_type=(item.get('item_type') or 'product').strip().lower(),
            quantity=quantity,
            unit_price=unit_price,
            discount_percent=to_float(item.get('discount_percent')),
        )

    def _meta_pills(self, answer):
        """The header pills, one per fact the service measured, in order."""
        self.ensure_one()
        structured = self._structured(answer)
        pills = []
        confidence = answer.get('confidence')
        if confidence is not None:
            pills.append(_("Confidence %s%%", round(float(confidence) * 100)))
        milliseconds = answer.get('processing_time_ms')
        if milliseconds:
            pills.append(_("Read in %s s", round(float(milliseconds) / 1000, 1)))
        tokens = (answer.get('tokens') or {}).get('total')
        if tokens:
            pills.append(_("Tokens: %s", tokens))
        pages = (structured.get('metadata') or {}).get('page_count')
        if pages:
            pills.append(_("Pages: %s", pages))
        return pills
