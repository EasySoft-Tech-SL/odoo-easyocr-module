# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

import hashlib
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .easyocr_values import to_float

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


class EasyocrDocument(models.Model):
    """A file dropped into the OCR inbox, plus whatever was read from it.

    The record exists from the moment the document is uploaded, so a file that
    fails extraction is still visible and can be retried instead of vanishing.
    """

    _name = 'easyocr.document'
    _description = 'OCR Document'
    _inherit = ['mail.thread', 'mail.activity.mixin']
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
    amount_untaxed = fields.Monetary(
        string='Untaxed Amount',
        currency_field='currency_id',
    )
    amount_total = fields.Monetary(
        string='Total',
        currency_field='currency_id',
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

    def action_create_bill(self):
        """Create a draft supplier bill from what was read from this document.

        One bill line for every line the service read, each with its own product,
        discount and rate. When the document has no lines -- a reading that came
        back with nothing but a total, or a document filed by hand -- the whole
        amount goes on a single line instead, untaxed, as it always did.
        """
        self.ensure_one()
        if self.move_id:
            raise UserError(_("This document already has a bill."))

        partner = self._resolve_partner()
        if not partner:
            raise UserError(_(
                "No vendor could be matched. Set the vendor on the document, "
                "or make sure the tax number is on a contact."
            ))

        move = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': partner.id,
            'ref': self.ref or self.name,
            'invoice_date': self.document_date or fields.Date.context_today(self),
            'currency_id': self.currency_id.id,
            'invoice_line_ids': [(0, 0, values) for values in self._bill_line_values(partner)],
        })

        self.move_id = move
        self.state = 'processed'
        self._confirm_bill(move)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': move.id,
            'view_mode': 'form',
            'target': 'current',
        }

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
                'price_unit': self.amount_untaxed or self.amount_total or 0.0,
            }]

        values = []
        for line in self.line_ids:
            product = line._resolve_product(partner)
            values.append({
                'name': line.name,
                'quantity': line.quantity or 1.0,
                'price_unit': line.unit_price,
                'discount': line.discount_percent,
                'product_id': product.id if product else False,
                'tax_ids': [(6, 0, line._tax_ids().ids)],
            })
        return values

    def _compute_line_count(self):
        for document in self:
            document.line_count = len(document.line_ids)

    def _confirm_bill(self, move):
        """Post the bill when the company asked for it, without ever losing it.

        Posting books the bill and gives it a number, which is why it is off by
        default: the module proposes, and a person confirms. When it is on and
        posting fails -- a missing account, a tax Odoo cannot work out -- the
        bill stays in draft with the reason written on it. A bill that could not
        be confirmed is worth a great deal more than no bill at all.
        """
        self.ensure_one()
        if not self.company_id.easyocr_bill_post:
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
        """Open the full screen viewer on this document."""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'easyocr.document_viewer',
            'name': _('Document Viewer'),
            'params': {'document_id': self.id},
            'target': 'fullscreen',
        }

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
