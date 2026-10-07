# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestEasyocrHome(TransactionCase):
    """The screen the app opens on, and the way to everything else from it."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Menu = cls.env['ir.ui.menu']

    def test_the_app_opens_on_the_home_screen(self):
        """Odoo opens the first child of a root menu that carries an action.

        A home screen hung anywhere else is one nobody ever sees, which is the
        whole reason for having it.
        """
        root = self.env.ref('easyocr.menu_easyocr_root')

        candidates = root.child_id.filtered('action').sorted('sequence')

        self.assertTrue(candidates, "The app has no menu entry with an action.")
        self.assertEqual(
            candidates[0].action,
            self.env.ref('easyocr.action_easyocr_home'),
            "The app opens on %r. The home screen is no longer first."
            % candidates[0].action.name,
        )

    def test_the_home_action_carries_the_tag_the_component_registers(self):
        """The tag is the only thing joining the action to the JavaScript."""
        action = self.env.ref('easyocr.action_easyocr_home')

        self.assertEqual(action.type, 'ir.actions.client')
        self.assertEqual(action.tag, 'easyocr.home')

    def test_the_home_screen_offers_every_screen_the_module_has(self):
        """A card the component names but that does not exist is a dead click."""
        for xmlid in (
            'easyocr.action_easyocr_document',
            'easyocr.action_easyocr_inbox',
            'easyocr.action_easyocr_template',
            'easyocr.action_easyocr_webhook_log',
        ):
            action = self.env.ref(xmlid, raise_if_not_found=False)
            self.assertTrue(action, "%s is missing." % xmlid)
            self.assertEqual(action.type, 'ir.actions.act_window')

    def test_the_home_screen_is_the_first_thing_in_the_menu_bar(self):
        """It sits before the documents, so the bar reads in the order of use."""
        home = self.env.ref('easyocr.menu_easyocr_home')
        documents = self.env.ref('easyocr.menu_easyocr_document')

        self.assertEqual(home.parent_id, documents.parent_id)
        self.assertLess(home.sequence, documents.sequence)
