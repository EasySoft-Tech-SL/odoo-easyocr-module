# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

import os

import polib

from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools.translate import (
    JAVASCRIPT_TRANSLATION_COMMENT,
    PYTHON_TRANSLATION_COMMENT,
)

# The strings the viewer's JavaScript asks for by hand. They cannot be derived
# from a model, so they are listed here: a new one added to the viewer without
# a translation is what this list is meant to catch.
VIEWER_STRINGS = (
    "Draw at least one box before saving a template.",
    "Give the template a name.",
    "Template saved.",
)

# The sentences the mobile capture page's JavaScript writes. They travel the
# other way round -- the server translates them and hands them to the page, so
# they need the Python marker rather than the JavaScript one. The list is the
# same as ``_page_strings`` in controllers/expense.py, and a sentence added
# there without a line here is exactly what would go unnoticed.
CAPTURE_STRINGS = (
    "The camera is not ready yet. Give it a second.",
    "That file could not be read as a photo.",
    "The photo could not be prepared. Try again.",
    "The photo is still larger than the %(limit)s MB the inbox takes. "
    "Take it from a little further away.",
    "Sending the photo…",
    "The photo could not be sent. Check the connection and try again.",
    "The photo could not be sent.",
    "Read from the receipt",
    "Saved to the inbox",
    "Vendor",
    "Date",
    "Total",
    "Number",
)

# Every string the home screen's JavaScript asks for, including the ones it
# reuses from the menus and the capture page. Those are the ones worth listing:
# they are already translated, so nothing looks wrong in the .po -- and they
# still arrived in English until their entries were flagged as JavaScript,
# which is how "Capture a receipt" ended up on a Spanish screen.
HOME_STRINGS = (
    "Capture a receipt",
    "Webhook Log",
    "Documents",
    "Templates",
    "Inbox",
    "Read supplier invoices and expense receipts, and turn them into accounting entries.",
    "Invoices and receipts read, or waiting to be",
    "Waiting to be looked at, handed over by other modules",
    "The boxes saved for each vendor",
    "Photograph one from a phone",
    "The calls the extraction service has made",
    "The extraction service and what a document becomes",
    "Settings",
)

# Sentences the module builds in Python and hands to the screen as a
# notification. They need the Python marker for the same reason the capture page
# does: they never pass through a view, so nothing else would carry them across.
MESSAGE_STRINGS = (
    "This file has already been read: %(document)s. Reading it again would cost "
    "the same and change nothing.",
    "The bill was left in draft: it could not be confirmed on its own "
    "(%(error)s). Review it and confirm it by hand.",
    # What a webhook writes into its own log when it goes further than filing.
    "The bill could not be created (%(error)s).",
    "The bill was created from it.",
    "The bill was created, but the payment was not registered (%(reason)s).",
    "The bill was created from it and the payment registered.",
    "no bank account is set in the EasyOCR settings",
    "the bill is not confirmed, so there is nothing to pay yet",
    "the bill has nothing left to pay",
)

# The models whose terms are ours to translate. The two settings models are here
# too, and only through their own fields: they carry a few hundred of Odoo's.
MODELS = (
    'easyocr.document',
    'easyocr.document.line',
    'easyocr.inbox.item',
    'easyocr.template',
    'easyocr.template.box',
    'easyocr.webhook.log',
    'res.company',
    'res.config.settings',
)

# For a model we only borrow fields from, the prefix that makes a field ours.
OUR_FIELDS = {
    'res.company': 'easyocr_',
    'res.config.settings': 'easyocr_',
}

# Fields the mail mixin brings along. Their labels belong to the mail module: a
# reference for them here would only copy someone else's strings, and counting
# them as missing would turn this test into noise nobody reads.
BORROWED = ('activity_', 'message_')

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

    def _assert_marked(self, po, msgid, marker, hint):
        """The entry exists, is translated, and carries the reference it needs.

        Translating the string is not enough: Odoo only serves a translation to
        the JavaScript terms it has flagged as such, and Python's ``_()`` only
        finds the ones flagged as Python. A translated entry with the wrong
        marker is English on screen, and nothing about it looks wrong in the
        .po file.
        """
        entry = self._entry(po, msgid)
        self.assertTrue(
            entry.msgstr,
            "%s leaves %r without a translation" % (os.path.basename(po.fpath), msgid),
        )
        self.assertIn(
            marker,
            entry.comment,
            "%r is translated but never reaches the reader: %s does not flag it "
            "as a %s term. %s" % (msgid, os.path.basename(po.fpath), marker, hint),
        )

    def _assert_reaches_the_browser(self, po, msgid):
        self._assert_marked(
            po, msgid, JAVASCRIPT_TRANSLATION_COMMENT,
            "Add the .js reference of whichever script asks for it.",
        )

    def _assert_reaches_python(self, po, msgid):
        self._assert_marked(
            po, msgid, PYTHON_TRANSLATION_COMMENT,
            "Add the controllers/expense.py reference to its entry.",
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

    def test_the_strings_the_home_screen_writes_are_translated(self):
        for name in self._po_files():
            po = polib.pofile(os.path.join(self.i18n_path, name))
            for msgid in HOME_STRINGS:
                self._assert_reaches_the_browser(po, msgid)

    def test_the_sentences_the_capture_page_writes_are_translated(self):
        """They are written by JavaScript but translated by the server."""
        for name in self._po_files():
            po = polib.pofile(os.path.join(self.i18n_path, name))
            for msgid in CAPTURE_STRINGS:
                self._assert_reaches_python(po, msgid)

    def test_the_messages_the_module_shows_are_translated(self):
        for name in self._po_files():
            po = polib.pofile(os.path.join(self.i18n_path, name))
            for msgid in MESSAGE_STRINGS:
                self._assert_reaches_python(po, msgid)

    def test_every_label_says_where_odoo_looks_for_it(self):
        """A translation without a reference is a translation that never arrives.

        Odoo reads a term through the reference it generates for the record that
        holds it: a field label through that field's record, a selection label
        through the record of that key. A .po entry pointed anywhere else is
        complete, correct, and invisible -- the screen shows English or, for a
        selection, the raw key. Both happened here, which is why every term of
        every model is checked and not just the ones a person remembered.
        """
        checked = 0
        for msgid, refs in sorted(self._expected_references().items()):
            checked += 1
            for name in self._po_files():
                po = polib.pofile(os.path.join(self.i18n_path, name))
                entry = self._entry(po, msgid)
                self.assertTrue(
                    entry.msgstr,
                    "%s leaves %r without a translation" % (os.path.basename(po.fpath), msgid),
                )
                here = {ref for ref, _line in entry.occurrences}
                for ref in sorted(refs - here):
                    self.fail(
                        "%r is translated in %s but points nowhere Odoo will look "
                        "for it: it needs the reference %s"
                        % (msgid, os.path.basename(po.fpath), ref)
                    )
        self.assertGreater(checked, 50, "Barely any term was checked at all.")

    def _expected_references(self):
        """Every term of this module, under the reference Odoo looks it up by."""
        expected = {}

        def want(msgid, ref):
            if msgid:
                expected.setdefault(msgid, set()).add(ref)

        for model_name in MODELS:
            model = self.env[model_name]
            slug = model_name.replace('.', '_')
            ours = OUR_FIELDS.get(model_name)
            for field_name, field in model._fields.items():
                if field_name in ('id', 'display_name') or field_name.startswith(BORROWED):
                    continue
                if ours and not field_name.startswith(ours):
                    continue
                base = 'model:ir.model.fields,%s:easyocr.field_%s__%s'
                want(field.string, base % ('field_description', slug, field_name))
                want(field.help, base % ('help', slug, field_name))
                if field.type == 'selection':
                    for key, label in field._description_selection(self.env):
                        want(label, 'model:ir.model.fields.selection,name:'
                                    'easyocr.selection__%s__%s__%s' % (slug, field_name, key))
            want(model._description, 'model:ir.model,name:easyocr.model_%s' % slug)
        return expected

    def test_the_module_summary_is_translated(self):
        """The Apps screen shows it on the card, before the module is installed."""
        for name in self._po_files():
            po = polib.pofile(os.path.join(self.i18n_path, name))
            self.assertTrue(
                self._entry(po, SUMMARY).msgstr,
                "%s leaves the module summary in English" % name,
            )
