# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

import base64
import json
from unittest import mock

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

# The one place the extractor reaches the network. Patching it here keeps every
# test off the wire: what is checked is how the answer is read, not the service.
POST = 'odoo.addons.easyocr.models.easyocr_extractor.requests.post'


@tagged('post_install', '-at_install')
class TestEasyocrExtractor(TransactionCase):
    """Reading the service answer, including the failures that come as HTTP 200."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Document = cls.env['easyocr.document']
        cls.company = cls.env.company
        cls.company.write({
            'easyocr_ai_enabled': True,
            'easyocr_ai_url': 'https://ocr.example.test',
            'easyocr_ai_apikey': 'test-key',
            'easyocr_ai_timeout': 30,
        })

    def _document(self, **values):
        attachment = self.env['ir.attachment'].create({
            'name': 'invoice.pdf',
            'datas': base64.b64encode(b'%PDF-1.4 fake invoice'),
            'mimetype': 'application/pdf',
        })
        values.setdefault('name', 'INV/2026/0001')
        values.setdefault('attachment_id', attachment.id)
        return self.Document.create(values)

    def _response(self, status_code=200, body=None, headers=None):
        response = mock.Mock()
        response.status_code = status_code
        response.headers = headers or {}
        response.json.return_value = body if body is not None else {}
        return response

    # ------------------------------------------------------------------
    # A good answer
    # ------------------------------------------------------------------
    def test_a_successful_extraction_fills_the_document(self):
        body = {
            'status': 'success',
            'confidence': 0.93,
            'processing_time_ms': 1200,
            'tokens': {'input': 10, 'output': 20, 'total': 30},
            'structured_data': {
                'document_type': 'invoice',
                'document_number': 'A/123',
                'issue_date': '2026-01-31',
                'due_date': '2026-03-02',
                'currency': 'EUR',
                'supplier': {
                    'name': 'Proveedor de prueba SL',
                    'tax_id': 'B3186006',
                    'address': 'Calle Mayor 1',
                    'phone': '',
                    'email': '',
                },
                'customer': {'name': '', 'tax_id': ''},
                'items': [],
                'totals': {
                    'net_subtotal': 100.0,
                    'tax_total': 21.0,
                    'discount_total': 0.0,
                    'total': 121.0,
                    'total_payable': 121.0,
                    'taxes': [],
                },
                'payment': {'method': 'transfer', 'reference': '', 'due_date': '2026-03-02'},
            },
        }
        document = self._document()

        with mock.patch(POST, return_value=self._response(body=body)) as post:
            document.action_extract()

        self.assertEqual(document.state, 'processed')
        self.assertFalse(document.error_message)
        self.assertEqual(document.ref, 'A/123')
        self.assertEqual(str(document.document_date), '2026-01-31')
        self.assertEqual(document.partner_name, 'Proveedor de prueba SL')
        self.assertEqual(document.partner_vat, 'B3186006')
        self.assertAlmostEqual(document.amount_untaxed, 100.0, places=2)
        self.assertAlmostEqual(document.amount_total, 121.0, places=2)
        self.assertAlmostEqual(document.extraction_confidence, 0.93, places=2)

        # The raw answer is kept, for support.
        self.assertIn('A/123', document.last_extraction)
        self.assertEqual(json.loads(document.last_extraction)['status'], 'success')

        # The call went to the configured endpoint, with the key and the file.
        post.assert_called_once()
        kwargs = post.call_args.kwargs
        self.assertTrue(post.call_args.args[0].startswith('https://ocr.example.test'))
        self.assertTrue(post.call_args.args[0].endswith('/api/v1/ocr/file'))
        self.assertEqual(kwargs['headers']['X-API-Key'], 'test-key')
        self.assertIn('file', kwargs['files'])

    def test_a_reading_that_comes_back_negative_is_a_credit_note(self):
        """A rectificativa is what a vendor writes when they owe you money."""
        body = {
            'status': 'success',
            'structured_data': {
                'document_number': 'R/2026/1',
                'supplier': {'name': 'Proveedor SL'},
                'totals': {'net_subtotal': -100.0, 'total': -121.0},
            },
        }
        document = self._document()

        with mock.patch(POST, return_value=self._response(body=body)):
            document.action_extract()

        self.assertTrue(document.is_refund)
        # What the paper says is what is kept: the sign is not tidied away.
        self.assertAlmostEqual(document.amount_total, -121.0, places=2)

    def test_a_reading_that_comes_back_positive_is_not(self):
        body = {
            'status': 'success',
            'structured_data': {
                'document_number': 'A/1',
                'supplier': {'name': 'Proveedor SL'},
                'totals': {'net_subtotal': 100.0, 'total': 121.0},
            },
        }
        document = self._document()

        with mock.patch(POST, return_value=self._response(body=body)):
            document.action_extract()

        self.assertFalse(document.is_refund)

    def test_a_date_the_model_cannot_store_is_skipped(self):
        """A date in an unexpected shape must not sink the whole extraction."""
        body = {
            'status': 'success',
            'structured_data': {
                'document_number': 'A/9',
                'issue_date': '31/01/2026',
                'supplier': {'name': 'Proveedor SL'},
                'totals': {'net_subtotal': 10.0, 'total': 10.0},
            },
        }
        document = self._document(document_date='2026-01-01')

        with mock.patch(POST, return_value=self._response(body=body)):
            document.action_extract()

        self.assertEqual(document.state, 'processed')
        self.assertEqual(str(document.document_date), '2026-01-01')  # kept, not wiped

    # ------------------------------------------------------------------
    # HTTP 200 that is really a failure
    # ------------------------------------------------------------------
    def test_a_truncated_extraction_leaves_the_document_in_error(self):
        body = {
            'status': 'partial',
            'error_code': 'STRUCTURING_TRUNCATED',
            'error_message': 'Output truncated at 4096 tokens',
            'confidence': 0.4,
            'structured_data': {'document_number': 'A/1'},
        }
        document = self._document()

        with mock.patch(POST, return_value=self._response(body=body)):
            document.action_extract()

        self.assertEqual(document.state, 'error')
        self.assertIn('STRUCTURING_TRUNCATED', document.error_message)
        self.assertIn('Output truncated', document.error_message)
        # The fields are left alone: a partial read is not written to the document.
        self.assertFalse(document.ref)

    def test_an_unreadable_structured_data_is_a_failure_even_on_success(self):
        body = {
            'status': 'success',
            'structured_data': {
                'raw': 'the model wrote prose instead of JSON',
                'parse_error': 'Expecting value: line 1 column 1',
            },
        }
        document = self._document()

        with mock.patch(POST, return_value=self._response(body=body)):
            document.action_extract()

        self.assertEqual(document.state, 'error')
        self.assertIn('Expecting value', document.error_message)

    # ------------------------------------------------------------------
    # Plain HTTP errors
    # ------------------------------------------------------------------
    def test_a_401_leaves_a_readable_error_and_does_not_raise(self):
        document = self._document()

        with mock.patch(POST, return_value=self._response(status_code=401)) as post:
            # Must not raise: the user gets the document, not a dialog.
            document.action_extract()

        self.assertEqual(document.state, 'error')
        self.assertTrue(document.error_message)
        self.assertIn('API key', document.error_message)
        post.assert_called_once()

    def test_a_403_names_the_key_as_the_problem(self):
        document = self._document()

        with mock.patch(POST, return_value=self._response(status_code=403)):
            document.action_extract()

        self.assertEqual(document.state, 'error')
        self.assertIn('API key', document.error_message)

    def test_a_key_that_was_refused_is_not_reported_as_a_key_that_was_missing(self):
        """Both arrive as 401, and they send the reader to different places.

        One is "paste your key"; the other is "that key is not mine". Reporting
        the second as the first is how a perfectly good-looking key ends up
        being pasted again and again.
        """
        document = self._document()
        body = {'success': False, 'error': {'code': 'INVALID_API_KEY', 'message': 'no'}}

        with mock.patch(POST, return_value=self._response(status_code=401, body=body)):
            document.action_extract()

        self.assertEqual(document.state, 'error')
        self.assertIn('rejected the API key', document.error_message)
        self.assertNotIn('none is set', document.error_message)

    def test_a_request_without_a_key_says_so(self):
        document = self._document()
        body = {'success': False, 'error': {'code': 'MISSING_API_KEY', 'message': 'no'}}

        with mock.patch(POST, return_value=self._response(status_code=401, body=body)):
            document.action_extract()

        self.assertEqual(document.state, 'error')
        self.assertIn('none is set', document.error_message)

    def test_an_account_with_nothing_left_says_what_to_do(self):
        """A quota problem is not a mistake in the settings, and saying so saves
        the reader from going over the key once more."""
        document = self._document()
        body = {'success': False, 'error': {'code': 'QUOTA_EXCEEDED', 'message': 'no'}}

        with mock.patch(POST, return_value=self._response(status_code=429, body=body)):
            document.action_extract()

        self.assertEqual(document.state, 'error')
        self.assertIn('monthly limit', document.error_message)

    # ------------------------------------------------------------------
    # Settings are honoured
    # ------------------------------------------------------------------
    def test_extraction_is_not_attempted_when_it_is_off(self):
        self.company.easyocr_ai_enabled = False
        document = self._document()

        with mock.patch(POST) as post:
            document.action_extract()

        post.assert_not_called()
        self.assertEqual(document.state, 'error')
        self.assertTrue(document.error_message)

    def test_a_document_without_a_file_stops_before_calling(self):
        document = self.Document.create({'name': 'INV/2026/0002'})

        with mock.patch(POST) as post:
            document.action_extract()

        post.assert_not_called()
        self.assertEqual(document.state, 'error')
        self.assertTrue(document.error_message)
