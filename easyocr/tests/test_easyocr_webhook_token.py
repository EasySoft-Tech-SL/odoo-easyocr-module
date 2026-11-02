# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

"""How a webhook call gets in, and what it may do once in.

Each company has a token of its own; the old shared secret is taken for 30
days from its first use and never records a payment. The body is sent as text
with its content type, which both the json2 route of 19.0 and the http one of
the earlier series read, so this file is the same on every series.
"""

import json
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import HttpCase

from odoo.addons.easyocr.models.easyocr_values import param_value, set_param_value

from .test_easyocr_unattended_vendor import CIF_A

WEBHOOK_URL = '/easyocr/webhook'
SECRET = 'an-old-shared-secret'


class _Busy(Exception):
    """What Postgres raises when a lock was not had in time."""

    pgcode = '55P03'


@tagged('post_install', '-at_install')
class TestEasyocrWebhookToken(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({
            'country_id': cls.env.ref('base.es').id,
            'easyocr_webhook_create_bill': True,
            'easyocr_webhook_mark_paid': False,
            'easyocr_invoice_draft': False,
        })
        cls.token = cls.company._easyocr_webhook_token(create=True)
        set_param_value(cls.env, 'easyocr.webhook_secret', SECRET)
        set_param_value(cls.env, 'easyocr.webhook_legacy_since', '')

    def _call(self, structured=None, document_id='svc-token-1', headers=None, url=WEBHOOK_URL):
        payload = {
            'event': 'document.completed',
            'data': {
                'document_id': document_id,
                'filename': 'factura.pdf',
                'structured_data': structured or {
                    'supplier': {'name': 'Ficticia Token SL', 'tax_id': 'ES' + CIF_A},
                    'document_number': 'TK-1',
                    'totals': {'net_subtotal': 100.0, 'tax_total': 21.0, 'total': 121.0},
                },
            },
        }
        all_headers = {'Content-Type': 'application/json'}
        all_headers.update(headers or {})
        return self.url_open(url, data=json.dumps(payload), headers=all_headers)

    def _log(self, document_id='svc-token-1'):
        return self.env['easyocr.webhook.log'].search(
            [('document_id_external', '=', document_id)], order='id desc', limit=1,
        )

    # ------------------------------------------------------------------
    # The token
    # ------------------------------------------------------------------
    def test_the_company_token_opens_the_webhook(self):
        response = self._call(headers={'X-Webhook-Token': self.token})

        self.assertEqual(response.status_code, 200)
        document = self.env['easyocr.document'].browse(response.json()['document_id'])
        self.assertEqual(document.company_id, self.company)
        self.assertEqual(document.service_document_id, 'svc-token-1')

    def test_the_token_can_travel_in_the_address(self):
        response = self._call(url='%s?token=%s' % (WEBHOOK_URL, self.token))

        self.assertEqual(response.status_code, 200)

    def test_a_wrong_token_is_a_bare_403(self):
        response = self._call(headers={'X-Webhook-Token': 'not-the-token'})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {'status': 'forbidden'})
        self.assertFalse(self._log())

    def test_a_new_token_closes_the_old_one(self):
        old = self.token
        self.company._easyocr_new_webhook_token()

        self.assertEqual(self._call(headers={'X-Webhook-Token': old}).status_code, 403)

    # ------------------------------------------------------------------
    # The old shared secret
    # ------------------------------------------------------------------
    def test_the_old_secret_still_works_and_starts_the_count(self):
        response = self._call(headers={'X-Webhook-Secret': SECRET})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(param_value(self.env, 'easyocr.webhook_legacy_since'))
        self.assertIn('old shared secret', self._log().message)

    def test_the_old_secret_is_refused_after_thirty_days(self):
        set_param_value(self.env, 'easyocr.webhook_legacy_since',
                        fields.Datetime.to_string(fields.Datetime.now() - timedelta(days=31)))

        response = self._call(headers={'X-Webhook-Secret': SECRET})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {'status': 'forbidden'})

    def test_the_old_secret_never_records_a_payment(self):
        journal = self.env['account.journal'].search([
            ('type', '=', 'bank'), ('company_id', '=', self.company.id),
        ], limit=1)
        self.company.write({'easyocr_webhook_mark_paid': True, 'easyocr_webhook_journal_id': journal.id})

        response = self._call(headers={'X-Webhook-Secret': SECRET})

        document = self.env['easyocr.document'].browse(response.json()['document_id'])
        self.assertEqual(document.move_id.state, 'posted')
        self.assertEqual(document.move_id.amount_residual, document.move_id.amount_total)

    # ------------------------------------------------------------------
    # The same document twice, and two calls at once
    # ------------------------------------------------------------------
    def test_the_same_document_twice_is_filed_once(self):
        first = self._call(headers={'X-Webhook-Token': self.token}).json()
        second = self._call(headers={'X-Webhook-Token': self.token}).json()

        self.assertEqual(second['document_id'], first['document_id'])
        self.assertTrue(second.get('duplicate'))
        self.assertEqual(self.env['easyocr.document'].search_count(
            [('service_document_id', '=', 'svc-token-1')]), 1)

    def test_a_vendor_held_by_another_call_answers_503(self):
        Document = type(self.env['easyocr.document'])
        with patch.object(Document, '_settle_webhook', side_effect=_Busy('lock timeout')):
            response = self._call(headers={'X-Webhook-Token': self.token}, document_id='svc-busy')

        self.assertEqual(response.status_code, 503)
        self.assertTrue(response.headers.get('Retry-After'))
        self.assertFalse(self.env['easyocr.document'].search([('service_document_id', '=', 'svc-busy')]))

    # ------------------------------------------------------------------
    # What the log keeps
    # ------------------------------------------------------------------
    def test_a_call_that_went_through_keeps_no_body(self):
        self._call(headers={'X-Webhook-Token': self.token})

        self.assertFalse(self._log().payload)

    def test_a_call_to_review_keeps_its_body(self):
        self._call(structured={
            'supplier': {'name': 'Ficticia Token SL', 'tax_id': 'ES' + CIF_A},
            'document_number': 'TK-2',
            'totals': {'net_subtotal': 100.0, 'tax_total': 21.0, 'total': 150.0},
        }, headers={'X-Webhook-Token': self.token}, document_id='svc-token-2')

        self.assertIn('TK-2', self._log('svc-token-2').payload)
