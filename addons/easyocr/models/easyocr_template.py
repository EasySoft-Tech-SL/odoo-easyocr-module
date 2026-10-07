# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

from odoo import _, api, fields, models

# The nine fields a template can mark on a page. The key is what gets stored and
# what the extraction code matches on; the colour is only how it is painted, and
# it is kept here so the viewer and the API agree on one list.
BOX_FIELDS = [
    ('document_date', 'Date', '#6c3483'),
    ('document_number', 'Invoice number', '#2980b9'),
    ('amount_untaxed', 'Untaxed total', '#c0392b'),
    ('amount_total', 'Total', '#d4458b'),
    ('tax_amount', 'Tax', '#ff6b35'),
    ('description', 'Description', '#27ae60'),
    ('partner_vat', 'Tax number', '#16a085'),
    ('due_date', 'Due date', '#f39c12'),
    ('partner_name', 'Vendor', '#5d6d7e'),
]


class EasyocrTemplate(models.Model):
    """The boxes to read from a vendor's documents, saved once and reused.

    A template belongs to a vendor, so the next invoice from that vendor is read
    without drawing anything again.
    """

    _name = 'easyocr.template'
    _description = 'OCR Extraction Template'
    _inherit = ['mail.thread']
    _order = 'name'

    name = fields.Char(string='Name', required=True, tracking=True)
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Vendor',
        ondelete='cascade',
        tracking=True,
        help='Vendor this template belongs to. Leave empty for a generic template.',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )
    custom_instructions = fields.Text(
        string='Extra instructions',
        help='Sent to the extraction service on top of the standard instructions.',
    )
    box_ids = fields.One2many(
        comodel_name='easyocr.template.box',
        inverse_name='template_id',
        string='Fields',
        copy=True,
    )
    box_count = fields.Integer(string='Boxes', compute='_compute_box_count')
    active = fields.Boolean(default=True)

    @api.depends('box_ids')
    def _compute_box_count(self):
        for template in self:
            template.box_count = len(template.box_ids)

    @api.depends('partner_id', 'name')
    def _compute_display_name(self):
        for template in self:
            if template.partner_id:
                template.display_name = f'{template.name} ({template.partner_id.display_name})'
            else:
                template.display_name = template.name


class EasyocrTemplateBox(models.Model):
    """One rectangle on one page, and the field it feeds.

    Coordinates are PDF points, not screen pixels: the viewer divides by the zoom
    before saving and multiplies after loading, so a template drawn at one zoom
    level works at any other, and on any screen size.
    """

    _name = 'easyocr.template.box'
    _description = 'OCR Extraction Box'
    _order = 'page, id'

    template_id = fields.Many2one(
        comodel_name='easyocr.template',
        string='Template',
        required=True,
        ondelete='cascade',
    )
    company_id = fields.Many2one(
        related='template_id.company_id',
        store=True,
        index=True,
    )
    page = fields.Integer(
        string='Page',
        required=True,
        default=1,
        help='1-based page number.',
    )
    field_key = fields.Selection(
        selection=[(key, label) for key, label, _colour in BOX_FIELDS],
        string='Field',
        required=True,
    )
    x = fields.Float(string='X', required=True, help='PDF points from the left edge.')
    y = fields.Float(string='Y', required=True, help='PDF points from the top edge.')
    width = fields.Float(string='Width', required=True)
    height = fields.Float(string='Height', required=True)
    text = fields.Char(
        string='Last read',
        readonly=True,
        help='What was read the last time this box was applied, for checking.',
    )

    @api.depends('field_key', 'template_id.name')
    def _compute_display_name(self):
        labels = dict(self._fields['field_key']._description_selection(self.env))
        for box in self:
            box.display_name = labels.get(box.field_key, box.field_key)
