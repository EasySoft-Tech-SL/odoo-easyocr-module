# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

"""The icons the module paints on its own screens.

Odoo ships FontAwesome 4 and the Dolibarr module this one is a port of draws
its icons from FontAwesome 5, so the names that look right in that source are
frequently not there. A name that does not exist is not an error anywhere: it
paints nothing at all, and a card ends up with an empty chip where its icon
should be. Nothing in Python can see that, which is why it is checked here.
"""

import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

# Where this module names its classes: the screens it draws itself, plus the
# views, which can carry an icon on a button.
FOLDERS = (
    os.path.join('static', 'src', 'js'),
    os.path.join('static', 'src', 'xml'),
    os.path.join('static', 'src', 'scss'),
    'views',
)
EXTENSIONS = ('.js', '.xml', '.scss')

ICON = re.compile(r'\bfa-[a-z0-9-]+\b')

# FontAwesome's own modifiers, not icons: they change whatever they are next to.
NOT_AN_ICON = {'fa-spin', 'fa-fw', 'fa-lg', 'fa-2x', 'fa-3x', 'fa-4x', 'fa-5x'}

# The stylesheet the browser is actually given.
FONTAWESOME = os.path.join(
    'static', 'src', 'libs', 'fontawesome', 'css', 'font-awesome.css',
)


@tagged('post_install', '-at_install')
class TestEasyocrIcons(TransactionCase):
    """An icon name that is not in the stylesheet is an icon nobody sees."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.module_path = get_module_path('easyocr')
        cls.web_path = get_module_path('web')

    def _named_icons(self):
        """Every icon name this module writes down, and where it wrote it."""
        found = {}
        for folder in FOLDERS:
            directory = os.path.join(self.module_path, folder)
            if not os.path.isdir(directory):
                continue
            for name in sorted(os.listdir(directory)):
                if not name.endswith(EXTENSIONS):
                    continue
                with open(os.path.join(directory, name), encoding='utf-8') as handle:
                    for icon in ICON.findall(handle.read()):
                        if icon not in NOT_AN_ICON:
                            found.setdefault(icon, set()).add(os.path.join(folder, name))
        return found

    def test_every_icon_the_module_names_is_one_that_exists(self):
        stylesheet = os.path.join(self.web_path, FONTAWESOME)
        self.assertTrue(
            os.path.exists(stylesheet),
            "FontAwesome is not where it used to be: %s" % stylesheet,
        )
        with open(stylesheet, encoding='utf-8') as handle:
            css = handle.read()

        named = self._named_icons()
        self.assertTrue(named, "No icon was found at all: the sweep is broken.")

        missing = {
            icon: sorted(where)
            for icon, where in named.items()
            if '.%s:before' % icon not in css
        }
        self.assertFalse(
            missing,
            "These icons are named but do not exist in the FontAwesome Odoo "
            "ships, so they paint nothing: %s"
            % ', '.join('%s (in %s)' % (icon, ', '.join(where))
                        for icon, where in sorted(missing.items())),
        )
