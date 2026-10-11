# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

import os
import re
from unittest import mock
from xml.etree import ElementTree

from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.easyocr.models.easyocr_extractor import EasyocrServiceError

ACCOUNT = 'odoo.addons.easyocr.models.easyocr_extractor.EasyocrExtractor.account'

MODULE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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

    def test_each_tab_is_a_page_of_its_own_and_not_the_one_before_it(self):
        """A page that is patched in place keeps showing what the tab before it asked for.

        The bar used to open the five pages as an action of their own, and the
        left panel of the settings lives in the settings form: it went away with
        it. Now the pages are drawn inside the settings screen, under the bar.
        That leaves the page component in the same place of the tree, and OWL
        patches it instead of making a new one: opening the changelog right after
        the plan showed "ChangeLog file not found", because the answer on state
        was still the plan's. The key is what makes each tab a fresh page. Its
        being there is the whole fix, and nothing on screen goes wrong without
        it, which is why it is checked here.
        """
        tree = ElementTree.parse(
            os.path.join(MODULE_ROOT, 'static', 'src', 'xml', 'easyocr_admin.xml'))
        bar = tree.find(".//t[@t-name='easyocr.AdminTabs']")
        self.assertIsNotNone(bar, "The tab bar's template is gone.")

        page = bar.find('.//EasyocrAdminPage')
        self.assertIsNotNone(page, "The bar no longer draws the pages.")
        self.assertEqual(
            page.get('t-key'), 'active',
            "The page is drawn without a key: switching tabs patches it in place "
            "and it keeps showing the tab before it.",
        )
        self.assertIn('setup', page.get('t-if') or '',
                      "The page is drawn on the settings tab as well.")

    def test_the_bar_sits_where_the_rule_that_hides_the_fields_can_reach_it(self):
        """While a page shows, the settings fields step aside by a CSS rule.

        The rule only reaches the bar's node directly under the app's block,
        which is also the node the widget is drawn into. One wrapping div in
        between and the rule hides the bar too: nothing is left on screen but
        the fields it was meant to replace.
        """
        tree = ElementTree.parse(os.path.join(MODULE_ROOT, 'views', 'res_config_settings_views.xml'))
        hosts = [node for node in tree.iter() if 'o_easyocr_admin_tabs_host' in (node.get('class') or '')]
        self.assertEqual(len(hosts), 1, "The bar's host node is not where it was.")

        # Odoo draws the <app> of the settings form as the app's block.
        parents = [
            node for node in tree.iter()
            if node.tag == 'app' and any('o_easyocr_admin_tabs_host' in (child.get('class') or '') for child in node)
        ]
        self.assertTrue(
            parents,
            "The bar's host is no longer a direct child of the app's block: the "
            "rule that hides the settings fields while a page shows cannot reach it.",
        )
        self.assertTrue(
            hosts[0].find(".//widget[@name='easyocr_admin_tabs']") is not None,
            "The host node no longer draws the bar.",
        )

    def test_the_class_the_javascript_toggles_is_the_one_the_style_hides_by(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, 'static', 'src', 'js', 'easyocr_admin.js'), encoding='utf-8') as handle:
            script = handle.read()
        with open(os.path.join(root, 'static', 'src', 'scss', 'easyocr_admin.scss'), encoding='utf-8') as handle:
            style = handle.read()
        # The whole class, not a class starting the same way: a rule left over
        # from a rename hides nothing and nothing says so.
        whole = re.compile(r'o_easyocr_admin_page_mode(?![\w-])')
        self.assertTrue(whole.search(script), "Nothing tells the page from the fields.")
        self.assertTrue(
            whole.search(style),
            "The script toggles a class no rule hides anything by: the fields and "
            "the page are shown together, and nothing says so.",
        )
