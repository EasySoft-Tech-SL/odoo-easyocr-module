# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

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
        # Set here and not assumed: this switch lives on the company, so a test
        # that trusts the shipped default is really testing the database it runs
        # against, and goes red the moment somebody turns it on.
        self.env.company.easyocr_bill_post = False
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

    # ------------------------------------------------------------------
    # The tax of a document that was only read as a total
    #
    # A reading that comes back with the two amounts and no lines still has to
    # become a bill whose total matches the paper. The rate is worked back from
    # the amounts, and used only when the company has that exact tax.
    # ------------------------------------------------------------------
    # A rate no standard chart carries, so a tax found can only be this one.
    RATE_ONLY_THIS_TEST_HAS = 7.7

    def _tax(self, rate, usage='purchase'):
        return self.env['account.tax'].create({
            'name': 'IVA %s%% %s' % (rate, usage),
            'amount': rate,
            'amount_type': 'percent',
            'type_tax_use': usage,
            'company_id': self.env.company.id,
        })

    def _billed_lines(self, **values):
        # Set here and not assumed, like the bill-posted switch above: what is
        # being tested is the line, and a bill that gets posted on the way adds
        # a second reason for the test to fail.
        self.env.company.easyocr_bill_post = False
        values.setdefault('partner_id', self.partner.id)
        document = self._document(**values)
        document.action_create_bill()
        return document.move_id.invoice_line_ids

    def test_the_two_amounts_bring_the_tax_to_the_bill(self):
        tax = self._tax(self.RATE_ONLY_THIS_TEST_HAS)

        lines = self._billed_lines(amount_untaxed=100.0, amount_total=107.70)

        self.assertEqual(len(lines), 1)
        self.assertEqual(lines.tax_ids, tax)
        self.assertAlmostEqual(lines.price_unit, 100.0, places=2)

    def test_the_bill_adds_up_to_the_paper_it_came_from(self):
        self._tax(self.RATE_ONLY_THIS_TEST_HAS)

        lines = self._billed_lines(amount_untaxed=100.0, amount_total=107.70)

        self.assertAlmostEqual(lines.move_id.amount_total, 107.70, places=2)

    def test_the_cent_the_paper_rounds_off_is_not_a_reason_to_give_up(self):
        """33,33 with 7,7% prints 35,90, which works back to 7,71%."""
        tax = self._tax(self.RATE_ONLY_THIS_TEST_HAS)

        lines = self._billed_lines(amount_untaxed=33.33, amount_total=35.90)

        self.assertEqual(lines.tax_ids, tax)

    def test_a_rate_nobody_has_leaves_the_line_untaxed(self):
        """A rate with no tax behind it is a rate nobody agreed on."""
        lines = self._billed_lines(amount_untaxed=100.0, amount_total=133.33)

        self.assertFalse(lines.tax_ids)

    def test_a_sales_tax_is_not_taken_for_a_purchase_tax(self):
        self._tax(self.RATE_ONLY_THIS_TEST_HAS, usage='sale')

        lines = self._billed_lines(amount_untaxed=100.0, amount_total=107.70)

        self.assertFalse(lines.tax_ids)

    def test_a_total_below_the_amount_before_tax_is_not_a_tax(self):
        """A discount, or the shape a credit note has. Neither is 21% of anything."""
        self._tax(self.RATE_ONLY_THIS_TEST_HAS)

        lines = self._billed_lines(amount_untaxed=100.0, amount_total=90.0)

        self.assertFalse(lines.tax_ids)

    def test_a_document_with_no_amounts_is_still_billed(self):
        lines = self._billed_lines()

        self.assertEqual(len(lines), 1)
        self.assertFalse(lines.tax_ids)
        self.assertAlmostEqual(lines.price_unit, 0.0, places=2)

    def test_a_total_with_no_amount_before_it_is_not_a_rate(self):
        """The amount before tax is what the rate is a percentage of."""
        self._tax(self.RATE_ONLY_THIS_TEST_HAS)

        lines = self._billed_lines(amount_total=107.70)

        self.assertFalse(lines.tax_ids)
        self.assertAlmostEqual(lines.price_unit, 107.70, places=2)

    # ------------------------------------------------------------------
    # A rectificativa, which is a bill the other way round
    # ------------------------------------------------------------------
    def test_a_credit_note_becomes_a_credit_note(self):
        document = self._document(
            partner_id=self.partner.id,
            is_refund=True,
            amount_untaxed=-100.0,
            amount_total=-121.0,
        )

        document.action_create_bill()

        self.assertEqual(document.move_id.move_type, 'in_refund')

    def test_a_bill_is_still_a_bill(self):
        document = self._document(
            partner_id=self.partner.id, amount_untaxed=100.0, amount_total=121.0,
        )

        document.action_create_bill()

        self.assertEqual(document.move_id.move_type, 'in_invoice')

    def test_the_credit_note_is_worth_what_the_paper_says(self):
        """What says which way the money goes is the entry, not the total.

        Measured on Odoo 19 and not assumed: a refund of 100 with 7,7% answers
        with a positive 107,70 from `amount_total`, the same as a bill, and puts
        the sign on the accounting entries instead. A credit note whose product
        line came out in debit is a bill with a refund printed on it.
        """
        self._tax(self.RATE_ONLY_THIS_TEST_HAS)
        document = self._document(
            partner_id=self.partner.id,
            is_refund=True,
            amount_untaxed=-100.0,
            amount_total=-107.70,
        )

        document.action_create_bill()

        move = document.move_id
        self.assertAlmostEqual(move.amount_untaxed, 100.0, places=2)
        self.assertAlmostEqual(move.amount_total, 107.70, places=2)
        self.assertLess(move.invoice_line_ids.balance, 0)

    def test_the_credit_note_carries_the_tax_of_the_paper(self):
        tax = self._tax(self.RATE_ONLY_THIS_TEST_HAS)
        document = self._document(
            partner_id=self.partner.id,
            is_refund=True,
            amount_untaxed=-100.0,
            amount_total=-107.70,
        )

        document.action_create_bill()

        self.assertEqual(document.move_id.invoice_line_ids.tax_ids, tax)

    # ------------------------------------------------------------------
    # What the document belongs to
    # ------------------------------------------------------------------
    def _analytic_account(self, name='Obra del cliente'):
        """The analytic account a project brings with it.

        Nothing here depends on the Projects app: a project has one of these of
        its own, and that is what both Odoo and the reader end up picking.
        """
        plan = self.env['account.analytic.plan'].search([], limit=1)
        if not plan:
            plan = self.env['account.analytic.plan'].create({'name': 'Proyectos'})
        return self.env['account.analytic.account'].create({
            'name': name,
            'plan_id': plan.id,
        })

    def test_the_bill_takes_the_project_of_the_document(self):
        account = self._analytic_account()
        self.env.company.easyocr_bill_post = False
        document = self._document(
            partner_id=self.partner.id,
            amount_untaxed=100.0,
            amount_total=121.0,
            analytic_distribution={str(account.id): 100},
        )

        document.action_create_bill()

        self.assertEqual(
            document.move_id.invoice_line_ids.analytic_distribution,
            {str(account.id): 100},
        )

    def test_a_bill_with_no_project_gets_none(self):
        self.env.company.easyocr_bill_post = False
        document = self._document(
            partner_id=self.partner.id, amount_untaxed=100.0, amount_total=121.0,
        )

        document.action_create_bill()

        self.assertFalse(document.move_id.invoice_line_ids.analytic_distribution)

    def test_a_negative_price_does_not_turn_a_credit_note_into_a_bill(self):
        """Odoo turns a refund's lines round: carrying the sign as well undoes it."""
        document = self._document(
            partner_id=self.partner.id,
            name='ABONO-1',
            is_refund=True,
            amount_untaxed=-100.0,
            amount_total=-121.0,
        )
        document.line_ids = [(0, 0, {
            'name': 'Devolucion de material',
            'quantity': 1,
            'unit_price': -100.0,
            'tax_rate': 21.0,
        })]

        document.action_create_bill()

        line = document.move_id.invoice_line_ids
        self.assertEqual(len(line), 1)
        self.assertAlmostEqual(line.price_unit, 100.0, places=2)
        self.assertLess(line.balance, 0)
