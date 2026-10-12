# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

import functools
import hashlib
import io
import json
import logging
import os

from PIL import Image, ImageOps, UnidentifiedImageError
from markupsafe import Markup

from odoo import _, http
from odoo.exceptions import UserError
from odoo.http import request

from odoo.addons.easyocr.models.easyocr_inbox import MAX_SIZE_MB

_logger = logging.getLogger(__name__)

# The name the tray shows as the origin of the file, next to easyscan or a mail
# gateway: whoever opens the inbox can see the photo came from a phone.
CAPTURE_ORIGIN = 'expense-capture'

# The script the page loads, and the module folder it sits in.
CAPTURE_SCRIPT = '/easyocr/static/src/js/expense_capture.js'
CAPTURE_SCRIPT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'static', 'src', 'js', 'expense_capture.js',
)


@functools.lru_cache(maxsize=1)
def capture_script_version():
    """A token that changes whenever the page's own script does.

    Odoo serves everything under ``static/`` with a week of cache. A phone that
    has opened the page once therefore keeps running that copy of the script
    for seven days -- across an update of the module, which is precisely when it
    must not: the page would talk to a newer server with an older script and
    nothing would say so. Putting the file's own digest in the URL makes the
    address change with the file, so the cached copy can never outlive the code.

    Read once per process: the file cannot change under a running server, and a
    restart is what picks up a deploy anyway.
    """
    try:
        with open(CAPTURE_SCRIPT_PATH, 'rb') as handle:
            return hashlib.sha1(handle.read()).hexdigest()[:12]
    except OSError:
        # A module installed without its script is broken in a louder way than
        # this; the digest only has to be stable, not right.
        _logger.warning("EasyOCR: could not read %s", CAPTURE_SCRIPT_PATH)
        return '0'

# The same ceiling the inbox applies, taken from there so the two can never
# drift apart. The browser resize keeps a photo well under it.
MAX_UPLOAD_BYTES = MAX_SIZE_MB * 1024 * 1024

# What a phone camera and a screenshot produce. HEIC is left out on purpose: it
# is what an iPhone writes, but the browser re-encodes the photo as JPEG before
# uploading, and reading HEIC on the server would need a decoder we would have
# to add as a dependency.
IMAGE_MIMETYPES = ('image/jpeg', 'image/png', 'image/webp')

# The resolution the page is written at. A phone photo carries no page size, and
# the default of 72 dots per inch would turn a 1600 px picture into a 22 inch
# sheet. 150 puts it at a size a PDF reader opens without zooming out.
PDF_RESOLUTION = 150

# The web app icon, drawn here rather than shipped as a file: the module already
# has an icon, but it is 32 px and an installable app needs something that
# survives a home screen. An SVG carries its own size, so one entry is enough.
APP_ICON = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <rect width="512" height="512" rx="96" fill="#2c3e50"/>
  <path d="M170 154h172a34 34 0 0 1 34 34v170a34 34 0 0 1-34 34H170a34 34 0 0 1-34-34V188a34 34
           0 0 1 34-34z" fill="none" stroke="#ffffff" stroke-width="22"/>
  <circle cx="256" cy="262" r="58" fill="none" stroke="#ffffff" stroke-width="22"/>
  <path d="M214 154l18-30h48l18 30" fill="none" stroke="#ffffff" stroke-width="22" stroke-linejoin="round"/>
</svg>
'''

# Network-first: the page is always fetched from the server when there is one,
# and the cache is only what is shown when the phone has no signal. A request
# that is not a GET is never answered from the cache, which is what keeps an
# upload from being replayed with a stale answer.
SERVICE_WORKER = '''// EasyOCR mobile capture service worker.
const CACHE = 'easyocr-capture-v1';

self.addEventListener('install', () => self.skipWaiting());

self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()));

self.addEventListener('fetch', (event) => {
    const request = event.request;
    // Only a GET is cached. Answering a POST from the cache would report a
    // photo as sent when it never left the phone.
    if (request.method !== 'GET' || !request.url.startsWith('http')) {
        return;
    }
    event.respondWith(
        fetch(request)
            .then((response) => {
                const copy = response.clone();
                caches.open(CACHE).then((cache) => cache.put(request, copy)).catch(() => {});
                return response;
            })
            .catch(() => caches.match(request)),
    );
});
'''


class EasyocrExpenseCapture(http.Controller):
    """The page an employee opens on a phone to photograph a receipt.

    It is the whole of phase 6: a camera button, the photo resized before it
    leaves the phone, and the photo filed in the tray with the extraction
    started on it. Nothing is sent anywhere the company has not turned on: the
    AI service is only called when the company enabled it, and the page says so
    when it is off.
    """

    # ------------------------------------------------------------------
    # The page
    # ------------------------------------------------------------------
    @http.route('/easyocr/capture', type='http', auth='user', methods=['GET'])
    def easyocr_capture_page(self, **kwargs):
        response = request.render('easyocr.expense_capture_page', {
            'upload_url': '/easyocr/capture/upload',
            'manifest_url': '/easyocr/capture/manifest.json',
            'icon_url': '/easyocr/capture/icon.svg',
            'service_worker_url': '/easyocr/capture/sw.js',
            'max_size_mb': MAX_SIZE_MB,
            'ai_enabled': request.env.company.easyocr_ai_enabled,
            'strings_json': self._strings_json(),
            'script_url': '%s?v=%s' % (CAPTURE_SCRIPT, capture_script_version()),
        })
        return self._harden(response)

    @staticmethod
    def _page_strings():
        """The sentences the page's own JavaScript writes, in the reader's language.

        The page is a plain script with no Odoo web client behind it -- that is
        the point of it, a phone on a bad connection -- so it has no ``_t`` to
        call and cannot translate anything itself. Everything it says is
        translated here instead and handed over as data, the same way its URLs
        are, so the copy lives in the .po files with the rest and nowhere else.
        """
        return {
            'cameraNotReady': _("The camera is not ready yet. Give it a second."),
            'fileUnreadable': _("That file could not be read as a photo."),
            'photoNotPrepared': _("The photo could not be prepared. Try again."),
            'photoTooBig': _(
                "The photo is still larger than the %(limit)s MB the inbox takes. "
                "Take it from a little further away.",
                limit=MAX_SIZE_MB,
            ),
            'sending': _("Sending the photo…"),
            'sendFailed': _("The photo could not be sent. Check the connection and try again."),
            'sendFailedShort': _("The photo could not be sent."),
            'readTitle': _("Read from the receipt"),
            'savedTitle': _("Saved to the inbox"),
            'labelVendor': _("Vendor"),
            'labelDate': _("Date"),
            'labelTotal': _("Total"),
            'labelNumber': _("Number"),
        }

    @classmethod
    def _strings_json(cls):
        """The same sentences, ready to be dropped into the page.

        ``<`` is escaped because the block sits inside a ``<script>`` and a
        translation carrying ``</script>`` would end it early. JSON itself has
        no such problem: ``\\u003c`` is just a ``<`` to whoever parses it.
        """
        payload = json.dumps(cls._page_strings(), ensure_ascii=False)
        return Markup(payload.replace('<', '\\u003c'))

    # The manifest, the icon and the worker are public on purpose: they hold
    # nothing of anybody's, and the browser asks for a manifest without the
    # session cookie. Behind the session they would answer a redirect to the
    # login page, and the app would quietly stop being installable.
    @http.route('/easyocr/capture/manifest.json', type='http', auth='public', methods=['GET'])
    def easyocr_capture_manifest(self, **kwargs):
        """The manifest that makes the page installable on a home screen."""
        manifest = {
            'name': _('EasyOCR — Capture a receipt'),
            'short_name': _('EasyOCR'),
            'description': _('Photograph a receipt and send it to the EasyOCR inbox.'),
            'start_url': '/easyocr/capture',
            'scope': '/easyocr/capture',
            'display': 'standalone',
            'orientation': 'portrait',
            'background_color': '#ffffff',
            'theme_color': '#2c3e50',
            'icons': [{
                'src': '/easyocr/capture/icon.svg',
                'sizes': 'any',
                'type': 'image/svg+xml',
                'purpose': 'any maskable',
            }],
        }
        return self._harden(request.make_json_response(
            manifest, headers=[('Content-Type', 'application/manifest+json')],
        ))

    @http.route('/easyocr/capture/icon.svg', type='http', auth='public', methods=['GET'])
    def easyocr_capture_icon(self, **kwargs):
        return self._harden(request.make_response(APP_ICON, headers=[
            ('Content-Type', 'image/svg+xml; charset=utf-8'),
            ('Cache-Control', 'public, max-age=86400'),
        ]))

    @http.route('/easyocr/capture/sw.js', type='http', auth='public', methods=['GET'])
    def easyocr_capture_service_worker(self, **kwargs):
        # The script lives one level below the page, so its own directory would
        # cap the scope at /easyocr/capture/ — which does not cover
        # /easyocr/capture, the URL the page is opened at. The header widens it.
        return self._harden(request.make_response(SERVICE_WORKER, headers=[
            ('Content-Type', 'text/javascript; charset=utf-8'),
            ('Service-Worker-Allowed', '/easyocr/capture'),
            # Never let a cached copy of the worker outlive a deploy: a phone
            # holding an old one would keep behaving like the old page.
            ('Cache-Control', 'no-cache, no-store, must-revalidate'),
        ]))

    # ------------------------------------------------------------------
    # The photo
    # ------------------------------------------------------------------
    @http.route(
        '/easyocr/capture/upload',
        type='http',
        auth='user',
        methods=['POST'],
        # The framework refuses a body larger than this before it is read, as a
        # backstop behind the check this controller makes to answer in words.
        max_content_length=MAX_UPLOAD_BYTES + 1024 * 1024,
    )
    def easyocr_capture_upload(self, **kwargs):
        upload = request.httprequest.files.get('image')
        if upload is None or not (upload.filename or '').strip():
            return self._fail(400, _("No photo was sent."))

        mimetype = (upload.mimetype or '').split(';')[0].strip().lower()
        if mimetype not in IMAGE_MIMETYPES:
            return self._fail(
                415,
                _("That file is not a photo. Send a JPEG or a PNG."),
            )

        content = upload.read()
        if not content:
            return self._fail(400, _("The photo arrived empty. Take it again."))

        if len(content) > MAX_UPLOAD_BYTES:
            return self._fail(413, _(
                "The photo is larger than the %(limit)s MB the inbox takes.",
                limit=MAX_SIZE_MB,
            ))

        try:
            image = self._read_image(content)
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
            _logger.warning("EasyOCR capture: could not read an uploaded %s", mimetype)
            return self._fail(415, _("That file could not be read as a photo."))

        filename = self._pdf_name(upload.filename)
        result = request.env['easyocr.inbox.item'].recibir(
            self._as_pdf(image), filename, CAPTURE_ORIGIN,
        )
        if not result['ok']:
            if result['id']:
                return self._fail(409, _(
                    "This photo is already in the inbox. It was not sent twice."
                ))
            return self._fail(400, result['error'] or _("The photo could not be saved."))

        item = request.env['easyocr.inbox.item'].browse(result['id'])
        try:
            item.action_process()
        except UserError as error:
            return self._fail(400, error.args[0] if error.args else str(error))

        document = item.document_id
        if request.env.company.easyocr_ai_enabled:
            # Only when the company asked for it: with AI off the photo stays on
            # our own server and is read by hand, which is the whole point of
            # the setting. A failure here is written on the document, never
            # raised, so the photo is never lost to a bad reading.
            document.action_extract()

        payload = self._capture_result(item, document)
        self._file_as_expense(document, payload)
        return self._json(payload)

    def _file_as_expense(self, document, payload):
        """Put the receipt in the employee's expenses, when the company says so.

        Only a receipt that was actually read: filing an unread photo would push
        a number nobody has looked at into an approval chain. Nothing here ever
        raises, because the photo is already saved and losing it over this would
        be the worst of both.
        """
        company = request.env.company
        if company.easyocr_expense_target != 'expense':
            return
        if document.state != 'processed':
            # No reading, nothing to file: the photo waits in the inbox.
            return

        try:
            expense = document._become_expense()
        except UserError as error:
            reason = error.args[0] if error.args else str(error)
        except Exception:  # noqa: BLE001 - the photo is saved; never lose it here
            _logger.exception("EasyOCR capture: could not file document %s as an expense", document.id)
            reason = _("It could not be filed as an expense.")
        else:
            payload['expense'] = {'id': expense.id, 'state': expense.state}
            payload['message'] = '%s %s' % (payload['message'], _("Filed as an expense."))
            return

        payload['expense'] = False
        payload['message'] = '%s %s' % (payload['message'], reason)

    # ------------------------------------------------------------------
    # Reading the photo, in plain words
    # ------------------------------------------------------------------
    @staticmethod
    def _read_image(content):
        """Open the photo and put it the right way up.

        The browser already bakes the EXIF rotation into the pixels it sends,
        so this only matters for a caller that skips the page; doing it here
        means a sideways receipt can never reach the viewer.
        """
        image = Image.open(io.BytesIO(content))
        image = ImageOps.exif_transpose(image)  # forces the pixels to be read
        if image.mode not in ('RGB', 'L'):
            image = image.convert('RGB')
        return image

    @staticmethod
    def _as_pdf(image):
        """Wrap the photo in a one page PDF, the only thing the tray takes.

        It is also what everything downstream expects: the viewer paints the
        document with PDF.js, and the extraction service reads a PDF the same
        way it reads a scanned invoice.

        The two dates Pillow stamps on the file by default are left out on
        purpose. They carry the very second the PDF was written, so the same
        photo handed over twice a moment apart came out as two files with two
        different fingerprints -- and the tray, which turns a file away by its
        fingerprint, took both and filed one receipt as two documents. Without
        them the bytes depend on the photo and on nothing else.
        """
        buffer = io.BytesIO()
        image.save(
            buffer,
            format='PDF',
            resolution=PDF_RESOLUTION,
            creationDate=None,
            modDate=None,
        )
        return buffer.getvalue()

    @staticmethod
    def _pdf_name(filename):
        """The name the document will carry, with the extension the file has."""
        stem = os.path.splitext(os.path.basename(filename or ''))[0].strip()
        return f'{stem or "receipt"}.pdf'

    def _capture_result(self, item, document):
        """The photo is filed; say what was read from it, or why nothing was."""
        company = request.env.company
        summary = {
            'id': document.id,
            'reference': document.ref or '',
            'vendor': document.partner_name or document.partner_id.display_name or '',
            'date': str(document.document_date or ''),
            'total': document.amount_total or 0.0,
            'currency': document.currency_id.name or '',
            'state': document.state,
            'reason': document.error_message or '',
        }

        if not company.easyocr_ai_enabled:
            message = _(
                "Saved. Reading with AI is off for your company, so the photo is "
                "waiting in the inbox to be read by hand."
            )
            read = False
        elif document.state == 'processed':
            message = _("Saved and read.")
            read = True
        else:
            # The photo is filed either way: what failed is the reading, and the
            # document keeps the reason so it can be looked at or tried again.
            message = document.error_message or _("Saved, but it could not be read.")
            read = False

        return {
            'ok': True,
            'read': read,
            'message': message,
            'inbox_item_id': item.id,
            'document': summary,
        }

    # ------------------------------------------------------------------
    # Answers
    # ------------------------------------------------------------------
    @staticmethod
    def _harden(response):
        """Nothing we serve is ever sniffed into a type it does not declare."""
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    def _json(self, payload, status=200):
        return self._harden(request.make_json_response(payload, status=status))

    def _fail(self, status, message):
        return self._json({'ok': False, 'message': message}, status=status)
