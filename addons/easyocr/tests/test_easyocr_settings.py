# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

"""The settings that change what the module does.

Each one of these was a switch in the module this port comes from, and each of
them is checked here by looking at the effect and not at the switch: a setting
that stores a value and changes nothing is exactly the failure this file exists
to catch, and it is invisible from the settings screen.
"""

import base64
from datetime import timedelta
from unittest import mock

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

POST = 'odoo.addons.easyocr.models.easyocr_extractor.requests.post'

# The same bytes for every document in a test is the whole point of the
# duplicate guard, so they are written once here.
FILE_BYTES = b'%PDF-1.4 the same invoice twice'


@tagged('post_install', '-at_install')
class TestEasyocrSettings(TransactionCase):
    """What each switch does, checked by its effect."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Document = cls.env['easyocr.document']
        cls.company = cls.env.company
        cls.partner = cls.env['res.partner'].create({
            'name': 'Proveedor de ajustes SL',
            'vat': 'B3186006',
        })
        # The AI has to be reachable on paper for the extraction paths to run at
        # all; the call itself is patched away in every test that gets that far.
        cls.company.write({
            'easyocr_ai_enabled': True,
            'easyocr_ai_url': 'https://ocr.example.test',
            'easyocr_ai_apikey': 'test-key',
        })

    def setUp(self):
        super().setUp()
        # Every switch back to how the module ships, so one test cannot decide
        # what the next one measures.
        self.company.write({
            'easyocr_bill_post': False,
            'easyocr_autocreate_product': False,
            'easyocr_allow_self_vendor': False,
            'easyocr_ai_receiver_context': False,
            'easyocr_duplicate_check': True,
            'easyocr_duplicate_window_days': 0,
        })

    def _attachment(self, content=FILE_BYTES, name='invoice.pdf'):
        return self.env['ir.attachment'].create({
            'name': name,
            'datas': base64.b64encode(content),
            'mimetype': 'application/pdf',
        })

    def _document(self, with_file=True, **values):
        if with_file:
            values.setdefault('attachment_id', self._attachment().id)
        values.setdefault('name', 'FAC-2026-0001')
        return self.Document.create(values)

    def _response(self, body=None):
        response = mock.Mock()
        response.status_code = 200
        response.headers = {}
        response.json.return_value = body if body is not None else {
            'status': 'success',
            'confidence': 0.9,
            'structured_data': {'document_number': 'A/1', 'totals': {'total': 121.0}},
        }
        return response

    # ------------------------------------------------------------------
    # Confirming the bill
    # ------------------------------------------------------------------
    def test_the_bill_stays_in_draft_unless_the_company_says_otherwise(self):
        """The module proposes; a person confirms. That is the shipped default."""
        document = self._document(partner_id=self.partner.id, amount_untaxed=100.0)

        document.action_create_bill()

        self.assertEqual(document.move_id.state, 'draft')

    def test_the_bill_is_confirmed_when_the_company_asks_for_it(self):
        self.company.easyocr_bill_post = True
        document = self._document(partner_id=self.partner.id, amount_untaxed=100.0)

        document.action_create_bill()

        self.assertEqual(document.move_id.state, 'posted')

    def test_a_bill_that_cannot_be_confirmed_is_still_created(self):
        """A bill left in draft with a reason beats no bill at all."""
        self.company.easyocr_bill_post = True
        document = self._document(partner_id=self.partner.id, amount_untaxed=100.0)
        move_action_post = 'odoo.addons.account.models.account_move.AccountMove.action_post'

        with mock.patch(move_action_post, side_effect=UserError('no account here')):
            document.action_create_bill()

        self.assertTrue(document.move_id)
        self.assertEqual(document.move_id.state, 'draft')
        self.assertIn('draft', document.move_id.message_ids.mapped('body')[0])

    # ------------------------------------------------------------------
    # Our own tax number as the vendor
    # ------------------------------------------------------------------
    def test_our_own_tax_number_is_taken_when_the_company_asks_for_it(self):
        """The switch is an escape hatch: the guard is the only thing in the way."""
        self.company.partner_id.with_context(no_vat_validation=True).vat = 'B12345678'
        self.company.easyocr_allow_self_vendor = True
        document = self._document(with_file=False, partner_vat='B12345678')

        document._resolve_partner()

        self.assertEqual(document.partner_id, self.company.partner_id)

    # ------------------------------------------------------------------
    # Duplicates
    # ------------------------------------------------------------------
    def test_the_same_file_is_not_read_twice(self):
        """Reading it again would cost the same and tell us nothing new."""
        first = self._document(name='PRIMERA')
        with mock.patch(POST, return_value=self._response()):
            first.action_extract()
        second = self._document(name='SEGUNDA')

        with mock.patch(POST) as post:
            result = second.action_extract()

        post.assert_not_called()
        self.assertIn('PRIMERA', result['params']['message'])
        # Turned away, not broken: the document is untouched and can be read by
        # hand or sent again on purpose.
        self.assertEqual(second.state, 'draft')

    def test_the_guard_can_be_turned_off(self):
        first = self._document(name='PRIMERA')
        with mock.patch(POST, return_value=self._response()):
            first.action_extract()
        self.company.easyocr_duplicate_check = False
        second = self._document(name='SEGUNDA')

        with mock.patch(POST, return_value=self._response()) as post:
            second.action_extract()

        post.assert_called_once()

    def test_the_window_lets_a_monthly_document_through_again(self):
        """A fixed monthly charge is the same file every month on purpose."""
        first = self._document(name='MENSUAL')
        with mock.patch(POST, return_value=self._response()):
            first.action_extract()
        # create_date is a log column and write() drops it without a word, so the
        # window has to count back from something the ORM will actually accept.
        first.sudo().extraction_date = first.extraction_date - timedelta(days=40)
        self.company.easyocr_duplicate_window_days = 30
        second = self._document(name='MENSUAL-OTRA-VEZ')

        with mock.patch(POST, return_value=self._response()) as post:
            second.action_extract()

        post.assert_called_once()

    def test_inside_the_window_the_same_file_is_still_turned_away(self):
        """The other half of the window: recent enough and the guard still holds."""
        first = self._document(name='MENSUAL')
        with mock.patch(POST, return_value=self._response()):
            first.action_extract()
        first.sudo().extraction_date = first.extraction_date - timedelta(days=10)
        self.company.easyocr_duplicate_window_days = 30
        second = self._document(name='MENSUAL-OTRA-VEZ')

        with mock.patch(POST) as post:
            second.action_extract()

        post.assert_not_called()

    def test_a_draft_is_not_a_duplicate_to_hide_behind(self):
        """A document nobody ever sent was never read, so it blocks nothing."""
        first = self._document(name='SIN-LEER')
        second = self._document(name='LEIDA')

        with mock.patch(POST, return_value=self._response()) as post:
            second.action_extract()

        post.assert_called_once()
        self.assertEqual(first.state, 'draft')

    # ------------------------------------------------------------------
    # Telling the service who we are
    # ------------------------------------------------------------------
    def test_nothing_extra_is_sent_to_the_service_by_default(self):
        self.company.partner_id.with_context(no_vat_validation=True).vat = 'B12345678'
        document = self._document()

        with mock.patch(POST, return_value=self._response()) as post:
            document.action_extract()

        self.assertNotIn('custom_instructions', post.call_args.kwargs['data'])

    def test_our_own_identity_goes_with_the_request_when_it_is_asked_for(self):
        self.company.partner_id.with_context(no_vat_validation=True).vat = 'B12345678'
        self.company.easyocr_ai_receiver_context = True
        document = self._document()

        with mock.patch(POST, return_value=self._response()) as post:
            document.action_extract()

        sent = post.call_args.kwargs['data']['custom_instructions']
        self.assertIn(self.company.name, sent)
        self.assertIn('B12345678', sent)

    def test_the_identity_sent_says_what_it_is_and_nothing_more(self):
        """Facts, never a procedure: an instruction the model cannot satisfy
        makes it run to the output ceiling and the call times out."""
        self.company.easyocr_ai_receiver_context = True

        sent = self.env['easyocr.extractor']._receiver_context(self.company)

        self.assertIn('Context', sent)
        self.assertIn('exactly as printed', sent)
        for procedure in ('verify', 're-read', 'check'):
            self.assertNotIn(procedure, sent.lower())
