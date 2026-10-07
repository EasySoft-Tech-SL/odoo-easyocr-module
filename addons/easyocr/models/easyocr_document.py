# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License OPL-1 (see LICENSE file).

from odoo import _, api, fields, models
from odoo.exceptions import UserError


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
    error_message = fields.Text(string='Error Detail', readonly=True)
    note = fields.Text(string='Notes')

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
            own_vat = self._normalize_vat(self.env.company.partner_id.vat)
            if own_vat and own_vat == vat_clean:
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

        The amount goes on a single line, untaxed. Taxes are left for the person
        reviewing it: guessing the wrong rate on a booked bill is worse than
        typing it.
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
            'invoice_line_ids': [(0, 0, {
                'name': self.name,
                'quantity': 1.0,
                'price_unit': self.amount_untaxed or self.amount_total or 0.0,
            })],
        })

        self.move_id = move
        self.state = 'processed'

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': move.id,
            'view_mode': 'form',
            'target': 'current',
        }

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
