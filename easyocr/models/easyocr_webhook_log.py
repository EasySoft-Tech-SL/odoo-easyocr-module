# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

from datetime import timedelta

from odoo import api, fields, models

from .easyocr_values import param_value

# How many days a call is kept. A parameter, so whoever runs the server decides;
# 0 or less keeps them for ever.
RETENTION_PARAM = 'easyocr.webhook_log_days'
RETENTION_DAYS = 30


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
    filename = fields.Char(string='File', readonly=True)
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
        help='Body of the call, trimmed if it was too long. Kept only for a '
             'call that failed or left something to review.',
    )
    document_id = fields.Many2one(
        comodel_name='easyocr.document',
        string='Document',
        readonly=True,
        ondelete='set null',
    )
    # What the call ended up producing, read from the document it filed, so
    # the log answers "did anything come of it" without opening the document.
    move_id = fields.Many2one(
        related='document_id.move_id',
        string='Invoice',
        readonly=True,
    )
    partner_id = fields.Many2one(
        related='document_id.partner_id',
        string='Supplier',
        readonly=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )

    @api.model
    def _cron_purge(self):
        """Forget the calls older than the retention, every day.

        The log answers what happened to a call while someone may still ask;
        kept for ever it is a copy of every reading that ever came in. The
        vendor claims of the webhooks go too: they only matter while held.
        """
        try:
            days = int(param_value(self.env, RETENTION_PARAM) or RETENTION_DAYS)
        except ValueError:
            days = RETENTION_DAYS
        if days > 0:
            limit = fields.Datetime.now() - timedelta(days=days)
            self.sudo().search([('create_date', '<', limit)]).unlink()
        self.env['easyocr.vendor.claim'].sudo()._purge()
