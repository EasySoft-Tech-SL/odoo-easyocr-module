# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

import hashlib
import json
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import format_datetime

from .easyocr_values import to_amount, to_date, to_float

_logger = logging.getLogger(__name__)

# What the service says each line is. Anything it does not name is put under
# "Other" rather than dropped, so a line is never lost for being odd.
ITEM_TYPES = [
    ('product', 'Product'),
    ('service', 'Service'),
    ('shipping', 'Shipping'),
    ('surcharge', 'Surcharge'),
    ('fee', 'Fee'),
    ('discount', 'Discount'),
    ('other', 'Other'),
]

# Lines that are not an article, so no product is looked up for them: a discount
# is not a thing you buy, and looking one up would invent a catalogue entry.
NO_PRODUCT_TYPES = ('discount', 'surcharge', 'other', '')

# Lines that are a service rather than goods, so a product created for one is
# created as a service.
SERVICE_TYPES = ('service', 'shipping', 'fee')

# The code Odoo gives its generic expense category. Used only to prefer it over
# the others when a receipt needs one and nobody said which.
EXPENSE_PRODUCT_CODE = 'EXP_GEN'

# How far the rate worked back from a document's two amounts may be from a tax
# the company has, in percentage points. An invoice of 33,33 with 7,7% of tax
# prints 35,90, which works back to 7,71: the cent the paper rounds off is not
# a different rate. Anything wider starts matching rates nobody uses.
TOTALS_RATE_TOLERANCE = 0.05

# What can be handed to the service. A PDF or a photo; anything else is turned
# away where it is chosen, with a sentence saying so, instead of being filed and
# then failing at the service.
READABLE_EXTENSIONS = ('.pdf', '.jpg', '.jpeg', '.png')


class EasyocrDocument(models.Model):
    """A file dropped into the OCR inbox, plus whatever was read from it.

    The record exists from the moment the document is uploaded, so a file that
    fails extraction is still visible and can be retried instead of vanishing.
    """

    _name = 'easyocr.document'
    _description = 'OCR Document'
    # `analytic.mixin` is what Odoo itself uses to say which project or account
    # a line of an expense or a bill belongs to. Bringing it in here is what
    # lets a photographed receipt be charged to a project without this module
    # dragging the Projects app in: a project has an analytic account of its own,
    # and that account is what both Odoo and the reader pick.
    _inherit = ['mail.thread', 'mail.activity.mixin', 'analytic.mixin']
    _order = 'create_date desc, id desc'

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        default=lambda self: _('New'),
        tracking=True,
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Pending'),
            ('processed', 'Processed'),
            ('error', 'Error'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Vendor',
        tracking=True,
    )
    ref = fields.Char(string='Document Number')
    document_date = fields.Date(string='Document Date')
    due_date = fields.Date(
        string='Due Date',
        help='The day the vendor wants to be paid, as printed on the document.',
    )
    amount_untaxed = fields.Monetary(
        string='Untaxed Amount',
        currency_field='currency_id',
    )
    amount_total = fields.Monetary(
        string='Total',
        currency_field='currency_id',
    )
    is_refund = fields.Boolean(
        string='Credit Note',
        help='A rectificativa: the vendor is giving money back instead of asking '
             'for it, and the bill is made the other way round. A reading that '
             'brings a negative total turns this on by itself.',
    )
    attachment_id = fields.Many2one(
        comodel_name='ir.attachment',
        string='File',
        ondelete='set null',
    )
    partner_vat = fields.Char(string='Tax Number', help='Read from the document.')
    partner_name = fields.Char(string='Vendor Name', help='Read from the document.')
    move_id = fields.Many2one(
        comodel_name='account.move',
        string='Bill',
        readonly=True,
        copy=False,
    )
    line_ids = fields.One2many(
        comodel_name='easyocr.document.line',
        inverse_name='document_id',
        string='Lines',
        copy=True,
        help='What the service read line by line. The bill is built from these.',
    )
    line_count = fields.Integer(string='Lines', compute='_compute_line_count')
    error_message = fields.Text(string='Error Detail', readonly=True)
    note = fields.Text(string='Notes')
    file_hash = fields.Char(
        string='Fingerprint',
        readonly=True,
        copy=False,
        help='SHA-256 of the attached file. Two documents with the same '
             'fingerprint carry exactly the same file, whatever they are called.',
    )

    # ------------------------------------------------------------------
    # The fingerprint of the file
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        documents = super().create(vals_list)
        documents._refresh_file_hash()
        return documents

    def write(self, values):
        result = super().write(values)
        if 'attachment_id' in values:
            self._refresh_file_hash()
        return result

    def _refresh_file_hash(self):
        for document in self:
            document.file_hash = document._fingerprint()

    def _fingerprint(self):
        """SHA-256 of the attached file, or False when there is nothing to read.

        Worked out from the bytes and never taken from a caller, so it cannot
        disagree with the file it is supposed to describe.
        """
        self.ensure_one()
        if not self.attachment_id:
            return False
        try:
            content = self.attachment_id.raw
        except Exception:  # noqa: BLE001 - an unreadable file just has no fingerprint
            _logger.warning("EasyOCR: could not read the file of document %s", self.id)
            return False
        return hashlib.sha256(content).hexdigest() if content else False

    def _duplicate_of(self):
        """Another document carrying the same file that has already been read.

        Only documents that were actually sent count: a draft was never read, so
        reading it first costs nothing. The window is what makes a document that
        really is the same every month (a fixed fee, a standing charge) readable
        again once enough time has gone by.
        """
        self.ensure_one()
        if not self.file_hash:
            return self.env['easyocr.document']
        domain = [
            ('id', '!=', self.id),
            ('company_id', '=', self.company_id.id),
            ('file_hash', '=', self.file_hash),
            ('state', 'in', ('processed', 'error')),
        ]
        window = self.company_id.easyocr_duplicate_window_days or 0
        if window > 0:
            # Counted back from when the file was read, not from when the row was
            # made: what the window forgives is a reading, and that is the date it
            # happened on. A document that was never sent carries no date and is
            # left out, which is what a window is for.
            domain.append(('extraction_date', '>=', fields.Datetime.now() - timedelta(days=window)))
        return self.search(domain, limit=1)

    def _duplicate_message(self, duplicate):
        """What the reader is told before paying for the same reading twice.

        One sentence per piece, because the date and the bill are only there
        when there is one, and a translator gets whole sentences to work with
        either way. It lives here and not in the dialog because there are two
        dialogs: the one the server opens for the button on the document, and
        the one the viewer paints itself so it can show the reading while it
        happens.
        """
        self.ensure_one()
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

    # ------------------------------------------------------------------
    # Business methods
    # ------------------------------------------------------------------
    def action_mark_processed(self):
        """Flag the document as read. Placeholder for the extraction result."""
        for document in self:
            document.state = 'processed'

    # ------------------------------------------------------------------
    # From the document to a supplier bill
    # ------------------------------------------------------------------
    @api.model
    def _normalize_vat(self, vat):
        """Drop what people type by hand: spaces, dashes and dots."""
        return ''.join(character for character in (vat or '') if character.isalnum()).upper()

    def _resolve_partner(self):
        """The vendor of the document: by tax number first, by name after."""
        self.ensure_one()
        if self.partner_id:
            return self.partner_id

        vat_typed = (self.partner_vat or '').strip()
        vat_clean = self._normalize_vat(vat_typed)
        if vat_clean:
            own_vat = self._normalize_vat(self.company_id.partner_id.vat)
            if own_vat and own_vat == vat_clean and not self.company_id.easyocr_allow_self_vendor:
                raise UserError(_(
                    "The tax number on this document belongs to your own company, "
                    "so it cannot be booked as a supplier bill."
                ))
            partner = self.env['res.partner'].search(
                ['|', ('vat', '=', vat_typed), ('vat', '=', vat_clean)],
                limit=1,
            )
            if partner:
                self.partner_id = partner
                return partner

        name = (self.partner_name or '').strip()
        if name:
            partner = self.env['res.partner'].search([('name', '=ilike', name)], limit=1)
            if partner:
                self.partner_id = partner
                return partner

        return self.env['res.partner']

    @api.model
    def action_check_supplier(self, vat='', name=''):
        """Who the supplier on screen is, before anything is created.

        ``found`` names the contact the bill will go to, ``new`` says one will
        be created from what was read, and ``own`` that the tax number is the
        company's own. Nothing is written: the dialog asks this as the reader
        types.
        """
        Partner = self.env['res.partner']
        vat_typed = (vat or '').strip()
        vat_clean = self._normalize_vat(vat_typed)
        company = self.env.company
        if vat_clean:
            own_vat = self._normalize_vat(company.partner_id.vat)
            if own_vat and own_vat == vat_clean and not company.easyocr_allow_self_vendor:
                return {'status': 'own', 'name': company.name, 'id': False}
            partner = Partner.search(['|', ('vat', '=', vat_typed), ('vat', '=', vat_clean)], limit=1)
            if partner:
                return {'status': 'found', 'name': partner.display_name, 'id': partner.id}
        clean_name = (name or '').strip()
        if clean_name:
            partner = Partner.search([('name', '=ilike', clean_name)], limit=1)
            if partner:
                return {'status': 'found', 'name': partner.display_name, 'id': partner.id}
            return {'status': 'new', 'name': clean_name, 'id': False}
        return {'status': 'none', 'name': '', 'id': False}

    @api.model
    def action_resolve_codes(self, partner_id=False, codes=None):
        """Which product each code on the lines points to, for the dialog.

        Advisory only, the same lookup the bill makes: the reader sees which
        lines will be tied to a product and which will go as free text.
        """
        partner = self.env['res.partner'].browse(partner_id or [])
        found = {}
        for code in codes or []:
            product = self._product_for_code(partner, (code or '').strip())
            if product:
                found[code] = product.display_name
        return found

    def action_create_bill(self, draft=False, journal_id=False, items=None,
                           register_payment=False, bank_id=False, overrides=None,
                           payment_method_id=False, is_refund=None):
        """Create a supplier bill from what was read from this document.

        One bill line for every line the service read, each with its own product,
        discount and rate. When the document has no lines -- a reading that came
        back with nothing but a total, or a document filed by hand -- the whole
        amount goes on a single line instead, untaxed, as it always did.

        The dialog can ask for a draft, which leaves the bill unposted for review
        instead of validating it right away, and can pick the journal. When the
        dialog hands back the lines as the reader left them, the bill is made
        from those and not from the reading. A posted bill can also be paid right
        away, from the bank account the reader picked.

        What the reader corrected in the dialog (the invoice number, the dates,
        the supplier's details) comes back as ``overrides`` and is written onto
        the document first, so the bill and the document say the same thing.
        A supplier nobody has on file is created from what was read, the way
        the module this is a port of does it.
        """
        self.ensure_one()
        if self.move_id:
            raise UserError(_("This document already has a bill."))

        self._apply_overrides(overrides or {})
        if is_refund is not None:
            self.is_refund = bool(is_refund)

        partner = self._resolve_partner() or self._create_partner_from_reading(
            (overrides or {}).get('supplier') or {},
        )
        if not partner:
            raise UserError(_(
                "No vendor could be matched. Set the vendor on the document, "
                "or make sure the tax number is on a contact."
            ))

        line_values = (
            self._bill_line_values_from_items(items)
            if items
            else self._bill_line_values(partner)
        )
        values = {
            'move_type': 'in_refund' if self.is_refund else 'in_invoice',
            'partner_id': partner.id,
            'ref': self.ref or self.name,
            'invoice_date': self.document_date or fields.Date.context_today(self),
            'currency_id': self.currency_id.id,
            'invoice_line_ids': [
                (0, 0, line) for line in line_values
            ],
        }
        if journal_id:
            values['journal_id'] = journal_id
        if self.due_date:
            # Only when the paper says one: left out, Odoo works it out from the
            # payment terms of the vendor, which is better than a blank.
            values['invoice_date_due'] = self.due_date
        move = self.env['account.move'].create(values)

        self.move_id = move
        self.state = 'processed'
        if not draft:
            self._confirm_bill(move)
        if register_payment and not draft:
            self._register_payment(move, bank_id, payment_method_id)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': move.id,
            'views': [(False, 'form')],
            'view_mode': 'form',
            'target': 'current',
        }

    def _register_payment(self, move, bank_id, payment_method_id=False):
        """Pay a posted bill straight away, from the bank the reader picked.

        The payment goes through Odoo's own register, so the reconciliation and
        the numbering are Odoo's and not something the module invents. A bank
        without a journal, or a bill that could not be posted, is paid by nobody:
        the bill is still there, in draft, for a person to finish. With no bank
        picked, the company's first bank journal pays it.
        """
        if move.state != 'posted':
            return
        if bank_id:
            journal = self.env['res.partner.bank'].browse(bank_id).journal_id
        else:
            journal = self.env['account.journal'].search([
                ('company_id', '=', move.company_id.id),
                ('type', '=', 'bank'),
            ], limit=1)
        if not journal:
            return
        values = {
            'journal_id': journal.id,
            'amount': move.amount_total,
        }
        method_line = self._payment_method_line(journal, payment_method_id)
        if method_line:
            values['payment_method_line_id'] = method_line.id
        register = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=[move.id],
        ).create(values)
        register.action_create_payments()

    def _payment_method_line(self, journal, payment_method_id):
        """The journal's outgoing line for the method the reader picked."""
        if not payment_method_id:
            return self.env['account.payment.method.line']
        return journal.outbound_payment_method_line_ids.filtered(
            lambda line: payment_method_id in (line.id, line.payment_method_id.id),
        )[:1]

    def _apply_overrides(self, overrides):
        """Write onto the document what the reader corrected in the dialog."""
        self.ensure_one()
        document = overrides.get('document') or {}
        supplier = overrides.get('supplier') or {}
        values = {}
        if (document.get('document_number') or '').strip():
            values['ref'] = document['document_number'].strip()
        for key, field_name in (('issue_date', 'document_date'), ('due_date', 'due_date')):
            if key in document:
                values[field_name] = to_date(document.get(key)) or False
        if (supplier.get('name') or '').strip():
            values['partner_name'] = supplier['name'].strip()
        if 'tax_id' in supplier:
            values['partner_vat'] = (supplier.get('tax_id') or '').strip()
        changed = (
            values.get('partner_name', self.partner_name) != self.partner_name
            or values.get('partner_vat', self.partner_vat) != self.partner_vat
        )
        if changed:
            # A supplier the reader changed by hand is looked up again.
            values['partner_id'] = False
        if values:
            self.write(values)

    def _reading_supplier(self):
        """The supplier block of the last reading, as the service sent it."""
        self.ensure_one()
        try:
            answer = json.loads(self.last_extraction or '{}')
        except (ValueError, TypeError):
            return {}
        return ((answer.get('structured_data') or {}).get('supplier')) or {}

    def _create_partner_from_reading(self, edited=None):
        """A supplier nobody has on file, created from what was read.

        The same as the module this is a port of: the name and the tax number,
        and the address, town, postal code, country, phone and email when the
        reading has them. Without a name there is nobody to create.
        """
        self.ensure_one()
        data = dict(self._reading_supplier())
        data.update({key: value for key, value in (edited or {}).items() if value not in (None, '')})
        name = (self.partner_name or data.get('name') or '').strip()
        if not name:
            return self.env['res.partner']
        vat = (self.partner_vat or data.get('tax_id') or '').strip()
        values = {
            'name': name,
            'is_company': True,
            'supplier_rank': 1,
            'street': data.get('address') or False,
            'city': data.get('city') or False,
            'zip': data.get('postal_code') or False,
            'phone': data.get('phone') or False,
            'email': data.get('email') or False,
        }
        country = self._country_from_reading(data.get('country'), vat)
        if country:
            values['country_id'] = country.id
        partner = self.env['res.partner'].create(values)
        if vat:
            # Written apart, without the format check: a tax number the
            # reading got slightly wrong must not stop the bill being made.
            partner.with_context(no_vat_validation=True).vat = vat
        self.partner_id = partner
        return partner

    def _country_from_reading(self, country, vat):
        """The country the reading named, or the one its tax number starts with."""
        Country = self.env['res.country']
        text = (country or '').strip()
        if len(text) == 2:
            found = Country.search([('code', '=ilike', text)], limit=1)
            if found:
                return found
        if text:
            found = Country.search([('name', '=ilike', text)], limit=1)
            if found:
                return found
        clean = self._normalize_vat(vat)
        if len(clean) > 2 and clean[:2].isalpha():
            return Country.search([('code', '=', clean[:2])], limit=1)
        return Country

    def _bill_line_values(self, partner):
        """What goes on the bill, line by line.

        With nothing read line by line there is still a bill to make, so the
        whole amount goes on one line. That is the shape the module had before
        it read lines at all, and it is also what a document filled in by hand
        or delivered by the webhook has to fall back on.
        """
        self.ensure_one()
        if not self.line_ids:
            return [{
                'name': self.name,
                'quantity': 1.0,
                'price_unit': self._as_bill_amount(self.amount_untaxed or self.amount_total or 0.0),
                'tax_ids': [(6, 0, self._tax_from_totals().ids)],
                'analytic_distribution': self.analytic_distribution or False,
            }]

        values = []
        for line in self.line_ids:
            product = line._resolve_product(partner)
            values.append({
                'name': line.name,
                'quantity': self._as_bill_amount(line.quantity or 1.0),
                'price_unit': self._as_bill_amount(line.unit_price),
                'discount': line.discount_percent,
                'product_id': product.id if product else False,
                'tax_ids': [(6, 0, line._tax_ids().ids)],
                'analytic_distribution': self.analytic_distribution or False,
            })
        return values

    def _bill_line_values_from_items(self, items):
        """What goes on the bill when the reader corrected the lines on screen.

        The dialog hands the lines back exactly as the reader left them, so the
        bill follows the reader and not the reading: a description fixed, a
        quantity corrected, a line added or taken out is the reader's word.
        """
        values = []
        partner = self.partner_id
        for item in items or []:
            taxes = self._purchase_tax(to_float(item.get('tax_rate')))
            taxes |= self._purchase_tax(to_float(item.get('re_rate')))
            irpf = to_float(item.get('irpf_rate'))
            if irpf:
                taxes |= self._purchase_tax(-abs(irpf))
            product = self._product_for_code(
                partner, (item.get('code') or '').strip(), item.get('item_type') or '',
            )
            values.append({
                'name': (item.get('description') or '').strip() or _('Line'),
                'quantity': to_float(item.get('quantity'), 1.0) or 1.0,
                'price_unit': self._as_bill_amount(to_float(item.get('unit_price'))),
                'discount': to_float(item.get('discount_percent')),
                'product_id': product.id if product else False,
                'tax_ids': [(6, 0, taxes.ids)],
                'analytic_distribution': self.analytic_distribution or False,
            })
        return values

    def _purchase_tax(self, rate):
        """The company's purchase tax with exactly this rate, or none."""
        if not rate:
            return self.env['account.tax']
        return self.env['account.tax'].search([
            ('company_id', '=', self.company_id.id),
            ('type_tax_use', '=', 'purchase'),
            ('amount_type', '=', 'percent'),
            ('amount', '=', rate),
        ], limit=1)

    def _product_for_code(self, partner, code, item_type=''):
        """The product a code on the paper points to, without creating one."""
        Product = self.env['product.product']
        if not code or item_type in ('discount', 'surcharge', 'other'):
            return Product
        if partner:
            info = self.env['product.supplierinfo'].search([
                ('partner_id', '=', partner.id),
                ('product_code', '=', code),
            ], limit=1)
            if info:
                return info.product_id or info.product_tmpl_id.product_variant_id
        return Product.search(['|', ('default_code', '=', code), ('barcode', '=', code)], limit=1)

    def _as_bill_amount(self, amount):
        """An amount written the way the bill it goes on expects it.

        A credit note carries its own sign: Odoo turns a refund's lines round
        when it works out the total, so a line that already came back negative
        would turn the refund back into a bill. What the paper says is what the
        document keeps; only the bill is written the other way round.
        """
        if self.is_refund:
            return abs(amount or 0.0)
        return amount

    @api.model
    def action_list_payment_modes(self):
        """The payment methods Odoo knows, for the footer of the result dialog.

        Kept as a list of id/name pairs so the screen paints them like the
        journals and nothing else. ``account.payment.method`` is the model Odoo
        introduced to hold the method on its own; older series keep it on the
        journal's payment line, so that is the fallback.
        """
        Model = self.env.get('account.payment.method')
        if Model is None:
            Model = self.env.get('account.payment.method.line')
        if Model is None:
            return []
        methods = Model.search([], order='name')
        return [{'id': method.id, 'name': method.name} for method in methods]

    @api.model
    def action_list_banks(self):
        """The company's bank accounts, for the footer of the result dialog."""
        banks = self.env['res.partner.bank'].search([
            ('company_id', '=', self.env.company.id),
        ], order='display_name')
        return [{
            'id': bank.id,
            'name': bank.display_name,
            'journal_id': bank.journal_id.id,
        } for bank in banks]

    def _compute_line_count(self):
        for document in self:
            document.line_count = len(document.line_ids)

    # ------------------------------------------------------------------
    # From the boxes drawn on the page to the fields of the document
    # ------------------------------------------------------------------
    # What a rectangle fills in. The key is the one the viewer stores and the
    # one a template keeps; the rest is the field of this record it writes to,
    # and how to read what came out of the box when the paper prints it the way
    # a person reads it instead of the way a database keeps it.
    BOX_DESTINATIONS = {
        'document_number': ('ref', None),
        'document_date': ('document_date', to_date),
        'due_date': ('due_date', to_date),
        'amount_untaxed': ('amount_untaxed', to_amount),
        'amount_total': ('amount_total', to_amount),
        'partner_vat': ('partner_vat', None),
        'partner_name': ('partner_name', None),
    }

    def action_apply_reading(self, values):
        """Fill the document with what the boxes read, without calling anyone.

        This is the free reading, and the one that needs no account: the boxes
        are already over the right words and the text came out of the file's own
        text layer, so the only thing missing was putting it where the rest of
        the module can use it. A box whose text cannot be read as the field it
        was drawn for is left alone, and the others are not held back by it:
        one rectangle over the wrong part of the page is not a reason to lose
        the four that are right.

        Answers with what it wrote, so the screen can say so.
        """
        self.ensure_one()
        written = {}
        for key, text in (values or {}).items():
            destination = self.BOX_DESTINATIONS.get(key)
            if not destination or not isinstance(text, str) or not text.strip():
                continue
            field_name, reader = destination
            value = reader(text) if reader else text.strip()
            if value is None or value is False or value == '':
                continue
            written[field_name] = value
        if written:
            self.write(written)
        return written

    def _tax_from_totals(self):
        """The purchase tax the document's own two amounts imply.

        A document read as a total and nothing else has no line to carry a rate,
        but it does carry the amount before tax and the amount after it, and the
        difference between the two is the tax. The rate worked back from them is
        used only when the company has a purchase tax with that rate: a bill
        whose total does not add up to the paper it came from is worse than one
        left for whoever reviews it to finish.
        """
        self.ensure_one()
        # A credit note prints its amounts negative and carries the same rate as
        # the bill it corrects, so what the rate is a percentage of is the size
        # of each amount and not its sign.
        untaxed = abs(self.amount_untaxed or 0.0)
        total = abs(self.amount_total or 0.0)
        if not untaxed or total <= untaxed:
            # Nothing to work with, or a total smaller than the amount before
            # tax: a discount, or a paper whose numbers do not add up. Neither
            # of those is a rate.
            return self.env['account.tax']
        rate = (total / untaxed - 1.0) * 100.0
        return self.env['account.tax'].search([
            ('company_id', '=', self.company_id.id),
            ('type_tax_use', '=', 'purchase'),
            ('amount_type', '=', 'percent'),
            ('amount', '>=', rate - TOTALS_RATE_TOLERANCE),
            ('amount', '<=', rate + TOTALS_RATE_TOLERANCE),
        ], order='amount', limit=1)

    # ------------------------------------------------------------------
    # From the document to an employee expense
    # ------------------------------------------------------------------
    def _become_expense(self, user=None):
        """Hand this document to the employee's expenses, and return the expense.

        This is what a receipt photographed from a phone becomes when the
        company says so. It is not a supplier bill: nobody is a vendor of a
        ticket from a petrol station, and Odoo already keeps an employee's own
        receipts, with their approval, in ``hr.expense``.

        Raises UserError with a sentence fit for the phone when it cannot, which
        is the same shape the rest of the capture flow answers in.
        """
        self.ensure_one()
        user = user or self.env.user
        employee = self.env['hr.employee'].search([('user_id', '=', user.id)], limit=1)
        if not employee:
            raise UserError(_(
                "You have no employee record, so the receipt cannot be filed as "
                "an expense. Ask whoever administers your Odoo to create one for "
                "you, or file it as a supplier bill."
            ))

        # hr.expense has no field for the document's own number, so it goes into
        # the name the approver reads, next to who the receipt is from.
        title = self.partner_name or self.name
        if self.ref and self.ref not in title:
            title = '%s - %s' % (title, self.ref)

        expense = self.env['hr.expense'].create({
            'name': title,
            'employee_id': employee.id,
            'company_id': self.company_id.id,
            'date': self.document_date or fields.Date.context_today(self),
            'total_amount': self.amount_total or self.amount_untaxed or 0.0,
            'product_id': self._expense_product().id,
            'vendor_id': self.partner_id.id,
            'description': self.note or False,
            'analytic_distribution': self.analytic_distribution or False,
        })

        # The photo goes with the expense: the person approving it has to be
        # able to see the paper it came from, and the document is not where they
        # will look.
        if self.attachment_id:
            self.attachment_id.copy({
                'res_model': 'hr.expense',
                'res_id': expense.id,
            })

        if self.company_id.easyocr_expense_allow_validate:
            # Put it forward, not approve it: approving your own expense is what
            # Odoo's own controls are there to stop, so it stays with the
            # approver. Off, the expense waits in draft like any other.
            #
            # In the module this port comes from the phone could go all the way
            # to validating the expense. Doing that here would mean the person
            # who spent the money also approving it, which is the one thing
            # Odoo's approval chain exists to prevent, so the phone goes as far
            # as handing it over and no further.
            #
            # 18.0 still calls this action_submit_expenses and 19.0 shortened
            # it. Branching is cheaper than a version check and says out loud
            # that the two series disagree.
            if hasattr(expense, 'action_submit'):
                expense.action_submit()
            else:
                expense.action_submit_expenses()

        return expense

    @api.model
    def _expense_product(self):
        """The category Odoo files a receipt under when nobody picked one.

        The same rule Odoo itself uses when it turns an attachment into an
        expense: the generic category if the chart has one, and otherwise
        whichever category the company made expensable. A company with none gets
        an expense without a category, which Odoo allows and the approver fills
        in.
        """
        products = self.env['product.product'].search([('can_be_expensed', '=', True)])
        if not products:
            return self.env['product.product']
        return products.filtered(
            lambda product: product.default_code == EXPENSE_PRODUCT_CODE
        )[:1] or products[:1]

    def _settle_webhook(self):
        """Bill the document, and pay it, when the company has asked for it.

        Off unless the company says so. A webhook is a message from outside, and
        this turns it into a bill -- an accounting entry -- or even into the
        record of money having gone out. The rule about the payment is the one
        the module this port comes from uses: only a confirmed bill has
        something to pay against, so a bill left in draft is not paid.

        Never raises. Whatever goes wrong comes back as a sentence for the log,
        because answering anything but 200 makes the sender send the same body
        again and the document ends up filed twice.
        """
        self.ensure_one()
        company = self.company_id
        if not company.easyocr_webhook_create_bill:
            return ''

        try:
            self.action_create_bill()
        except Exception as error:  # noqa: BLE001 - the answer has to go back as text
            _logger.warning("EasyOCR webhook: no bill for document %s: %s", self.id, error)
            return _("The bill could not be created (%(error)s).", error=error)

        if not company.easyocr_webhook_mark_paid:
            return _("The bill was created from it.")

        reason = self._register_webhook_payment(self.move_id, company)
        if reason:
            return _("The bill was created, but the payment was not registered (%(reason)s).",
                     reason=reason)
        return _("The bill was created from it and the payment registered.")

    @api.model
    def _register_webhook_payment(self, move, company):
        """Record the payment on the bill. Says why not, or nothing at all."""
        journal = company.easyocr_webhook_journal_id
        if not journal:
            return _("no bank account is set in the EasyOCR settings")
        if move.state != 'posted':
            return _("the bill is not confirmed, so there is nothing to pay yet")
        if not move.amount_residual:
            return _("the bill has nothing left to pay")

        values = {'journal_id': journal.id}
        method = company.easyocr_webhook_payment_method_line_id
        if method:
            values['payment_method_line_id'] = method.id
        try:
            wizard = self.env['account.payment.register'].with_context(
                active_model='account.move',
                active_ids=move.ids,
            ).create(values)
            wizard.action_create_payments()
        except Exception as error:  # noqa: BLE001 - the answer has to go back as text
            _logger.warning("EasyOCR webhook: no payment for bill %s: %s", move.id, error)
            return str(error)
        return ''

    def _confirm_bill(self, move):
        """Post the bill when the company asked for it, without ever losing it.

        Posting books the bill and gives it a number, which is why it is off by
        default: the module proposes, and a person confirms. When it is on and
        posting fails -- a missing account, a tax Odoo cannot work out -- the
        bill stays in draft with the reason written on it. A bill that could not
        be confirmed is worth a great deal more than no bill at all.
        """
        self.ensure_one()
        if self.company_id.easyocr_invoice_draft:
            return
        try:
            move.action_post()
        except (UserError, ValidationError) as error:
            _logger.warning(
                "EasyOCR: bill %s of document %s stayed in draft: %s",
                move.id, self.id, error,
            )
            move.message_post(body=_(
                "The bill was left in draft: it could not be confirmed on its own "
                "(%(error)s). Review it and confirm it by hand.",
                error=error,
            ))

    def action_open_viewer(self):
        """Open the viewer on this document, keeping Odoo's own navigation.

        ``current`` and not ``fullscreen``: the module this is a port of sits
        inside the ERP with its menus still reachable, and a reader who opened a
        document has to be able to get to another screen without losing their way.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'easyocr.document_viewer',
            'name': _('Document Viewer'),
            'params': {'document_id': self.id},
            'target': 'current',
        }

    @api.model
    def action_account_state(self):
        """What the service says about the account, for the AI banner of the viewer.

        Two things come out of this: whether the account can read right now (and
        why not when it cannot), and the subscription the viewer shows as its
        banner -- the plan, how much of the monthly quota is used, what is left,
        when it resets, and the prepaid wallet. It all comes out of the same
        ``account/me`` answer, so the banner and the blocked sentence can never
        disagree.

        The sentences are built here, in Python, so they come out in the reader's
        language like every other sentence of the module -- the service answers in
        Spanish whatever the screen is set to.

        Nothing is asked when the AI is off or has no key set, and a service that
        does not answer is not reported as a blocked account: silence is not a
        reason to tell someone their subscription lapsed.
        """
        company = self.env.company
        if not company.easyocr_ai_enabled or not company.easyocr_ai_apikey:
            return {
                'ai_enabled': False, 'blocked': False, 'message': '',
                'plan': {}, 'quota': {}, 'wallet': {}, 'has_custom_instructions': False,
            }

        extractor = self.env['easyocr.extractor']
        try:
            account = extractor.account(company)
        except Exception as error:  # noqa: BLE001 - the screen must open anyway
            _logger.info('EasyOCR: could not ask about the account: %s', error)
            return {
                'ai_enabled': True, 'blocked': False, 'message': '',
                'plan': {}, 'quota': {}, 'wallet': {}, 'has_custom_instructions': False,
            }

        status = account.get('status') or {}
        blocked = not status.get('can_process', True)

        known = {
            'SUBSCRIPTION_OVERDUE': _(
                "The EasyOCR subscription is overdue, so the service will not read "
                "anything until it is brought up to date."
            ),
            'WALLET_EMPTY': _("The EasyOCR account has no readings left."),
            'QUOTA_EXCEEDED': _("The monthly limit of the EasyOCR plan has been reached."),
            'ACCOUNT_DISABLED': _("The EasyOCR account is switched off. Contact support."),
        }
        message = known.get(status.get('block_code'), '') if blocked else ''

        # The numbers the banner shows, kept only when the service sent them: a
        # plan that does not answer its quota shows no invented zeros.
        plan = account.get('plan') or {}
        quota = account.get('quota') or {}
        wallet = account.get('wallet') or {}
        features = account.get('features') or {}

        return {
            'ai_enabled': True,
            'blocked': blocked,
            'message': message,
            'block_code': status.get('block_code') or '',
            'plan': {
                'name': plan.get('name') or '',
                'is_free': bool(plan.get('is_free')),
            },
            'quota': {
                'pages_used': quota.get('pages_used'),
                'pages_limit': quota.get('pages_limit'),
                'pages_remaining': quota.get('pages_remaining'),
                'usage_percentage': quota.get('usage_percentage'),
                'reset_date': quota.get('reset_date') or '',
            },
            'wallet': {
                'exists': bool(wallet.get('exists')),
                'balance_pages': wallet.get('balance_pages'),
            },
            'has_custom_instructions': bool(features.get('custom_instructions')),
        }

    @api.model
    def action_file_upload(self, filename, datas, name=False):
        """File a file handed over by the screen and answer with its document.

        The screen is where a PDF is dropped on, so it is the screen that has to
        turn it into a document and an attachment. Both are made here rather
        than from the browser, so the rules -- which files are readable, what
        the document is called -- are the same rules the tests check, and not a
        second copy of them written in JavaScript.

        Returns the id of the new document, which the viewer then opens on.
        """
        filename = (filename or '').strip()
        if not datas:
            raise UserError(_("Choose a file first."))
        if not filename.lower().endswith(READABLE_EXTENSIONS):
            raise UserError(_(
                "That kind of file cannot be read. Send a PDF or a photo."
            ))

        document = self.create({
            'name': name or filename or _('New'),
            'company_id': self.env.company.id,
            'currency_id': self.env.company.currency_id.id,
        })
        document.attachment_id = self.env['ir.attachment'].create({
            'name': filename or document.name,
            'datas': datas,
            'res_model': 'easyocr.document',
            'res_id': document.id,
        }).id
        return document.id

    def action_reset_to_draft(self):
        for document in self:
            document.state = 'draft'
            document.error_message = False

    @api.depends('name', 'partner_id')
    def _compute_display_name(self):
        for document in self:
            label = document.name
            if document.partner_id:
                label = f'{label} - {document.partner_id.display_name}'
            document.display_name = label


class EasyocrDocumentLine(models.Model):
    """One line the service read off the document.

    Kept apart from the bill because the two are not the same thing: a reading
    that turns out to be wrong must be fixable without touching anything that
    has been booked, and a document may be read long before anyone bills it.
    """

    _name = 'easyocr.document.line'
    _description = 'OCR Document Line'
    _order = 'sequence, id'

    document_id = fields.Many2one(
        comodel_name='easyocr.document',
        string='Document',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(string='Sequence', default=10)
    name = fields.Char(
        string='Description',
        required=True,
        help='Description as printed on the document.',
    )
    product_code = fields.Char(
        string='Supplier Reference',
        help='Article reference the document prints. It is what the product is '
             'looked up by, and it belongs to the vendor, not to us.',
    )
    item_type = fields.Selection(
        selection=ITEM_TYPES,
        string='Line Type',
        help='What the service made of the line. It decides whether a product '
             'is looked up at all, and whether a new one is a service or goods.',
    )
    quantity = fields.Float(string='Quantity', digits=(12, 3), default=1.0)
    unit_price = fields.Monetary(
        string='Unit Price',
        currency_field='currency_id',
        help='Price before discount, as printed.',
    )
    discount_percent = fields.Float(string='Discount (%)', digits=(5, 2))
    net_amount = fields.Monetary(
        string='Net Amount',
        currency_field='currency_id',
        compute='_compute_net_amount',
        store=True,
        help='What the line comes to, discount taken off. It follows the '
             'quantity, the price and the discount, the way the bill will.',
    )
    tax_rate = fields.Float(
        string='Tax Rate',
        digits=(5, 2),
        help='Rate read from the line, used to pick the purchase tax of the same '
             'rate when the bill is made.',
    )
    product_id = fields.Many2one(
        comodel_name='product.product',
        string='Product',
        ondelete='set null',
    )
    currency_id = fields.Many2one(
        related='document_id.currency_id',
        string='Currency',
    )
    company_id = fields.Many2one(
        related='document_id.company_id',
        string='Company',
        store=True,
        index=True,
    )

    # ------------------------------------------------------------------
    # Filling the line
    # ------------------------------------------------------------------
    @api.model
    def _values_from_item(self, item, sequence):
        """Turn one item of the service answer into values for a line.

        The model prints a unit price most of the time and leaves it out the
        rest, so when it is missing the price is worked back from what the line
        comes to. A quantity of nothing would divide by zero, hence the guard:
        a line that says it has no quantity is read as one.
        """
        quantity = to_float(item.get('quantity'), 1.0) or 1.0
        unit_price = to_float(item.get('unit_price'))
        net_amount = to_float(item.get('net_amount'))
        if not unit_price and net_amount:
            unit_price = net_amount / quantity

        item_type = (item.get('item_type') or '').strip().lower()
        if item_type not in dict(ITEM_TYPES):
            item_type = 'other'

        return {
            'sequence': sequence,
            'name': (item.get('description') or '').strip() or _('Line'),
            'product_code': (item.get('code') or '').strip(),
            'item_type': item_type,
            'quantity': quantity,
            'unit_price': unit_price,
            'discount_percent': to_float(item.get('discount_percent')),
            'tax_rate': self._tax_rate_from_item(item),
        }

    @api.depends('quantity', 'unit_price', 'discount_percent')
    def _compute_net_amount(self):
        """Worked out, never read back.

        The figure the document prints is kept in the raw answer; what this
        column shows is what the line comes to with the values on screen, so
        that correcting a quantity corrects the total with it instead of
        leaving the two disagreeing.
        """
        for line in self:
            discount = 1 - (line.discount_percent or 0.0) / 100.0
            line.net_amount = line.quantity * line.unit_price * discount

    @api.model
    def _tax_rate_from_item(self, item):
        """The rate charged on one line: the VAT one, not the withholding.

        A document can carry several rates on a line and only one of them is the
        tax that goes on the bill, so the one the service called VAT is taken and
        the rest are left where they are.
        """
        taxes = item.get('taxes')
        if not isinstance(taxes, list):
            return to_float(item.get('tax_rate'))
        for tax in taxes:
            if not isinstance(tax, dict):
                continue
            if str(tax.get('tax_type') or '').lower() in ('tva', 'iva', 'vat'):
                return to_float(tax.get('tax_rate'))
        return to_float(item.get('tax_rate'))

    # ------------------------------------------------------------------
    # What the line becomes
    # ------------------------------------------------------------------
    def _resolve_product(self, partner):
        """The product this line is about, in the order the document offers clues.

        The reference the document prints is the vendor's, so it is looked up
        against that vendor's own references first, then against our own code
        and barcode in case the document printed one of those instead. Creating a
        product is the last resort and only when the company asked for it: a
        catalogue that grows on its own is worse than a line with no product.
        """
        self.ensure_one()
        if self.product_id:
            return self.product_id

        code = (self.product_code or '').strip()
        if not code or (self.item_type or '') in NO_PRODUCT_TYPES:
            return self.env['product.product']

        supplier_info = self.env['product.supplierinfo'].search([
            ('partner_id', '=', partner.id),
            ('product_code', '=', code),
        ], limit=1)
        if supplier_info:
            self.product_id = supplier_info.product_id
            return self.product_id

        product = self.env['product.product'].search([
            '|', ('default_code', '=', code), ('barcode', '=', code),
        ], limit=1)
        if product:
            self.product_id = product
            return product

        if self.document_id.company_id.easyocr_autocreate_product:
            return self._create_product(code)
        return self.env['product.product']

    def _create_product(self, code):
        """Make the catalogue entry the document implies, and remember it."""
        self.ensure_one()
        product = self.env['product.product'].create({
            'name': self.name or code,
            'default_code': code,
            'type': 'service' if (self.item_type or '') in SERVICE_TYPES else 'consu',
            'purchase_ok': True,
            'sale_ok': True,
            'list_price': abs(self.unit_price or 0.0),
        })
        self.product_id = product
        return product

    def _tax_ids(self):
        """The purchase tax that matches the rate on the line, if there is one.

        Nothing is guessed: a rate the company has no tax for leaves the line
        without tax, exactly as a line with no rate does.
        """
        self.ensure_one()
        rate = self.tax_rate or 0.0
        if not rate:
            return self.env['account.tax']
        return self.env['account.tax'].search([
            ('company_id', '=', self.document_id.company_id.id),
            ('type_tax_use', '=', 'purchase'),
            ('amount_type', '=', 'percent'),
            ('amount', '=', rate),
        ], limit=1)
