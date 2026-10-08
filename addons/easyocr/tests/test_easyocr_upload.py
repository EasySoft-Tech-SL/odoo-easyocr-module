# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

"""Filing the file the screen was handed.

The screen that waits for a PDF is the start of the module's own flow: one file
in, the viewer open on it. What is checked here is the step between the two --
turning what the browser sends into a document with its attachment, under the
rules the module already has.
"""

import base64

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

FILE_BYTES = b'%PDF-1.4 a supplier invoice'
PDF = base64.b64encode(FILE_BYTES)


@tagged('post_install', '-at_install')
class TestEasyocrUpload(TransactionCase):
    """One file in, a document with its file out."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Document = cls.env['easyocr.document']

    def test_the_file_is_filed_with_its_name_as_the_reference(self):
        document = self.Document.browse(
            self.Document.action_file_upload('factura.pdf', PDF)
        )

        self.assertEqual(document.name, 'factura.pdf')
        self.assertEqual(document.attachment_id.name, 'factura.pdf')
        self.assertEqual(document.attachment_id.raw, FILE_BYTES)
        self.assertEqual(document.attachment_id.res_model, 'easyocr.document')
        self.assertEqual(document.attachment_id.res_id, document.id)

    def test_the_reference_given_wins_over_the_file_name(self):
        document = self.Document.browse(
            self.Document.action_file_upload('factura.pdf', PDF, name='FAC-2026-0100')
        )

        self.assertEqual(document.name, 'FAC-2026-0100')

    def test_nothing_is_read_just_because_a_file_was_chosen(self):
        """Opening a document is not asking for it to be sent anywhere."""
        document = self.Document.browse(
            self.Document.action_file_upload('factura.pdf', PDF)
        )

        self.assertFalse(document.last_extraction)
        self.assertEqual(document.state, 'draft')

    def test_a_photo_is_taken_as_well_as_a_pdf(self):
        document = self.Document.browse(
            self.Document.action_file_upload('ticket.jpg', PDF)
        )

        self.assertTrue(document.attachment_id)

    def test_a_kind_of_file_that_cannot_be_read_is_turned_away(self):
        with self.assertRaises(UserError):
            self.Document.action_file_upload('hoja-de-calculo.xlsx', PDF)

        self.assertFalse(self.Document.search([('name', '=', 'hoja-de-calculo.xlsx')]))

    def test_without_content_nothing_is_filed(self):
        with self.assertRaises(UserError):
            self.Document.action_file_upload('factura.pdf', False)

        self.assertFalse(self.Document.search([('name', '=', 'factura.pdf')]))

    def test_the_action_the_home_screen_opens_waits_for_a_file(self):
        """It is the viewer's own action, opened with nothing in it.

        The card on the home screen has to land on the screen that waits for a
        file, not on a dialog that files one and sends the reader elsewhere.
        """
        action = self.env.ref('easyocr.action_easyocr_new_document')

        self.assertEqual(action.type, 'ir.actions.client')
        self.assertEqual(action.tag, 'easyocr.document_viewer')
