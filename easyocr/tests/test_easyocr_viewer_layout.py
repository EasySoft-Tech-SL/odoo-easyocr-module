# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

import os
import xml.etree.ElementTree as ElementTree

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestEasyocrViewerLayout(TransactionCase):
    """The viewer's column: fixed top and bottom, only the middle scrolls.

    In the module this is a port of, the AI block stays at the top and the
    actions and the help stay at the bottom while the fields, the template and
    the extracted data scroll between them. Here the AI block scrolled away
    with the rest.
    """

    def _sidebar(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        tree = ElementTree.parse(os.path.join(root, 'static', 'src', 'xml', 'easyocr_document_viewer.xml'))
        for node in tree.iter():
            if 'o_easyocr_sidebar' in (node.get('class') or '').split():
                return node
        self.fail("The viewer has no sidebar.")

    def _classes(self, node):
        return (node.get('class') or '').split()

    def test_the_ai_block_and_the_actions_are_outside_the_scrolling_middle(self):
        sidebar = self._sidebar()
        scroll = next(child for child in sidebar if 'o_easyocr_sidebar_scroll' in self._classes(child))

        inside = [node for node in scroll.iter() if self._classes(node)]
        for unwanted in ('o_easyocr_ai_hero', 'o_easyocr_actions_footer', 'o_easyocr_help'):
            self.assertFalse(
                [node for node in inside if unwanted in self._classes(node)],
                "%s is inside the scrolling part of the column" % unwanted,
            )
        order = [next(c for c in self._classes(child) if c.startswith('o_easyocr_'))
                 for child in sidebar if self._classes(child)]
        self.assertLess(order.index('o_easyocr_sidebar_fixed'), order.index('o_easyocr_sidebar_scroll'))
        self.assertLess(order.index('o_easyocr_sidebar_scroll'), order.index('o_easyocr_actions_footer'))
