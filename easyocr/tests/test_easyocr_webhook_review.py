# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

"""A webhook reading in the shape the service sends it, and the log it leaves.

The body is sent as text with its content type, which both the json2 route of
19.0 and 20.0 and the http one of 18.0 read. On 20.0 a parameter is set with
set_str(): set_param() is gone.
The tax numbers are made up, with a valid control character.
"""

import json

from odoo.tests import tagged
from odoo.tests.common import HttpCase

from .test_easyocr_unattended_vendor import CIF_A

WEBHOOK_URL = '/easyocr/webhook'
SECRET = 'a-secret-only-the-service-knows'


@tagged('post_install', '-at_install')
class TestEasyocrWebhookReview(HttpCase):
    """What the service really sends: supplier, totals and items nested."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_str('easyocr.webhook_secret', SECRET)
        cls.env.company.write({
            'country_id': cls.env.ref('base.es').id,
            'easyocr_webhook_create_bill': True,
            'easyocr_webhook_mark_paid': False,
            'easyocr_invoice_draft': False,
        })

    def _call(self, structured):
        payload = {
            'event': 'document.completed',
            'data': {
                'document_id': 'svc-review-1',
                'filename': 'factura.pdf',
                'status': 'completed',
                'structured_data': structured,
            },
        }
        return self.url_open(
            WEBHOOK_URL, data=json.dumps(payload),
            headers={'X-Webhook-Secret': SECRET, 'Content-Type': 'application/json'},
        )

    def _log(self):
        return self.env['easyocr.webhook.log'].search(
            [('document_id_external', '=', 'svc-review-1')], limit=1,
        )

    def test_the_nested_reading_is_read_and_kept(self):
        response = self._call({
            'supplier': {'name': 'Ficticia Webhook SL', 'tax_id': 'ES' + CIF_A},
            'document_number': 'FW-1',
            'totals': {'net_subtotal': 100.0, 'tax_total': 21.0, 'surcharge_total': 5.2,
                       'withholding_total': 15.0, 'total': 111.2},
            'items': [{'description': 'Servicio', 'quantity': 1, 'unit_price': 100.0}],
        })

        document = self.env['easyocr.document'].browse(response.json()['document_id'])
        self.assertEqual(document.partner_vat, 'ES' + CIF_A)
        self.assertEqual(len(document.line_ids), 1)
        self.assertIn('withholding_total', document.last_extraction)
        # Nothing to review: a new vendor with a valid number, totals that add up
        self.assertEqual(document.move_id.state, 'posted', self._log().message)

    def test_a_reading_to_review_says_why_in_the_log(self):
        response = self._call({
            'supplier': {'name': 'Ficticia Webhook SL', 'tax_id': 'ES' + CIF_A},
            'document_number': 'FW-2',
            'totals': {'net_subtotal': 100.0, 'tax_total': 21.0, 'total': 150.0},
        })

        document = self.env['easyocr.document'].browse(response.json()['document_id'])
        self.assertEqual(document.move_id.state, 'draft')
        log = self._log()
        self.assertEqual(log.status, 'ok')
        self.assertIn('review', log.message)
        self.assertIn('150.0', log.message)
