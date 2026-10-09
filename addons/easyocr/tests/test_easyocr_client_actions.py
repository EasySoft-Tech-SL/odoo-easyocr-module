# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

import os
import re

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

REGISTERED = re.compile(r'registry\.category\("actions"\)\.add\(\s*"[^"]+"\s*,\s*(\w+)\s*\)')


@tagged('post_install', '-at_install')
class TestEasyocrClientActions(TransactionCase):
    """A client action has to take whatever props Odoo gives it.

    Odoo passes ``updateActionState``, ``className`` and others to every client
    action. In debug mode OWL checks props, and a component that lists its own
    and nothing else refuses to open: the viewer showed "Oops" to anyone with
    debug on, and nothing in production mode gave it away.
    """

    def test_every_client_action_accepts_the_props_odoo_passes(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        folder = os.path.join(root, 'static', 'src', 'js')
        checked = 0
        for name in sorted(os.listdir(folder)):
            if not name.endswith('.js'):
                continue
            with open(os.path.join(folder, name), encoding='utf-8') as handle:
                source = handle.read()
            for component in REGISTERED.findall(source):
                body = re.search(
                    r'class\s+%s\b.*?\n}' % re.escape(component), source, re.S,
                )
                self.assertTrue(body, "%s registers %s but does not define it" % (name, component))
                props = re.search(r'static props = \{(.*?)\n    \};', body.group(0), re.S)
                if not props:
                    # Without a props declaration OWL checks nothing.
                    continue
                checked += 1
                self.assertIn(
                    '"*": true', props.group(1),
                    "%s (%s) lists its props and nothing else: in debug mode it "
                    "will not open." % (component, name),
                )
        self.assertGreater(checked, 1, "No client action with props was found to check.")

    def test_no_dialog_is_awaited_for_an_answer_it_never_gives(self):
        """``dialog.add`` answers with the function that closes the dialog.

        Awaiting it for what was typed reads the close function instead: the
        viewer saved every template without showing the dialog, under the name
        "removeCurrentOverlay". An answer has to come back through a callback.
        """
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        folder = os.path.join(root, 'static', 'src', 'js')
        for name in sorted(os.listdir(folder)):
            if name.endswith('.js'):
                with open(os.path.join(folder, name), encoding='utf-8') as handle:
                    source = handle.read()
                self.assertNotRegex(
                    source, r'=\s*await\s+this\.dialog\.add\(',
                    "%s awaits dialog.add for an answer; it only returns the close function." % name,
                )
