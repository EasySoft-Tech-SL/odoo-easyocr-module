# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License OPL-1 (see LICENSE file).

from odoo import fields, models


class EasyocrWebhookLog(models.Model):
    """One received webhook call, kept whether it worked or not.

    This log is the only trace of a call that created nothing: an event we do
    not handle, a notification without structured data, a value we could not
    read. Without it those calls would leave no sign anywhere.
    """

    _name = 'easyocr.webhook.log'
    _description = 'OCR Webhook Call'
    _order = 'create_date desc, id desc'

    event = fields.Char(string='Event', readonly=True)
    document_id_external = fields.Char(
        string='Service Document',
        readonly=True,
        help='Identifier the OCR service gives to the document.',
    )
    filename = fields.Char(string='File Name', readonly=True)
    status = fields.Selection(
        selection=[
            ('ok', 'Created'),
            ('ignored', 'Ignored'),
            ('error', 'Error'),
        ],
        string='Status',
        readonly=True,
    )
    message = fields.Text(string='Message', readonly=True)
    payload = fields.Text(
        string='Payload',
        readonly=True,
        help='Body of the call, trimmed if it was too long.',
    )
    document_id = fields.Many2one(
        comodel_name='easyocr.document',
        string='Document',
        readonly=True,
        ondelete='set null',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )
