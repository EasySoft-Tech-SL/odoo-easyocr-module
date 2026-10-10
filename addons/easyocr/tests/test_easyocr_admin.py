# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

from unittest import mock

from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.easyocr.models.easyocr_extractor import EasyocrServiceError

ACCOUNT = 'odoo.addons.easyocr.models.easyocr_extractor.EasyocrExtractor.account'


@tagged('post_install', '-at_install')
class TestEasyocrAdmin(TransactionCase):
    """The configuration tabs besides the settings, as the module this ports has them."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Admin = cls.env['easyocr.admin']
        cls.company = cls.env.company

    def _configured(self):
        self.company.write({
            'easyocr_ai_enabled': True,
            'easyocr_ai_apikey': 'clave-de-prueba',
            'easyocr_ai_url': 'https://servicio.example',
        })

    def test_about_license_and_changelog_read_the_module_files(self):
        about = self.Admin.action_admin_page('about')
        license_page = self.Admin.action_admin_page('license')
        changelog = self.Admin.action_admin_page('changelog')

        self.assertIn('EasyOCR', about['readme_html'])
        self.assertIn('<', about['readme_html'], "The README comes back rendered, not raw.")
        self.assertIn('GNU LESSER GENERAL PUBLIC LICENSE', license_page['license_text'])
        self.assertIn('## [Unreleased]', changelog['changelog'])
        self.assertEqual(about['module']['license'], 'LGPL-3')

    def test_telemetry_says_whether_our_identity_goes_with_the_request(self):
        self.company.easyocr_ai_receiver_context = True
        self.assertTrue(self.Admin.action_admin_page('telemetry')['receiver_context'])

        self.company.easyocr_ai_receiver_context = False
        self.assertFalse(self.Admin.action_admin_page('telemetry')['receiver_context'])

    def test_the_plan_is_not_asked_for_without_a_key(self):
        self.company.write({'easyocr_ai_enabled': True, 'easyocr_ai_apikey': False})

        with mock.patch(ACCOUNT) as account:
            page = self.Admin.action_admin_page('plan')

        self.assertEqual(page['state'], 'not_configured')
        account.assert_not_called()

    def test_the_plan_shows_the_account_the_service_answers(self):
        self._configured()
        answer = {'plan': {'name': 'EASYSOFT', 'is_free': True}, 'quota': {'pages_used': 3}}

        with mock.patch(ACCOUNT, return_value=answer):
            page = self.Admin.action_admin_page('plan')

        self.assertEqual(page['state'], 'ok')
        self.assertEqual(page['data']['plan']['name'], 'EASYSOFT')

    def test_a_rejected_key_is_told_apart_from_a_service_that_is_down(self):
        self._configured()

        with mock.patch(ACCOUNT, side_effect=EasyocrServiceError('rechazada', 401)):
            rejected = self.Admin.action_admin_page('plan')
        with mock.patch(ACCOUNT, side_effect=EasyocrServiceError('caído', 0)):
            down = self.Admin.action_admin_page('plan')

        self.assertEqual(rejected['state'], 'auth_error')
        self.assertEqual(down['state'], 'api_error')

    def test_only_managers_see_the_configuration(self):
        clerk = self.env['res.users'].create({
            'name': 'Usuario EasyOCR de prueba',
            'login': 'usuario-easyocr-admin-prueba',
            'group_ids': [(6, 0, [self.env.ref('easyocr.group_easyocr_user').id])],
        }) if 'group_ids' in self.env['res.users']._fields else self.env['res.users'].create({
            'name': 'Usuario EasyOCR de prueba',
            'login': 'usuario-easyocr-admin-prueba',
            'groups_id': [(6, 0, [self.env.ref('easyocr.group_easyocr_user').id])],
        })

        with self.assertRaises(AccessError):
            self.Admin.with_user(clerk).action_admin_page('about')
