# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

import hmac
import json
import logging
import re
from datetime import timedelta

from odoo import _, fields, http
from odoo.http import request

from odoo.addons.easyocr.models.easyocr_values import (
    is_concurrency_error, param_value, set_param_value,
)

_logger = logging.getLogger(__name__)

# The old way in: one shared secret for the whole database, set by hand as a
# system parameter. Each company now has a token of its own (see res.company);
# the secret is still taken for LEGACY_DAYS from the first call that used it,
# never to record a payment, and refused after that.
WEBHOOK_SECRET_PARAM = 'easyocr.webhook_secret'
LEGACY_SINCE_PARAM = 'easyocr.webhook_legacy_since'
LEGACY_DAYS = 30

# What a retry is told to wait, in seconds, when another call is creating the
# same vendor.
RETRY_AFTER = 5

# A token or a secret in an address, as the access log would print it.
SECRET_IN_URL = re.compile(r'((?:token|secret)=)[^&\s"]+', re.IGNORECASE)


class RedactWebhookSecrets(logging.Filter):
    """Keep the webhook token out of the access log.

    The service is only ever given an address, so the token travels in it, and
    the server prints every address it serves. This blanks it before the line
    is written.
    """

    def filter(self, record):
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001 - a log line must never break a request
            return True
        if 'token=' in message.lower() or 'secret=' in message.lower():
            record.msg = SECRET_IN_URL.sub(r'\1***', message)
            record.args = ()
        return True


for _logger_name in ('werkzeug', 'odoo.http'):
    _target = logging.getLogger(_logger_name)
    if not any(isinstance(item, RedactWebhookSecrets) for item in _target.filters):
        _target.addFilter(RedactWebhookSecrets())

# The event that carries a finished reading of a document sent on its own. The
# batch ones carry the same reading, one document at a time, and the end of the
# stack after them.
COMPLETED_EVENT = 'document.completed'

# One document of a batch coming back, and the batch itself being done. Both
# carry the document or the batch inside `data`, which is where the service puts
# it -- not in a `document` key, whatever the shape of the call.
BATCH_DOCUMENT_EVENT = 'batch.document.completed'
BATCH_DOCUMENT_FAILED_EVENT = 'batch.document.failed'
BATCH_FINISHED_EVENT = 'batch.completed'

# The body is kept to be looked at, not replayed: enough to see what arrived,
# without turning the log table into a copy of every payload.
PAYLOAD_MAX_LENGTH = 10000

# structured_data as the extraction service sends it, mapped to the document
# field each value feeds. The keys are the ones a template box uses, so what the
# webhook stores is what the viewer shows.
STRUCTURED_DATA_MAPPING = (
    ('partner_name', 'partner_name'),
    ('partner_vat', 'partner_vat'),
    ('document_number', 'ref'),
    ('ref', 'ref'),
    ('document_date', 'document_date'),
    ('amount_untaxed', 'amount_untaxed'),
    ('amount_total', 'amount_total'),
)

DATE_FIELDS = ('document_date',)
AMOUNT_FIELDS = ('amount_untaxed', 'amount_total')


class EasyocrWebhook(http.Controller):
    """The call the OCR service makes when it has finished reading a document.

    The caller has no Odoo session and no user: it authenticates with the
    token of one company, in the X-Webhook-Token header or in the address, and
    everything it writes goes through sudo, in that company. A refused call is
    answered with a bare 403 that says nothing of why.

    A failure the sender could fix by sending the same body again (a bad secret,
    a body that is not a JSON object) is answered with 400 or 403. Anything that
    would only be retried in vain (an event we do not handle, a value we cannot
    read) is answered with 200 and written to the log: a 500 here means the
    sender retries and the document ends up created twice.

    The route is json2, not json. Since 19.0 type='json' is an alias of
    jsonrpc: it expects the JSON-RPC envelope, so a plain body never reaches
    the arguments, it wraps every answer in that envelope, and it always
    answers 200. json2 takes the body as it was sent and lets the status code
    through. Branch 18.0 has no json2 and reads the body by hand instead.
    """

    @http.route(
        '/easyocr/webhook',
        type='json2',
        auth='public',
        methods=['POST'],
        csrf=False,
        save_session=False,
    )
    def easyocr_webhook(self, event=None, data=None, **kwargs):
        company, legacy = self._authenticate()
        if not company:
            _logger.warning("EasyOCR webhook: rejected a call that did not authenticate.")
            return request.make_json_response({'status': 'forbidden'}, status=403)

        body = request.httprequest.get_json(silent=True)
        if body is not None and not isinstance(body, dict):
            return request.make_json_response(
                {'status': 'error', 'message': 'Malformed request: the body must be a JSON object.'},
                status=400,
            )

        if data is not None and not isinstance(data, dict):
            return request.make_json_response(
                {'status': 'error', 'message': 'Malformed request: "data" must be a JSON object.'},
                status=400,
            )

        if event in (BATCH_DOCUMENT_EVENT, BATCH_DOCUMENT_FAILED_EVENT):
            return self._batch_document(event, data, company, legacy)
        if event == BATCH_FINISHED_EVENT:
            return self._batch_finished(event, data, company, legacy)

        if event != COMPLETED_EVENT:
            self._keep('ignored', event, data, _('Event "%s" is not handled.', event or ''),
                       company=company)
            return {'status': 'ignored'}

        structured_data = (data or {}).get('structured_data')
        if not isinstance(structured_data, dict) or not structured_data:
            self._keep('ignored', event, data, _('The notification carries no structured data.'),
                       company=company)
            return {'status': 'ignored'}

        Document = request.env['easyocr.document'].sudo().with_company(company)
        external_id = str((data or {}).get('document_id') or '').strip()
        if external_id:
            # The same document sent again -- a retry after a timeout, a
            # duplicated delivery -- is answered with the one already filed,
            # and nothing is billed or paid a second time.
            known = Document.search([
                ('service_document_id', '=', external_id),
                ('company_id', '=', company.id),
            ], limit=1)
            if known:
                self._keep('ok', event, data, _('Already received: nothing was done again.'),
                           known, company=company)
                return {'status': 'ok', 'document_id': known.id, 'duplicate': True}

        try:
            values = self._document_values(structured_data, data)
            values['company_id'] = company.id
            if external_id:
                values['service_document_id'] = external_id
            document = Document.create(values)
            # The service sends the reading nested (supplier, totals, items), the
            # same shape a batch document gets: read it the same way, so the
            # vendor's tax number, the lines and the totals -- surcharge and
            # withholding included -- are there to check the bill against. Kept
            # whole as well, without the file, as a reading made from here is.
            # A block of an odd shape is left out rather than answered with a
            # 500: the sender would retry and the document be filed twice.
            try:
                document._apply_extraction(structured_data)
            except (AttributeError, TypeError) as error:
                _logger.warning("EasyOCR webhook: part of the reading was not usable: %s", error)
            document.last_extraction = json.dumps(
                {'structured_data': structured_data}, indent=2, ensure_ascii=False, default=str,
            )
        except ValueError as error:
            # A business failure: sending the same body again would fail the
            # same way, so it is answered with 200 and left in the log.
            self._keep('error', event, data, str(error), company=company, keep_payload=True)
            return {'status': 'error', 'message': str(error)}

        # What the call may do beyond filing the document lives on the document,
        # where it can be tested without an HTTP request in the way.
        outcome = {}
        try:
            note = document._settle_webhook(allow_payment=not legacy, outcome=outcome)
        except Exception as error:
            if not is_concurrency_error(error):
                raise
            # Another call is creating the same vendor. Nothing of this one is
            # kept, so the retry files the document once, from a fresh look.
            request.env.cr.rollback()
            return request.make_json_response(
                {'status': 'retry'}, status=503, headers=[('Retry-After', str(RETRY_AFTER))],
            )
        message = _('Document created from the OCR result.')
        if note:
            message = '%s %s' % (message, note)
        if legacy:
            message = '%s %s' % (message, self._legacy_note())
        self._keep('ok', event, data, message, document, company=company,
                   keep_payload=outcome.get('review'))
        return {'status': 'ok', 'document_id': document.id}

    def _batch_document(self, event, data, company, legacy=False):
        """One document of a batch, read or failed, as the service finishes it.

        A reading that could not be made is not an error of this endpoint: it is
        answered with 200 and written down, because the sender retrying it would
        change nothing.
        """
        try:
            note = self._batches(company, legacy)._settle_webhook(
                data, self._batch_reference()
            )
        except ValueError as error:
            self._keep('error', event, data, str(error), company=company, keep_payload=True)
            return {'status': 'error', 'message': str(error)}
        self._keep('ok', event, data, note, company=company)
        return {'status': 'ok'}

    def _batch_finished(self, event, data, company, legacy=False):
        """The whole batch is done. Its readings come from the service itself."""
        try:
            note = self._batches(company, legacy)._finish_webhook(
                data, self._batch_reference()
            )
        except ValueError as error:
            self._keep('error', event, data, str(error), company=company, keep_payload=True)
            return {'status': 'error', 'message': str(error)}
        self._keep('ok', event, data, note, company=company)
        return {'status': 'ok'}

    @staticmethod
    def _batches(company, legacy):
        """The batches a call may touch: with a token, only its company's."""
        Batch = request.env['easyocr.batch'].sudo().with_company(company)
        if legacy:
            return Batch
        return Batch.with_context(easyocr_webhook_company_id=company.id)

    @staticmethod
    def _batch_reference():
        """Which batch the call is about, out of the address it was sent to.

        The address is the one we handed the service when the batch was made, so
        it is ours and it is the batch's own name for itself. The body carries a
        batch too, and it is the better source when it is there -- but not every
        event carries one.
        """
        return request.httprequest.args.get('batch') or ''

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _authenticate():
        """Which company the call is for, and whether it came the old way.

        Answers ``(company, legacy)``, with no company when the call is
        refused. The token of a company is looked for in the X-Webhook-Token
        header and in the address (a batch only ever gives the service an
        address). The old shared secret, in X-Webhook-Secret or ``secret=``,
        is taken for LEGACY_DAYS counted from the first call that used it, for
        the company of the public user as before, and refused after that.
        Every comparison is made in constant time.
        """
        http_request = request.httprequest
        Company = request.env['res.company'].sudo()
        token = (
            http_request.headers.get('X-Webhook-Token')
            or http_request.args.get('token')
            or ''
        )
        if token:
            return Company._easyocr_company_of_webhook_token(token), False

        expected = param_value(request.env, WEBHOOK_SECRET_PARAM)
        provided = (
            http_request.headers.get('X-Webhook-Secret')
            or http_request.args.get('secret')
            or ''
        )
        if not expected or not provided or not hmac.compare_digest(
                provided.encode('utf-8'), expected.encode('utf-8')):
            return Company.browse(), False

        now = fields.Datetime.now()
        try:
            since = fields.Datetime.to_datetime(param_value(request.env, LEGACY_SINCE_PARAM) or None)
        except ValueError:
            since = None
        if not since:
            set_param_value(request.env, LEGACY_SINCE_PARAM, fields.Datetime.to_string(now))
            since = now
        if now - since > timedelta(days=LEGACY_DAYS):
            return Company.browse(), False
        _logger.warning(
            "EasyOCR webhook: a call used the old shared secret, accepted until %s. "
            "Give the service the webhook address shown in the EasyOCR settings.",
            fields.Datetime.to_string(since + timedelta(days=LEGACY_DAYS)),
        )
        return request.env.company.sudo(), True

    @staticmethod
    def _legacy_note():
        return _("This call used the old shared secret, which is accepted for %(days)s "
                 "days from its first use and never records payments: give the service "
                 "the webhook address shown in the EasyOCR settings.", days=LEGACY_DAYS)

    @staticmethod
    def _payload_text():
        """The body as it was received, trimmed to something reasonable."""
        body = request.httprequest.get_data(as_text=True) or ''
        if len(body) > PAYLOAD_MAX_LENGTH:
            body = body[:PAYLOAD_MAX_LENGTH] + '...'
        return body

    def _keep(self, status, event, data, message, document=None, company=None,
              keep_payload=False):
        """Record the call. For an ignored one this is its only trace.

        The body is kept only when the call failed or left something for a
        person to review, which is when somebody will want to see what came
        in. A call that went through has its outcome on the document; keeping
        its reading here as well would be a second copy of personal data.
        """
        data = data if isinstance(data, dict) else {}
        values = {
            'event': event or '',
            'document_id_external': data.get('document_id') or '',
            'filename': data.get('filename') or '',
            'status': status,
            'message': message,
            'payload': self._payload_text() if keep_payload else False,
            'document_id': document.id if document else False,
        }
        if company:
            values['company_id'] = company.id
        return request.env['easyocr.webhook.log'].sudo().create(values)

    def _document_values(self, structured_data, data):
        """Turn structured_data into easyocr.document values.

        Raises ValueError when a value cannot be read: a document that silently
        loses its date is worse than no document at all.
        """
        values = {'state': 'processed'}
        for source_key, field_name in STRUCTURED_DATA_MAPPING:
            if source_key not in structured_data:
                continue
            raw = structured_data[source_key]
            if field_name in DATE_FIELDS:
                parsed = self._to_date(field_name, raw)
            elif field_name in AMOUNT_FIELDS:
                parsed = self._to_amount(field_name, raw)
            else:
                parsed = ('' if raw is None else str(raw)).strip()
            if parsed:
                values[field_name] = parsed

        # Who the paper is addressed to, flat or under ``customer`` as the
        # reading sends it: the bill this call may create is refused when it
        # is not us.
        customer = structured_data.get('customer')
        customer_vat = (
            customer.get('tax_id') if isinstance(customer, dict) else None
        ) or structured_data.get('customer_vat')
        if customer_vat:
            values['customer_vat'] = str(customer_vat).strip()

        values['name'] = (
            values.get('ref')
            or ((data or {}).get('filename') or '').strip()
            or values.get('partner_name')
            or _('New')
        )
        return values

    @staticmethod
    def _to_date(field_name, value):
        if value in (None, ''):
            return False
        try:
            return fields.Date.to_date(value)
        except (ValueError, TypeError) as error:
            raise ValueError(
                _("The value sent for %s, %s, is not a date.", field_name, value)
            ) from error

    @staticmethod
    def _to_amount(field_name, value):
        if value in (None, ''):
            return 0.0
        try:
            return float(value)
        except (TypeError, ValueError) as error:
            raise ValueError(
                _("The value sent for %s, %s, is not a number.", field_name, value)
            ) from error
