# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

import json

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestEasyocrResultDialog(TransactionCase):
    """The reading result dialog: what it draws and what it hands back."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Document = cls.env['easyocr.document']
        cls.tax21 = cls.env['account.tax'].create({
            'name': 'IVA 21% compras (prueba)',
            'type_tax_use': 'purchase',
            'amount_type': 'percent',
            'amount': 21.0,
            'company_id': cls.env.company.id,
        })
        cls.answer = {
            'confidence': 0.9,
            'structured_data': {
                'document': {'document_number': 'F-77', 'issue_date': '2026-03-01'},
                'supplier': {
                    'name': 'Suministros Ficticios del Sur SL',
                    'tax_id': 'B99887766',
                    'address': 'Calle Inventada 3',
                    'city': 'Sevilla',
                    'postal_code': '41001',
                    'email': 'facturas@ficticios.example',
                },
                'totals': {'net_subtotal': '100.00', 'tax_total': 21, 'total': 121},
                'items': [{
                    'description': 'Tornillos',
                    'quantity': 2,
                    'unit_price': 50,
                    'taxes': [
                        {'tax_type': 'IVA', 'tax_rate': 21},
                        {'tax_type': 'IRPF', 'tax_rate': -15},
                    ],
                }],
            },
        }

    def _document(self, **values):
        values.setdefault('name', 'DIALOGO-1')
        values.setdefault('last_extraction', json.dumps(self.answer))
        return self.Document.create(values)

    def test_the_dialog_gets_keyed_rows_numbers_and_the_rates_of_each_line(self):
        data = self._document().action_result_data()

        totals = {row[0]: row[2] for row in data['sections']['totals']}
        self.assertEqual(totals['subtotal'], 100.0)
        self.assertEqual(totals['tax'], 21.0)
        item = data['items'][0]
        self.assertEqual(item['tax_rate'], 21.0)
        self.assertEqual(item['irpf_rate'], 15.0)
        self.assertEqual(item['item_type'], 'product')
        # Nobody has this tax number on file yet: the dialog says it will be created.
        self.assertEqual(data['supplier_match']['status'], 'new')

    def test_a_supplier_nobody_has_is_created_from_the_reading(self):
        """The module this is a port of creates the supplier; so does this."""
        self.env.company.easyocr_invoice_draft = True
        document = self._document(partner_name='Suministros Ficticios del Sur SL', partner_vat='B99887766')

        document.action_create_bill()

        partner = document.move_id.partner_id
        self.assertEqual(partner.name, 'Suministros Ficticios del Sur SL')
        self.assertEqual(partner.vat, 'B99887766')
        self.assertEqual(partner.street, 'Calle Inventada 3')
        self.assertEqual(partner.city, 'Sevilla')
        self.assertEqual(partner.zip, '41001')
        self.assertEqual(partner.email, 'facturas@ficticios.example')
        self.assertGreater(partner.supplier_rank, 0)
        self.assertEqual(
            self.Document.action_check_supplier('B99887766', '')['status'], 'found',
        )

    def test_what_the_reader_corrected_reaches_the_bill(self):
        self.env.company.easyocr_invoice_draft = True
        document = self._document()

        document.action_create_bill(overrides={
            'document': {'document_number': 'F-77-BIS', 'issue_date': '15/03/2026', 'due_date': ''},
            'supplier': {'name': 'Otro Proveedor Ficticio SL', 'tax_id': 'B11223344'},
        }, items=[{
            'description': 'Tornillos', 'quantity': 2, 'unit_price': 50,
            'tax_rate': 21, 're_rate': 0, 'irpf_rate': 0,
        }])

        move = document.move_id
        self.assertEqual(move.ref, 'F-77-BIS')
        self.assertEqual(str(move.invoice_date), '2026-03-15')
        self.assertEqual(move.partner_id.name, 'Otro Proveedor Ficticio SL')
        # The rate typed on the line becomes the company's tax with that rate.
        self.assertEqual(move.invoice_line_ids.tax_ids.mapped("amount"), [21.0])
        self.assertAlmostEqual(move.amount_total, 121.0, places=2)

    def test_the_dialog_can_turn_it_into_a_credit_note(self):
        self.env.company.easyocr_invoice_draft = True
        document = self._document()

        action = document.action_create_bill(is_refund=True)

        self.assertEqual(document.move_id.move_type, 'in_refund')
        # Odoo 17+ opens nothing without ``views``: the dialog would report a
        # bill that does exist as one that failed.
        self.assertEqual(action['views'], [(False, 'form')])

    def test_paying_with_no_bank_picked_uses_the_company_bank_journal(self):
        self.env.company.easyocr_invoice_draft = False
        journal = self.env['account.journal'].search([
            ('company_id', '=', self.env.company.id), ('type', '=', 'bank'),
        ], limit=1)
        if not journal:
            self.skipTest('No bank journal in this database')
        document = self._document()

        document.action_create_bill(register_payment=True, items=[{
            'description': 'Tornillos', 'quantity': 1, 'unit_price': 100, 'tax_rate': 21,
        }])

        self.assertEqual(document.move_id.state, 'posted')
        self.assertIn(document.move_id.payment_state, ('paid', 'in_payment'))

    def test_the_codes_on_the_lines_are_resolved_without_creating_anything(self):
        product = self.env['product.product'].create({
            'name': 'Tornillo ficticio', 'default_code': 'TORN-1',
        })
        before = self.env['product.product'].search_count([])

        found = self.Document.action_resolve_codes(False, ['TORN-1', 'NO-EXISTE'])

        self.assertEqual(list(found), ['TORN-1'])
        self.assertIn(product.name, found['TORN-1'])
        self.assertEqual(self.env['product.product'].search_count([]), before)
