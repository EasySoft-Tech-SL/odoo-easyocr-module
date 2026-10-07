# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License OPL-1 (see LICENSE file).

import json
import logging

import requests

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

SERVICE_PATH = '/api/v1/ocr/file'
DEFAULT_TIMEOUT = 120

# error_code values that mean "send it again". STRUCTURING_TRUNCATED is left out
# on purpose: the model stopped for a reason that will be the same next time.
RETRYABLE_ERROR_CODES = ('OCR_EMPTY', 'PARTIAL_DEGRADATION')


class EasyocrServiceError(Exception):
    """A failure talking to the service, carrying a message fit for the user."""


def _to_float(value, default=0.0):
    """Read a number that may arrive as a string, without blowing up on junk."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class EasyocrExtractor(models.AbstractModel):
    """The client of the EasyOCR extraction service.

    It only knows about the wire: build the request, read the body, and say in
    plain words whether the document could be read. Nothing about documents
    lives here, so the same client can serve the inbox of phase 4 later on.
    """

    _name = 'easyocr.extractor'
    _description = 'EasyOCR Extraction Service Client'

    # ------------------------------------------------------------------
    # The call
    # ------------------------------------------------------------------
    @api.model
    def _service_endpoint(self, company):
        base = (company.easyocr_ai_url or '').strip().rstrip('/')
        return base + SERVICE_PATH

    @api.model
    def _post_file(self, company, content, filename, include_text=False, custom_instructions=None):
        """Send one file and return the parsed body, or raise a readable error.

        The service answers HTTP 200 even when the extraction came out partial,
        so the status code is only the first half of the story; the body is read
        by the caller.
        """
        payload = {'include_text': 'true' if include_text else 'false'}
        if custom_instructions:
            payload['custom_instructions'] = custom_instructions

        timeout = company.easyocr_ai_timeout or DEFAULT_TIMEOUT
        try:
            response = requests.post(
                self._service_endpoint(company),
                headers={'X-API-Key': company.easyocr_ai_apikey or ''},
                files={'file': (filename, content)},
                data=payload,
                timeout=timeout,
            )
        except requests.RequestException as error:
            _logger.warning('EasyOCR service unreachable at %s: %s', company.easyocr_ai_url, error)
            raise EasyocrServiceError(
                _("The extraction service could not be reached (%(error)s).", error=error)
            ) from error

        if not 200 <= response.status_code < 300:
            raise EasyocrServiceError(self._http_error_message(response))

        try:
            return response.json()
        except ValueError as error:
            raise EasyocrServiceError(
                _("The extraction service answered with something that is not JSON.")
            ) from error

    @api.model
    def _http_error_message(self, response):
        """Turn a failure status into a sentence the user can act on."""
        status = response.status_code
        if status == 401:
            return _("The extraction service requires an API key, and none was sent.")
        if status == 403:
            return _("The extraction service rejected the API key.")
        if status == 413:
            return _("The file is too large for the extraction service.")
        if status == 422:
            return _("The extraction service could not read the request.")
        if status == 503:
            message = _("The extraction service is down or busy.")
            retry_after = response.headers.get('Retry-After') if response.headers else None
            if retry_after:
                message = _(
                    "%(message)s Try again in %(seconds)s seconds.",
                    message=message,
                    seconds=retry_after,
                )
            return message
        return _(
            "The extraction service answered with an unexpected error (HTTP %(status)s).",
            status=status,
        )

    # ------------------------------------------------------------------
    # Reading the answer
    # ------------------------------------------------------------------
    @api.model
    def extract(self, company, content, filename, include_text=False, custom_instructions=None):
        """Send a file and normalize whatever comes back into one result.

        Returns a dict: ``ok`` says whether the document could be read, ``reason``
        carries the sentence to show when it could not, ``retryable`` says whether
        sending it again is worth anything, ``data`` is the ``structured_data``
        block and ``raw`` is the whole body, kept for the document to log.
        """
        result = {
            'ok': False,
            'reason': False,
            'error_code': False,
            'retryable': False,
            'data': {},
            'confidence': 0.0,
            'raw': False,
        }

        try:
            body = self._post_file(
                company, content, filename,
                include_text=include_text,
                custom_instructions=custom_instructions,
            )
        except EasyocrServiceError as error:
            # A refused or failed call is always worth another try later.
            result['reason'] = str(error)
            result['retryable'] = True
            return result

        if not isinstance(body, dict):
            result['reason'] = _("The extraction service returned an unexpected response.")
            return result

        result['raw'] = body
        result['confidence'] = _to_float(body.get('confidence'))

        data = body.get('structured_data')
        if not isinstance(data, dict):
            result['reason'] = _("The extraction service returned no data for this document.")
            return result

        # The model did not emit valid JSON: the body looks fine but carries only
        # the raw text and the parser error, which is a failure however it is dressed.
        if data.get('parse_error'):
            result['error_code'] = 'PARSE_ERROR'
            result['reason'] = _(
                "The extraction service could not make sense of the document (%(error)s).",
                error=data['parse_error'],
            )
            return result

        error_code = body.get('error_code')
        if body.get('status') == 'partial' or error_code:
            result['error_code'] = error_code
            result['retryable'] = error_code in RETRYABLE_ERROR_CODES
            result['reason'] = self._partial_reason(body)
            return result

        result['ok'] = True
        result['data'] = data
        return result

    @api.model
    def _partial_reason(self, body):
        """Explain a partial extraction and whether running it again would help."""
        code = body.get('error_code') or ''
        detail = body.get('error_message') or body.get('structuring_error') or ''

        message = _("The extraction service could only read the document in part.")
        if code:
            message += ' (%s)' % code
        if detail:
            message += ' %s' % detail
        if code in RETRYABLE_ERROR_CODES:
            message += ' ' + _("Sending it again may help.")
        elif code == 'STRUCTURING_TRUNCATED':
            message += ' ' + _("Sending it again will not change the result.")
        return message


class EasyocrDocument(models.Model):
    """Wiring the extraction service to a document of the inbox."""

    _inherit = 'easyocr.document'

    last_extraction = fields.Text(
        string='Last Extraction Response',
        readonly=True,
        copy=False,
        help='Raw answer of the service, kept for support and troubleshooting.',
    )
    extraction_confidence = fields.Float(
        string='Extraction Confidence',
        readonly=True,
        copy=False,
        digits=(3, 2),
        help='How sure the service was of what it read, from 0 to 1.',
    )

    def action_extract(self):
        """Read the attached file with the service and fill in what it returns.

        A failure is written to the document instead of raised: the file stays
        visible with the reason it could not be read, ready to be tried again.
        """
        self.ensure_one()
        company = self.company_id or self.env.company

        if not company.easyocr_ai_enabled:
            return self._fail_extraction(
                _("AI extraction is off. Turn it on in the EasyOCR settings.")
            )

        attachment = self.attachment_id
        if not attachment:
            return self._fail_extraction(_("This document has no file attached."))

        try:
            content = attachment.raw
        except Exception:  # noqa: BLE001 - any read failure is the same to the user
            _logger.exception('Could not read the file of OCR document %s', self.id)
            content = False
        if not content:
            return self._fail_extraction(_("The attached file is empty or cannot be read."))

        try:
            result = self.env['easyocr.extractor'].extract(
                company, content, attachment.name or self.name,
            )
        except Exception:  # noqa: BLE001 - the user must never get a dialog
            _logger.exception('Unexpected error extracting OCR document %s', self.id)
            return self._fail_extraction(
                _("The extraction failed unexpectedly. The server log has the detail.")
            )

        if result.get('raw'):
            self.last_extraction = json.dumps(result['raw'], indent=2, ensure_ascii=False)
        self.extraction_confidence = result.get('confidence') or 0.0

        if not result.get('ok'):
            return self._fail_extraction(
                result.get('reason') or _("The document could not be read.")
            )

        self._apply_extraction(result['data'])
        self.state = 'processed'
        self.error_message = False
        return self._extraction_notification(
            'success', _("The document was read.")
        )

    # ------------------------------------------------------------------
    # Filling the document
    # ------------------------------------------------------------------
    def _apply_extraction(self, data):
        """Copy the fields we use out of the structured data.

        Only what the service actually returned is written, so a missing value
        never wipes something already typed by hand.
        """
        self.ensure_one()
        values = {}

        supplier = data.get('supplier') or {}
        if supplier.get('name'):
            values['partner_name'] = supplier['name']
        if supplier.get('tax_id'):
            values['partner_vat'] = supplier['tax_id']

        if data.get('document_number'):
            values['ref'] = data['document_number']

        document_date = self._clean_date(data.get('issue_date'))
        if document_date:
            values['document_date'] = document_date

        totals = data.get('totals') or {}
        if totals.get('net_subtotal') is not None:
            values['amount_untaxed'] = _to_float(totals['net_subtotal'])
        if totals.get('total') is not None:
            values['amount_total'] = _to_float(totals['total'])

        if values:
            self.write(values)

    @api.model
    def _clean_date(self, value):
        """Keep a date the model can store, drop anything else quietly."""
        try:
            return fields.Date.to_date(value)
        except (ValueError, TypeError):
            return False

    def _fail_extraction(self, message):
        self.state = 'error'
        self.error_message = message
        return self._extraction_notification('warning', message)

    def _extraction_notification(self, kind, message):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': kind,
                'message': message,
                'sticky': False,
            },
        }
