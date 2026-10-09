# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

import os
import re
import xml.etree.ElementTree as ElementTree

import polib

from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools.translate import (
    JAVASCRIPT_TRANSLATION_COMMENT,
    PYTHON_TRANSLATION_COMMENT,
)

# Attributes an OWL template paints as they are written. A literal in any of
# them is a term the reader sees.
TEMPLATE_ATTRIBUTES = ('string', 'title', 'placeholder', 'alt')

# Text that is punctuation, an entity or a lone symbol rather than a sentence.
NOT_A_SENTENCE = re.compile(r'^[^\w]*$')

# Written into a template and never translated, on purpose: it is the product's
# name, and a translated one would be a different product. "1-8" is the key
# hint next to the fields, not a word.
NEVER_TRANSLATED = ('EasyOCR', 'easyOCR AI', 'PRO', '1-8')

# The strings the viewer's JavaScript asks for by hand. They cannot be derived
# from a model, so they are listed here: a new one added to the viewer without
# a translation is what this list is meant to catch.
VIEWER_STRINGS = (
    # The stages of the reading bar. They are estimates of a reading in
    # progress, painted while the server says nothing, and they are read out
    # loud on the screen: a stage left in English is as visible as any label.
    "Sending the file...",
    "Checking the document...",
    "Reading the text (OCR)...",
    "Working through the pages...",
    "OCR finished...",
    "Structuring the data with AI...",
    "Analysing the fields...",
    "Finishing the analysis...",
    "Almost there...",
    "Checking the result...",
    # The question the viewer asks itself, because it is the one that shows the
    # reading while it happens.
    "Read it again?",
    "Read it again",
    "Leave it",
    "Draw at least one box before saving a template.",
    "Give the template a name.",
    "Template saved.",
    # What the toolbar says while the service is thinking. A reading takes
    # seconds, and a button that looks dead for that long gets pressed again.
    "Reading the document. A scanned page takes a while.",
    "Preparing the bill.",
    # Sentences the viewer builds and paints itself. The ones with a number in
    # them are here for the same reason the others are: glued together in the
    # markup they would never be looked up, and the number is the only part that
    # reads right in English.
    "%s page(s)",
    "Remove %s",
    # Where the boxes on the page came from, and what was kept of them.
    "Using the boxes of %s.",
    "Template saved for %s.",
    # Putting what was read on the document itself, which is the free reading.
    "There is nothing read to put on the document.",
    "Writing what was read on the document.",
    "None of the boxes could be read as the field they were drawn for.",
    "%s field(s) written on the document.",
    # The keyboard help, one sentence.
    "Keys: 1-8 select a field, Ctrl+S saves the template, Ctrl+Enter makes the bill, Esc releases the field.",
    # The template dropdown: what it says when nothing can be applied, and when
    # the chosen template turns out to have nothing to draw.
    "Pick a template to apply it.",
    "That template has no boxes.",
)

# What the batch screen writes by itself. Same rule, and the same reason they
# are listed: a sentence the JavaScript builds is invisible to every other check
# in this file.
BATCH_STRINGS = (
    "%(count)s file(s), %(size)s",
    "%(read)s of %(total)s read, %(failed)s failed",
    "Batch of %s",
    "Remove %s",
    "Some of these files have already been read",
    "%s file(s) were left out: they had already been read.",
    "Reading them again costs the same and will not change anything.",
    "Send them anyway",
    "Leave them out",
    "The batch could not be sent.",
    "The service is reading them.",
    "The batch was cancelled.",
    "None of these files could be read.",
    "Some files could not be read. The rest are ready to review.",
    "All of them were read. Review them before they become bills.",
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
    "Bills",
    "Vendor bills",
    "What the documents became",
    "Sections",
    "Open",
    "Upload a document",
    "Pick a PDF or a photo and open it in the viewer",
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
    # What the dialog that asks before reading the same file twice is made of.
    # One sentence per piece, because the date and the bill are only there when
    # there is one, and a translator gets whole sentences either way.
    "This file has already been read: %(document)s.",
    "It was read on %s.",
    "It became %s.",
    # The reading summary, which Python puts together and a dialog shows: the
    # badges above, and the vendor details the document has no field for.
    "Confidence %s%%",
    "Read in %s s",
    "Tokens: %s",
    "Pages: %s",
    "Type",
    "Address",
    "City",
    "Postal code",
    "Country",
    "Phone",
    "Email",
    "Payment method",
    "Payment reference",
    "The service answered with the fields of the document and nothing else.",
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
    # What the capture flow answers when the receipt becomes an expense.
    "You have no employee record, so the receipt cannot be filed as an expense. "
    "Ask whoever administers your Odoo to create one for you, or file it as a "
    "supplier bill.",
    "Filed as an expense.",
    "It could not be filed as an expense.",
    # Why the service turned a document away. The service says it with a code
    # of its own, and the code is what the module turns into a sentence: a key
    # that was refused and a key that was never set arrive as the same HTTP 401,
    # so a sentence that guesses between them sends the reader to the wrong fix.
    "The extraction service needs an API key, and none is set in the EasyOCR settings.",
    "The extraction service rejected the API key. Check it in the EasyOCR "
    "settings: it may belong to another account, or have been switched off.",
    "That API key is switched off in the EasyOCR account.",
    "That API key has expired.",
    "The EasyOCR account is switched off. Contact support.",
    "This server's address is not allowed to use that API key.",
    "This server's domain is not allowed to use that API key.",
    "The EasyOCR account has no readings left. Top it up to keep reading documents.",
    "The EasyOCR account has no readings left.",
    "The monthly limit of the EasyOCR plan has been reached.",
    "This API key has reached its monthly limit.",
    "The EasyOCR plan does not include that feature.",
    "No extraction service is set in the EasyOCR settings.",
    # What the connection check on the settings screen answers.
    "The EasyOCR account cannot read documents right now.",
    "The service answered. Account: %(account)s, plan: %(plan)s.",
    "%(answer)s %(pages)s pages left to read this month.",
    "no name",
    "no plan",
    # What a batch says when it cannot be sent, and what it says when it is.
    # The plan's ceiling is named with the number the service gave, because
    # answering "too many" without saying how many sends the reader back to the
    # same refusal one file smaller at a time.
    "The EasyOCR plan reads %(ceiling)s files at a time at most, and this batch "
    "has %(count)s. Send them in smaller batches.",
    "The EasyOCR plan reads %(ceiling)s files at a time at most, and %(sent)s "
    "were sent. Send them in smaller batches.",
    "The EasyOCR plan does not read files in batches. It reads them one at a time.",
    "The EasyOCR plan does not say how many files it reads at a time.",
    "The EasyOCR plan does not allow a batch that large.",
    "The batch is on its way.",
    "The batch could not be sent.",
    "The batch had already finished, so it and its documents were dropped at "
    "the service.",
    "The batch was cancelled before this file was read.",
    "The extraction service could not read this file.",
    "The extraction service took the files but did not say which batch they are. "
    "Nothing here can follow them.",
    "The file of %(name)s is empty or cannot be read.",
    "The file arrived empty.",
    "The same file is twice in this batch.",
    "This file has already been read: %(document)s.",
    "This batch has already been sent.",
    "There is nothing to send.",
    "No document of this batch matches %(file)s.",
    "No batch matches %(batch)s.",
    "Document of batch %(batch)s updated.",
    "Batch %(batch)s is %(state)s.",
    "No API key is set in the EasyOCR settings.",
    "These files have already been read:\n\n%(files)s\n\nSending them again "
    "costs the same and changes nothing. Use the batch screen to send them anyway.",
    "Every file of this batch has already been read, so there is nothing left "
    "to send.",
)

# Strings that live only in a view's arch, so no model term carries them and
# nothing else in this file would notice them going untranslated. The button is
# the whole feature: a reader who cannot read it will not press it.
ARCH_STRINGS = (
    ("Test the connection", 'model_terms:ir.ui.view,arch_db:'
                            'easyocr.res_config_settings_view_form_easyocr'),
    # The batch screen's own words. Nothing but the view arch carries them, and
    # the button is the whole feature: a reader who cannot read it will not press
    # it. The list and the search view are here for the same reason.
    ("Send", 'model_terms:ir.ui.view,arch_db:easyocr.view_easyocr_batch_form'),
    ("Look again", 'model_terms:ir.ui.view,arch_db:easyocr.view_easyocr_batch_form'),
    ("How it is read", 'model_terms:ir.ui.view,arch_db:easyocr.view_easyocr_batch_form'),
    ("Batches", 'model_terms:ir.ui.view,arch_db:easyocr.view_easyocr_batch_list'),
    ("Being read", 'model_terms:ir.ui.view,arch_db:easyocr.view_easyocr_batch_search'),
    ("Partly read", 'model_terms:ir.ui.view,arch_db:easyocr.view_easyocr_batch_search'),
    # The dialog that asks before reading the same file twice. Both answers are
    # here: a reader who cannot read the second one has a dialog with one door.
    ("Read it again", 'model_terms:ir.ui.view,arch_db:'
                      'easyocr.view_easyocr_reprocess_wizard_form'),
    ("Leave it", 'model_terms:ir.ui.view,arch_db:'
                 'easyocr.view_easyocr_reprocess_wizard_form'),
    # The reading summary: the button that leads back to the document and the
    # two headings of its groups.
    ("Open the document", 'model_terms:ir.ui.view,arch_db:'
                          'easyocr.view_easyocr_reading_result_form'),
    ("Vendor", 'model_terms:ir.ui.view,arch_db:'
               'easyocr.view_easyocr_reading_result_form'),
)

# The models whose terms are ours to translate. The two settings models are here
# too, and only through their own fields: they carry a few hundred of Odoo's.
MODELS = (
    'easyocr.batch',
    'easyocr.document',
    'easyocr.document.line',
    'easyocr.inbox.item',
    'easyocr.reading.result',
    'easyocr.reprocess.wizard',
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

# Fields the mail mixin brings along, and the ones the analytic mixin brings.
# Their labels belong to those modules: a reference for them here would only
# copy someone else's strings, and counting them as missing would turn this test
# into noise nobody reads.
BORROWED = ('activity_', 'message_', 'analytic_', 'distribution_analytic')

# Except the borrowed ones this module does put on the screen. Odoo materialises
# a field's label on every model that shows it, so a label that lives in the
# mixin still has to be translated here, under this model's own reference, or the
# analytic widget reads "Analytic Distribution" on a Spanish screen with
# everything around it translated. Found in a browser, not here. The core does
# the same: sale/i18n/es.po translates it for sale.order.line.
SHOWN_BORROWED = {
    'Analytic Distribution':
        'model:ir.model.fields,field_description:'
        'easyocr.field_easyocr_document__analytic_distribution',
}

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

    def test_the_strings_the_batch_screen_writes_are_translated(self):
        for name in self._po_files():
            po = polib.pofile(os.path.join(self.i18n_path, name))
            for msgid in BATCH_STRINGS:
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

    def test_every_literal_in_a_template_reaches_the_browser(self):
        """A template's own words need a code reference, not a view one.

        The web client is handed the terms flagged as code and nothing else, so
        a sentence written straight into an OWL template is looked up in a map
        that holds only those. A term that exists in the .po with a view
        reference -- because a button on a form says the same thing -- is
        translated everywhere except there, and _t hands back the English word
        without a word of complaint. That is how the viewer's two buttons stayed
        in English on a Spanish screen while the field they were read from was
        translated.
        """
        terms = self._template_literals()
        self.assertGreater(len(terms), 4, "Barely any literal was found at all.")

        for name in self._po_files():
            po = polib.pofile(os.path.join(self.i18n_path, name))
            for msgid, where in sorted(terms.items()):
                entry = self._entry(po, msgid)
                self.assertTrue(
                    entry.msgstr,
                    "%s leaves %r without a translation (%s)"
                    % (os.path.basename(po.fpath), msgid, where),
                )
                self.assertIn(
                    JAVASCRIPT_TRANSLATION_COMMENT, entry.comment,
                    "%r is written into %s and the web client will never receive "
                    "its translation: %s does not flag it as a JavaScript term. "
                    "Add the .js reference of the component that paints it."
                    % (msgid, where, os.path.basename(po.fpath)),
                )
                self.assertTrue(
                    any(ref.startswith('code:addons/easyocr/') for ref, _line in entry.occurrences),
                    "%r needs a code reference under code:addons/easyocr/, the only "
                    "kind the client is given (%s)"
                    % (msgid, os.path.basename(po.fpath)),
                )

    def _template_literals(self):
        """Every word the module's own templates paint, and where it is written.

        ``tail`` is read as well, and it is the one that gets missed: a sentence
        written after a tag instead of before it is painted on the screen like
        any other, and nothing about it looks like a literal. "page(s)" and
        "Loading the document..." sat there, in English, on a Spanish screen.
        """
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        folder = os.path.join(root, 'static', 'src', 'xml')
        found = {}

        def want(text, where):
            text = (text or '').strip()
            if text and text not in NEVER_TRANSLATED and not NOT_A_SENTENCE.match(text):
                found.setdefault(text, where)

        for name in sorted(os.listdir(folder)):
            if not name.endswith('.xml'):
                continue
            where = 'static/src/xml/%s' % name
            tree = ElementTree.parse(os.path.join(folder, name))
            for node in tree.iter():
                want(node.text, '%s <%s>' % (where, node.tag))
                # Words that follow a tag, up to the next one.
                want(node.tail, '%s <%s> (after it)' % (where, node.tag))
                for attribute in TEMPLATE_ATTRIBUTES:
                    value = node.get(attribute)
                    # t-att-* and t-esc carry a binding, not a word.
                    if value and '{{' not in value and value.isprintable():
                        want(value, '%s <%s %s=>' % (where, node.tag, attribute))
        return found

    def test_the_strings_that_live_only_in_a_view_are_translated(self):
        """Nothing else carries these: they are text in the view and nowhere else."""
        for name in self._po_files():
            po = polib.pofile(os.path.join(self.i18n_path, name))
            for msgid, ref in ARCH_STRINGS:
                entry = self._entry(po, msgid)
                self.assertTrue(
                    entry.msgstr,
                    "%s leaves %r in English" % (os.path.basename(po.fpath), msgid),
                )
                self.assertIn(
                    ref, {reference for reference, _line in entry.occurrences},
                    "%r is translated in %s but points nowhere Odoo will look for "
                    "it: it needs the reference %s"
                    % (msgid, os.path.basename(po.fpath), ref),
                )

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

    def test_the_borrowed_labels_we_show_are_translated(self):
        """The other half of BORROWED: what we show, we translate."""
        for name in self._po_files():
            po = polib.pofile(os.path.join(self.i18n_path, name))
            for msgid, ref in SHOWN_BORROWED.items():
                entry = self._entry(po, msgid)
                self.assertTrue(
                    entry.msgstr,
                    "%s leaves %r in English, and that label is on the document's "
                    "form" % (os.path.basename(po.fpath), msgid),
                )
                self.assertIn(
                    ref, {reference for reference, _line in entry.occurrences},
                    "%r is translated in %s but points nowhere Odoo will look for "
                    "it: it needs the reference %s"
                    % (msgid, os.path.basename(po.fpath), ref),
                )
