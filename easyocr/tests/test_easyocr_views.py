# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

"""What the views are allowed to say about the fields they hide.

A field carries `groups="..."` when it is for some readers and not for others.
The same view may not then name that field in a modifier: Odoo 16 drops the
whole view with a ParseError, 17 drops it when the modifier is `readonly`, and
from 18 on it loads and quietly evaluates a condition on a field the reader was
never given. The first two stop the module from loading, so they are loud; the
third is the one worth a test, because nothing anywhere says a word about it.

Nothing in Python sees this while the module is loading, and the suite does not
see it either when it runs without `-u`: the views it exercises are the ones
already in the database. So it is read off the files here, which is where the
mistake is made.
"""

import ast
import os
import re

from lxml import etree

from odoo.modules.module import get_module_path
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

# The modifiers Odoo itself validates against the groups of the record.
MODIFIER_ATTRIBUTES = ('invisible', 'readonly', 'required', 'column_invisible')
# Painted with a domain of their own, and evaluated in the browser like the rest.
MODIFIER_PREFIXES = ('decoration-',)

IDENTIFIER = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')


@tagged('post_install', '-at_install')
class TestEasyocrViews(TransactionCase):
    """A condition on a field the view hides is a condition nobody can read."""

    def _arches(self):
        """Every view arch this module writes, file by file."""
        folder = os.path.join(get_module_path('easyocr'), 'views')
        for filename in sorted(os.listdir(folder)):
            if not filename.endswith('.xml'):
                continue
            tree = etree.parse(os.path.join(folder, filename))
            for record in tree.iter('record'):
                if record.get('model') != 'ir.ui.view':
                    continue
                arch = record.find("field[@name='arch']")
                if arch is None or len(arch) == 0:
                    continue
                yield filename, record.get('id'), arch[0]

    def _hidden_fields(self, root):
        """The fields this arch takes away from whoever is not in the group.

        A group on an element hides that element and everything under it, which
        is the same reading Odoo makes when it decides whether a field is in the
        view for this reader or not.
        """
        if root.get('groups'):
            return {node.get('name') for node in root.iter('field') if node.get('name')}
        hidden = set()
        for node in root.iter('field'):
            under_a_group = node.get('groups') or any(
                parent.get('groups')
                for parent in node.iterancestors()
                if parent is not root
            )
            if under_a_group and node.get('name'):
                hidden.add(node.get('name'))
        return hidden

    def _conditions(self, node):
        """The conditions an element carries, as (what, the text) pairs."""
        for name, value in node.attrib.items():
            if name in MODIFIER_ATTRIBUTES or name.startswith(MODIFIER_PREFIXES):
                yield name, value
        written = node.get('attrs')
        if not written:
            return
        try:
            parsed = ast.literal_eval(written)
        except (ValueError, SyntaxError):
            # Not the shape it should be: read it as it stands rather than look
            # away from it.
            yield 'attrs', written
        else:
            for key, value in parsed.items():
                yield 'attrs[%s]' % key, str(value)

    def test_a_condition_does_not_name_a_field_its_own_view_hides(self):
        read = 0
        offenders = []
        for filename, xmlid, root in self._arches():
            read += 1
            hidden = self._hidden_fields(root)
            if not hidden:
                continue
            for node in root.iter():
                for where, text in self._conditions(node):
                    for named in sorted(hidden & set(IDENTIFIER.findall(text))):
                        offenders.append(
                            '%s (%s): %s names %s, which this view hides'
                            % (filename, xmlid or 'no xmlid', where, named)
                        )

        self.assertTrue(read, "No view was read at all: the sweep is broken.")
        self.assertFalse(
            offenders,
            "A view cannot ask about a field it hides from the reader: Odoo 16 "
            "refuses to load it and from 18 on the condition is evaluated "
            "against a field nobody has. Give the condition a field the view "
            "shows, or stop hiding this one.\n" + '\n'.join(offenders),
        )
