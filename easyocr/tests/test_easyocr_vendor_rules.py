# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

"""Port of EasyOCR for Dolibarr 2.9.0 to the webhook path.

Labels chained in front of the tax number, a name typed in the tax number
field, archived vendors, foreign numbers kept without their prefix, totals that
were not read, a bill Odoo refuses to post, two webhooks creating one vendor,
and what the module keeps of a call. Every tax number and every vendor here is
made up.
"""

import json
import logging
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from odoo import fields
from odoo.sql_db import db_connect
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.easyocr.controllers.main import RedactWebhookSecrets
from odoo.addons.easyocr.models import easyocr_tax_id as tax_ids
from odoo.addons.easyocr.models.easyocr_values import is_concurrency_error, set_param_value

from .test_easyocr_unattended_vendor import CIF_A, CIF_B

LABELS = ('NIF/CIF: ', 'CIF/NIF ', 'Tax ID: ES', 'VAT Reg. No. ES', 'TIN ')


@tagged('post_install', '-at_install')
class TestEasyocrTaxIdRules(TransactionCase):
    """The comparisons, on their own."""

    def test_chained_labels_are_all_dropped(self):
        for label in LABELS:
            self.assertEqual(tax_ids.tax_id_key(label + CIF_A), CIF_A, label)
            self.assertIn(CIF_A, tax_ids.tax_id_variants(label + CIF_A), label)

    def test_gr_is_the_greek_prefix(self):
        _norm, country, bare = tax_ids.split_tax_id('GR 123456789')
        self.assertEqual((country, bare), ('EL', '123456789'))
        variants = tax_ids.tax_id_variants('GR123456789')
        for form in ('EL123456789', 'GR123456789', '123456789'):
            self.assertIn(form, variants)

    def test_a_name_in_the_tax_number_field_is_not_a_number(self):
        self.assertTrue(tax_ids.tax_id_is_a_name('FICTICIA EXTRANJERA', 'Ficticia Extranjera, L.L.C.'))
        self.assertTrue(tax_ids.tax_id_is_a_name('', 'Cualquiera'))
        # No digit at all: a word typed so the contact could be saved
        self.assertTrue(tax_ids.tax_id_is_a_name('SIN NIF', 'Ficticia Extranjera LLC'))
        # A name with digits is still a name when it is the contact's own
        self.assertTrue(tax_ids.tax_id_is_a_name('7M', '7M'))
        self.assertFalse(tax_ids.tax_id_is_a_name(CIF_A, 'Ficticia Uno SL'))
        self.assertFalse(tax_ids.tax_id_is_a_name('EU372041234', 'Ficticia Extranjera LLC'))

    def test_the_withholding_of_a_credit_note_goes_with_its_sign(self):
        self.assertIsNone(tax_ids.header_totals_mismatch(-100.0, -21.0, -106.0, 0.0, 15.0))
        self.assertIsNone(tax_ids.header_totals_mismatch(-100.0, -21.0, -106.0, 0.0, -15.0))
        self.assertIsNotNone(tax_ids.header_totals_mismatch(-100.0, -21.0, -136.0, 0.0, 15.0))
        # A bill is unchanged
        self.assertIsNone(tax_ids.header_totals_mismatch(100.0, 21.0, 106.0, 0.0, 15.0))

    def test_a_token_in_an_address_never_reaches_the_log(self):
        record = logging.LogRecord(
            'werkzeug', logging.INFO, __file__, 1, '"%s" %s %s',
            ('POST /easyocr/webhook?token=abc123&batch=4 HTTP/1.1', '200', '-'), None,
        )
        RedactWebhookSecrets().filter(record)
        message = record.getMessage()
        self.assertNotIn('abc123', message)
        self.assertIn('batch=4', message)


@tagged('post_install', '-at_install')
class TestEasyocrVendorRules(TransactionCase):
    """What the webhook does with them."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Document = cls.env['easyocr.document']
        cls.Partner = cls.env['res.partner']
        cls.company = cls.env.company
        cls.company.country_id = cls.env.ref('base.es')
        cls.journal = cls.env['account.journal'].search([
            ('type', '=', 'bank'), ('company_id', '=', cls.company.id),
        ], limit=1) or cls.env['account.journal'].create({
            'name': 'Banco reglas', 'code': 'WHRR', 'type': 'bank',
            'company_id': cls.company.id,
        })

    def setUp(self):
        super().setUp()
        self.company.write({
            'easyocr_webhook_create_bill': True,
            'easyocr_webhook_mark_paid': False,
            'easyocr_webhook_journal_id': self.journal.id,
            'easyocr_webhook_payment_method_line_id': False,
            'easyocr_invoice_draft': False,
            'easyocr_allow_foreign_customer': False,
        })

    def _vendor(self, name, vat=False, **values):
        partner = self.Partner.create(dict({'name': name, 'is_company': True, 'supplier_rank': 1}, **values))
        if vat:
            partner.with_context(no_vat_validation=True).vat = vat
        return partner

    def _document(self, vat='', name='', totals=None, items=None, **values):
        structured = {'supplier': {'name': name, 'tax_id': vat}}
        if totals is not None:
            structured['totals'] = totals
        values.setdefault('name', 'WH/0290')
        values.setdefault('state', 'processed')
        values.setdefault('amount_untaxed', 100.0)
        values.setdefault('amount_total', 121.0)
        document = self.Document.create(dict(values, partner_vat=vat, partner_name=name,
                                             last_extraction=json.dumps({'structured_data': structured})))
        if items:
            document._apply_lines(items)
        return document

    # ------------------------------------------------------------------
    # 1. Labels in front of the number
    # ------------------------------------------------------------------
    def test_a_labelled_number_finds_the_vendor_and_creates_nobody(self):
        vendor = self._vendor('Ficticia Etiqueta SL', CIF_A)
        before = self.Partner.search_count([])
        for label in LABELS:
            partner, reasons = self._document(label + CIF_A, 'Otro nombre impreso')._resolve_partner_unattended()
            self.assertEqual(partner, vendor, label)
            self.assertFalse(reasons, label)
        self.assertEqual(self.Partner.search_count([]), before)

    # ------------------------------------------------------------------
    # 2. A name typed in the tax number field
    # ------------------------------------------------------------------
    def test_a_name_in_the_tax_number_field_is_still_the_vendor(self):
        vendor = self._vendor('Ficticia Extranjera, L.L.C.', 'FICTICIA EXTRANJERA')
        before = self.Partner.search_count([])
        for vat, name in (
            ('', 'Ficticia Extranjera, L.L.C.'),
            ('', 'FICTICIA EXTRANJERA'),
            ('EU372041234', 'Ficticia Extranjera, L.L.C.'),
            ('92-1234567', 'Ficticia Extranjera LLC'),
            ('FICTICIA EXTRANJERA', 'Ficticia Extranjera'),
        ):
            partner, _reasons = self._document(vat, name)._resolve_partner_unattended()
            self.assertEqual(partner, vendor, (vat, name))

        document = self._document('EU372041234', 'Ficticia Extranjera LLC')
        note = document._settle_webhook()

        self.assertEqual(document.partner_id, vendor)
        self.assertEqual(self.Partner.search_count([]), before)
        self.assertEqual(document.move_id.state, 'draft')
        self.assertIn('add the tax number', note)

    # ------------------------------------------------------------------
    # 3. Archived vendors
    # ------------------------------------------------------------------
    def test_an_archived_vendor_is_used_for_review_rather_than_duplicated(self):
        archived = self._vendor('Ficticia Archivada SL', CIF_A)
        archived.active = False
        before = self.Partner.with_context(active_test=False).search_count([])
        document = self._document('ES' + CIF_A, 'Ficticia Archivada, S.L.')

        note = document._settle_webhook()

        self.assertEqual(document.partner_id, archived)
        self.assertEqual(document.move_id.state, 'draft')
        self.assertIn('archived', note)
        self.assertEqual(self.Partner.with_context(active_test=False).search_count([]), before)

    def test_an_active_vendor_wins_over_an_archived_one(self):
        archived = self._vendor('Ficticia Archivada SL', CIF_A)
        archived.active = False
        active = self._vendor('Ficticia Activa SL', CIF_A)

        partner, reasons = self._document('ES' + CIF_A, 'Cualquiera')._resolve_partner_unattended()

        self.assertEqual(partner, active)
        self.assertFalse(reasons)

    # ------------------------------------------------------------------
    # 4. A foreign number kept without its prefix
    # ------------------------------------------------------------------
    def test_a_foreign_number_kept_bare_is_found_with_its_prefix(self):
        vendor = self._vendor('Ficticia Portugal Lda', '501234567',
                              country_id=self.env.ref('base.pt').id)

        partner, reasons = self._document('PT501234567', 'Nombre comercial distinto')._resolve_partner_unattended()

        self.assertEqual(partner, vendor)
        self.assertFalse(reasons)
        # The same digits behind another country's prefix are another number
        self.assertNotIn(vendor, self.Document._partners_by_vat('DE501234567', self.company))

    # ------------------------------------------------------------------
    # 5. Totals that were not read
    # ------------------------------------------------------------------
    def test_totals_not_read_keep_the_lines_and_are_said(self):
        self._vendor('Ficticia Uno SL', CIF_A)
        document = self._document(CIF_A, 'Ficticia Uno SL', amount_untaxed=0.0, amount_total=0.0,
                                  items=[{'description': 'Linea', 'quantity': 2, 'unit_price': 50.0}])

        note = document._settle_webhook()

        self.assertEqual(document.move_id.state, 'draft')
        self.assertAlmostEqual(document.move_id.amount_untaxed, 100.0, places=2)
        self.assertIn('not read', note)

    # ------------------------------------------------------------------
    # 6. A bill Odoo refuses to post
    # ------------------------------------------------------------------
    def test_a_bill_that_cannot_be_posted_stays_in_draft_for_review(self):
        self._vendor('Ficticia Uno SL', CIF_A)
        document = self._document(CIF_A, 'Ficticia Uno SL',
                                  totals={'net_subtotal': 100.0, 'tax_total': 21.0, 'total': 121.0})
        Move = type(self.env['account.move'])

        with patch.object(Move, 'action_post', side_effect=RuntimeError('the ledger is closed')):
            note = document._settle_webhook()

        move = document.move_id
        self.assertTrue(move)
        self.assertEqual(move.state, 'draft')
        self.assertIn('review', note)
        self.assertIn('the ledger is closed', note)
        self.assertTrue(any('the ledger is closed' in (message.body or '') for message in move.message_ids))

    # ------------------------------------------------------------------
    # 7. Payments: never with the old secret, never from another company
    # ------------------------------------------------------------------
    def test_a_call_with_the_old_secret_never_pays(self):
        self.company.easyocr_webhook_mark_paid = True
        vendor = self._vendor('Ficticia Uno SL', CIF_A)
        document = self._document(CIF_A, 'Ficticia Uno SL',
                                  totals={'net_subtotal': 100.0, 'tax_total': 21.0, 'total': 121.0})

        note = document._settle_webhook(allow_payment=False)

        self.assertEqual(document.move_id.state, 'posted')
        self.assertFalse(self.env['account.payment'].search([('partner_id', '=', vendor.id)]))
        self.assertIn('old shared secret', note)

    def test_a_bank_account_of_another_company_is_not_used(self):
        other = self.env['res.company'].create({'name': 'Ficticia Otra Empresa'})
        move = SimpleNamespace(company_id=other, state='posted', amount_residual=10.0)

        reason = self.Document._register_webhook_payment(move, self.company)

        self.assertIn('another company', reason)

    # ------------------------------------------------------------------
    # 10. Two webhooks of one new vendor
    # ------------------------------------------------------------------
    def test_a_vendor_held_by_another_call_is_not_created_twice(self):
        set_param_value(self.env, 'easyocr.webhook_lock_timeout', '1')
        document = self._document(CIF_B, 'Ficticia Concurrente SL')
        before = self.Partner.search_count([])
        other = db_connect(self.env.cr.dbname).cursor()
        try:
            other.execute(
                "INSERT INTO easyocr_vendor_claim (company_id, key, claimed_at) "
                "VALUES (%s, %s, now() at time zone 'UTC')",
                [self.company.id, 'vat:' + CIF_B],
            )
            with self.assertRaises(Exception) as caught:
                document._settle_webhook()
        finally:
            other.rollback()
            other.close()

        self.assertTrue(is_concurrency_error(caught.exception), caught.exception)
        self.assertFalse(document.move_id)
        self.assertEqual(self.Partner.search_count([]), before)

    def test_a_free_vendor_is_claimed_and_created_once(self):
        document = self._document(CIF_B, 'Ficticia Libre SL')

        document._settle_webhook()

        self.assertEqual(document.partner_id.name, 'Ficticia Libre SL')
        self.env.cr.execute(
            "SELECT count(*) FROM easyocr_vendor_claim WHERE company_id = %s AND key = %s",
            [self.company.id, 'vat:' + CIF_B],
        )
        self.assertEqual(self.env.cr.fetchone()[0], 1)

    # ------------------------------------------------------------------
    # 9 and 11. What is kept of a call, and for how long
    # ------------------------------------------------------------------
    def _log(self, document=False, days_old=0):
        log = self.env['easyocr.webhook.log'].create({
            'event': 'document.completed', 'status': 'ok', 'message': 'x',
            'payload': '{"supplier": "Ficticia Persona"}',
            'document_id': document.id if document else False,
        })
        if days_old:
            log.flush_recordset()
            self.env.cr.execute(
                "UPDATE easyocr_webhook_log SET create_date = %s WHERE id = %s",
                [fields.Datetime.now() - timedelta(days=days_old), log.id],
            )
            log.invalidate_recordset()
        return log

    def test_old_calls_are_forgotten_every_day(self):
        old = self._log(days_old=31)
        recent = self._log(days_old=5)

        self.env['easyocr.webhook.log']._cron_purge()

        self.assertFalse(old.exists())
        self.assertTrue(recent.exists())

        set_param_value(self.env, 'easyocr.webhook_log_days', '3')
        self.env['easyocr.webhook.log']._cron_purge()
        self.assertFalse(recent.exists())

    def test_the_purge_runs_on_a_daily_cron(self):
        cron = self.env.ref('easyocr.ir_cron_easyocr_webhook_log_purge')
        self.assertEqual((cron.interval_number, cron.interval_type), (1, 'days'))
        self.assertTrue(cron.active)

    def test_deleting_the_bill_forgets_the_body_of_the_call(self):
        self._vendor('Ficticia Uno SL', CIF_A)
        document = self._document(CIF_A, 'Ficticia Uno SL',
                                  totals={'net_subtotal': 100.0, 'tax_total': 21.0, 'total': 999.0})
        document._settle_webhook()
        self.assertEqual(document.move_id.state, 'draft')
        log = self._log(document)

        document.move_id.unlink()

        self.assertFalse(log.payload)
        self.assertTrue(log.exists())

    def test_deleting_the_document_forgets_the_body_of_the_call(self):
        document = self._document(CIF_A, 'Ficticia Uno SL')
        log = self._log(document)

        document.unlink()

        self.assertFalse(log.payload)
