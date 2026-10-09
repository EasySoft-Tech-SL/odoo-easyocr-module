# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# The nine fields a template can mark on a page. The key is what gets stored and
# what the extraction code matches on; the colour is only how it is painted, and
# it is kept here so the viewer and the API agree on one list.

def _as_id(value):
    """A record id as an int, whatever the screen sent: 12, "12" or nothing."""
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0

BOX_FIELDS = [
    ('document_date', 'Invoice date', '#6c3483'),
    ('document_number', 'Invoice', '#2980b9'),
    ('amount_untaxed', 'Total excl. tax', '#c0392b'),
    ('amount_total', 'Total price', '#d4458b'),
    ('tax_amount', 'Tax amount', '#ff6b35'),
    ('description', 'Description', '#27ae60'),
    ('partner_vat', 'Tax ID', '#16a085'),
    ('due_date', 'Due date', '#f39c12'),
    ('partner_name', 'Supplier', '#5d6d7e'),
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
        string='AI Instructions',
        help='Sent to the extraction service on top of the standard instructions.',
    )
    box_ids = fields.One2many(
        comodel_name='easyocr.template.box',
        inverse_name='template_id',
        string='Fields',
        copy=True,
    )
    box_count = fields.Integer(string='Num. Fields', compute='_compute_box_count')
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


class EasyocrDocument(models.Model):
    """What a document needs to reuse the boxes saved for its vendor.

    A template only works if it can be found again, and finding it means knowing
    whose it is. That is the whole of this block: work out the vendor of the
    document, keep the boxes under it, and hand them back when the same vendor
    sends another document.
    """

    _inherit = 'easyocr.document'

    def _vendor_for_boxes(self):
        """The vendor these boxes belong to, without making a bill of it.

        The document has no vendor of its own until it becomes a bill, so it is
        worked out the way the bill works it out: tax number first, name after.
        A document that has neither, or that carries our own tax number, has no
        vendor and so no boxes of its own.
        """
        self.ensure_one()
        if self.partner_id:
            return self.partner_id
        try:
            return self._resolve_partner()
        except UserError:
            # Our own tax number as the vendor: the bill refuses it, and there
            # is no template of ours to apply either.
            return self.env['res.partner']

    def _template_for_boxes(self, partner):
        """The newest template with boxes saved for that vendor."""
        self.ensure_one()
        if not partner:
            return self.env['easyocr.template']
        return self.env['easyocr.template'].search([
            ('partner_id', '=', partner.id),
            ('company_id', '=', self.company_id.id),
            ('box_ids', '!=', False),
        ], order='write_date desc, id desc', limit=1)

    def action_template_for_reading(self):
        """The saved boxes to paint on this document, or nothing.

        Answers with what the screen needs and nothing more: the boxes, and the
        name of the template they came from so it can say where they came from
        instead of drawing them out of thin air.
        """
        self.ensure_one()
        partner = self._vendor_for_boxes()
        template = self._template_for_boxes(partner)
        if not template:
            return {'template': False, 'name': '', 'label': '', 'vendor': '', 'boxes': []}
        return {
            'template': template.id,
            'name': template.name,
            # The name and the vendor together, because a vendor can have more
            # than one template and "the boxes" alone would not say which.
            'label': template.display_name,
            'vendor': partner.display_name or '',
            'boxes': [{
                'page': box.page,
                'field_key': box.field_key,
                'x': box.x,
                'y': box.y,
                'width': box.width,
                'height': box.height,
            } for box in template.box_ids],
        }

    @api.model
    def action_list_templates(self):
        """The saved templates, for the dropdown that applies them.

        The screen offers the ones that have boxes, most recent first, each with
        the vendor it belongs to, so the reader can tell two templates apart when
        a vendor has more than one.
        """
        templates = self.env['easyocr.template'].search([
            ('company_id', '=', self.env.company.id),
            ('box_ids', '!=', False),
        ], order='write_date desc, id desc')
        return [{
            'id': template.id,
            'name': template.name,
            'vendor': template.partner_id.display_name or '',
            'label': template.display_name,
        } for template in templates]

    def action_load_template(self, template_id):
        """The boxes of one saved template, to paint them on the open document.

        The same shape as ``action_template_for_reading``, but for a template the
        reader picked from the dropdown rather than the one their vendor owns, so
        the custom instructions come back too.
        """
        self.ensure_one()
        # A <select> hands its value over as text; browse('12') finds nothing,
        # and the template came back "with no boxes" while it had seven.
        template = self.env['easyocr.template'].browse(_as_id(template_id))
        if not template.exists():
            return {'template': False, 'name': '', 'label': '', 'vendor': '',
                    'custom_instructions': '', 'boxes': []}
        return {
            'template': template.id,
            'name': template.name,
            'label': template.display_name,
            'vendor': template.partner_id.display_name or '',
            'custom_instructions': template.custom_instructions or '',
            'boxes': [{
                'page': box.page,
                'field_key': box.field_key,
                'x': box.x,
                'y': box.y,
                'width': box.width,
                'height': box.height,
            } for box in template.box_ids],
        }

    @api.model
    def action_list_suppliers(self):
        """The vendors the save dialog offers, most of them the ones already used."""
        suppliers = self.env['res.partner'].search([
            ('supplier_rank', '>', 0),
        ], order='name')
        return [{'id': supplier.id, 'name': supplier.display_name} for supplier in suppliers]

    def action_set_supplier(self, partner_id):
        """Set the vendor by hand, from the dropdown in the extracted data.

        The boxes are kept under whoever sent the document, so naming the vendor
        here also brings their template back on the next open.
        """
        self.ensure_one()
        partner = self.env['res.partner'].browse(_as_id(partner_id))
        if partner.exists():
            self.partner_id = partner.id
        return {'partner_id': self.partner_id.id, 'name': self.partner_id.display_name or ''}

    def action_save_template(self, name, boxes, partner_id=False, custom_instructions=False):
        """Keep these boxes for this document's vendor.

        The vendor is worked out here and not on the screen: the screen has no
        way to know it, and a template saved without one is a template nothing
        can ever find again. That is what the first one of these was, and it is
        why this moved to the server. The dialog can also hand a vendor picked by
        hand, or none for a generic template, and the extra instructions.
        """
        self.ensure_one()
        name = (name or '').strip()
        if not name:
            raise UserError(_("Give the template a name."))
        if not boxes:
            raise UserError(_("Draw at least one box before saving a template."))

        partner = self.env['res.partner'].browse(_as_id(partner_id)) if _as_id(partner_id) else self._vendor_for_boxes()
        template = self.env['easyocr.template'].create({
            'name': name,
            'partner_id': partner.id,
            'company_id': self.company_id.id,
            'custom_instructions': (custom_instructions or '').strip(),
            'box_ids': [(0, 0, self._box_values(box)) for box in boxes],
        })
        return {
            'template': template.id,
            'name': template.name,
            'label': template.display_name,
            'vendor': partner.display_name or '',
            'saved': len(template.box_ids),
        }

    @api.model
    def _box_values(self, box):
        """One box, with only the keys a template box knows how to keep."""
        return {
            key: box[key]
            for key in ('page', 'field_key', 'x', 'y', 'width', 'height', 'text')
            if box.get(key) not in (None, '')
        }


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
