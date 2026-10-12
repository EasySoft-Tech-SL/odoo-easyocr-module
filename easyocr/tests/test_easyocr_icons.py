# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

"""The icons the module paints on its own screens.

Odoo 20 dropped FontAwesome for a subset of Material Symbols, and the subset is
what matters: an icon is an element carrying the name in a `data-icon`
attribute, and the font turns that name into a glyph through a ligature. A name
the font was not built with is not an error anywhere: it paints nothing at all,
and a card ends up with an empty chip where its icon should be. Nothing in
Python can see that, which is why it is checked here.

The list of names that are really in the font is the one the web client itself
is built from, so it is read from there rather than copied.
"""

import os
import re

from odoo.addons.web.icons import ICONS
from odoo.modules.module import get_module_path
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

# Where this module names its icons: the screens it draws itself, plus the
# views, which can carry an icon on a button.
FOLDERS = (
    os.path.join('static', 'src', 'js'),
    os.path.join('static', 'src', 'xml'),
    os.path.join('static', 'src', 'scss'),
    'views',
)
EXTENSIONS = ('.js', '.xml', '.scss')

# The ways a name gets written down. A static attribute carries the name it
# paints with; a dynamic one carries an expression, and only the names the
# expression spells out are read out of it, since a name that only settles once
# the screen is painted cannot be checked here.
STATIC_ATTRIBUTE = re.compile(r'(?<!t-att-)data-icon="([^"]*)"')
DYNAMIC_ATTRIBUTE = re.compile(r'\bt-att-data-icon="([^"]*)"')
JS_KEY = re.compile(r'\bicon:\s*"([^"]*)"')
VIEW_ATTRIBUTE = re.compile(r'(?<![-\w])icon="([^"]*)"')

# A name written on its own, and the names spelled out inside an expression.
BARE_NAME = re.compile(r'^[a-z][a-z0-9_]*$')
QUOTED_NAME = re.compile(r"'([a-z][a-z0-9_]*)'")

# FontAwesome, which is what 19 and the Dolibarr module this is a port of paint
# with. Left behind here it paints nothing: no stylesheet answers to it any
# more. The three shapes are a name, the bare class in front of one, and the
# string a screen builds one from.
FONTAWESOME = re.compile(r'\bfa-[a-z0-9-]+\b|\bclass="fa\b|\'fa \+')


@tagged('post_install', '-at_install')
class TestEasyocrIcons(TransactionCase):
    """A name that is not in the font is an icon nobody sees."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.module_path = get_module_path('easyocr')

    def _sources(self):
        """Every file of this module that can name an icon, and its text."""
        for folder in FOLDERS:
            directory = os.path.join(self.module_path, folder)
            if not os.path.isdir(directory):
                continue
            for name in sorted(os.listdir(directory)):
                if not name.endswith(EXTENSIONS):
                    continue
                with open(os.path.join(directory, name), encoding='utf-8') as handle:
                    yield os.path.join(folder, name), handle.read()

    def _named_icons(self):
        """Every icon name this module writes down, and where it wrote it."""
        found = {}

        def note(icon, path):
            found.setdefault(icon, set()).add(path)

        for path, text in self._sources():
            for value in (STATIC_ATTRIBUTE.findall(text)
                          + JS_KEY.findall(text)
                          + VIEW_ATTRIBUTE.findall(text)):
                if BARE_NAME.match(value):
                    note(value, path)
            for expression in DYNAMIC_ATTRIBUTE.findall(text):
                for icon in QUOTED_NAME.findall(expression):
                    note(icon, path)
        return found

    def test_every_icon_the_module_names_is_one_that_exists(self):
        named = self._named_icons()
        self.assertTrue(named, "No icon was found at all: the sweep is broken.")

        missing = {
            icon: sorted(where)
            for icon, where in named.items()
            if icon not in ICONS
        }
        self.assertFalse(
            missing,
            "These icons are named but are not in the font Odoo ships, so they "
            "paint nothing: %s"
            % ', '.join('%s (in %s)' % (icon, ', '.join(where))
                        for icon, where in sorted(missing.items())),
        )

    def test_the_module_paints_no_fontawesome_left_over(self):
        """19 and the source this is a port of name their icons `fa-*`."""
        left = {}
        for path, text in self._sources():
            for line_no, line in enumerate(text.splitlines(), start=1):
                for hit in FONTAWESOME.findall(line):
                    left.setdefault(hit, []).append('%s:%s' % (path, line_no))
        self.assertFalse(
            left,
            "FontAwesome is not in Odoo 20, so these paint nothing: %s"
            % '; '.join('%s (%s)' % (hit, ', '.join(where[:3]))
                        for hit, where in sorted(left.items())),
        )
