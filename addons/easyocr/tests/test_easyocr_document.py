# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License OPL-1 (see LICENSE file).

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestEasyocrDocument(TransactionCase):
    """Smoke tests for the document model and its status flow."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Document = cls.env['easyocr.document']

    def test_default_status_is_pending(self):
        document = self.Document.create({'name': 'INV/2026/0001'})
        self.assertEqual(document.state, 'draft')

    def test_status_flow(self):
        document = self.Document.create({'name': 'INV/2026/0002'})

        document.action_mark_processed()
        self.assertEqual(document.state, 'processed')

        document.action_reset_to_draft()
        self.assertEqual(document.state, 'draft')

    def test_reset_clears_the_error_message(self):
        document = self.Document.create({
            'name': 'INV/2026/0003',
            'state': 'error',
            'error_message': 'Unreadable scan',
        })

        document.action_reset_to_draft()

        self.assertFalse(document.error_message)

    def test_display_name_includes_the_vendor(self):
        partner = self.env['res.partner'].create({'name': 'Proveedor de prueba'})
        document = self.Document.create({
            'name': 'INV/2026/0004',
            'partner_id': partner.id,
        })

        self.assertIn('Proveedor de prueba', document.display_name)
