# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

import os

import polib

from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools.translate import JAVASCRIPT_TRANSLATION_COMMENT

# The strings the viewer's JavaScript asks for by hand. They cannot be derived
# from a model, so they are listed here: a new one added to the viewer without
# a translation is what this list is meant to catch.
VIEWER_STRINGS = (
    "Draw at least one box before saving a template.",
    "Give the template a name.",
    "Template saved.",
)

# The summary the Apps screen shows on the module's card.
SUMMARY = "Extract supplier invoices and expense receipts from PDF and image files"


@tagged('post_install', '-at_install')
class TestEasyocrTranslations(TransactionCase):
    """Every string the interface shows must actually reach the user's language.

    A label declared in Python but never referenced from JavaScript is a label
    the web client never receives: the toolbar then falls back to English while
    the rest of the screen is translated. That is invisible from Python and
    invisible in the .po file, so it is checked here instead.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        module_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cls.i18n_path = os.path.join(module_path, 'i18n')

    def _po_files(self):
        names = sorted(name for name in os.listdir(self.i18n_path) if name.endswith('.po'))
        self.assertTrue(names, "The module ships no translation files at all.")
        return names

    def _entry(self, po, msgid):
        entry = po.find(msgid)
        self.assertIsNotNone(entry, "%s has no entry for %r" % (os.path.basename(po.fpath), msgid))
        return entry

    def _assert_reaches_the_browser(self, po, msgid):
        """The entry exists, is translated, and is flagged as a JavaScript term."""
        entry = self._entry(po, msgid)
        self.assertTrue(
            entry.msgstr,
            "%s leaves %r without a translation" % (os.path.basename(po.fpath), msgid),
        )
        self.assertIn(
            JAVASCRIPT_TRANSLATION_COMMENT,
            entry.comment,
            "%r is translated but never reaches the web client: %s does not flag "
            "it as a JavaScript term, so the interface falls back to English. "
            "Add the viewer's .js reference to its entry."
            % (msgid, os.path.basename(po.fpath)),
        )

    def test_every_field_label_is_translated_and_reaches_the_toolbar(self):
        """The nine labels the viewer paints, taken from the model itself."""
        selection = self.env['easyocr.template.box']._fields['field_key'].selection
        self.assertTrue(selection, "The field has no selection to check.")

        for name in self._po_files():
            po = polib.pofile(os.path.join(self.i18n_path, name))
            for _key, label in selection:
                self._assert_reaches_the_browser(po, label)

    def test_the_strings_the_viewer_writes_itself_are_translated(self):
        for name in self._po_files():
            po = polib.pofile(os.path.join(self.i18n_path, name))
            for msgid in VIEWER_STRINGS:
                self._assert_reaches_the_browser(po, msgid)

    def test_the_module_summary_is_translated(self):
        """The Apps screen shows it on the card, before the module is installed."""
        for name in self._po_files():
            po = polib.pofile(os.path.join(self.i18n_path, name))
            self.assertTrue(
                self._entry(po, SUMMARY).msgstr,
                "%s leaves the module summary in English" % name,
            )
