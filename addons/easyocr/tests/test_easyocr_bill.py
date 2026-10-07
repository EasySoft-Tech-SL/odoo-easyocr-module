# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License OPL-1 (see LICENSE file).

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestEasyocrBill(TransactionCase):
    """From a processed document to a supplier bill."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Document = cls.env['easyocr.document']
        cls.partner = cls.env['res.partner'].create({
            'name': 'Proveedor de prueba SL',
            'vat': 'B3186006',
        })

    def _document(self, **values):
        values.setdefault('name', 'FAC-2026-0001')
        return self.Document.create(values)

    def test_the_vendor_is_found_by_tax_number(self):
        document = self._document(partner_vat='B3186006')

        document._resolve_partner()

        self.assertEqual(document.partner_id, self.partner)

    def test_the_tax_number_is_matched_however_it_is_written(self):
        """People type dashes and dots; the tax number is the same one."""
        document = self._document(partner_vat='b-31.860.06')

        document._resolve_partner()

        self.assertEqual(document.partner_id, self.partner)

    def test_creating_a_bill_brings_the_reading_across(self):
        document = self._document(
            partner_id=self.partner.id,
            ref='A/123',
            document_date='2026-01-31',
            amount_untaxed=100.0,
            amount_total=121.0,
        )

        document.action_create_bill()

        move = document.move_id
        self.assertEqual(move.move_type, 'in_invoice')
        self.assertEqual(move.partner_id, self.partner)
        self.assertEqual(move.ref, 'A/123')
        self.assertEqual(str(move.invoice_date), '2026-01-31')
        self.assertEqual(move.state, 'draft')
        self.assertAlmostEqual(move.amount_untaxed, 100.0, places=2)
        self.assertEqual(document.state, 'processed')

    def test_a_document_cannot_be_billed_twice(self):
        document = self._document(partner_id=self.partner.id, amount_untaxed=50.0)
        document.action_create_bill()

        with self.assertRaises(UserError):
            document.action_create_bill()

    def test_a_bill_needs_a_vendor(self):
        document = self._document(amount_untaxed=50.0)

        with self.assertRaises(UserError):
            document.action_create_bill()

    def test_your_own_tax_number_is_not_a_vendor(self):
        """Booking your own company as a supplier is always a mistake."""
        # The tax number is not a real one, so the format check is skipped.
        self.env.company.partner_id.with_context(no_vat_validation=True).vat = 'B12345678'
        document = self._document(partner_vat='B12345678')

        with self.assertRaises(UserError):
            document._resolve_partner()
