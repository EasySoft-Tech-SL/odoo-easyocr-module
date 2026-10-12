# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

"""What a webhook call is allowed to do beyond filing the document.

A webhook is a message from outside. Left alone it files a document and stops;
these are the switches that let it go further, and each one is checked by what
it leaves behind in the accounts.
"""

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestEasyocrWebhookPayment(TransactionCase):
    """Billing and paying from a webhook, and stopping when told to."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Document = cls.env['easyocr.document']
        cls.company = cls.env.company
        cls.partner = cls.env['res.partner'].create({
            'name': 'Proveedor del webhook SL',
            'vat': 'B3186006',
        })
        cls.journal = cls.env['account.journal'].search([
            ('type', '=', 'bank'),
            ('company_id', '=', cls.company.id),
        ], limit=1)
        if not cls.journal:
            cls.journal = cls.env['account.journal'].create({
                'name': 'Banco del webhook',
                'code': 'WHBK',
                'type': 'bank',
                'company_id': cls.company.id,
            })

    def setUp(self):
        super().setUp()
        self.company.write({
            'easyocr_webhook_create_bill': False,
            'easyocr_webhook_mark_paid': False,
            'easyocr_webhook_journal_id': self.journal.id,
            'easyocr_webhook_payment_method_line_id': False,
            'easyocr_invoice_draft': True,
        })

    def _document(self, **values):
        """A document as the webhook leaves it: read, with no file attached."""
        values.setdefault('name', 'WEB/2026/0001')
        values.setdefault('state', 'processed')
        values.setdefault('partner_id', self.partner.id)
        values.setdefault('amount_untaxed', 100.0)
        values.setdefault('amount_total', 121.0)
        return self.Document.create(values)

    # ------------------------------------------------------------------
    # Doing nothing is the default
    # ------------------------------------------------------------------
    def test_a_webhook_files_the_document_and_stops(self):
        document = self._document()

        note = document._settle_webhook()

        self.assertFalse(note)
        self.assertFalse(document.move_id)

    # ------------------------------------------------------------------
    # Making the bill
    # ------------------------------------------------------------------
    def test_the_bill_is_made_when_the_company_asks_for_it(self):
        self.company.easyocr_webhook_create_bill = True
        document = self._document()

        note = document._settle_webhook()

        self.assertTrue(document.move_id)
        self.assertEqual(document.move_id.state, 'draft')
        self.assertIn('bill was created', note)

    def test_a_bill_that_cannot_be_made_is_said_and_not_raised(self):
        """A failure here has to come back as text: an error status makes the
        sender repeat the call and the document ends up filed twice."""
        self.company.easyocr_webhook_create_bill = True
        document = self._document(partner_id=False, partner_vat=False, partner_name=False)

        note = document._settle_webhook()

        self.assertFalse(document.move_id)
        self.assertIn('could not be created', note)

    def test_a_bill_is_not_made_when_the_company_did_not_ask(self):
        self.company.easyocr_webhook_mark_paid = True
        document = self._document()

        note = document._settle_webhook()

        self.assertFalse(document.move_id)
        self.assertFalse(note)

    # ------------------------------------------------------------------
    # Paying it
    # ------------------------------------------------------------------
    def test_the_bill_is_paid_when_the_company_asks_for_it(self):
        self.company.write({
            'easyocr_webhook_create_bill': True,
            'easyocr_webhook_mark_paid': True,
            'easyocr_invoice_draft': False,
        })
        document = self._document()

        note = document._settle_webhook()

        self.assertEqual(document.move_id.state, 'posted')
        self.assertFalse(document.move_id.amount_residual)
        self.assertIn('payment registered', note)

    def test_a_bill_in_draft_is_not_paid(self):
        """The rule the module this port comes from uses: a draft has no entry
        to pay against."""
        self.company.write({
            'easyocr_webhook_create_bill': True,
            'easyocr_webhook_mark_paid': True,
        })
        document = self._document()

        note = document._settle_webhook()

        self.assertEqual(document.move_id.state, 'draft')
        self.assertTrue(document.move_id.amount_residual)
        self.assertIn('not confirmed', note)

    def test_with_no_bank_account_the_payment_is_not_made_and_says_so(self):
        self.company.write({
            'easyocr_webhook_create_bill': True,
            'easyocr_webhook_mark_paid': True,
            'easyocr_invoice_draft': False,
            'easyocr_webhook_journal_id': False,
        })
        document = self._document()

        note = document._settle_webhook()

        self.assertTrue(document.move_id.amount_residual)
        self.assertIn('bank account', note)

    def test_the_payment_lands_on_the_account_the_company_chose(self):
        self.company.write({
            'easyocr_webhook_create_bill': True,
            'easyocr_webhook_mark_paid': True,
            'easyocr_invoice_draft': False,
        })
        document = self._document()

        document._settle_webhook()

        payment = self.env['account.payment'].search([
            ('partner_id', '=', self.partner.id),
            ('payment_type', '=', 'outbound'),
        ], limit=1)
        self.assertTrue(payment)
        self.assertEqual(payment.journal_id, self.journal)
