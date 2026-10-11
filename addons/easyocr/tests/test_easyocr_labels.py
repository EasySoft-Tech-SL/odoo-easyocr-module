# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestEasyocrLabels(TransactionCase):
    """No two fields of one model answer to the same name.

    Odoo walks every field of a model at install and warns for each pair that
    shares a label (`ir_model._reflect_fields`). This walks the same fields the
    same way, filter included, because the label is the only thing that tells
    two fields apart on screen: a list that draws one of them and a form that
    draws the other read as the same column with two different numbers in it.
    A filter of our own here would let through exactly the pairs the warning is
    about.
    """

    def test_no_two_fields_of_a_model_share_a_label(self):
        clashes = []
        for model_name in sorted(self.env.registry):
            if not model_name.startswith('easyocr.'):
                continue
            by_label = {}
            for field in self.env[model_name]._fields.values():
                other = by_label.setdefault(field.string, field)
                if other is not field:
                    clashes.append(
                        '%s: %s and %s both show as %r'
                        % (model_name, other.name, field.name, field.string)
                    )

        self.assertFalse(
            clashes,
            "Two fields of one model carry the same label, and Odoo warns at "
            "every install for it:\n  " + '\n  '.join(clashes),
        )
