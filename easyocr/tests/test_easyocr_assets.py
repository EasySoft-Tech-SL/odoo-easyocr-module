# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

"""The rules the browser side follows, which change from one series to the next.

The same module ships on five Odoo series and the frontend is not the same on
all of them. Four differences cost a debugging session each, and not one of them
can be seen from Python: the module installs, the suite passes, and the web
client is either blank or quietly missing a screen. So they are read off the
files here, with the series decided by the version the module is running on:
this file is the same on all five and each run checks what its own series reads.

1. Up to 17 the backend bundle is served as a classic script, and a file only
   becomes a module if it says so at the top. Without the marker its `import`
   statements land in a classic script and the whole client dies with
   "Cannot use import statement outside a module". From 18 on the bundle is a
   module already and the marker is not needed.
2. On 16 the asset templates are picked up with the `[t-name][owl]` selector, so
   a template without `owl="1"` never reaches the app, which then dies with
   "Missing template: ...". From 17 on the selector is `[t-name]`, and the
   attribute is neither needed nor removed.
3. The user is reached differently: 16 and 17 register a `user` service whose
   `hasGroup` is answered asynchronously, and have no `@web/core/user` at all;
   from 18 on it is the other way round, the object is imported from
   `@web/core/user` and no such service is registered. Importing the newer one
   on the older series leaves the module with an unmet dependency and the client
   never starts.
4. A view widget is registered with the component itself up to 16 and with a
   `{ component: ... }` wrapper from 17 on. On 16 the wrapper is read as a
   component and the screen dies with "C is not a constructor"; from 17 on a
   bare class has no `extractProps` and the screen does not render either.
"""

import os
import re

from lxml import etree

from odoo import release
from odoo.modules.module import get_module_path
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

# The series this run is on, which is what every rule below is decided by.
SERIES = release.version_info[0]

MODULE_MARKER = '/** @odoo-module **/'
# The marker has to open the file; one further down is not read. A couple of
# lines of room, for a licence header in front of it.
MARKER_WINDOW = 3

TEMPLATE_NAME = re.compile(r'<t\s+t-name="[^"]+"([^>]*)>')
WIDGET_REGISTRATION = re.compile(
    r'registry\.category\("view_widgets"\)\s*\.add\(\s*"([^"]+)"\s*,\s*(.+?)\s*\)\s*;',
    re.DOTALL,
)
# `{ component: Foo }` and nothing else around it: the whole value has to be
# the wrapper, not something that merely contains one.
WIDGET_WRAPPER = re.compile(r'^\{\s*component:\s*[A-Za-z_$][\w$.]*\s*\}$', re.DOTALL)

NEW_USER_IMPORT = re.compile(r'from\s+["\']@web/core/user["\']')
USER_SERVICE = re.compile(r'useService\(\s*["\']user["\']\s*\)')


@tagged('post_install', '-at_install')
class TestEasyocrAssets(TransactionCase):
    """The browser side has to be written for the series it is installed on."""

    def _static_files(self, folder, extension):
        """The files of an asset folder, name and text, in name order."""
        root = os.path.join(get_module_path('easyocr'), 'static', 'src', folder)
        for name in sorted(os.listdir(root)):
            if not name.endswith(extension):
                continue
            with open(os.path.join(root, name), encoding='utf-8') as handle:
                yield name, handle.read()

    def test_a_script_says_what_it_is_up_to_17(self):
        """Without the marker the client is blank, and says so in the console."""
        read = 0
        offenders = []
        for name, text in self._static_files('js', '.js'):
            read += 1
            if SERIES > 17:
                continue
            if not any(
                line.strip() == MODULE_MARKER
                for line in text.split('\n')[:MARKER_WINDOW]
            ):
                offenders.append(name)

        self.assertTrue(read, "No script was read at all: the sweep is broken.")
        self.assertFalse(
            offenders,
            "Up to Odoo 17 the backend bundle is a classic script and a file is "
            "only made a module by the marker on its first line. Without it the "
            "web client does not load at all. Put %s at the top of: %s"
            % (MODULE_MARKER, ', '.join(offenders)),
        )

    def test_a_template_is_marked_for_the_app_on_16(self):
        """Odoo 16 only hands over the templates that carry the attribute."""
        read = 0
        offenders = []
        for name, text in self._static_files('xml', '.xml'):
            root = etree.fromstring(text.encode('utf-8'))
            for node in root:
                if node.tag != 't' or not node.get('t-name'):
                    continue
                read += 1
                if SERIES == 16 and node.get('owl') != '1':
                    offenders.append('%s: %s' % (name, node.get('t-name')))

        self.assertTrue(read, "No template was read at all: the sweep is broken.")
        self.assertFalse(
            offenders,
            "On Odoo 16 a template reaches the app only with owl=\"1\" on it, or "
            "the app dies with \"Missing template\". From 17 on the attribute is "
            "not used and is not to be added. Add it to:\n" + '\n'.join(offenders),
        )

    def test_the_user_comes_from_where_this_series_keeps_it(self):
        """One of the two is missing on every series, and it is not the same one."""
        read = 0
        offenders = []
        for name, text in self._static_files('js', '.js'):
            read += 1
            if SERIES <= 17:
                if NEW_USER_IMPORT.search(text):
                    offenders.append(
                        '%s: imports @web/core/user, which this series does not '
                        'carry. Take it as a service and await its hasGroup'
                        % name
                    )
            elif USER_SERVICE.search(text):
                offenders.append(
                    '%s: takes the user as a service, which this series does not '
                    'register. Import it from @web/core/user instead' % name
                )

        self.assertTrue(read, "No script was read at all: the sweep is broken.")
        self.assertFalse(offenders, '\n'.join(offenders))

    def test_a_view_widget_is_registered_the_way_this_series_reads_it(self):
        """The registry value is the class on 16 and a wrapper from 17 on."""
        read = 0
        offenders = []
        for name, text in self._static_files('js', '.js'):
            for key, value in WIDGET_REGISTRATION.findall(text):
                read += 1
                wrapped = bool(WIDGET_WRAPPER.match(value))
                if SERIES <= 16 and wrapped:
                    offenders.append(
                        '%s: %s is registered as %s, and on this series the value '
                        'is read as the component itself' % (name, key, value)
                    )
                elif SERIES > 16 and not wrapped:
                    offenders.append(
                        '%s: %s is registered as %s, and from 17 on the registry '
                        'wants { component: ... }' % (name, key, value)
                    )

        self.assertTrue(read, "No view widget was read: the sweep is broken.")
        self.assertFalse(
            offenders,
            "A view widget registered the other series' way does not render, and "
            "nothing is logged to say why:\n" + '\n'.join(offenders),
        )
