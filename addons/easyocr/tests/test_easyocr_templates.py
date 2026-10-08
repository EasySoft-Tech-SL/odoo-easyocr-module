# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

"""What the templates ask the components for, and what the components have.

A binding in an OWL template that names something which is not there fails in
silence. ``t-if="state.documentId"`` reads a getter of the component that never
lands on ``state``, so it is false for ever: the button is in the file and on no
screen, the translations are all in place, the Python side is right, and no test
of the module notices. A ``t-on-click`` naming a method that was renamed paints
a button that does nothing when it is pressed, which is the same silence.

Nothing here can see a template being rendered, so what is checked is the
contract: every ``state.<name>`` a template reads must be a name the component
puts on ``state``, and every handler a template calls by name must exist.
"""

import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

STATE = re.compile(r'\bstate\.([A-Za-z_]\w*)')
HANDLER = re.compile(r'\bt-on-[a-z]+="([^"]*)"')
BARE_NAME = re.compile(r'^[A-Za-z_]\w*$')
# The keys of the literal handed to useState(), and the ones written later, which
# is the two ways a name ends up on state.
STATE_KEY = re.compile(r'^\s*([A-Za-z_]\w*)\s*:', re.M)
STATE_ASSIGNED = re.compile(r'this\.state\.([A-Za-z_]\w*)\s*=')
METHOD = re.compile(r'^\s+(?:async\s+)?([A-Za-z_]\w*)\s*\(', re.M)

FOLDERS = (os.path.join('static', 'src', 'xml'), os.path.join('static', 'src', 'js'))


@tagged('post_install', '-at_install')
class TestEasyocrTemplates(TransactionCase):
    """A name a template uses and the component does not have is nobody's error."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.module_path = get_module_path('easyocr')

    def _read(self, folder, name):
        with open(os.path.join(self.module_path, folder, name), encoding='utf-8') as handle:
            return handle.read()

    def _files(self, folder, suffix):
        directory = os.path.join(self.module_path, folder)
        return sorted(name for name in os.listdir(directory) if name.endswith(suffix))

    def _templates(self):
        """Every template of the module and the text of it."""
        folder = FOLDERS[0]
        return {name: self._read(folder, name) for name in self._files(folder, '.xml')}

    def _javascript(self):
        folder = FOLDERS[1]
        return ''.join(self._read(folder, name) for name in self._files(folder, '.js'))

    def test_every_state_a_template_reads_is_on_state(self):
        """The keys are taken from all the components at once.

        Union of every component rather than the one that owns the template: a
        name that belongs to another component would slip through, which is the
        safe way round. A check that cries wolf gets switched off.
        """
        javascript = self._javascript()
        known = set(STATE_KEY.findall(javascript)) | set(STATE_ASSIGNED.findall(javascript))
        self.assertIn('empty', known, 'No state was read at all: the sweep is broken.')

        missing = {}
        for name, template in self._templates().items():
            for key in sorted(set(STATE.findall(template)) - known):
                missing.setdefault(key, set()).add(name)

        self.assertFalse(
            missing,
            'These templates read state keys no component ever puts on state, so '
            'whatever they guard is false for ever: %s'
            % ', '.join('state.%s (in %s)' % (key, ', '.join(sorted(where)))
                        for key, where in sorted(missing.items())),
        )

    def test_every_handler_a_template_calls_exists(self):
        """The ones written inline are skipped: those are the component itself."""
        javascript = self._javascript()
        known = set(METHOD.findall(javascript))
        self.assertIn('setup', known, 'No method was read at all: the sweep is broken.')

        missing = {}
        for name, template in self._templates().items():
            for handler in HANDLER.findall(template):
                handler = handler.strip()
                if not BARE_NAME.match(handler):
                    continue
                if handler not in known:
                    missing.setdefault(handler, set()).add(name)

        self.assertFalse(
            missing,
            'These templates call handlers that no component defines, so the '
            'button does nothing when it is pressed: %s'
            % ', '.join('%s() (in %s)' % (handler, ', '.join(sorted(where)))
                        for handler, where in sorted(missing.items())),
        )
