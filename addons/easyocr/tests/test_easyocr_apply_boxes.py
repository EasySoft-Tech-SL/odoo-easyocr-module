# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

"""Putting what the boxes read onto the document, for free.

Drawing boxes over a page and reading the text under them costs nothing and
needs no account: the text is in the file. What was missing was somewhere to put
it. Everything else in the module reads the document, so a reading that stays in
the viewer's column is a reading nobody else can use.

What comes out of a rectangle is not a number and not a date: it is what the
paper printed. These tests are mostly about that difference.
"""

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.easyocr.models.easyocr_values import to_amount, to_date


@tagged('post_install', '-at_install')
class TestEasyocrValues(TransactionCase):
    """Reading an amount and a date the way they are printed."""

    def test_an_amount_with_its_currency(self):
        self.assertAlmostEqual(to_amount('320,77 EUR'), 320.77, places=2)

    def test_a_thousand_written_the_spanish_way(self):
        self.assertAlmostEqual(to_amount('1.234,56 €'), 1234.56, places=2)

    def test_a_thousand_written_the_other_way(self):
        self.assertAlmostEqual(to_amount('1,234.56'), 1234.56, places=2)

    def test_a_lone_dot_with_three_digits_is_a_thousand(self):
        """On a paper from here, 1.234 is one thousand two hundred and thirty four."""
        self.assertAlmostEqual(to_amount('1.234'), 1234.0, places=2)

    def test_a_lone_dot_with_two_digits_is_a_decimal(self):
        self.assertAlmostEqual(to_amount('320.77'), 320.77, places=2)

    def test_a_negative_amount_keeps_its_sign(self):
        """What a rectificativa prints."""
        self.assertAlmostEqual(to_amount('-107,70'), -107.70, places=2)

    def test_a_number_is_a_number(self):
        self.assertAlmostEqual(to_amount(320.77), 320.77, places=2)

    def test_words_are_not_an_amount(self):
        """A box over the wrong words has to leave the field alone."""
        self.assertIsNone(to_amount('Factura núm.'))
        self.assertIsNone(to_amount(''))
        self.assertIsNone(to_amount(None))

    def test_a_date_the_way_a_supplier_prints_it(self):
        self.assertEqual(str(to_date('30/09/2026')), '2026-09-30')

    def test_a_date_with_dashes_and_with_dots(self):
        self.assertEqual(str(to_date('30-09-2026')), '2026-09-30')
        self.assertEqual(str(to_date('30.09.2026')), '2026-09-30')

    def test_a_date_already_in_order(self):
        self.assertEqual(str(to_date('2026-09-30')), '2026-09-30')

    def test_words_are_not_a_date(self):
        self.assertIsNone(to_date('Vencimiento'))
        self.assertIsNone(to_date(''))
        self.assertIsNone(to_date(None))


@tagged('post_install', '-at_install')
class TestEasyocrApplyBoxes(TransactionCase):
    """Writing what was read onto the document."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Document = cls.env['easyocr.document']

    def _document(self, **values):
        values.setdefault('name', 'factura.pdf')
        return self.Document.create(values)

    def test_what_the_boxes_read_lands_on_the_document(self):
        document = self._document()

        written = document.action_apply_reading({
            'document_number': '2026/0451',
            'document_date': '30/09/2026',
            'amount_untaxed': '265,10 EUR',
            'amount_total': '320,77 EUR',
            'partner_vat': 'B12345674',
            'partner_name': 'FERRETERÍA INDUSTRIAL DEL NORTE, S.L.',
        })

        self.assertEqual(document.ref, '2026/0451')
        self.assertEqual(str(document.document_date), '2026-09-30')
        self.assertAlmostEqual(document.amount_untaxed, 265.10, places=2)
        self.assertAlmostEqual(document.amount_total, 320.77, places=2)
        self.assertEqual(document.partner_vat, 'B12345674')
        self.assertEqual(document.partner_name, 'FERRETERÍA INDUSTRIAL DEL NORTE, S.L.')
        self.assertEqual(sorted(written), sorted([
            'ref', 'document_date', 'amount_untaxed', 'amount_total',
            'partner_vat', 'partner_name',
        ]))

    def test_a_box_that_read_nothing_leaves_its_field_alone(self):
        """Emptying a field somebody typed by hand is worse than not filling it."""
        document = self._document(amount_total=99.0)

        written = document.action_apply_reading({'amount_total': ''})

        self.assertAlmostEqual(document.amount_total, 99.0, places=2)
        self.assertFalse(written)

    def test_a_box_over_the_wrong_words_does_not_stop_the_others(self):
        document = self._document(amount_total=99.0)

        written = document.action_apply_reading({
            'amount_total': 'Total factura',
            'document_number': '2026/0451',
        })

        self.assertAlmostEqual(document.amount_total, 99.0, places=2)
        self.assertEqual(document.ref, '2026/0451')
        self.assertEqual(list(written), ['ref'])

    def test_a_field_the_document_does_not_have_is_ignored(self):
        """The viewer draws boxes for a tax and a description there is no field for."""
        document = self._document()

        written = document.action_apply_reading({
            'tax_amount': '55,67',
            'description': 'Tornillería',
            'partner_name': 'Proveedor SL',
        })

        self.assertEqual(list(written), ['partner_name'])

    def test_the_due_date_the_box_read_goes_on_the_bill(self):
        """A date read and kept nowhere is a date nobody can use."""
        document = self._document(
            partner_id=self.env['res.partner'].create({
                'name': 'Proveedor del vencimiento', 'vat': 'B3186006',
            }).id,
            amount_untaxed=100.0,
            amount_total=121.0,
        )

        document.action_apply_reading({'due_date': '30/10/2026'})
        document.action_create_bill()

        self.assertEqual(str(document.move_id.invoice_date_due), '2026-10-30')

    def test_without_a_due_date_the_bill_is_left_to_its_payment_terms(self):
        document = self._document(
            partner_id=self.env['res.partner'].create({
                'name': 'Proveedor sin vencimiento', 'vat': 'B3186006',
            }).id,
            amount_untaxed=100.0,
            amount_total=121.0,
        )

        document.action_create_bill()

        self.assertNotEqual(str(document.move_id.invoice_date_due), '2026-10-30')

    def test_reading_the_boxes_twice_changes_nothing_the_second_time(self):
        """The button is meant to be pressed without thinking about it."""
        document = self._document()
        first = document.action_apply_reading({
            'document_number': '2026/0451', 'amount_total': '320,77 EUR',
        })

        second = document.action_apply_reading({
            'document_number': '2026/0451', 'amount_total': '320,77 EUR',
        })

        self.assertEqual(first, second)
        self.assertEqual(document.ref, '2026/0451')
