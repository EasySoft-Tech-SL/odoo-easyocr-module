# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

import base64
import io
import json
import re
import time
from unittest.mock import patch

from PIL import Image

from odoo.addons.easyocr.controllers import expense
from odoo.addons.easyocr.models.easyocr_extractor import EasyocrExtractor
from odoo.tests import tagged
from odoo.tests.common import HttpCase

PAGE_URL = '/easyocr/capture'
UPLOAD_URL = '/easyocr/capture/upload'
MANIFEST_URL = '/easyocr/capture/manifest.json'
ICON_URL = '/easyocr/capture/icon.svg'
SERVICE_WORKER_URL = '/easyocr/capture/sw.js'

CSRF_RE = re.compile(r'name="csrf_token" value="([^"]+)"')

def _jpeg():
    """A real JPEG, small enough to build here: the upload is read with Pillow,
    so a made up file would not do."""
    buffer = io.BytesIO()
    Image.new('RGB', (60, 40), 'white').save(buffer, format='JPEG')
    return buffer.getvalue()


# The photo of a receipt, the same one every test sends.
JPEG_BYTES = _jpeg()


@tagged('post_install', '-at_install')
class TestEasyocrExpenseCapture(HttpCase):
    """The page an employee photographs a receipt with."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Inbox = cls.env['easyocr.inbox.item']
        cls.Document = cls.env['easyocr.document']
        cls.admin = cls.env.ref('base.user_admin')

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _login(self):
        """Open a session as an employee who may file documents."""
        self.authenticate(self.admin.login, 'whatever')

    def _csrf(self):
        page = self.url_open(PAGE_URL)
        match = CSRF_RE.search(page.text)
        self.assertTrue(match, "The capture page carried no CSRF token.")
        return match.group(1)

    def _upload(self, content=None, filename='receipt-20260101-1200.jpg',
                mimetype='image/jpeg', token=None):
        return self.url_open(
            UPLOAD_URL,
            data={'csrf_token': self._csrf() if token is None else token},
            files={'image': (filename, JPEG_BYTES if content is None else content, mimetype)},
        )

    # ------------------------------------------------------------------
    # Getting to the page
    # ------------------------------------------------------------------
    def test_the_page_answers_an_employee_with_a_session(self):
        self._login()

        response = self.url_open(PAGE_URL)

        self.assertEqual(response.status_code, 200)
        # Asserted on the ids the page's own JavaScript drives, never on the
        # wording: the copy is translated, so checking it in English passes
        # only on an English database and fails on every other language.
        self.assertIn('id="easyocr_capture_shoot"', response.text)
        self.assertIn('id="easyocr_capture_pick"', response.text)
        self.assertIn('id="easyocr_capture_form"', response.text)
        # The page is an app: without the manifest and the script it is only a
        # form, and the whole phase is gone without anything failing loudly.
        self.assertIn('rel="manifest"', response.text)
        self.assertIn('expense_capture.js', response.text)
        # The one thing the page must never be served without.
        self.assertEqual(response.headers.get('X-Content-Type-Options'), 'nosniff')

    def test_the_page_is_closed_without_a_session(self):
        """No login, no page: the photo of a receipt is nobody else's business."""
        response = self.url_open(PAGE_URL, allow_redirects=False)

        self.assertEqual(response.status_code, 303)
        self.assertIn('/web/login', response.headers.get('Location', ''))

    def test_the_upload_is_closed_without_a_session(self):
        before = self.Inbox.search_count([])

        response = self.url_open(
            UPLOAD_URL,
            data={'csrf_token': 'not-a-token'},
            files={'image': ('receipt.jpg', JPEG_BYTES, 'image/jpeg')},
            allow_redirects=False,
        )

        self.assertEqual(response.status_code, 303)
        # Counted against what was already there: a database with files in it is
        # the normal case, and a test that assumes an empty one only passes on a
        # machine nobody has used.
        self.assertEqual(self.Inbox.search_count([]), before)

    # ------------------------------------------------------------------
    # A photo that works
    # ------------------------------------------------------------------
    def test_a_photo_lands_in_the_inbox(self):
        self._login()
        documents_before = self.Document.search_count([])

        response = self._upload()

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body['ok'], body.get('message'))

        item = self.Inbox.browse(body['inbox_item_id'])
        self.assertTrue(item.exists())
        self.assertEqual(item.origin, 'expense-capture')
        self.assertTrue(item.name.endswith('.pdf'), item.name)
        # The tray only takes PDFs, and the viewer paints a PDF, so the photo
        # has to arrive as one.
        self.assertTrue(base64.b64decode(item.datas).startswith(b'%PDF'))

        self.assertTrue(item.document_id)
        self.assertEqual(
            self.Document.search_count([]), documents_before + 1,
        )
        self.assertTrue(item.document_id.attachment_id)

    def test_a_photo_is_not_read_when_the_ai_is_off(self):
        """Nothing leaves the company until it says so: the photo is filed, and
        the page says as much instead of pretending it was read."""
        self._login()
        self.assertFalse(self.env.company.easyocr_ai_enabled)

        response = self._upload()

        body = response.json()
        self.assertTrue(body['ok'], body.get('message'))
        self.assertFalse(body['read'])
        self.assertTrue(body['message'])

    def test_a_photo_is_read_when_the_ai_is_on(self):
        self._login()
        self.env.company.easyocr_ai_enabled = True
        read = {
            'ok': True,
            'reason': False,
            'error_code': False,
            'retryable': False,
            'confidence': 0.91,
            'raw': {'status': 'completed'},
            'data': {
                'supplier': {'name': 'Proveedor de prueba SL', 'tax_id': 'B3186006'},
                'document_number': 'A/123',
                'issue_date': '2026-01-31',
                'totals': {'net_subtotal': 10.0, 'total': 12.1},
            },
        }

        with patch.object(EasyocrExtractor, 'extract', return_value=read):
            response = self._upload()

        body = response.json()
        self.assertTrue(body['ok'], body.get('message'))
        self.assertTrue(body['read'], body.get('message'))
        self.assertEqual(body['document']['vendor'], 'Proveedor de prueba SL')
        self.assertEqual(body['document']['date'], '2026-01-31')
        self.assertAlmostEqual(body['document']['total'], 12.1, places=2)

        document = self.Document.browse(body['document']['id'])
        self.assertEqual(document.state, 'processed')
        self.assertEqual(document.partner_name, 'Proveedor de prueba SL')
        self.assertEqual(document.ref, 'A/123')

    # ------------------------------------------------------------------
    # What is turned away, and why
    # ------------------------------------------------------------------
    def test_a_photo_over_the_limit_is_turned_away_with_a_reason(self):
        self._login()
        before = self.Inbox.search_count([])

        # The ceiling the inbox itself applies, read from there so the two can
        # never drift apart.
        self.assertEqual(expense.MAX_UPLOAD_BYTES, expense.MAX_SIZE_MB * 1024 * 1024)
        with patch.object(expense, 'MAX_UPLOAD_BYTES', 1024):
            response = self._upload(content=JPEG_BYTES + b'\x00' * 2048)

        self.assertEqual(response.status_code, 413)
        body = response.json()
        self.assertFalse(body['ok'])
        self.assertIn(str(expense.MAX_SIZE_MB), body['message'])
        self.assertEqual(self.Inbox.search_count([]), before)

    def test_a_file_that_is_not_a_photo_is_turned_away(self):
        self._login()
        before = self.Inbox.search_count([])

        response = self._upload(content=b'not a photo at all', filename='notes.txt',
                                mimetype='text/plain')

        self.assertEqual(response.status_code, 415)
        body = response.json()
        self.assertFalse(body['ok'])
        self.assertTrue(body['message'])
        self.assertEqual(self.Inbox.search_count([]), before)

    def test_a_file_wearing_a_photo_name_is_turned_away(self):
        """The type is what the browser says; the bytes are what decides."""
        self._login()

        response = self._upload(content=b'PK\x03\x04 a zip called receipt.jpg')

        self.assertEqual(response.status_code, 415)
        self.assertFalse(response.json()['ok'])

    def test_a_call_without_a_photo_is_turned_away(self):
        self._login()

        response = self.url_open(UPLOAD_URL, data={'csrf_token': self._csrf()})

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['ok'])

    def test_the_same_photo_is_not_filed_twice(self):
        """The tray recognises the bytes, so a double tap is not two documents."""
        self._login()
        first = self._upload()
        self.assertTrue(first.json()['ok'])
        before = self.Inbox.search_count([])

        second = self._upload(filename='receipt-20260101-1201.jpg')

        self.assertEqual(second.status_code, 409)
        self.assertFalse(second.json()['ok'])
        self.assertEqual(self.Inbox.search_count([]), before)

    # ------------------------------------------------------------------
    # The file that reaches the tray
    # ------------------------------------------------------------------
    def test_the_same_photo_becomes_the_same_file_every_time(self):
        """The tray tells one file from another by its bytes, so they must not move.

        Pillow stamps the moment it wrote the PDF on the file unless it is told
        not to. Two conversions of the same photo then differ by a second, and
        the tray -- which knows a file by its fingerprint -- files one receipt
        as two documents.
        """
        first = expense.EasyocrExpenseCapture._as_pdf(
            expense.EasyocrExpenseCapture._read_image(JPEG_BYTES),
        )
        # Past the second the stamp would have carried, so that a conversion
        # that still writes one has moved on by the time of the second call.
        time.sleep(1.1)
        second = expense.EasyocrExpenseCapture._as_pdf(
            expense.EasyocrExpenseCapture._read_image(JPEG_BYTES),
        )

        self.assertEqual(first, second)

    # ------------------------------------------------------------------
    # The bits that make it an app
    # ------------------------------------------------------------------
    def test_the_page_carries_the_sentences_its_script_writes(self):
        """The page has no web client behind it, so it cannot translate itself.

        Whatever this block is missing is a sentence that reaches an employee's
        phone in the wrong language -- or as "undefined", since the script reads
        the keys off it by name.
        """
        self._login()

        response = self.url_open(PAGE_URL)

        self.assertIn('id="easyocr_capture_strings"', response.text)
        block = re.search(
            r'<script type="application/json" id="easyocr_capture_strings"[^>]*>(.*?)</script>',
            response.text, re.S,
        )
        self.assertTrue(block, "The page carried no strings block.")
        strings = json.loads(block.group(1))

        for key in (
            'cameraNotReady', 'fileUnreadable', 'photoNotPrepared', 'photoTooBig',
            'sending', 'sendFailed', 'sendFailedShort', 'readTitle', 'savedTitle',
            'labelVendor', 'labelDate', 'labelTotal', 'labelNumber',
        ):
            self.assertIn(key, strings, "The page left %r out." % key)
            self.assertTrue(strings[key], "%r arrived empty." % key)

    def test_the_page_loads_its_script_under_a_version_that_can_change(self):
        """Odoo caches everything under static/ for a week.

        Without something that changes in the URL, a phone that has opened the
        page once keeps running the script it downloaded then -- across an
        update of the module, which is when it matters most.
        """
        self._login()

        response = self.url_open(PAGE_URL)

        match = re.search(r'src="([^"]*expense_capture\.js[^"]*)"', response.text)
        self.assertTrue(match, "The page carried no script tag.")
        url = match.group(1)
        self.assertIn('?v=', url, "The script is loaded without a version.")
        version = url.split('?v=', 1)[1]
        self.assertTrue(version.strip(), "The version in the URL is empty.")
        self.assertNotEqual(version, '0', "The script's digest could not be read.")

    def test_the_manifest_is_served_without_a_session(self):
        """A browser asks for a manifest without the session cookie. Behind the
        login it would be answered with a redirect, and the page would stop
        being installable without anything saying so."""
        response = self.url_open(MANIFEST_URL)

        self.assertEqual(response.status_code, 200)

        self.assertIn('application/manifest+json', response.headers.get('Content-Type', ''))
        manifest = response.json()
        self.assertEqual(manifest['start_url'], '/easyocr/capture')
        self.assertEqual(manifest['display'], 'standalone')
        self.assertTrue(manifest['icons'])

    def test_the_icon_the_manifest_points_at_is_served(self):
        response = self.url_open(ICON_URL)

        self.assertEqual(response.status_code, 200)
        self.assertIn('image/svg+xml', response.headers.get('Content-Type', ''))
        self.assertIn('<svg', response.text)

    def test_the_service_worker_is_served_and_never_caches_a_post(self):
        response = self.url_open(SERVICE_WORKER_URL)

        self.assertEqual(response.status_code, 200)
        self.assertIn('javascript', response.headers.get('Content-Type', ''))
        # The page is one level above the script, so the scope has to be granted.
        self.assertEqual(response.headers.get('Service-Worker-Allowed'), '/easyocr/capture')
        self.assertIn("request.method !== 'GET'", response.text)
        self.assertEqual(response.headers.get('X-Content-Type-Options'), 'nosniff')
