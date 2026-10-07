# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

import hmac
import logging

from odoo import _, fields, http
from odoo.http import request

_logger = logging.getLogger(__name__)

# Where the shared secret lives. It is set on the settings screen and never
# shipped with the module: a secret with a default value is no secret at all,
# and an empty one closes the endpoint instead of opening it.
WEBHOOK_SECRET_PARAM = 'easyocr.webhook_secret'

# The only event that carries a finished reading. Anything else is recorded and
# dropped, so an event we do not handle yet never looks like a failure.
COMPLETED_EVENT = 'document.completed'

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

    The caller has no Odoo session and no user: it authenticates with a shared
    secret sent in a header, and everything it writes goes through sudo.

    A failure the sender could fix by sending the same body again (a bad secret,
    a body that is not a JSON object) is answered with 400 or 403. Anything that
    would only be retried in vain (an event we do not handle, a value we cannot
    read) is answered with 200 and written to the log: a 500 here means the
    sender retries and the document ends up created twice.

    The route is type='http', not type='json'. On 18.0 type='json' is the
    JSON-RPC dispatcher: it expects the envelope, so a plain body never reaches
    the arguments, and it always answers 200, which would make the 400 and 403
    below impossible. Odoo 19 replaced that with a json2 route that takes the
    body as sent; branch 19.0 uses it. Here nothing is parsed for us, so the
    body is read and the answer built by hand.
    """

    @http.route(
        '/easyocr/webhook',
        type='http',
        auth='public',
        methods=['POST'],
        csrf=False,
        save_session=False,
    )
    def easyocr_webhook(self, **kwargs):
        if not self._secret_is_valid():
            _logger.warning("EasyOCR webhook: rejected a call with a bad or missing secret.")
            return self._answer(
                {'status': 'forbidden', 'message': 'Invalid or missing webhook secret.'},
                status=403,
            )

        body = request.httprequest.get_json(silent=True)
        if not isinstance(body, dict):
            return self._answer(
                {'status': 'error', 'message': 'Malformed request: the body must be a JSON object.'},
                status=400,
            )

        event = body.get('event')
        data = body.get('data')
        if data is not None and not isinstance(data, dict):
            return self._answer(
                {'status': 'error', 'message': 'Malformed request: "data" must be a JSON object.'},
                status=400,
            )

        if event != COMPLETED_EVENT:
            self._keep('ignored', event, data, _('Event "%s" is not handled.', event or ''))
            return self._answer({'status': 'ignored'})

        structured_data = (data or {}).get('structured_data')
        if not isinstance(structured_data, dict) or not structured_data:
            self._keep('ignored', event, data, _('The notification carries no structured data.'))
            return self._answer({'status': 'ignored'})

        try:
            values = self._document_values(structured_data, data)
            document = request.env['easyocr.document'].sudo().create(values)
        except ValueError as error:
            # A business failure: sending the same body again would fail the
            # same way, so it is answered with 200 and left in the log.
            self._keep('error', event, data, str(error))
            return self._answer({'status': 'error', 'message': str(error)})

        # What the call may do beyond filing the document lives on the document,
        # where it can be tested without an HTTP request in the way.
        note = document._settle_webhook()
        message = _('Document created from the OCR result.')
        if note:
            message = '%s %s' % (message, note)
        self._keep('ok', event, data, message, document)
        return self._answer({'status': 'ok', 'document_id': document.id})

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _answer(payload, status=200):
        return request.make_json_response(payload, status=status)

    @staticmethod
    def _secret_is_valid():
        """Compare the header with the configured secret, in constant time."""
        expected = request.env['ir.config_parameter'].sudo().get_param(WEBHOOK_SECRET_PARAM) or ''
        if not expected:
            return False
        provided = request.httprequest.headers.get('X-Webhook-Secret') or ''
        return hmac.compare_digest(provided.encode('utf-8'), expected.encode('utf-8'))

    @staticmethod
    def _payload_text():
        """The body as it was received, trimmed to something reasonable."""
        body = request.httprequest.get_data(as_text=True) or ''
        if len(body) > PAYLOAD_MAX_LENGTH:
            body = body[:PAYLOAD_MAX_LENGTH] + '...'
        return body

    def _keep(self, status, event, data, message, document=None):
        """Record the call. For an ignored one this is its only trace."""
        data = data if isinstance(data, dict) else {}
        return request.env['easyocr.webhook.log'].sudo().create({
            'event': event or '',
            'document_id_external': data.get('document_id') or '',
            'filename': data.get('filename') or '',
            'status': status,
            'message': message,
            'payload': self._payload_text(),
            'document_id': document.id if document else False,
        })

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
