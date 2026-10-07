# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License OPL-1 (see LICENSE file).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    """The EasyOCR block of the settings screen.

    Each field mirrors a field on res.company through a writable related field,
    so saving the screen updates the company that is being configured and the
    value is read back from it next time.
    """

    _inherit = 'res.config.settings'

    easyocr_ai_enabled = fields.Boolean(
        related='company_id.easyocr_ai_enabled',
        readonly=False,
    )
    easyocr_ai_url = fields.Char(
        related='company_id.easyocr_ai_url',
        readonly=False,
    )
    easyocr_ai_apikey = fields.Char(
        related='company_id.easyocr_ai_apikey',
        readonly=False,
    )
    easyocr_ai_timeout = fields.Integer(
        related='company_id.easyocr_ai_timeout',
        readonly=False,
    )
