# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

"""The boxes a vendor's documents are read with, saved once and painted again.

A template is only worth keeping if it can be found when the next document from
that vendor arrives, and finding it means knowing whose it is. The first one this
module saved had no vendor at all -- the screen had no way to work one out -- and
it was a template nothing would ever look up again. These tests are about that
link, and about the boxes coming back where they were left.
"""

import base64

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

# Two boxes with the numbers spelled out, so a change in how they are stored
# shows up here as a difference and not as a rounding.
BOXES = [
    {'page': 1, 'field_key': 'document_number', 'x': 40.0, 'y': 90.5,
     'width': 120.0, 'height': 14.0, 'text': 'FA-2026-0042'},
    {'page': 2, 'field_key': 'amount_total', 'x': 300.0, 'y': 560.25,
     'width': 90.0, 'height': 16.0, 'text': '121,00'},
]


@tagged('post_install', '-at_install')
class TestEasyocrTemplateApply(TransactionCase):
    """Saving the boxes under a vendor, and finding them again."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Document = cls.env['easyocr.document']
        cls.Template = cls.env['easyocr.template']
        cls.company = cls.env.company
        cls.vendor = cls.env['res.partner'].create({
            'name': 'Ferreteria Industrial del Norte SL',
            'vat': 'B3186006',
        })
        cls.other = cls.env['res.partner'].create({
            'name': 'Otro Proveedor SA',
            'vat': 'B99999999',
        })

    def _document(self, **values):
        values.setdefault('name', 'factura.pdf')
        values.setdefault('company_id', self.company.id)
        return self.Document.create(values)

    # ------------------------------------------------------------------
    # Saving
    # ------------------------------------------------------------------
    def test_the_boxes_are_saved_under_the_vendor_of_the_document(self):
        """The vendor comes from the tax number the reading left behind."""
        document = self._document(partner_vat='B3186006')

        answer = document.action_save_template('Facturas del norte', BOXES)

        template = self.Template.browse(answer['template'])
        self.assertEqual(template.partner_id, self.vendor)
        self.assertEqual(template.box_count, 2)
        self.assertIn(self.vendor.name, answer['label'])

    def test_the_vendor_is_found_by_name_when_there_is_no_tax_number(self):
        document = self._document(partner_name='Ferreteria Industrial del Norte SL')

        answer = document.action_save_template('Por nombre', BOXES)

        self.assertEqual(self.Template.browse(answer['template']).partner_id, self.vendor)

    def test_the_vendor_the_document_already_has_wins(self):
        """A vendor set by hand is a decision, not a guess to be second-guessed."""
        document = self._document(partner_id=self.other.id, partner_vat='B3186006')

        answer = document.action_save_template('Manda el de la ficha', BOXES)

        self.assertEqual(self.Template.browse(answer['template']).partner_id, self.other)

    def test_boxes_with_no_vendor_to_hang_them_on_are_still_saved(self):
        """A document nobody has identified yet: the boxes are kept generic."""
        document = self._document()

        answer = document.action_save_template('Sin proveedor', BOXES)

        self.assertEqual(self.Template.browse(answer['template']).partner_id.id, False)
        self.assertFalse(answer['vendor'])

    def test_our_own_tax_number_is_not_a_vendor_and_gets_no_template(self):
        """The bill refuses it, and so does this: there are no boxes of ours."""
        self.company.partner_id.with_context(no_vat_validation=True).vat = 'B12345678'
        document = self._document(partner_vat='B12345678')

        answer = document.action_save_template('Nuestra', BOXES)

        self.assertEqual(self.Template.browse(answer['template']).partner_id.id, False)

    def test_the_boxes_keep_where_they_were(self):
        document = self._document(partner_id=self.vendor.id)

        answer = document.action_save_template('Con coordenadas', BOXES)

        boxes = self.Template.browse(answer['template']).box_ids.sorted('page')
        self.assertEqual(boxes.mapped('page'), [1, 2])
        self.assertEqual(boxes.mapped('field_key'), ['document_number', 'amount_total'])
        self.assertAlmostEqual(boxes[0].x, 40.0)
        self.assertAlmostEqual(boxes[1].y, 560.25)
        self.assertEqual(boxes[0].text, 'FA-2026-0042')

    def test_a_template_without_a_name_or_boxes_is_refused(self):
        document = self._document(partner_id=self.vendor.id)
        with self.assertRaises(UserError):
            document.action_save_template('   ', BOXES)
        with self.assertRaises(UserError):
            document.action_save_template('Sin cajas', [])

    # ------------------------------------------------------------------
    # Finding them again
    # ------------------------------------------------------------------
    def test_the_next_document_of_that_vendor_gets_the_boxes(self):
        self._document(partner_id=self.vendor.id).action_save_template('Del norte', BOXES)

        arrived = self._document(partner_vat='B3186006')
        answer = arrived.action_template_for_reading()

        self.assertTrue(answer['template'])
        self.assertEqual(len(answer['boxes']), 2)
        self.assertEqual(answer['boxes'][0]['field_key'], 'document_number')
        self.assertEqual(answer['vendor'], self.vendor.display_name)

    def test_a_document_of_another_vendor_gets_nothing(self):
        self._document(partner_id=self.vendor.id).action_save_template('Del norte', BOXES)

        arrived = self._document(partner_vat='B99999999')

        self.assertFalse(arrived.action_template_for_reading()['template'])

    def test_a_document_nobody_has_identified_gets_nothing(self):
        self._document(partner_id=self.vendor.id).action_save_template('Del norte', BOXES)

        self.assertFalse(self._document().action_template_for_reading()['template'])

    def test_the_newest_template_of_that_vendor_is_the_one_that_comes(self):
        document = self._document(partner_id=self.vendor.id)
        document.action_save_template('Vieja', BOXES[:1])
        document.action_save_template('Nueva', BOXES)

        answer = document.action_template_for_reading()

        self.assertEqual(answer['name'], 'Nueva')
        self.assertEqual(len(answer['boxes']), 2)

    def test_a_template_with_no_boxes_is_not_offered(self):
        """It would paint nothing, which looks like the template not working."""
        self.Template.create({'name': 'Vacía', 'partner_id': self.vendor.id})

        self.assertFalse(
            self._document(partner_id=self.vendor.id).action_template_for_reading()['template']
        )

    def test_a_template_of_another_company_is_not_offered(self):
        other_company = self.env['res.company'].create({'name': 'Otra sociedad'})
        self.Template.create({
            'name': 'De la otra',
            'partner_id': self.vendor.id,
            'company_id': other_company.id,
            'box_ids': [(0, 0, BOXES[0])],
        })

        self.assertFalse(
            self._document(partner_id=self.vendor.id).action_template_for_reading()['template']
        )

    def test_what_comes_back_is_only_what_the_screen_paints(self):
        """The answer travels to the browser, so it carries no records."""
        self._document(partner_id=self.vendor.id).action_save_template('Del norte', BOXES)

        answer = self._document(partner_id=self.vendor.id).action_template_for_reading()

        self.assertEqual(
            sorted(answer['boxes'][0]),
            ['field_key', 'height', 'page', 'width', 'x', 'y'],
        )


@tagged('post_install', '-at_install')
class TestEasyocrTemplateFromTheService(TransactionCase):
    """The reading is what usually says whose document this is.

    Nothing in the viewer can work the vendor out on its own, so a document that
    has just been read has to be asked again: it is the reading that turned a
    nameless file into one with a tax number on it.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Document = cls.env['easyocr.document']
        cls.company = cls.env.company
        cls.vendor = cls.env['res.partner'].create({
            'name': 'Ferreteria Industrial del Norte SL',
            'vat': 'B3186006',
        })

    def test_a_document_read_after_the_boxes_were_saved_finds_them(self):
        self.env['easyocr.template'].create({
            'name': 'Del norte',
            'partner_id': self.vendor.id,
            'box_ids': [(0, 0, BOXES[0])],
        })

        # The document as it is when it is filed: a file and nothing else.
        document = self.Document.create({
            'name': 'escaneo.pdf',
            'company_id': self.company.id,
            'attachment_id': self.env['ir.attachment'].create({
                'name': 'escaneo.pdf', 'datas': base64.b64encode(b'%PDF-1.4 x'),
            }).id,
        })
        self.assertFalse(document.action_template_for_reading()['template'])

        # And as it is after the service has read it.
        document.write({'partner_vat': 'B3186006', 'partner_name': 'Ferreteria Industrial del Norte SL'})

        self.assertTrue(document.action_template_for_reading()['template'])
