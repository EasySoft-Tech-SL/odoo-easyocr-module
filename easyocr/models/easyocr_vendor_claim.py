# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

from datetime import timedelta

from odoo import api, fields, models


class EasyocrVendorClaim(models.Model):
    """One row per vendor a webhook is about to look up or create.

    Nobody reads these: they exist to be written. Two webhooks of the same new
    vendor both write the row of its tax number (and of its name), so the second
    one waits for the first and, once that one commits, Postgres refuses it as a
    concurrent update instead of letting it create the vendor a second time.
    See ``easyocr.document._claim_vendor``.
    """

    _name = 'easyocr.vendor.claim'
    _description = 'OCR Vendor Claim'
    _log_access = False

    company_id = fields.Many2one('res.company', required=True, ondelete='cascade')
    key = fields.Char(required=True)
    claimed_at = fields.Datetime()

    def init(self):
        # Raw SQL and not a constraint declared on the model: the way to declare
        # one changed between series, and ON CONFLICT needs exactly this index.
        self.env.cr.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS easyocr_vendor_claim_company_key_uniq
                ON easyocr_vendor_claim (company_id, key)
            """
        )

    @api.model
    def _purge(self, days=1):
        """Drop the rows nobody has written for a while: they only matter while held."""
        limit = fields.Datetime.now() - timedelta(days=days)
        self.search([('claimed_at', '<', limit)]).unlink()
