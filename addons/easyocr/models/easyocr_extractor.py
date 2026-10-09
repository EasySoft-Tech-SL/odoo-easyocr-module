# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

import hashlib
import json
import logging

import requests

from odoo import _, api, fields, models

from .easyocr_values import to_float

_logger = logging.getLogger(__name__)

SERVICE_PATH = '/api/v1/ocr/file'

# Who the key belongs to and what is left. It sits behind the key check but not
# behind the plan limiter, so asking costs nothing while answering the two
# questions that come before sending a document at all.
# The full endpoint is /account/me, the one the module this is a port of reads
# its subscription widget from: it carries the plan, the quota (pages used,
# limit, remaining, reset date), the wallet and the features, where /me only
# says who the key is. The same call is what the viewer uses to draw the plan
# and the quota, so it has to be the full one.
ACCOUNT_PATH = '/api/v1/account/me'

# Many files in one call. The service takes them all in a single multipart body
# and answers straight away with a batch to follow, so nothing here waits for a
# reading to finish.
BATCH_PATH = '/api/v1/batch'

DEFAULT_TIMEOUT = 120

# A probe is a courtesy call, not a reading: it should not sit for two minutes
# because the timeout was raised for long scans.
PROBE_TIMEOUT = 30

# error_code values that mean "send it again". STRUCTURING_TRUNCATED is left out
# on purpose: the model stopped for a reason that will be the same next time.
RETRYABLE_ERROR_CODES = ('OCR_EMPTY', 'PARTIAL_DEGRADATION')


class EasyocrServiceError(Exception):
    """A failure talking to the service, carrying a message fit for the user."""


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
    def _error_code(self, response):
        """The service's own code for what went wrong, or nothing."""
        try:
            return ((response.json() or {}).get('error') or {}).get('code') or ''
        except (ValueError, AttributeError):
            return ''

    @api.model
    def _error_details(self, response):
        """Everything the service put next to the code, as a flat dict."""
        try:
            return ((response.json() or {}).get('error') or {})
        except (ValueError, AttributeError):
            return {}

    @api.model
    def _http_error_message(self, response):
        """Turn a failure into a sentence fit for the person who has to fix it.

        The service says why in the body, and the status code on its own is not
        enough to go on: a 401 covers both "no key was sent" and "the key was
        rejected", which send the reader to two different places. Reading the
        code first is what keeps a rejected key from being reported as a missing
        one -- which is precisely what this used to say.
        """
        known = {
            'MISSING_API_KEY': _(
                "The extraction service needs an API key, and none is set in the EasyOCR settings."
            ),
            'INVALID_API_KEY': _(
                "The extraction service rejected the API key. Check it in the EasyOCR "
                "settings: it may belong to another account, or have been switched off."
            ),
            'API_KEY_INACTIVE': _("That API key is switched off in the EasyOCR account."),
            'API_KEY_EXPIRED': _("That API key has expired."),
            'ACCOUNT_DISABLED': _("The EasyOCR account is switched off. Contact support."),
            'IP_NOT_ALLOWED': _("This server's address is not allowed to use that API key."),
            'DOMAIN_NOT_ALLOWED': _("This server's domain is not allowed to use that API key."),
            'WALLET_EMPTY': _(
                "The EasyOCR account has no readings left. Top it up to keep reading documents."
            ),
            'QUOTA_EXCEEDED': _("The monthly limit of the EasyOCR plan has been reached."),
            'KEY_QUOTA_EXCEEDED': _("This API key has reached its monthly limit."),
            'FEATURE_NOT_AVAILABLE': _("The EasyOCR plan does not include that feature."),
        }
        code = self._error_code(response)
        if code in known:
            return known[code]

        # The plan's own ceiling on how many files travel together. The service
        # says which one it is, so the number can be named instead of guessed --
        # answering "too many" without saying how many would send the reader
        # back to the same refusal one file smaller at a time.
        if code == 'BATCH_TOO_LARGE':
            details = self._error_details(response)
            ceiling = details.get('max_batch_size')
            sent = details.get('files_sent')
            if ceiling and sent:
                return _(
                    "The EasyOCR plan reads %(ceiling)s files at a time at most, and "
                    "%(sent)s were sent. Send them in smaller batches.",
                    ceiling=ceiling,
                    sent=sent,
                )
            return _("The EasyOCR plan does not allow a batch that large.")

        status = response.status_code
        if status == 401:
            # With no code to read, a 401 means the key did not get through. Of
            # the two reasons the service has for saying that, a refused key is
            # the one worth naming by default: the other one is set up once, and
            # the module will not even call without a key.
            return _("The extraction service rejected the API key.")
        if status == 402:
            return _("The EasyOCR account has no readings left.")
        if status == 403:
            return _("The extraction service rejected the API key.")
        if status == 413:
            return _("The file is too large for the extraction service.")
        if status == 422:
            return _("The extraction service could not read the request.")
        if status in (429, 503):
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
    # Asking about the account
    # ------------------------------------------------------------------
    @api.model
    def account(self, company):
        """Who the key belongs to and how much is left, without reading anything.

        This is the only way to tell a key that was mistyped from a service that
        is down *before* sending a document, because a reading that comes back
        refused has already been paid for on the way out. Answers with the
        service's own view of the account: plan, quota and whether it is in a
        position to process at all.
        """
        base = (company.easyocr_ai_url or '').strip().rstrip('/')
        if not base:
            raise EasyocrServiceError(
                _("No extraction service is set in the EasyOCR settings.")
            )

        try:
            response = requests.get(
                base + ACCOUNT_PATH,
                headers={'X-API-Key': company.easyocr_ai_apikey or ''},
                timeout=PROBE_TIMEOUT,
            )
        except requests.RequestException as error:
            _logger.warning('EasyOCR service unreachable at %s: %s', base, error)
            raise EasyocrServiceError(
                _("The extraction service could not be reached (%(error)s).", error=error)
            ) from error

        if not 200 <= response.status_code < 300:
            raise EasyocrServiceError(self._http_error_message(response))

        try:
            return (response.json() or {}).get('data') or {}
        except ValueError as error:
            raise EasyocrServiceError(
                _("The extraction service answered with something that is not JSON.")
            ) from error

    # ------------------------------------------------------------------
    # Many files at once
    # ------------------------------------------------------------------
    @api.model
    def _batch_endpoint(self, company):
        base = (company.easyocr_ai_url or '').strip().rstrip('/')
        if not base:
            raise EasyocrServiceError(
                _("No extraction service is set in the EasyOCR settings.")
            )
        return base + BATCH_PATH

    @api.model
    def create_batch(self, company, files, options=None):
        """Hand a stack of files over and come back with the batch to follow.

        ``files`` is a list of ``(filename, content)``. The answer arrives before
        anything has been read: the service queues the documents and names the
        batch, and the readings come later -- by webhook when one is given, or by
        asking. So this call is short whatever the stack weighs.
        """
        options = options or {}
        # Several parts called `files` without brackets collapse into one on the
        # way in and the service would read a single document out of the stack,
        # silently. The brackets are not cosmetic.
        multipart = [('files[]', (filename, content)) for filename, content in files]
        for key, value in options.items():
            if value is None or value == '':
                continue
            # A switch turned off has to travel as the word. Left as a Python
            # False the multipart encoder writes "False", and a service reading
            # "true"/"false" does not recognise it: the option is either lost or
            # taken for on, and either way the batch is not read the way it was
            # asked for.
            if isinstance(value, bool):
                value = 'true' if value else 'false'
            multipart.append((key, value))

        timeout = company.easyocr_ai_timeout or DEFAULT_TIMEOUT
        try:
            response = requests.post(
                self._batch_endpoint(company),
                headers={'X-API-Key': company.easyocr_ai_apikey or ''},
                files=multipart,
                timeout=timeout,
            )
        except requests.RequestException as error:
            _logger.warning('EasyOCR service unreachable at %s: %s', company.easyocr_ai_url, error)
            raise EasyocrServiceError(
                _("The extraction service could not be reached (%(error)s).", error=error)
            ) from error

        return self._batch_body(response)

    @api.model
    def batch_status(self, company, uuid):
        return self._batch_body(self._batch_call(company, 'get', uuid))

    @api.model
    def batch_results(self, company, uuid):
        return self._batch_body(self._batch_call(company, 'get', uuid, suffix='/results'))

    @api.model
    def batch_cancel(self, company, uuid):
        """Cancel a batch that is still running, or drop one that has finished.

        The service reads the same call two ways depending on the batch's state:
        a running batch is cancelled, a finished one and its documents are
        deleted. Either way it is the batch that decides, not us.
        """
        return self._batch_body(self._batch_call(company, 'delete', uuid))

    @api.model
    def _batch_call(self, company, method, uuid, suffix=''):
        url = '%s/%s%s' % (self._batch_endpoint(company), uuid, suffix)
        timeout = company.easyocr_ai_timeout or DEFAULT_TIMEOUT
        try:
            response = getattr(requests, method)(
                url,
                headers={'X-API-Key': company.easyocr_ai_apikey or ''},
                timeout=timeout,
            )
        except requests.RequestException as error:
            _logger.warning('EasyOCR service unreachable at %s: %s', company.easyocr_ai_url, error)
            raise EasyocrServiceError(
                _("The extraction service could not be reached (%(error)s).", error=error)
            ) from error
        return response

    @api.model
    def _batch_body(self, response):
        """The body of a batch call, or a readable error.

        Unlike a reading, a batch call that fails has cost nothing: nothing was
        queued, or the batch never started. So the message can be blunt.
        """
        if not 200 <= response.status_code < 300:
            raise EasyocrServiceError(self._http_error_message(response))
        try:
            body = response.json()
        except ValueError as error:
            raise EasyocrServiceError(
                _("The extraction service answered with something that is not JSON.")
            ) from error
        # A successful batch call answers with the batch itself at the top level.
        # Some calls come wrapped; both are unwrapped here so the caller sees the
        # same shape whichever way it arrived.
        if isinstance(body, dict) and isinstance(body.get('data'), dict):
            return body['data']
        return body or {}

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
        result['confidence'] = to_float(body.get('confidence'))

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
    def _receiver_context(self, company):
        """Who we are, in one declarative sentence, for the service to read.

        The wording matters and is deliberately short: it says who is reading the
        document and stops there. The module this port comes from tried twice to
        say more and both versions were harmful -- one asked the model to verify
        its own answer before returning it, the other asserted what the document
        contained. Against a model that answers in one pass, the first burns the
        output budget until the call times out, and the second is simply false
        whenever both parties are the same. So: never assert anything about the
        document, and always leave an instruction the model can satisfy.
        """
        if not company.easyocr_ai_receiver_context:
            return ''
        name = (company.name or '').strip()
        vat = (company.partner_id.vat or '').strip()
        if not name and not vat:
            return ''
        who = ', '.join(part for part in (
            '"%s"' % name if name else '',
            'tax id %s' % vat if vat else '',
        ) if part)
        # Left in English on purpose: this sentence is read by the service, not
        # by a person, and it is the same request whichever language the screen
        # is in.
        return (
            'Context, for telling the parties apart: this document is being '
            'processed by %s. Extract supplier and customer exactly as printed '
            'on the document.' % who
        )

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
    extraction_date = fields.Datetime(
        string='Last Read On',
        readonly=True,
        copy=False,
        help='When the file was last sent to the service. It is what the '
             'duplicate window counts back from, so it notes the moment the call '
             'was made and not the moment it went well: a reading that failed '
             'cost the same.',
    )
    extraction_confidence = fields.Float(
        string='Extraction Confidence',
        readonly=True,
        copy=False,
        digits=(3, 2),
        help='How sure the service was of what it read, from 0 to 1.',
    )

    def action_extract(self, force=False):
        """Read the attached file with the service and fill in what it returns.

        A failure is written to the document instead of raised: the file stays
        visible with the reason it could not be read, ready to be tried again.

        ``force`` reads a file that has already been read. That decision is the
        reader's and not the fingerprint's, so without it the answer is the
        question rather than a refusal: a fixed monthly charge really is the
        same file every month, and a reading only a person can tell apart is a
        reading a person has to be allowed to ask for.
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

        # Doing the same reading twice costs the same and tells us nothing new, so
        # the guard sits here: right before the call, and nowhere earlier. The
        # fingerprint is written down on the way through, from the bytes already
        # in hand, so a document filed before this guard existed is covered too.
        self.file_hash = hashlib.sha256(content).hexdigest()
        if company.easyocr_duplicate_check and not force:
            duplicate = self._duplicate_of()
            if duplicate:
                return self._reprocess_question(duplicate)

        # Noted before the call and not after: the window counts what has cost
        # money, and a reading that came back empty cost exactly the same.
        self.extraction_date = fields.Datetime.now()

        try:
            result = self.env['easyocr.extractor'].extract(
                company, content, attachment.name or self.name,
                custom_instructions=self.env['easyocr.extractor']._receiver_context(company),
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
        # What it read, on a screen of its own: a reading costs money and takes
        # seconds, and until this existed the only proof it had happened was a
        # notice in the corner that faded. The module this is a port of shows
        # the same summary, and the vendor's address and phone, which have
        # nowhere else to be seen.
        return self._reading_result_action()

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

        # The service puts it under the payment, and it is the day the vendor
        # wants the money: it was being read and thrown away.
        payment = data.get('payment') or {}
        due_date = self._clean_date(
            data.get('due_date') or payment.get('due_date'),
        )
        if due_date:
            values['due_date'] = due_date

        totals = data.get('totals') or {}
        if totals.get('net_subtotal') is not None:
            values['amount_untaxed'] = to_float(totals['net_subtotal'])
        if totals.get('total') is not None:
            values['amount_total'] = to_float(totals['total'])

        # A rectificativa is the one kind of vendor document that comes back
        # negative, and it is the writing on the paper that decides what the
        # bill becomes. Nothing is turned round here: the document keeps what
        # the paper says, and only says which way the bill goes.
        total = values.get('amount_total', self.amount_total)
        if total is not None and total < 0:
            values['is_refund'] = True

        # The lines are replaced, never merged: a second reading of the same
        # document supersedes the first, and keeping both would double the bill.
        self._apply_lines(data.get('items'))

        if values:
            self.write(values)

    def _apply_lines(self, items):
        """Write down the lines the service read, in the order it read them."""
        self.ensure_one()
        commands = [(5, 0, 0)]
        if isinstance(items, list):
            for sequence, item in enumerate(items, start=1):
                if isinstance(item, dict):
                    commands.append((0, 0, self.env['easyocr.document.line']._values_from_item(
                        item, sequence,
                    )))
        self.line_ids = commands

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

    def action_check_duplicate(self):
        """Whether this file was already read, asked before reading anything.

        The viewer asks with its own dialog and then does the reading itself, so
        that it can show the reading while it happens instead of a still screen.
        To do that it has to know beforehand, and this is how: the same
        fingerprint and the same window the guard uses, and not a call to the
        service.

        Returns nothing at all when there is nothing to ask about, which is the
        answer the viewer wants in one line of code.
        """
        self.ensure_one()
        company = self.company_id or self.env.company
        if not company.easyocr_duplicate_check:
            return {}
        self._refresh_file_hash()
        duplicate = self._duplicate_of()
        if not duplicate:
            return {}
        return {
            'document_id': duplicate.id,
            'document': duplicate.display_name,
            'message': self._duplicate_message(duplicate),
        }

    def _reading_result_action(self):
        """The summary of the reading, as the sectioned dialog."""
        self.ensure_one()
        return self.action_open_result_dialog()

    def action_result_data(self):
        """Everything the result dialog draws, read from this document."""
        self.ensure_one()
        wizard = self.env['easyocr.reading.result'].new({'document_id': self.id})
        return wizard.action_result_data()

    def action_open_result_dialog(self):
        """The reading result, as the sectioned dialog the module this is a port
        of shows: the cards, the raw payload, and the footer that makes the bill."""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'easyocr.ocr_result_dialog',
            'name': _("What the reading found"),
            'params': {'document_id': self.id},
        }

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

    def _reprocess_question(self, duplicate):
        """Open the dialog that asks whether to read it again.

        A dialog and not a notification, because a notification has no answer:
        it was what this used to do, and a reader who knew the document was
        worth reading again had nowhere to say so. Every caller gets the same
        thing, so the button on the document and the button in the viewer ask
        the same question, and neither of them has to know about the other.

        ``views`` travels with it because the viewer hands this action to the
        client, and the client reads the list before asking the server for it:
        without the key the action never opens and the screen says nothing.
        """
        wizard = self.env['easyocr.reprocess.wizard'].create({
            'document_id': self.id,
            'duplicate_id': duplicate.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _("Read it again"),
            'res_model': 'easyocr.reprocess.wizard',
            'res_id': wizard.id,
            'views': [(False, 'form')],
            'view_mode': 'form',
            'target': 'new',
        }
