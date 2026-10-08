# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3.0 or later (see LICENSE file).

"""Where a photographed receipt ends up.

The Dolibarr module offers three destinations. Two of them exist in Odoo and
are here; the third, the miscellaneous payment, has no counterpart and is not
ported at all. Each of the two is checked by the object it leaves behind.
"""

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestEasyocrExpenseTarget(TransactionCase):
    """A receipt becomes a bill or an employee expense, and nothing else."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Document = cls.env['easyocr.document']
        cls.company = cls.env.company
        cls.user = cls.env.user
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Empleado de pruebas',
            'user_id': cls.user.id,
            'company_id': cls.company.id,
        })
        cls.partner = cls.env['res.partner'].create({
            'name': 'Proveedor de gastos SL',
            'vat': 'B3186006',
        })

    def setUp(self):
        super().setUp()
        self.company.write({
            'easyocr_expense_target': 'bill',
            'easyocr_expense_allow_validate': False,
        })

    def _document(self, **values):
        values.setdefault('name', 'TICKET/2026/0001')
        values.setdefault('state', 'processed')
        values.setdefault('partner_name', 'Gasolinera de pruebas')
        values.setdefault('amount_total', 45.5)
        return self.Document.create(values)

    # ------------------------------------------------------------------
    # The employee's expense
    # ------------------------------------------------------------------
    def test_a_receipt_becomes_an_expense_for_the_employee_who_sent_it(self):
        document = self._document()

        expense = document._become_expense()

        self.assertEqual(expense.employee_id, self.employee)
        self.assertEqual(expense.total_amount, 45.5)
        self.assertEqual(expense.name, 'Gasolinera de pruebas')
        self.assertEqual(expense.state, 'draft')

    def test_the_photo_travels_with_the_expense(self):
        """Whoever approves it has to be able to see the paper."""
        import base64
        attachment = self.env['ir.attachment'].create({
            'name': 'ticket.pdf',
            'datas': base64.b64encode(b'%PDF-1.4 ticket'),
            'mimetype': 'application/pdf',
        })
        document = self._document(attachment_id=attachment.id)

        expense = document._become_expense()

        self.assertIn('ticket.pdf', expense.attachment_ids.mapped('name'))

    def test_the_expense_is_put_forward_when_the_phone_is_allowed_to(self):
        self.company.easyocr_expense_allow_validate = True
        document = self._document()

        expense = document._become_expense()

        self.assertNotEqual(expense.state, 'draft')

    def test_the_expense_waits_in_draft_when_the_phone_is_not_allowed_to(self):
        document = self._document()

        expense = document._become_expense()

        self.assertEqual(expense.state, 'draft')

    def test_an_expense_needs_an_employee_and_says_so(self):
        """Plenty of people use Odoo without an employee record."""
        other = self.env['res.users'].create({
            'name': 'Sin ficha de empleado',
            'login': 'sin_empleado_easyocr',
            'email': 'sin_empleado@example.test',
        })
        document = self._document()

        with self.assertRaises(UserError):
            document._become_expense(user=other)

    def test_the_category_prefers_the_generic_one_odoo_uses(self):
        # Cleared first: Odoo's own demo data already carries a category with
        # that code, and leaving it in would let this pass without the rule
        # being looked at.
        self.env['product.product'].search([('can_be_expensed', '=', True)]).write({
            'can_be_expensed': False,
        })
        generic = self.env['product.product'].create({
            'name': 'Gastos generales',
            'default_code': 'EXP_GEN',
            'can_be_expensed': True,
        })
        self.env['product.product'].create({
            'name': 'Otra categoria',
            'can_be_expensed': True,
        })

        product = self.Document._expense_product()

        self.assertEqual(product, generic)

    def test_a_company_with_no_expense_category_still_gets_the_expense(self):
        """Odoo allows an expense with no category, and the approver fills it."""
        self.env['product.product'].search([('can_be_expensed', '=', True)]).write({
            'can_be_expensed': False,
        })

        expense = self._document()._become_expense()

        self.assertTrue(expense)
        self.assertFalse(expense.product_id)

    # ------------------------------------------------------------------
    # Still a bill by default
    # ------------------------------------------------------------------
    def test_a_receipt_is_not_an_expense_unless_the_company_says_so(self):
        document = self._document(partner_id=self.partner.id)

        document.action_create_bill()

        self.assertTrue(document.move_id)
        self.assertFalse(self.env['hr.expense'].search([('name', '=', document.name)]))
