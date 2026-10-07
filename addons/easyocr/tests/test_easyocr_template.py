# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License OPL-1 (see LICENSE file).

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestEasyocrTemplate(TransactionCase):
    """Tests for the extraction templates and their boxes."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Template = cls.env['easyocr.template']
        cls.Box = cls.env['easyocr.template.box']

    def _make_template(self, **values):
        values.setdefault('name', 'Standard invoice')
        return self.Template.create(values)

    def test_box_count_matches_the_boxes(self):
        template = self._make_template()
        self.assertEqual(template.box_count, 0)

        self.Box.create({
            'template_id': template.id,
            'page': 1,
            'field_key': 'document_number',
            'x': 10,
            'y': 20,
            'width': 30,
            'height': 40,
        })

        self.assertEqual(template.box_count, 1)

    def test_deleting_a_template_takes_its_boxes_with_it(self):
        template = self._make_template()
        box = self.Box.create({
            'template_id': template.id,
            'page': 1,
            'field_key': 'amount_total',
            'x': 0,
            'y': 0,
            'width': 10,
            'height': 10,
        })

        template.unlink()

        self.assertFalse(box.exists())

    def test_a_box_keeps_the_coordinates_it_was_given(self):
        """Coordinates are PDF points; nothing should round or rescale them here."""
        template = self._make_template()
        box = self.Box.create({
            'template_id': template.id,
            'page': 2,
            'field_key': 'document_date',
            'x': 123.45,
            'y': 67.89,
            'width': 12.5,
            'height': 7.25,
        })

        self.assertEqual(box.page, 2)
        self.assertAlmostEqual(box.x, 123.45, places=2)
        self.assertAlmostEqual(box.y, 67.89, places=2)

    def test_the_box_label_follows_the_field_key(self):
        template = self._make_template()
        box = self.Box.create({
            'template_id': template.id,
            'page': 1,
            'field_key': 'partner_name',
            'x': 0,
            'y': 0,
            'width': 1,
            'height': 1,
        })

        self.assertEqual(box.display_name, 'Vendor')
