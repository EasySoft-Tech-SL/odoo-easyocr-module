# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

from odoo import fields, models

# The public EasyOCR service, so a fresh company only has to add its key.
DEFAULT_AI_URL = 'https://app.easyocr.es'
DEFAULT_AI_TIMEOUT = 120


class ResCompany(models.Model):
    """Extraction settings, one set per company.

    They live on the company and not in ir.config_parameter because the service
    and its key are per company: a group with several companies can point each
    one at its own service, and the settings screen writes straight to the
    company the user is working in.
    """

    _inherit = 'res.company'

    easyocr_ai_enabled = fields.Boolean(
        string='AI Extraction',
        help='Send documents to the EasyOCR service to read them. Off by default: '
             'nothing leaves the server until this is on.',
    )
    easyocr_ai_url = fields.Char(
        string='Service URL',
        default=DEFAULT_AI_URL,
        help='Base address of the EasyOCR service. The endpoint is added on top.',
    )
    easyocr_ai_apikey = fields.Char(
        string='API Key',
        help='Key sent as the X-API-Key header. Requested from the service provider.',
    )
    easyocr_ai_timeout = fields.Integer(
        string='Timeout (seconds)',
        default=DEFAULT_AI_TIMEOUT,
        help='How long to wait for the service before giving up. A scanned page '
             'can take a while, so keep it generous.',
    )
