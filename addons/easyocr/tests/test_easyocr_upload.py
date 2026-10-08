# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

"""Uploading a file and landing in the viewer.

What is checked here is the whole point of the screen: one file in, the tool
with the document open. Anything that leaves the reader on a record with an
attachment to find is the three-step path this exists to replace.
"""

import base64

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

PDF = base64.b64encode(b'%PDF-1.4 a supplier invoice')


@tagged('post_install', '-at_install')
class TestEasyocrUpload(TransactionCase):
    """One file in, the viewer out."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Wizard = cls.env['easyocr.upload.wizard']

    def _wizard(self, **values):
        values.setdefault('file', PDF)
        values.setdefault('filename', 'factura.pdf')
        return self.Wizard.create(values)

    def test_the_file_is_filed_and_the_viewer_opens_on_it(self):
        wizard = self._wizard(name='FAC-2026-0100')

        action = wizard.action_read()

        self.assertEqual(action['tag'], 'easyocr.document_viewer')
        self.assertEqual(action['target'], 'fullscreen')
        document = self.env['easyocr.document'].browse(action['params']['document_id'])
        self.assertEqual(document.name, 'FAC-2026-0100')
        self.assertTrue(document.attachment_id)
        # Nothing was read: opening a file is not asking for it to be sent
        # anywhere, and the viewer has its own button for that.
        self.assertEqual(document.last_extraction, False)

    def test_the_attachment_keeps_the_name_of_the_chosen_file(self):
        action = self._wizard().action_read()

        document = self.env['easyocr.document'].browse(action['params']['document_id'])

        self.assertEqual(document.attachment_id.name, 'factura.pdf')

    def test_the_file_name_is_used_when_no_reference_is_typed(self):
        action = self._wizard(filename='ticket-gasolinera.pdf').action_read()

        document = self.env['easyocr.document'].browse(action['params']['document_id'])

        self.assertEqual(document.name, 'ticket-gasolinera.pdf')

    def test_the_reference_is_filled_in_from_the_file_as_it_is_chosen(self):
        """So nobody has to type the same thing twice."""
        wizard = self._wizard(name=False)

        wizard._onchange_file()

        self.assertEqual(wizard.name, 'factura.pdf')

    def test_a_kind_of_file_that_cannot_be_read_is_turned_away(self):
        wizard = self._wizard(filename='hoja-de-calculo.xlsx')

        with self.assertRaises(UserError):
            wizard.action_read()

    def test_without_a_file_nothing_is_filed(self):
        wizard = self._wizard(file=False)

        with self.assertRaises(UserError):
            wizard.action_read()

        self.assertFalse(self.env['easyocr.document'].search([('name', '=', 'factura.pdf')]))

    def test_a_photo_is_taken_as_well_as_a_pdf(self):
        action = self._wizard(filename='ticket.jpg').action_read()

        document = self.env['easyocr.document'].browse(action['params']['document_id'])

        self.assertTrue(document.attachment_id)
