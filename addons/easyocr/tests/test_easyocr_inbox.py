# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

import base64
import hashlib

from psycopg2 import IntegrityError

from odoo.addons.easyocr.models.easyocr_inbox import MAX_SIZE_MB
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

# The smallest thing that is still a PDF: a header and the end marker. The tray
# only looks at the first four bytes, so a real file would be noise here.
PDF_BYTES = b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n'


@tagged('post_install', '-at_install')
class TestEasyocrInbox(TransactionCase):
    """The tray other modules drop their files into."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Inbox = cls.env['easyocr.inbox.item']

    def _receive(self, content=PDF_BYTES, filename='scan.pdf', origin='easyscan'):
        return self.Inbox.recibir(content, filename, origin)

    def _item(self, **kwargs):
        """Receive a file and return the record it became."""
        result = self._receive(**kwargs)
        self.assertTrue(result['ok'], result['error'])
        return self.Inbox.browse(result['id'])

    # ------------------------------------------------------------------
    # Getting a file in
    # ------------------------------------------------------------------
    def test_a_pdf_lands_in_the_tray_pending(self):
        result = self._receive()

        self.assertTrue(result['ok'], result['error'])
        item = self.Inbox.browse(result['id'])
        self.assertEqual(item.state, 'pending')
        self.assertEqual(item.name, 'scan.pdf')
        self.assertEqual(item.origin, 'easyscan')
        self.assertFalse(item.document_id)
        self.assertEqual(item.file_size, len(PDF_BYTES))
        self.assertEqual(item.file_hash, hashlib.sha256(PDF_BYTES).hexdigest())
        # The file has to come back out of the tray byte for byte.
        self.assertEqual(base64.b64decode(item.datas), PDF_BYTES)

    def test_the_same_file_is_not_taken_twice(self):
        """The same bytes under a different name are still the same file."""
        first = self._receive()
        second = self._receive(filename='rescan-of-the-same.pdf')

        self.assertFalse(second['ok'])
        self.assertEqual(second['id'], first['id'])
        self.assertTrue(second['error'])
        self.assertEqual(self.Inbox.search_count([]), 1)

    def test_a_file_that_is_not_a_pdf_is_turned_away(self):
        result = self._receive(content=b'PK\x03\x04 a zip wearing a .pdf name')

        self.assertFalse(result['ok'])
        self.assertEqual(result['id'], 0)
        self.assertIn('PDF', result['error'])
        self.assertEqual(self.Inbox.search_count([]), 0)

    def test_an_empty_file_is_turned_away(self):
        result = self._receive(content=b'')

        self.assertFalse(result['ok'])
        self.assertTrue(result['error'])
        self.assertEqual(self.Inbox.search_count([]), 0)

    def test_a_file_without_a_name_is_turned_away(self):
        result = self._receive(filename='   ')

        self.assertFalse(result['ok'])
        self.assertTrue(result['error'])
        self.assertEqual(self.Inbox.search_count([]), 0)

    def test_a_file_over_the_limit_is_turned_away(self):
        too_big = PDF_BYTES + b'0' * (MAX_SIZE_MB * 1024 * 1024)

        result = self._receive(content=too_big)

        self.assertFalse(result['ok'])
        self.assertIn(str(MAX_SIZE_MB), result['error'])
        self.assertEqual(self.Inbox.search_count([]), 0)

    def test_a_file_kept_as_base64_is_read_the_same_way(self):
        """A caller reading a binary field hands over base64, not raw bytes."""
        result = self._receive(content=base64.b64encode(PDF_BYTES))

        self.assertTrue(result['ok'], result['error'])
        self.assertEqual(self.Inbox.browse(result['id']).file_size, len(PDF_BYTES))

    def test_the_same_file_is_welcome_in_another_company(self):
        """Two companies can hold the same scan; one tray cannot hold it twice."""
        self._receive()
        other = self.env['res.company'].create({'name': 'Second company'})

        result = self.Inbox.with_company(other).recibir(PDF_BYTES, 'scan.pdf', 'easyscan')

        self.assertTrue(result['ok'], result['error'])
        self.assertEqual(self.Inbox.browse(result['id']).company_id, other)

    # ------------------------------------------------------------------
    # A file put in the tray by hand
    # ------------------------------------------------------------------
    def test_a_file_uploaded_by_hand_gets_its_fingerprint(self):
        item = self.Inbox.create({
            'name': 'scan.pdf',
            'datas': base64.b64encode(PDF_BYTES),
        })

        self.assertEqual(item.file_hash, hashlib.sha256(PDF_BYTES).hexdigest())
        self.assertEqual(item.file_size, len(PDF_BYTES))

    def test_replacing_the_file_refreshes_the_fingerprint(self):
        """Otherwise the tray would keep a fingerprint of a file it no longer holds."""
        item = self.Inbox.create({
            'name': 'scan.pdf',
            'datas': base64.b64encode(PDF_BYTES),
        })
        other = b'%PDF-1.4\n% another invoice\n%%EOF\n'

        item.write({'datas': base64.b64encode(other)})

        self.assertEqual(item.file_hash, hashlib.sha256(other).hexdigest())
        self.assertEqual(item.file_size, len(other))

    def test_the_database_refuses_a_second_copy_of_the_same_file(self):
        """The check in ``recibir`` is not enough on its own: two modules can
        hand the same scan over at the same moment."""
        self.Inbox.create({
            'name': 'scan.pdf',
            'datas': base64.b64encode(PDF_BYTES),
        })

        with self.assertRaises(IntegrityError):
            self.Inbox.create({
                'name': 'scan.pdf',
                'datas': base64.b64encode(PDF_BYTES),
            })

    # ------------------------------------------------------------------
    # What a person does with the tray
    # ------------------------------------------------------------------
    def test_processing_an_item_creates_the_document(self):
        item = self._item()

        action = item.action_process()

        self.assertEqual(item.state, 'processed')
        self.assertTrue(item.document_id)
        self.assertEqual(item.document_id.name, item.name)
        self.assertEqual(item.document_id.company_id, item.company_id)
        self.assertEqual(
            base64.b64decode(item.document_id.attachment_id.datas), PDF_BYTES,
        )
        # And the viewer opens on the document that was just built.
        self.assertEqual(action['tag'], 'easyocr.document_viewer')
        self.assertEqual(action['params']['document_id'], item.document_id.id)

    def test_processing_twice_keeps_one_document(self):
        item = self._item()
        # Counted against what was already there: a database with documents in
        # it is the normal case, and a test that assumes an empty one only
        # passes on a machine nobody has used.
        before = self.env['easyocr.document'].search_count([])

        item.action_process()
        item.action_process()

        self.assertEqual(self.env['easyocr.document'].search_count([]), before + 1)

    def test_a_discarded_item_is_not_processed(self):
        item = self._item()
        item.action_discard()

        with self.assertRaises(UserError):
            item.action_process()

    def test_discarding_changes_the_state(self):
        item = self._item()

        item.action_discard()
        self.assertEqual(item.state, 'discarded')

        item.action_restore()
        self.assertEqual(item.state, 'pending')
