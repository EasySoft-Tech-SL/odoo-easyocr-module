# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

"""The vendor of a bill nobody looks at before it is made: the webhook path.

Port of EasyOCR for Dolibarr 2.8.2 and 2.8.3. Every tax number here is made up
and built by ``_cif`` / ``_dni`` with the right control character, so none of
them is anybody's.
"""

import json
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.easyocr.models import easyocr_tax_id as tax_ids


def _cif(letter, digits, as_letter=False):
    """A CIF with a valid control: ``_cif('B', '7654321')``."""
    total = 0
    for position, char in enumerate(digits, start=1):
        digit = int(char)
        if position % 2 == 1:
            digit *= 2
            digit = digit // 10 + digit % 10
        total += digit
    control = (10 - total % 10) % 10
    return letter + digits + ('JABCDEFGHI'[control] if as_letter else str(control))


def _dni(number):
    """A DNI with its valid letter: ``_dni('04247123')``."""
    return number + tax_ids.DNI_LETTERS[int(number) % 23]


def _broken(tax_id):
    """The same tax number with a wrong control character."""
    last = tax_id[-1]
    if last.isdigit():
        return tax_id[:-1] + str((int(last) + 1) % 10)
    return tax_id[:-1] + ('A' if last != 'A' else 'B')


CIF_A = _cif('B', '7654321')
CIF_B = _cif('B', '1357913')
CIF_LETTER = _cif('Q', '2810040', as_letter=True)


@tagged('post_install', '-at_install')
class TestEasyocrTaxIds(TransactionCase):
    """The comparisons, on their own."""

    def test_the_generated_numbers_are_valid(self):
        for tax_id in (CIF_A, CIF_B, CIF_LETTER, _dni('04247123'), 'X1234567L', 'K1234567L'):
            self.assertTrue(tax_ids.is_valid_spanish_tax_id(tax_id), tax_id)

    def test_a_wrong_control_character_is_caught(self):
        for tax_id in (CIF_A, CIF_LETTER, _dni('04247123'), 'X1234567L'):
            self.assertFalse(tax_ids.is_valid_spanish_tax_id(_broken(tax_id)), tax_id)

    def test_the_forms_of_one_number(self):
        variants = tax_ids.tax_id_variants('ES ' + CIF_A[0] + '-' + CIF_A[1:])
        self.assertIn(CIF_A, variants)
        self.assertIn('ES' + CIF_A, variants)
        self.assertIn('ES' + CIF_A, tax_ids.tax_id_variants(CIF_A))
        self.assertIn(CIF_A, tax_ids.tax_id_variants('CIF: ' + CIF_A))

    def test_a_dni_without_its_zero_is_searched_with_it_but_not_rewritten(self):
        dni = _dni('04247123')
        variants = tax_ids.tax_id_variants(dni[1:])
        self.assertEqual(variants[0], dni[1:])
        self.assertIn(dni, variants)
        self.assertEqual(tax_ids.tax_id_key(dni[1:]), tax_ids.tax_id_key(dni))

    def test_the_bare_number_is_only_offered_for_spain_and_greece(self):
        self.assertNotIn('123456789', tax_ids.tax_id_variants('DE123456789'))
        self.assertIn('123456789', tax_ids.tax_id_variants('EL123456789'))
        self.assertIn('GR123456789', tax_ids.tax_id_variants('EL123456789'))

    def test_what_counts_as_misread(self):
        bad = _broken(CIF_A)
        self.assertTrue(tax_ids.tax_id_looks_invalid('ES' + bad))
        self.assertTrue(tax_ids.tax_id_looks_invalid(bad, 'España'))
        self.assertTrue(tax_ids.tax_id_looks_invalid(bad, '', 'ES'))
        # Foreign, or with nothing that says Spanish: not judged
        self.assertFalse(tax_ids.tax_id_looks_invalid(bad, 'France'))
        self.assertFalse(tax_ids.tax_id_looks_invalid(bad, '', 'FR'))
        self.assertFalse(tax_ids.tax_id_looks_invalid('FR' + bad))
        # Nine digits and no letter is a foreign number without its prefix
        self.assertFalse(tax_ids.tax_id_looks_invalid('123456789', 'ES', 'ES'))
        self.assertFalse(tax_ids.tax_id_looks_invalid(CIF_A, 'ES', 'ES'))

    def test_the_legal_form_does_not_count_in_a_name(self):
        self.assertEqual(tax_ids.name_core('Ficticia Uno, S.L.'), 'FICTICIAUNO')
        self.assertEqual(tax_ids.name_core('FICTICIA UNO SLU'), 'FICTICIAUNO')
        self.assertEqual(tax_ids.name_core('Ficticia Uno Sociedad Limitada'), 'FICTICIAUNO')
        self.assertEqual(tax_ids.name_core('Ficticia Uno GmbH'), 'FICTICIAUNO')
        self.assertNotEqual(tax_ids.name_core('Ficticia Uno Dos SL'), 'FICTICIAUNO')
        # Never the whole name
        self.assertEqual(tax_ids.name_core('S.L.'), 'SL')

    def test_the_header_totals(self):
        self.assertIsNone(tax_ids.header_totals_mismatch(100.0, 21.0, 121.0))
        # Surcharge and withholding, the total after or before the withholding
        self.assertIsNone(tax_ids.header_totals_mismatch(100.0, 21.0, 111.2, 5.2, 15.0))
        self.assertIsNone(tax_ids.header_totals_mismatch(100.0, 21.0, 126.2, 5.2, 15.0))
        # Within five cents
        self.assertIsNone(tax_ids.header_totals_mismatch(100.0, 21.0, 121.04))
        self.assertEqual(tax_ids.header_totals_mismatch(100.0, 21.0, 112.1), 121.0)
        # An amount that was not read is not checked
        self.assertIsNone(tax_ids.header_totals_mismatch(100.0, None, 500.0))


@tagged('post_install', '-at_install')
class TestEasyocrUnattendedVendor(TransactionCase):
    """Who the webhook bill goes to, and when it is left for a person."""

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
            'name': 'Banco desatendido', 'code': 'WHUV', 'type': 'bank',
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
        values.setdefault('name', 'WH/0001')
        values.setdefault('state', 'processed')
        values.setdefault('amount_untaxed', 100.0)
        values.setdefault('amount_total', 121.0)
        document = self.Document.create(dict(values, partner_vat=vat, partner_name=name,
                                             last_extraction=json.dumps({'structured_data': structured})))
        if items:
            document._apply_lines(items)
        return document

    # ------------------------------------------------------------------
    # By the tax number, in any of its forms
    # ------------------------------------------------------------------
    def test_the_prefix_on_either_side_finds_the_vendor(self):
        vendor = self._vendor('Ficticia Uno SL', CIF_A[0] + '-' + CIF_A[1:])
        other = self._vendor('Ficticia Dos SL', 'ES' + CIF_B)

        self.assertEqual(self._document('ES' + CIF_A, 'X')._resolve_partner_unattended()[0], vendor)
        self.assertEqual(self._document(CIF_B, 'X')._resolve_partner_unattended()[0], other)
        self.assertEqual(self._document('CIF: ' + CIF_B, 'X')._resolve_partner_unattended()[0], other)

    def test_a_dni_without_its_zero_finds_the_vendor(self):
        dni = _dni('04247123')
        vendor = self._vendor('Autonomo Ficticio', dni)

        partner, reasons = self._document(dni[1:], 'Otro nombre')._resolve_partner_unattended()

        self.assertEqual(partner, vendor)
        self.assertFalse(reasons)

    def test_the_viewer_finds_it_too(self):
        """The lookup on screen only gains the normalization."""
        vendor = self._vendor('Ficticia Uno SL', 'ES' + CIF_A)

        # A name that finds nobody, so only the number can find it
        self.assertEqual(self._document(CIF_A, 'Nombre que no casa')._resolve_partner(), vendor)
        self.assertEqual(self.Document.action_check_supplier(vat=CIF_A)['id'], vendor.id)

    def test_a_contact_person_does_not_make_two_candidates(self):
        vendor = self._vendor('Ficticia Uno SL', 'ES' + CIF_A)
        contact = self.Partner.create({'name': 'Persona de contacto', 'parent_id': vendor.id})
        self.assertEqual(contact.vat, vendor.vat)

        # A name that matches neither, so two candidates would be reported
        partner, reasons = self._document(CIF_A, 'Nombre que no casa')._resolve_partner_unattended()

        self.assertEqual(partner, vendor)
        self.assertFalse(reasons)

    def test_several_with_the_number_take_the_one_with_the_name(self):
        self._vendor('Ficticia Antigua SL', CIF_A)
        named = self._vendor('Ficticia Uno SL', 'ES' + CIF_A)

        partner, reasons = self._document(CIF_A, 'FICTICIA UNO, S.L.')._resolve_partner_unattended()

        self.assertEqual(partner, named)
        self.assertFalse(reasons)

    def test_several_with_the_number_and_no_name_take_the_oldest_and_say_so(self):
        oldest = self._vendor('Ficticia Antigua SL', CIF_A)
        self._vendor('Ficticia Nueva SL', 'ES' + CIF_A)

        partner, reasons = self._document(CIF_A, 'Nombre que no casa')._resolve_partner_unattended()

        self.assertEqual(partner, oldest)
        self.assertEqual(len(reasons), 1)
        self.assertIn(CIF_A, reasons[0])

    def test_your_own_number_is_refused_with_or_without_prefix(self):
        self.company.partner_id.with_context(no_vat_validation=True).vat = 'ES' + CIF_B

        with self.assertRaises(UserError):
            self._document(CIF_B, 'Nosotros')._resolve_partner_unattended()

    # ------------------------------------------------------------------
    # By the name, and only the whole name
    # ------------------------------------------------------------------
    def test_without_the_number_the_exact_name_finds_it_for_review(self):
        vendor = self._vendor('Ficticia Uno, S.L.')

        partner, reasons = self._document(CIF_A, 'FICTICIA UNO SL')._resolve_partner_unattended()

        self.assertEqual(partner, vendor)
        self.assertEqual(len(reasons), 1)

    def test_part_of_a_name_is_not_a_match(self):
        self._vendor('Ficticia Uno Distribuciones SL')

        partner, _reasons = self._document(CIF_A, 'Ficticia Uno SL')._resolve_partner_unattended()

        self.assertFalse(partner)

    def test_a_namesake_with_another_valid_number_is_another_company(self):
        self._vendor('Ficticia Uno SL', 'ES' + CIF_B)

        partner, _reasons = self._document(CIF_A, 'Ficticia Uno SL')._resolve_partner_unattended()

        self.assertFalse(partner)

    def test_a_namesake_with_a_misread_number_on_file_is_the_same_company(self):
        vendor = self._vendor('Ficticia Uno SL', _broken(CIF_A))

        partner, _reasons = self._document(CIF_A, 'Ficticia Uno SL')._resolve_partner_unattended()

        self.assertEqual(partner, vendor)

    # ------------------------------------------------------------------
    # A misread number
    # ------------------------------------------------------------------
    def test_a_misread_number_is_not_searched_and_the_name_decides(self):
        # The duplicate an older version made from the same misreading
        self._vendor('Ficticia Uno Duplicado SL', _broken(CIF_A))
        real = self._vendor('Ficticia Uno SL', CIF_A)

        partner, reasons = self._document(_broken(CIF_A), 'Ficticia Uno SL')._resolve_partner_unattended()

        self.assertEqual(partner, real)
        self.assertIn(_broken(CIF_A), reasons[0])

    def test_a_misread_number_with_nobody_of_that_name_creates_it_as_read(self):
        document = self._document(_broken(CIF_A), 'Ficticia Nueva SL')

        note = document._settle_webhook()

        self.assertEqual(document.partner_id.name, 'Ficticia Nueva SL')
        self.assertEqual(document.partner_id.vat, _broken(CIF_A))
        self.assertEqual(document.move_id.state, 'draft')
        self.assertIn('review', note)

    # ------------------------------------------------------------------
    # What it does to the bill
    # ------------------------------------------------------------------
    def test_with_nothing_to_review_the_bill_is_posted_as_configured(self):
        self._vendor('Ficticia Uno SL', CIF_A)
        document = self._document(CIF_A, 'Ficticia Uno SL',
                                  totals={'net_subtotal': 100.0, 'tax_total': 21.0, 'total': 121.0})

        document._settle_webhook()

        self.assertEqual(document.move_id.state, 'posted')

    def test_something_to_review_leaves_a_draft_unpaid_with_the_reasons(self):
        self.company.easyocr_webhook_mark_paid = True
        self._vendor('Ficticia Uno, S.L.')
        document = self._document(CIF_A, 'Ficticia Uno SL')

        note = document._settle_webhook()

        move = document.move_id
        self.assertEqual(move.state, 'draft')
        self.assertFalse(self.env['account.payment'].search([('partner_id', '=', move.partner_id.id)]))
        self.assertIn(CIF_A, note)
        self.assertTrue(any(CIF_A in (message.body or '') for message in move.message_ids))

    def test_totals_that_do_not_add_up_leave_a_draft(self):
        self._vendor('Ficticia Uno SL', CIF_A)
        document = self._document(CIF_A, 'Ficticia Uno SL',
                                  totals={'net_subtotal': 100.0, 'tax_total': 21.0, 'total': 112.1})

        note = document._settle_webhook()

        self.assertEqual(document.move_id.state, 'draft')
        self.assertIn('112.1', note)

    def test_surcharge_and_withholding_are_read_from_the_service_names(self):
        self._vendor('Ficticia Uno SL', CIF_A)
        document = self._document(CIF_A, 'Ficticia Uno SL', totals={
            'net_subtotal': 100.0, 'tax_total': 21.0, 'surcharge_total': 5.2,
            'withholding_total': 15.0, 'total': 111.2,
        })

        self.assertFalse(document._review_totals())

    def test_lines_that_do_not_add_up_to_the_base_are_said(self):
        document = self._document(CIF_A, 'Ficticia Uno SL', totals={'net_subtotal': 100.0},
                                  items=[{'description': 'Uno', 'quantity': 1, 'unit_price': 60.0}])

        reasons = document._review_totals()

        self.assertEqual(len(reasons), 1)
        self.assertIn('60.0', reasons[0])

    def test_a_refused_document_leaves_no_vendor_and_no_new_supplier(self):
        """A customer with the number only becomes a vendor when a bill is made."""
        self.company.partner_id.with_context(no_vat_validation=True).vat = 'ES' + CIF_B
        customer = self.Partner.create({'name': 'Cliente Ficticio SL', 'customer_rank': 1})
        customer.with_context(no_vat_validation=True).vat = CIF_A
        document = self._document(CIF_A, 'Cliente Ficticio SL', customer_vat='ES' + _cif('A', '2468024'))
        before = self.Partner.search_count([])

        note = document._settle_webhook()

        self.assertFalse(document.move_id)
        self.assertIn('could not be created', note)
        self.assertEqual(customer.supplier_rank, 0)
        self.assertEqual(self.Partner.search_count([]), before)

    def test_a_vendor_created_for_a_bill_that_fails_is_undone(self):
        document = self._document(CIF_A, 'Ficticia Nueva SL')
        with patch.object(type(self.env['account.move']), 'create', side_effect=UserError('no')):
            note = document._settle_webhook()

        self.assertIn('could not be created', note)
        self.assertFalse(self.Partner.search([('name', '=', 'Ficticia Nueva SL')]))

    # ------------------------------------------------------------------
    # 2.8.3: a payment that fails half way
    # ------------------------------------------------------------------
    def test_a_payment_that_fails_half_way_is_undone_and_said(self):
        self.company.easyocr_webhook_mark_paid = True
        vendor = self._vendor('Ficticia Uno SL', CIF_A)
        document = self._document(CIF_A, 'Ficticia Uno SL')
        Register = type(self.env['account.payment.register'])
        original = Register._create_payments

        def half_way(wizard):
            original(wizard)
            raise UserError('refused by the bank')

        with patch.object(Register, '_create_payments', half_way):
            note = document._settle_webhook()

        move = document.move_id
        self.assertEqual(move.state, 'posted')
        self.assertEqual(move.amount_residual, move.amount_total)
        self.assertFalse(self.env['account.payment'].search([('partner_id', '=', vendor.id)]))
        self.assertIn('refused by the bank', note)
        self.assertTrue(any('pending payment' in (message.body or '') for message in move.message_ids))
