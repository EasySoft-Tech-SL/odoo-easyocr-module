# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

"""From the lines the service read to the lines of the bill.

One bill line per line on the document is the difference a person notices
first: a document read with five articles used to arrive as a single line with
the total on it, and every article had to be typed again.
"""

import base64
from unittest import mock

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

POST = 'odoo.addons.easyocr.models.easyocr_extractor.requests.post'


@tagged('post_install', '-at_install')
class TestEasyocrLines(TransactionCase):
    """Reading the lines, and turning them into the lines of a bill."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Document = cls.env['easyocr.document']
        cls.company = cls.env.company
        cls.company.write({
            'easyocr_ai_enabled': True,
            'easyocr_ai_url': 'https://ocr.example.test',
            'easyocr_ai_apikey': 'test-key',
        })
        cls.partner = cls.env['res.partner'].create({
            'name': 'Proveedor de lineas SL',
            'vat': 'B3186006',
        })

    def setUp(self):
        super().setUp()
        self.company.easyocr_autocreate_product = False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _document(self, items=None, **values):
        """A document whose extraction answer carries these lines."""
        attachment = self.env['ir.attachment'].create({
            'name': 'invoice.pdf',
            'datas': base64.b64encode(b'%PDF-1.4 lines'),
            'mimetype': 'application/pdf',
        })
        values.setdefault('name', 'FAC-2026-0007')
        values.setdefault('partner_id', self.partner.id)
        values.setdefault('attachment_id', attachment.id)
        document = self.Document.create(values)
        if items is not None:
            document.line_ids = [
                (0, 0, self.env['easyocr.document.line']._values_from_item(item, index))
                for index, item in enumerate(items, start=1)
            ]
        return document

    def _item(self, **values):
        item = {
            'code': '',
            'description': 'Articulo',
            'item_type': 'product',
            'quantity': 1,
            'unit_price': 10.0,
            'discount_percent': 0,
            'net_amount': 10.0,
            'taxes': [],
        }
        item.update(values)
        return item

    def _bill_lines(self, document):
        document.action_create_bill()
        return document.move_id.invoice_line_ids

    # ------------------------------------------------------------------
    # What the reading writes down
    # ------------------------------------------------------------------
    def test_the_lines_of_the_answer_become_lines_on_the_document(self):
        values = self.env['easyocr.document.line']._values_from_item(
            self._item(
                code='REF-9',
                description='Tornillos',
                quantity=3,
                unit_price=2.5,
                discount_percent=10,
                net_amount=6.75,
                taxes=[{'tax_type': 'tva', 'tax_rate': 21}],
            ),
            1,
        )

        self.assertEqual(values['name'], 'Tornillos')
        self.assertEqual(values['product_code'], 'REF-9')
        self.assertEqual(values['quantity'], 3)
        self.assertEqual(values['unit_price'], 2.5)
        self.assertEqual(values['discount_percent'], 10)
        self.assertEqual(values['tax_rate'], 21)

    def test_the_price_is_worked_back_when_the_document_does_not_print_one(self):
        """The model leaves the unit price out often enough to matter."""
        values = self.env['easyocr.document.line']._values_from_item(
            self._item(quantity=4, unit_price=None, net_amount=40.0), 1,
        )

        self.assertEqual(values['unit_price'], 10.0)

    def test_a_line_with_no_quantity_is_read_as_one(self):
        """Dividing by it to work out the price would be a crash, not a bill."""
        values = self.env['easyocr.document.line']._values_from_item(
            self._item(quantity=0, unit_price=None, net_amount=40.0), 1,
        )

        self.assertEqual(values['quantity'], 1.0)
        self.assertEqual(values['unit_price'], 40.0)

    def test_the_rate_taken_is_the_vat_one_and_not_the_withholding(self):
        values = self.env['easyocr.document.line']._values_from_item(
            self._item(taxes=[
                {'tax_type': 'irpf', 'tax_rate': 15},
                {'tax_type': 'tva', 'tax_rate': 21},
            ]),
            1,
        )

        self.assertEqual(values['tax_rate'], 21)

    def test_a_line_type_nobody_knows_is_kept_as_other(self):
        values = self.env['easyocr.document.line']._values_from_item(
            self._item(item_type='something-new'), 1,
        )

        self.assertEqual(values['item_type'], 'other')

    def test_a_second_reading_replaces_the_lines_of_the_first(self):
        """Keeping both would put the same article on the bill twice."""
        document = self._document(items=[self._item(description='Primera')])
        first = document.line_ids

        document._apply_lines([self._item(description='Segunda')])

        self.assertEqual(len(document.line_ids), 1)
        self.assertEqual(document.line_ids.name, 'Segunda')
        self.assertNotIn(document.line_ids, first)

    def test_a_reading_that_brings_no_lines_clears_the_ones_before(self):
        document = self._document(items=[self._item(description='Primera')])

        document._apply_lines([])

        self.assertFalse(document.line_ids)

    # ------------------------------------------------------------------
    # From the lines to the bill
    # ------------------------------------------------------------------
    def test_the_bill_has_one_line_for_every_line_read(self):
        document = self._document(items=[
            self._item(description='Tornillos', quantity=3, unit_price=2.5),
            self._item(description='Transporte', item_type='service', unit_price=15.0),
        ])

        lines = self._bill_lines(document)

        self.assertEqual(len(lines), 2)
        self.assertEqual(lines.mapped('name'), ['Tornillos', 'Transporte'])
        self.assertEqual(lines[0].quantity, 3)
        self.assertEqual(lines[0].price_unit, 2.5)

    def test_a_document_with_no_lines_still_makes_one_bill_line(self):
        """What a document filed by hand, or delivered by the webhook, has."""
        document = self._document(amount_untaxed=100.0, amount_total=121.0)

        lines = self._bill_lines(document)

        self.assertEqual(len(lines), 1)
        self.assertEqual(lines.price_unit, 100.0)

    def test_the_discount_carries_to_the_bill(self):
        document = self._document(items=[self._item(unit_price=10.0, discount_percent=25)])

        lines = self._bill_lines(document)

        self.assertEqual(lines.discount, 25)

    # Rates no standard chart carries, so the tax looked up can only be the one
    # this test made. With a 21% one the demo data's own tax answered first.
    RATE_ONLY_THIS_TEST_HAS = 7.7
    RATE_NOBODY_HAS = 33.33

    def test_the_tax_of_the_rate_read_lands_on_the_bill_line(self):
        tax = self.env['account.tax'].create({
            'name': 'IVA 7,7% compras',
            'amount': self.RATE_ONLY_THIS_TEST_HAS,
            'amount_type': 'percent',
            'type_tax_use': 'purchase',
            'company_id': self.company.id,
        })
        document = self._document(items=[
            self._item(taxes=[{'tax_type': 'tva', 'tax_rate': self.RATE_ONLY_THIS_TEST_HAS}]),
        ])

        lines = self._bill_lines(document)

        self.assertEqual(lines.tax_ids, tax)
        self.assertEqual(lines.tax_ids.type_tax_use, 'purchase')

    def test_a_sales_tax_is_not_taken_for_a_purchase_tax(self):
        """A bill is a purchase: the tax has to be the one for buying."""
        self.env['account.tax'].create({
            'name': 'IVA 7,7% ventas',
            'amount': self.RATE_ONLY_THIS_TEST_HAS,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'company_id': self.company.id,
        })
        document = self._document(items=[
            self._item(taxes=[{'tax_type': 'tva', 'tax_rate': self.RATE_ONLY_THIS_TEST_HAS}]),
        ])

        lines = self._bill_lines(document)

        self.assertFalse(lines.tax_ids)

    def test_a_rate_with_no_tax_configured_leaves_the_line_without_tax(self):
        """Guessing a rate the company has no tax for is worse than no tax."""
        document = self._document(items=[
            self._item(taxes=[{'tax_type': 'tva', 'tax_rate': self.RATE_NOBODY_HAS}]),
        ])

        lines = self._bill_lines(document)

        self.assertFalse(lines.tax_ids)

    # ------------------------------------------------------------------
    # The product of a line
    # ------------------------------------------------------------------
    def test_the_product_is_found_by_the_vendors_own_reference(self):
        product = self.env['product.product'].create({'name': 'Tornillo del proveedor'})
        self.env['product.supplierinfo'].create({
            'partner_id': self.partner.id,
            'product_id': product.id,
            'product_code': 'REF-9',
        })
        document = self._document(items=[self._item(code='REF-9')])

        lines = self._bill_lines(document)

        self.assertEqual(lines.product_id, product)

    def test_the_product_is_found_by_our_own_code(self):
        product = self.env['product.product'].create({
            'name': 'Tornillo nuestro',
            'default_code': 'REF-9',
        })
        document = self._document(items=[self._item(code='REF-9')])

        lines = self._bill_lines(document)

        self.assertEqual(lines.product_id, product)

    def test_no_product_is_created_unless_the_company_asks_for_it(self):
        document = self._document(items=[self._item(code='NUEVO-1')])

        lines = self._bill_lines(document)

        self.assertFalse(lines.product_id)
        self.assertFalse(self.env['product.product'].search([('default_code', '=', 'NUEVO-1')]))

    def test_the_product_is_created_when_the_company_asks_for_it(self):
        self.company.easyocr_autocreate_product = True
        document = self._document(items=[
            self._item(code='NUEVO-1', description='Articulo nuevo', unit_price=7.5),
        ])

        lines = self._bill_lines(document)

        self.assertTrue(lines.product_id)
        self.assertEqual(lines.product_id.default_code, 'NUEVO-1')
        self.assertEqual(lines.product_id.name, 'Articulo nuevo')
        self.assertEqual(lines.product_id.type, 'consu')
        self.assertTrue(lines.product_id.purchase_ok)
        self.assertEqual(lines.product_id.list_price, 7.5)

    def test_a_created_product_for_a_service_line_is_a_service(self):
        self.company.easyocr_autocreate_product = True
        document = self._document(items=[
            self._item(code='SERV-1', item_type='service'),
        ])

        lines = self._bill_lines(document)

        self.assertEqual(lines.product_id.type, 'service')

    def test_a_discount_line_gets_no_product_even_with_the_switch_on(self):
        """A discount is not something you buy: making a product of it invents
        a catalogue entry nobody sells."""
        self.company.easyocr_autocreate_product = True
        document = self._document(items=[
            self._item(code='DTO-1', description='Descuento comercial', item_type='discount'),
        ])

        lines = self._bill_lines(document)

        self.assertFalse(lines.product_id)
        self.assertFalse(self.env['product.product'].search([('default_code', '=', 'DTO-1')]))

    def test_two_lines_of_the_same_article_share_one_product(self):
        self.company.easyocr_autocreate_product = True
        document = self._document(items=[
            self._item(code='NUEVO-1'),
            self._item(code='NUEVO-1'),
        ])

        lines = self._bill_lines(document)

        self.assertEqual(lines[0].product_id, lines[1].product_id)
        self.assertEqual(len(self.env['product.product'].search([('default_code', '=', 'NUEVO-1')])), 1)

    # ------------------------------------------------------------------
    # The reading itself
    # ------------------------------------------------------------------
    def test_a_successful_reading_writes_the_lines_of_the_answer(self):
        body = {
            'status': 'success',
            'confidence': 0.9,
            'structured_data': {
                'document_number': 'A/9',
                'items': [
                    self._item(code='REF-1', description='Uno'),
                    self._item(code='REF-2', description='Dos'),
                ],
                'totals': {'net_subtotal': 20.0, 'total': 24.2},
            },
        }
        response = mock.Mock(status_code=200, headers={})
        response.json.return_value = body
        document = self.env['easyocr.document'].create({
            'name': 'FAC-2026-0009',
            'attachment_id': self.env['ir.attachment'].create({
                'name': 'otra.pdf',
                'datas': base64.b64encode(b'%PDF-1.4 otra'),
                'mimetype': 'application/pdf',
            }).id,
        })

        with mock.patch(POST, return_value=response):
            document.action_extract()

        self.assertEqual(document.line_ids.mapped('name'), ['Uno', 'Dos'])
        self.assertEqual(document.line_ids.mapped('product_code'), ['REF-1', 'REF-2'])

    def test_a_reading_with_no_lines_leaves_the_document_without_lines(self):
        body = {
            'status': 'success',
            'confidence': 0.9,
            'structured_data': {
                'document_number': 'A/9',
                'totals': {'net_subtotal': 20.0, 'total': 24.2},
            },
        }
        response = mock.Mock(status_code=200, headers={})
        response.json.return_value = body
        document = self.env['easyocr.document'].create({
            'name': 'FAC-2026-0010',
            'attachment_id': self.env['ir.attachment'].create({
                'name': 'tercera.pdf',
                'datas': base64.b64encode(b'%PDF-1.4 tercera'),
                'mimetype': 'application/pdf',
            }).id,
        })

        with mock.patch(POST, return_value=response):
            document.action_extract()

        self.assertFalse(document.line_ids)
