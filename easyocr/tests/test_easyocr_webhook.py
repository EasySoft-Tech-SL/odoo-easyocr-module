# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

import json

from odoo.tests import tagged
from odoo.tests.common import HttpCase

WEBHOOK_URL = '/easyocr/webhook'

# Set on the configuration, and sent by the service in a header.
SECRET = 'a-secret-only-the-service-knows'

COMPLETED_EVENT = 'document.completed'


@tagged('post_install', '-at_install')
class TestEasyocrWebhook(HttpCase):
    """The inbound call from the OCR service, and the log it leaves behind."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Document = cls.env['easyocr.document']
        cls.Log = cls.env['easyocr.webhook.log']
        cls.env['ir.config_parameter'].sudo().set_param('easyocr.webhook_secret', SECRET)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _call(self, payload, secret=SECRET):
        """Send a body to the webhook, signed with ``secret`` (None to omit it)."""
        headers = {}
        if secret is not None:
            headers['X-Webhook-Secret'] = secret
        # On 18.0 url_open() has no json= argument, so the body is serialised and
        # the content type declared by hand: without them the route sees no JSON.
        return self.url_open(
            WEBHOOK_URL,
            data=json.dumps(payload),
            headers={**headers, 'Content-Type': 'application/json'},
        )

    def _completed_payload(self, **data_overrides):
        data = {
            'document_id': 'svc-0001',
            'filename': 'invoice.pdf',
            'status': 'completed',
            'page_count': 2,
            'ocr_confidence': 0.93,
            'structured_data': {
                'partner_name': 'Proveedor de prueba SL',
                'partner_vat': 'B3186006',
                'document_number': 'A/123',
                'document_date': '2026-01-31',
                'amount_untaxed': 100.0,
                'amount_total': 121.0,
            },
        }
        data.update(data_overrides)
        return {'event': COMPLETED_EVENT, 'timestamp': '2026-01-31T10:00:00Z', 'data': data}

    def _the_log(self):
        return self.Log.search([('document_id_external', '=', 'svc-0001')], limit=1)

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------
    def test_a_call_without_a_secret_is_rejected(self):
        response = self._call(self._completed_payload(), secret=None)

        self.assertEqual(response.status_code, 403)

    def test_a_call_with_the_wrong_secret_is_rejected(self):
        response = self._call(self._completed_payload(), secret='not-the-secret')

        self.assertEqual(response.status_code, 403)

    def test_a_rejected_call_creates_nothing(self):
        """The secret is checked before anything is written or logged."""
        self._call(self._completed_payload(), secret='not-the-secret')

        self.assertFalse(self.Document.search([('ref', '=', 'A/123')]))
        self.assertFalse(self._the_log())

    # ------------------------------------------------------------------
    # A completed document
    # ------------------------------------------------------------------
    def test_a_completed_document_creates_the_document(self):
        response = self._call(self._completed_payload())

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['status'], 'ok')

        document = self.Document.browse(body['document_id'])
        self.assertTrue(document.exists())
        self.assertEqual(document.ref, 'A/123')
        self.assertEqual(document.partner_name, 'Proveedor de prueba SL')
        self.assertEqual(document.partner_vat, 'B3186006')
        self.assertEqual(str(document.document_date), '2026-01-31')
        self.assertAlmostEqual(document.amount_untaxed, 100.0, places=2)
        self.assertAlmostEqual(document.amount_total, 121.0, places=2)
        self.assertEqual(document.state, 'processed')

    def test_a_completed_document_leaves_a_log(self):
        self._call(self._completed_payload())

        log = self._the_log()
        self.assertTrue(log)
        self.assertEqual(log.status, 'ok')
        self.assertEqual(log.event, COMPLETED_EVENT)
        self.assertEqual(log.filename, 'invoice.pdf')
        self.assertTrue(log.document_id)
        self.assertIn('structured_data', log.payload)

    # ------------------------------------------------------------------
    # What is not acted on
    # ------------------------------------------------------------------
    def test_an_event_we_do_not_handle_is_ignored(self):
        payload = self._completed_payload()
        payload['event'] = 'document.started'

        response = self._call(payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ignored')
        self.assertFalse(self.Document.search([('ref', '=', 'A/123')]))
        self.assertEqual(self._the_log().status, 'ignored')

    def test_a_payload_without_structured_data_is_ignored(self):
        payload = self._completed_payload()
        payload['data'].pop('structured_data')

        response = self._call(payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ignored')
        self.assertFalse(self.Document.search([('ref', '=', 'A/123')]))
        self.assertEqual(self._the_log().status, 'ignored')

    def test_a_value_we_cannot_read_is_logged_as_an_error(self):
        """A business failure answers 200: a 500 would make the sender retry."""
        payload = self._completed_payload()
        payload['data']['structured_data']['document_date'] = 'not a date'

        response = self._call(payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'error')
        self.assertFalse(self.Document.search([('ref', '=', 'A/123')]))
        log = self._the_log()
        self.assertEqual(log.status, 'error')
        self.assertTrue(log.message)
