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

import requests

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

POST = 'odoo.addons.easyocr.models.easyocr_extractor.requests.post'
GET = 'odoo.addons.easyocr.models.easyocr_extractor.requests.get'

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
            'easyocr_invoice_draft': True,
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
            'processing_time_ms': 1234,
            'structured_data': {'document_number': 'A/1', 'totals': {'total': 121.0}},
        }
        return response

    def _account_response(self, body=None):
        response = mock.Mock()
        response.status_code = 200
        response.headers = {}
        response.json.return_value = body if body is not None else {
            'data': {
                'account': {'name': 'EasySoft Tech SL'},
                'plan': {'name': 'Professional', 'is_free': False},
                'status': {'can_process': True, 'block_code': None, 'block_message': None},
                'quota': {
                    'pages_used': 120, 'pages_limit': 600, 'pages_remaining': 480,
                    'usage_percentage': 20, 'reset_date': '2026-11-01T00:00:00+01:00',
                },
                'wallet': {'exists': True, 'balance_pages': 0},
                'features': {'custom_instructions': True},
            },
        }
        return response

    def _settings(self, company=None):
        return self.env['res.config.settings'].create({
            'company_id': (company or self.company).id,
        })

    # ------------------------------------------------------------------
    # Confirming the bill
    # ------------------------------------------------------------------
    def test_the_bill_stays_in_draft_unless_the_company_says_otherwise(self):
        """The module proposes; a person confirms. That is the shipped default."""
        document = self._document(partner_id=self.partner.id, amount_untaxed=100.0)

        document.action_create_bill()

        self.assertEqual(document.move_id.state, 'draft')

    def test_the_bill_is_confirmed_when_the_company_asks_for_it(self):
        self.company.easyocr_invoice_draft = False
        document = self._document(partner_id=self.partner.id, amount_untaxed=100.0)

        document.action_create_bill()

        self.assertEqual(document.move_id.state, 'posted')

    def test_a_bill_that_cannot_be_confirmed_is_still_created(self):
        """A bill left in draft with a reason beats no bill at all."""
        self.company.easyocr_invoice_draft = False
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
    #
    # What the guard does when it finds one is ask, not refuse: the reader may
    # know that this month's fixed fee really is the same file as last month's.
    # The three things to hold down are that it asks, that asking costs nothing,
    # and that the answer is honoured.
    # ------------------------------------------------------------------
    def test_the_same_file_is_not_read_twice_without_asking(self):
        """Reading it again would cost the same and tell us nothing new."""
        first = self._document(name='PRIMERA')
        with mock.patch(POST, return_value=self._response()):
            first.action_extract()
        second = self._document(name='SEGUNDA')

        with mock.patch(POST) as post:
            result = second.action_extract()

        post.assert_not_called()
        self.assertEqual(result['res_model'], 'easyocr.reprocess.wizard')
        wizard = self.env['easyocr.reprocess.wizard'].browse(result['res_id'])
        self.assertEqual(wizard.document_id, second)
        self.assertEqual(wizard.duplicate_id, first)
        self.assertIn('PRIMERA', wizard.message)
        # Turned away, not broken: the document is untouched and can be read by
        # hand or sent again on purpose.
        self.assertEqual(second.state, 'draft')

    def test_the_reader_can_ask_for_it_anyway(self):
        """The other half: the question has an answer that is yes."""
        first = self._document(name='PRIMERA')
        with mock.patch(POST, return_value=self._response()):
            first.action_extract()
        second = self._document(name='SEGUNDA')

        with mock.patch(POST, return_value=self._response()) as post:
            second.action_extract(force=True)

        post.assert_called_once()
        self.assertEqual(second.state, 'processed')

    def test_the_dialog_reads_it_again_and_says_so(self):
        """The button of the dialog, which is what a reader actually presses."""
        first = self._document(name='PRIMERA')
        with mock.patch(POST, return_value=self._response()):
            first.action_extract()
        second = self._document(name='SEGUNDA')
        wizard = self.env['easyocr.reprocess.wizard'].create({
            'document_id': second.id,
            'duplicate_id': first.id,
        })

        with mock.patch(POST, return_value=self._response()) as post:
            result = wizard.action_read_again()

        post.assert_called_once()
        self.assertEqual(second.state, 'processed')
        # And it says what was read, on the dialog the module keeps for that.
        self.assertEqual(result['tag'], 'easyocr.ocr_result_dialog')

    def test_leaving_the_dialog_alone_reads_nothing(self):
        first = self._document(name='PRIMERA')
        with mock.patch(POST, return_value=self._response()):
            first.action_extract()
        second = self._document(name='SEGUNDA')
        wizard = self.env['easyocr.reprocess.wizard'].create({
            'document_id': second.id,
            'duplicate_id': first.id,
        })

        with mock.patch(POST) as post:
            result = wizard.action_cancel()

        post.assert_not_called()
        self.assertEqual(result['type'], 'ir.actions.act_window_close')
        self.assertEqual(second.state, 'draft')

    def test_the_question_names_the_date_and_the_bill_of_the_earlier_reading(self):
        """What a reader needs to tell the two apart, when there is one."""
        first = self._document(name='PRIMERA', partner_id=self.partner.id)
        with mock.patch(POST, return_value=self._response()):
            first.action_extract()
        first.move_id = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner.id,
        })
        second = self._document(name='SEGUNDA')

        with mock.patch(POST):
            result = second.action_extract()

        message = self.env['easyocr.reprocess.wizard'].browse(result['res_id']).message
        self.assertIn('PRIMERA', message)
        self.assertIn('read on', message.lower())
        self.assertIn(first.move_id.display_name, message)

    def test_the_reader_is_told_what_was_read(self):
        """A reading costs money and takes time: it ends on a screen, not in a toast.

        The answer here carries what the service really sends back, which is
        more than the document has fields for.
        """
        document = self._document(partner_id=self.partner.id)
        answer = {
            'status': 'success',
            'confidence': 0.94,
            'processing_time_ms': 1234,
            'structured_data': {
                'document_number': 'A/1',
                'totals': {'total': 121.0},
                'supplier': {'address': 'Calle Mayor 1', 'city': 'Valencia'},
                'payment': {'method': 'Transferencia'},
            },
        }

        with mock.patch(POST, return_value=self._response(answer)):
            result = document.action_extract()

        self.assertEqual(result['tag'], 'easyocr.ocr_result_dialog')
        self.assertEqual(result['params']['document_id'], document.id)
        # The data the dialog draws: the confidence and the time are the ones
        # the service answered, and what it did not answer is not invented.
        data = document.action_result_data()
        self.assertIn('94', data['meta_pills'][0])
        self.assertIn('1.2', data['meta_pills'][1])
        # And the vendor details the document has no field for, which used to be
        # read and thrown away.
        self.assertIn('Calle Mayor 1', [v for row in data['sections']['supplier'] for v in row])
        self.assertIn('Transferencia', [v for row in data['sections']['payment'] for v in row])

    def test_the_viewer_can_ask_before_reading(self):
        """The viewer asks on its own, so it can show the reading while it runs."""
        first = self._document(name='PRIMERA')
        with mock.patch(POST, return_value=self._response()):
            first.action_extract()
        second = self._document(name='SEGUNDA')

        answer = second.action_check_duplicate()

        self.assertEqual(answer['document_id'], first.id)
        self.assertIn('PRIMERA', answer['message'])

    def test_there_is_nothing_to_ask_about_a_file_nobody_read(self):
        document = self._document(name='NUEVA')

        self.assertFalse(document.action_check_duplicate())

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

    # ------------------------------------------------------------------
    # Asking the service about the account before sending anything
    # ------------------------------------------------------------------
    def test_the_connection_button_says_who_the_key_belongs_to(self):
        """The answer to "is this key any good", in one press and no invoice."""
        settings = self._settings()

        with mock.patch(GET, return_value=self._account_response()):
            answer = settings.action_easyocr_test_connection()

        self.assertEqual(answer['params']['type'], 'success')
        self.assertIn('EasySoft Tech SL', answer['params']['message'])
        self.assertIn('Professional', answer['params']['message'])
        self.assertIn('480', answer['params']['message'])

    def test_asking_about_the_account_does_not_spend_a_reading(self):
        """The whole point of the button: it costs nothing to be told no.

        A reading that comes back refused was paid for on the way out, so the
        check has to go to the endpoint that only asks who the key is.
        """
        settings = self._settings()

        with mock.patch(GET, return_value=self._account_response()) as get:
            with mock.patch(POST) as post:
                settings.action_easyocr_test_connection()

        self.assertTrue(get.call_args.args[0].endswith('/api/v1/account/me'))
        post.assert_not_called()

    def test_the_connection_button_reports_a_key_the_service_does_not_know(self):
        settings = self._settings()
        refused = self._account_response({
            'success': False,
            'error': {'code': 'INVALID_API_KEY', 'message': 'API Key inválida o revocada.'},
        })
        refused.status_code = 401

        with mock.patch(GET, return_value=refused):
            answer = settings.action_easyocr_test_connection()

        self.assertEqual(answer['params']['type'], 'warning')
        self.assertIn('rejected the API key', answer['params']['message'])

    def test_the_connection_button_says_when_there_is_nothing_left_to_read_with(self):
        """A key can be perfectly good and the account still unable to read."""
        settings = self._settings()
        blocked = self._account_response({
            'success': True,
            'data': {
                'account': {'name': 'EasySoft Tech SL'},
                'plan': {'name': 'Professional'},
                'status': {
                    'can_process': False,
                    'block_code': 'QUOTA_EXCEEDED',
                    'block_message': 'Has alcanzado el límite de 500 páginas/mes.',
                },
                'quota': {'pages_available_now': 0},
            },
        })

        with mock.patch(GET, return_value=blocked):
            answer = settings.action_easyocr_test_connection()

        self.assertEqual(answer['params']['type'], 'warning')
        self.assertIn('500', answer['params']['message'])

    def test_the_connection_button_says_when_the_service_does_not_answer(self):
        settings = self._settings()

        with mock.patch(GET, side_effect=requests.exceptions.ConnectionError('no route')):
            answer = settings.action_easyocr_test_connection()

        self.assertEqual(answer['params']['type'], 'warning')
        self.assertIn('could not be reached', answer['params']['message'])

    def test_the_connection_button_checks_the_company_of_the_screen(self):
        """Not the one the user happens to be working in.

        The settings screen is opened *for* a company, and checking the other one
        would answer about a key nobody asked about.
        """
        other = self.env['res.company'].create({
            'name': 'Sociedad de pruebas',
            'easyocr_ai_url': 'https://otra.example.test',
            'easyocr_ai_apikey': 'otra-clave',
        })
        self.assertNotEqual(other, self.env.company)
        settings = self._settings(other)

        with mock.patch(GET, return_value=self._account_response()) as get:
            settings.action_easyocr_test_connection()

        self.assertIn('otra.example.test', get.call_args.args[0])
        self.assertEqual(get.call_args.kwargs['headers']['X-API-Key'], 'otra-clave')

    def test_the_connection_button_is_on_the_settings_screen(self):
        """A method nobody can press is a method that does not exist."""
        view = self.env.ref('easyocr.res_config_settings_view_form_easyocr')
        arch = view.arch

        self.assertIn('action_easyocr_test_connection', arch)
        self.assertIn('Test the connection', arch)

    # ------------------------------------------------------------------
    # The account, as the viewer's banner reads it
    # ------------------------------------------------------------------
    def test_the_viewer_is_told_the_plan_and_the_quota(self):
        """The banner shows the plan and the quota, straight from the service."""
        with mock.patch(GET, return_value=self._account_response()):
            state = self.Document.action_account_state()

        self.assertFalse(state['blocked'])
        self.assertEqual(state['plan']['name'], 'Professional')
        self.assertFalse(state['plan']['is_free'])
        self.assertEqual(state['quota']['pages_used'], 120)
        self.assertEqual(state['quota']['pages_limit'], 600)
        self.assertEqual(state['quota']['pages_remaining'], 480)
        self.assertEqual(state['quota']['usage_percentage'], 20)
        self.assertTrue(state['wallet']['exists'])
        self.assertTrue(state['has_custom_instructions'])

    def test_the_viewer_is_told_when_the_account_cannot_read(self):
        """A blocked account is named, with the reason the service gives."""
        blocked = self._account_response({
            'data': {
                'account': {'name': 'EasySoft Tech SL'},
                'plan': {'name': 'Professional'},
                'status': {
                    'can_process': False,
                    'block_code': 'QUOTA_EXCEEDED',
                    'block_message': 'Has alcanzado el límite.',
                },
                'quota': {'pages_used': 600, 'pages_limit': 600, 'pages_remaining': 0},
                'wallet': {'exists': True, 'balance_pages': 0},
                'features': {},
            },
        })

        with mock.patch(GET, return_value=blocked):
            state = self.Document.action_account_state()

        self.assertTrue(state['blocked'])
        self.assertEqual(state['block_code'], 'QUOTA_EXCEEDED')
        self.assertIn('monthly limit', state['message'])

    def test_the_identity_sent_says_what_it_is_and_nothing_more(self):
        """Facts, never a procedure: an instruction the model cannot satisfy
        makes it run to the output ceiling and the call times out."""
        self.company.easyocr_ai_receiver_context = True

        sent = self.env['easyocr.extractor']._receiver_context(self.company)

        self.assertIn('Context', sent)
        self.assertIn('exactly as printed', sent)
        for procedure in ('verify', 're-read', 'check'):
            self.assertNotIn(procedure, sent.lower())
