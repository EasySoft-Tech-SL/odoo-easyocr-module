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
        self.assertRegex(
            changelog['changelog'], r'(?m)^## \[\d+\.\d+\.\d+\] - \d{4}-\d{2}-\d{2}$',
            "The changelog no longer carries one section per released version: the "
            "page has nothing to fold and shows every bullet the module ever had.",
        )
        self.assertNotIn(
            '[Unreleased]', changelog['changelog'],
            "A block with no version in it is a block with no date and no release "
            "behind it: the page hangs it off nothing.",
        )
        self.assertEqual(about['module']['license'], 'LGPL-3')

    def test_the_changelog_is_read_in_the_readers_language(self):
        if not self.env['res.lang']._activate_lang('es_ES'):
            self.skipTest("Spanish is not loaded in this database, so there is nothing to read.")

        admin = self.env['easyocr.admin']
        self.env.user.write({'lang': 'en_US'})
        english = admin.action_admin_page('changelog')['changelog']
        self.env.user.write({'lang': 'es_ES'})
        spanish = admin.action_admin_page('changelog')['changelog']

        self.assertIn('# Changelog', english)
        self.assertIn('# Registro de cambios', spanish)
        self.assertNotEqual(english, spanish, "Spanish is served the English file.")
        self.assertEqual(
            re.findall(r'(?m)^## .*$', spanish), re.findall(r'(?m)^## .*$', english),
            "The two files do not carry the same versions.",
        )

    def test_the_spanish_changelog_keeps_up_with_the_english_one(self):
        """The two files are one changelog in two languages, not two changelogs.

        They are edited apart, so they drift apart: a version that lands in one
        and not in the other, or a bullet that grew a translation and no twin.
        Nothing on screen says so, and the reader of the other language is told
        about a release that, as far as they can see, never happened.
        """
        with open(os.path.join(MODULE_ROOT, 'CHANGELOG.md'), encoding='utf-8') as handle:
            english = handle.read()
        with open(os.path.join(MODULE_ROOT, 'CHANGELOG.es.md'), encoding='utf-8') as handle:
            spanish = handle.read()

        count = lambda text, mark: len(re.findall(r'(?m)^%s ' % mark, text))
        self.assertEqual(
            re.findall(r'(?m)^## .*$', spanish), re.findall(r'(?m)^## .*$', english),
            "One of the two files carries a version the other does not.",
        )
        self.assertEqual(count(spanish, '-'), count(english, '-'),
                         "A bullet was written in one language and not in the other.")
        self.assertEqual(count(spanish, '###'), count(english, '###'),
                         "A version has a section in one language and not in the other.")
        self.assertGreater(count(english, '##'), 1, "The changelog has no versions to keep in step.")

    def test_the_about_tab_is_read_in_the_readers_language(self):
        """The page hands the reader a README they can read.

        The changelog has been served in the reader's language for as long as
        the page has folded it. The README beside it was served in English
        whatever the screen spoke, which turns the one page that explains the
        module into the one page a Spanish reader has to work through in a
        language that is not theirs.
        """
        if not self.env['res.lang']._activate_lang('es_ES'):
            self.skipTest("Spanish is not loaded in this database, so there is nothing to read.")

        admin = self.env['easyocr.admin']
        self.env.user.write({'lang': 'en_US'})
        english = admin.action_admin_page('about')['readme_html']
        self.env.user.write({'lang': 'es_ES'})
        spanish = admin.action_admin_page('about')['readme_html']

        self.assertIn('The module depends on', english)
        self.assertIn('El módulo depende de', spanish)
        self.assertNotEqual(english, spanish, "Spanish is served the English README.")
        self.assertEqual(
            len(re.findall(r'<h[1-6]', english)), len(re.findall(r'<h[1-6]', spanish)),
            "The two pages do not carry the same sections: a heading of one of the "
            "files is not underlined the way rst needs it, so it reads as a paragraph.",
        )

    def test_a_language_without_a_readme_gets_the_english_one(self):
        """No reader is left with an empty About page.

        Only English and Spanish ship a README, and the interface speaks five
        more languages. A reader of one of those has no file of their own, and
        the page is the only place that explains the module. Serving them an
        empty page would take it away from them, so the English one stands in.
        """
        admin = self.env['easyocr.admin']
        missing = sorted(
            lang.code
            for lang in self.env['res.lang'].search([('active', '=', True)])
            if not os.path.isfile(
                os.path.join(MODULE_ROOT, 'README.%s.rst' % lang.code[:2].lower())
            )
        )
        if not missing:
            self.skipTest("Every active language ships a README of its own.")

        for code in missing:
            self.env.user.write({'lang': code})
            page = admin.action_admin_page('about')['readme_html']
            self.assertIn(
                'The module depends on', page,
                "The About page came out empty for %s, which has no README of "
                "its own and should have been served the English one." % code,
            )

    def test_the_spanish_readme_keeps_up_with_the_english_one(self):
        """The two files are one README in two languages, not two READMEs.

        They are edited apart, so they drift apart: an install step or a caveat
        added to one and not to the other. Nothing on screen says so, and the
        reader of the other language is never told about it.
        """
        english = self._readme_sections('README.rst')
        spanish = self._readme_sections('README.es.rst')

        self.assertGreater(len(english), 4, "The README has no sections to keep in step.")
        self.assertEqual(
            spanish, english,
            "One of the two files carries a section the other does not.",
        )

    def _readme_sections(self, name):
        """The shape of an rst file: one character per section, in order.

        The two READMEs say the same thing in two languages, so their words
        differ on purpose and comparing the words would compare nothing. What
        has to match is the shape.
        """
        with open(os.path.join(MODULE_ROOT, name), encoding='utf-8') as handle:
            lines = handle.read().splitlines()
        sections = []
        for index in range(1, len(lines)):
            title, underline = lines[index - 1].strip(), lines[index].strip()
            if not title or not underline:
                continue
            if len(underline) >= len(title) and len(set(underline)) == 1 \
                    and underline[0] in '=-~^"\'`#*+':
                sections.append(underline[0])
        return sections

    def test_the_website_the_module_points_at_is_the_product_one(self):
        """The licence tab sends the reader to easyocr.es, not to a dead name.

        The product has a site of its own, and it used to be written as a
        subdomain of the company's one. That address never answered. Nothing
        breaks when it is wrong either: the reader clicks and lands nowhere,
        and a test that only counts links would stay green.
        """
        with open(os.path.join(MODULE_ROOT, 'static', 'src', 'xml', 'easyocr_admin.xml'),
                  encoding='utf-8') as handle:
            template = handle.read()

        self.assertIn('https://easyocr.es/', template)
        for href in re.findall(r'href="([^"]+)"', template):
            if href.startswith('mailto:'):
                continue
            self.assertNotIn(
                'easysoft.es', href,
                "The module sends the reader to the company's site where the product's goes.",
            )
        self.assertNotIn('easyocr.easysoft.es', template)

        i18n = os.path.join(MODULE_ROOT, 'i18n')
        for name in sorted(os.listdir(i18n)):
            if not name.endswith('.po'):
                continue
            with open(os.path.join(i18n, name), encoding='utf-8') as handle:
                content = handle.read()
            self.assertNotIn(
                'easyocr.easysoft.es', content,
                "%s still translates the retired address." % name,
            )

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
        # Owl 3 wants a component's own values named as ``this.`` in a template
        # expression; up to 19 the bare name was read as the component's.
        self.assertEqual(
            page.get('t-key'), 'this.active',
            "The page is drawn without a key: switching tabs patches it in place "
            "and it keeps showing the tab before it.",
        )
        self.assertIn('setup', page.get('t-if') or '',
                      "The page is drawn on the settings tab as well.")

    def test_the_changelog_is_drawn_one_block_per_version(self):
        """Folding the changelog is two halves that have to agree.

        The file is cut into versions in the JavaScript and the template draws
        one block per piece. Lose either half and the page shows the whole file
        flat again, or nothing at all, and neither of those is an error
        anywhere: the page just comes out wrong.
        """
        tree = ElementTree.parse(
            os.path.join(MODULE_ROOT, 'static', 'src', 'xml', 'easyocr_admin.xml'))
        page = tree.find(".//t[@t-name='easyocr.AdminPage']")
        self.assertIsNotNone(page, "The page's template is gone.")

        blocks = list(page.iter('details'))
        self.assertEqual(len(blocks), 1, "The changelog is no longer drawn as blocks.")
        # ``this.`` for the same reason as the page key above: Owl 3 reads the
        # template expression with the component as its scope.
        self.assertEqual(blocks[0].get('t-foreach'), 'this.changelogVersions',
                         "The blocks are not the versions of the file.")
        self.assertIn('version.open', blocks[0].get('t-att-open') or '',
                      "No version is the one open when the page opens.")
        self.assertIsNotNone(blocks[0].find('summary'),
                             "A block has no heading to click, so it cannot be folded.")

        with open(os.path.join(MODULE_ROOT, 'static', 'src', 'js', 'easyocr_admin.js'),
                  encoding='utf-8') as handle:
            script = handle.read()
        self.assertIn('index === 0', script,
                      "The versions come back without one of them marked to open.")

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
