# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# What a document can be. The same list the inbox holds the line at.
ACCEPTED_MIMETYPES = ('application/pdf', 'image/jpeg', 'image/png')
ACCEPTED_EXTENSIONS = ('.pdf', '.jpg', '.jpeg', '.png')


class EasyocrUploadWizard(models.TransientModel):
    """Pick a file and go straight to the viewer.

    The Dolibarr module this is a port of opens on a screen where uploading a
    PDF is one button and lands you in the tool with the document in front of
    you. Going through a record, attaching a file, saving and only then opening
    the viewer is three steps for something that should be one, so this is that
    button: the file in, the viewer out.
    """

    _name = 'easyocr.upload.wizard'
    _description = 'Upload a Document to Read'

    file = fields.Binary(string='File', required=True)
    filename = fields.Char(string='File Name')
    name = fields.Char(
        string='Reference',
        help='How this document is listed. Left empty, the file name is used.',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )

    @api.onchange('file', 'filename')
    def _onchange_file(self):
        """Put the file name in the reference, so nobody has to type it twice."""
        if not self.name and self.filename:
            self.name = self.filename

    def action_read(self):
        """File the document and open the viewer on it. Nothing is read yet."""
        self.ensure_one()
        if not self.file:
            raise UserError(_("Choose a file first."))
        if self.filename and not self.filename.lower().endswith(ACCEPTED_EXTENSIONS):
            raise UserError(_(
                "That kind of file cannot be read. Send a PDF or a photo."
            ))

        document = self.env['easyocr.document'].create({
            'name': self.name or self.filename or _('New'),
            'company_id': self.company_id.id,
            'currency_id': self.company_id.currency_id.id,
        })
        document.attachment_id = self.env['ir.attachment'].create({
            'name': self.filename or document.name,
            'datas': self.file,
            'res_model': 'easyocr.document',
            'res_id': document.id,
        }).id

        # Straight to the tool, with the document up: reading it with the
        # service is a decision for whoever is looking at it, not a side effect
        # of having opened the file.
        return document.action_open_viewer()
