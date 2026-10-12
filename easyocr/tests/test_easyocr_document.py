# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestEasyocrDocument(TransactionCase):
    """Smoke tests for the document model and its status flow."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Document = cls.env['easyocr.document']

    def test_default_status_is_pending(self):
        document = self.Document.create({'name': 'INV/2026/0001'})
        self.assertEqual(document.state, 'draft')

    def test_status_flow(self):
        document = self.Document.create({'name': 'INV/2026/0002'})

        document.action_mark_processed()
        self.assertEqual(document.state, 'processed')

        document.action_reset_to_draft()
        self.assertEqual(document.state, 'draft')

    def test_reset_clears_the_error_message(self):
        document = self.Document.create({
            'name': 'INV/2026/0003',
            'state': 'error',
            'error_message': 'Unreadable scan',
        })

        document.action_reset_to_draft()

        self.assertFalse(document.error_message)

    def test_display_name_includes_the_vendor(self):
        partner = self.env['res.partner'].create({'name': 'Proveedor de prueba'})
        document = self.Document.create({
            'name': 'INV/2026/0004',
            'partner_id': partner.id,
        })

        self.assertIn('Proveedor de prueba', document.display_name)


@tagged('post_install', '-at_install')
class TestEasyocrProjectField(TransactionCase):
    """The field that says which project a document belongs to.

    It hides behind the core's analytic-accounting group on purpose. The widget
    asks the server for the analytic plans, and a user who may not read them
    does not simply get an empty field: the form refuses to open with an access
    error, and the document becomes unreachable for them. Found in a browser and
    not in a test, because the suite runs as an administrator who has the group.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Document = cls.env['easyocr.document']
        cls.group_user = cls.env.ref('base.group_user')
        cls.group_reader = cls.env.ref('easyocr.group_easyocr_user')
        cls.group_analytic = cls.env.ref('analytic.group_analytic_accounting')

    def _reader(self, *extra_groups):
        groups = [self.group_user, self.group_reader, *extra_groups]
        # Odoo 19 renamed res.users.groups_id to group_ids, and this file is the
        # same one on both branches.
        field = 'group_ids' if 'group_ids' in self.env['res.users']._fields else 'groups_id'
        return self.env['res.users'].create({
            'name': 'Lectora',
            'login': 'lectora-%s' % len(extra_groups),
            field: [(6, 0, [group.id for group in groups])],
        })

    def _arch(self, user):
        arch = self.Document.with_user(user).get_view()['arch']
        return arch if isinstance(arch, str) else str(arch)

    def test_a_reader_without_analytic_accounting_does_not_get_the_field(self):
        user = self._reader()

        self.assertNotIn('name="analytic_distribution"', self._arch(user))

    def test_a_reader_with_analytic_accounting_does_get_the_field(self):
        """The other half: hiding it from everybody would pass the test above."""
        user = self._reader(self.group_analytic)

        self.assertIn('name="analytic_distribution"', self._arch(user))
