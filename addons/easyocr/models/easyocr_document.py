# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License OPL-1 (see LICENSE file).

from odoo import _, api, fields, models


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
    error_message = fields.Text(string='Error Detail', readonly=True)
    note = fields.Text(string='Notes')

    # ------------------------------------------------------------------
    # Business methods
    # ------------------------------------------------------------------
    def action_mark_processed(self):
        """Flag the document as read. Placeholder for the extraction result."""
        for document in self:
            document.state = 'processed'

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
