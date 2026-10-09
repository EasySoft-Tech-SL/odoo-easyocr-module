# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .easyocr_document import READABLE_EXTENSIONS

_logger = logging.getLogger(__name__)

# The same file twice in one stack costs twice and tells us nothing new, which
# is the whole reason the guard exists. What makes it worth repeating is time,
# and that is the company's duplicate window, not a number of its own.
BATCH_STATES = [
    ('pending', 'Pending'),
    ('processing', 'Processing'),
    ('completed', 'Completed'),
    ('partial', 'Partial'),
    ('failed', 'Failed'),
    ('cancelled', 'Cancelled'),
]

# A running batch is asked about again every so often, and then let go: a batch
# the service has stopped answering about is not going to answer later, and a
# cron that keeps asking forever is a cron that never stops.
REFRESH_EVERY_MINUTES = 10
GIVE_UP_AFTER_HOURS = 24

# How many files may travel together is the plan's business and the service
# says so, but only once the call is made -- and a call that comes back refused
# leaves the whole stack unread. So the number is read from the account first.
UNKNOWN_CEILING = 0


class EasyocrBatch(models.Model):
    """A stack of files handed to the service in one go.

    The batch exists before anything is sent, so the files are filed and visible
    while the decision to pay for them is still being made. Sending is the only
    step that costs anything, and it is the only step that cannot be undone.
    """

    _name = 'easyocr.batch'
    _description = 'EasyOCR Batch'
    _order = 'create_date desc, id desc'

    name = fields.Char(
        string='Name',
        required=True,
        default=lambda self: _('New'),
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )
    state = fields.Selection(
        selection=BATCH_STATES,
        string='Status',
        default='pending',
        required=True,
        readonly=True,
    )
    service_uuid = fields.Char(
        string='Batch at the service',
        readonly=True,
        copy=False,
        help='What the service calls this batch. Empty until it has been sent.',
    )
    document_ids = fields.One2many(
        comodel_name='easyocr.document',
        inverse_name='batch_id',
        string='Documents',
    )
    document_count = fields.Integer(string='Documents', compute='_compute_counts')
    completed_count = fields.Integer(string='Completed documents', compute='_compute_counts')
    failed_count = fields.Integer(string='Failed documents', compute='_compute_counts')
    progress = fields.Float(string='Progress', compute='_compute_counts')
    sent_at = fields.Datetime(string='Sent On', readonly=True, copy=False)
    finished_at = fields.Datetime(string='Completed at', readonly=True, copy=False)
    error_message = fields.Text(string='Detail', readonly=True, copy=False)

    include_extracted_text = fields.Boolean(
        string='Include extracted text',
        default=False,
        help='Ask the service to send back the raw text of every page as well. '
             'It is not needed to make a bill, and it is not kept here.',
    )
    auto_correct = fields.Boolean(
        string='Auto-correction',
        default=False,
        help='Let the service fix what it can make out and mark what it changed, '
             'instead of returning the document exactly as it stands.',
    )
    custom_instructions = fields.Text(
        string='AI Instructions',
        help='Told to the service once, for every file of this batch. It is not '
             'kept on the documents.',
    )
    notify_url = fields.Char(
        string='Webhook URL',
        help='Where the service is to say that a file has been read. Left empty, '
             'this installation answers for itself and each reading is filed on '
             'the document it belongs to. Set it only when the webhook is '
             'answered somewhere else: without one the readings still arrive, a '
             'little later, from the job that asks.',
    )

    # ------------------------------------------------------------------
    # Counts
    # ------------------------------------------------------------------
    @api.depends('document_ids.state')
    def _compute_counts(self):
        for batch in self:
            documents = batch.document_ids
            total = len(documents)
            read = len(documents.filtered(lambda d: d.state == 'processed'))
            failed = len(documents.filtered(lambda d: d.state == 'error'))
            batch.document_count = total
            batch.completed_count = read
            batch.failed_count = failed
            # Worked out here and not taken from the service, so the bar moves
            # the moment a document comes back instead of on the next ask.
            batch.progress = (read + failed) * 100.0 / total if total else 0.0

    # ------------------------------------------------------------------
    # Filling the batch
    # ------------------------------------------------------------------
    def action_add_files(self, files):
        """File the chosen files as documents, ready to be sent.

        Nothing leaves the machine here: this is what lets the reader see the
        stack, and what the duplicate guard has to look at, before anything is
        paid for. Each file becomes a document of its own so that whatever comes
        back can be reviewed, corrected and billed one by one.
        """
        self.ensure_one()
        documents = self.env['easyocr.document']
        refused = []

        for chosen in files or []:
            filename = (chosen.get('filename') or '').strip()
            datas = chosen.get('datas')
            if not filename or not datas:
                refused.append({
                    'filename': filename or '?',
                    'reason': _("The file arrived empty."),
                })
                continue
            # .pdf, .jpg, .jpeg and .png, the same four the single document
            # accepts. The service takes more, but a batch is not the place to
            # widen what the module reads: whatever enters here has to be
            # something the viewer can paint afterwards.
            if not filename.lower().endswith(READABLE_EXTENSIONS):
                refused.append({
                    'filename': filename,
                    'reason': _("That kind of file cannot be read. Send a PDF or a photo."),
                })
                continue

            document = self.env['easyocr.document'].create({
                'name': filename,
                'company_id': self.company_id.id,
                'currency_id': self.company_id.currency_id.id,
                'batch_id': self.id,
            })
            document.attachment_id = self.env['ir.attachment'].create({
                'name': filename,
                'datas': datas,
                'res_model': 'easyocr.document',
                'res_id': document.id,
            }).id
            documents |= document

        return {
            'documents': len(documents),
            'refused': refused,
            'duplicates': self._duplicates(documents),
        }

    def _duplicates(self, documents):
        """Files of this batch that have been read before, or twice in the stack.

        Two readings of one file cost like two, and the second one says nothing
        the first did not. Both ways it can happen are looked at together,
        because the answer to the reader is the same: these are already paid for,
        send them anyway?
        """
        found = []
        seen = {}
        # In the order they were added, and not in the order the records come
        # back: the one of a pair that gets flagged is the second one the reader
        # chose, which is the copy they meant to drop.
        for document in documents.sorted('id'):
            if not document.file_hash:
                continue
            twin = seen.get(document.file_hash)
            if twin:
                found.append(self._duplicate_entry(document, twin, in_batch=True))
                continue
            seen[document.file_hash] = document
            already = document._duplicate_of()
            if already:
                found.append(self._duplicate_entry(document, already, in_batch=False))
        return found

    def _duplicate_entry(self, document, twin, in_batch):
        return {
            'document_id': document.id,
            'filename': document.attachment_id.name or document.name,
            'reason': _("The same file is twice in this batch.") if in_batch else _(
                "This file has already been read: %(document)s.",
                document=twin.display_name,
            ),
        }

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------
    def action_send(self, force=False, leave_out_duplicates=False):
        """Hand the stack over, once.

        Answers with what happened rather than raising: a service that refuses,
        an account that cannot read and a stack the plan is too small for are all
        things the screen has to say in place, next to the files they are about.

        ``force`` sends the files that have already been read anyway, and
        ``leave_out_duplicates`` drops them from the batch and sends the rest.
        The two are the two answers to the same question, and neither is what
        happens when neither is asked for: then the question is handed back, so
        the money is spent once and by the reader's decision.
        """
        self.ensure_one()
        if self.service_uuid:
            raise UserError(_("This batch has already been sent."))
        if not self.document_ids:
            raise UserError(_("There is nothing to send."))

        state = self._service_state()
        if state['blocked']:
            return self._refuse(state['message'])

        if self.document_count > state['ceiling']:
            return self._refuse(_(
                "The EasyOCR plan reads %(ceiling)s files at a time at most, and this "
                "batch has %(count)s. Send them in smaller batches.",
                ceiling=state['ceiling'],
                count=self.document_count,
            ))

        # Asked again here and not only when the files were added: the answer
        # changes as soon as one of these files is read somewhere else.
        skipped = []
        duplicates = self._duplicates(self.document_ids)
        if duplicates and not force:
            if not leave_out_duplicates:
                return {
                    'sent': False, 'duplicates': duplicates, 'skipped': [], 'message': '',
                }
            skipped = self._leave_out(duplicates)
            if not self.document_ids:
                return self._refuse(_(
                    "Every file of this batch has already been read, so there is "
                    "nothing left to send."
                ))

        files = []
        for document in self.document_ids:
            attachment = document.attachment_id
            try:
                content = attachment.raw
            except Exception:  # noqa: BLE001 - any read failure is the same here
                _logger.exception("EasyOCR: could not read file of document %s", document.id)
                content = False
            if not content:
                return self._refuse(_(
                    "The file of %(name)s is empty or cannot be read.",
                    name=document.attachment_id.name or document.name,
                ))
            files.append((attachment.name or document.name, content))

        options = {
            'name': self.name,
            'include_extracted_text': self.include_extracted_text,
            'auto_correct': self.auto_correct,
            # We already hold every one of these files; asking for them back
            # would send each of them across twice for nothing.
            'include_original_document': False,
        }
        instructions = self._instructions()
        if instructions:
            options['custom_instructions'] = instructions

        notify = (self.notify_url or '').strip() or self._default_notify_url()
        if notify:
            options['webhook_url'] = notify

        try:
            answer = self.env['easyocr.extractor'].create_batch(
                self.company_id, files, options
            )
        except Exception as error:  # noqa: BLE001 - said on the record, not thrown
            _logger.warning('EasyOCR: could not send batch %s: %s', self.id, error)
            return self._refuse(str(error))

        self.service_uuid = answer.get('batch_id') or answer.get('uuid') or ''
        if not self.service_uuid:
            return self._refuse(_(
                "The extraction service took the files but did not say which batch "
                "they are. Nothing here can follow them."
            ))

        now = fields.Datetime.now()
        self.write({'state': 'processing', 'sent_at': now, 'error_message': False})
        # Written down on the way out, exactly as a single document does it: the
        # batch has been paid for from this moment, whether or not the readings
        # come back well, and it is these that the duplicate window counts.
        self.document_ids.write({'extraction_date': now})
        self.document_ids._refresh_file_hash()
        return {
            'sent': True,
            'skipped': skipped,
            'duplicates': [],
            'message': _("The batch is on its way."),
        }

    def _leave_out(self, duplicates):
        """Drop the files that were already read, and send what is left.

        What the reader is told when they answer "leave them out" is that those
        files will not go. So they go out of the batch entirely and not just out
        of the call: a document left behind in a batch that has been sent is a
        file nobody sent and nobody is waiting for.
        """
        self.ensure_one()
        documents = self.env['easyocr.document']
        names = []
        for entry in duplicates:
            document = self.env['easyocr.document'].browse(entry['document_id'])
            if not document.exists() or document.batch_id != self:
                continue
            names.append(entry['filename'])
            documents |= document
        # Taken out of the batch and not deleted: the file was filed, and a
        # person said not to send it. It stays where a file that was never sent
        # belongs, in the list of documents, and it is not a reading, so the
        # duplicate guard does not count it either. Deleting it would need a
        # permission the reader of a batch does not have to have.
        documents.write({'batch_id': False})
        return names

    def _default_notify_url(self):
        """This installation's own webhook, with the batch it is about.

        Built here rather than stored, and not built at all when the endpoint is
        closed: the secret is what opens it, so an address without one would be
        an address the service calls and this side refuses. The batch is named
        in the address because not every event carries one in its body, and the
        secret travels in it for the same reason the module this is a port of
        carries its instance identifier there: an address is the only thing the
        service is given to call back on.
        """
        self.ensure_one()
        parameters = self.env['ir.config_parameter'].sudo()
        secret = parameters.get_param('easyocr.webhook_secret') or ''
        if not secret:
            return ''
        base = (parameters.get_param('web.base.url') or '').strip().rstrip('/')
        if not base:
            return ''
        return '%s/easyocr/webhook?batch=%s&secret=%s' % (base, self.id, secret)

    def _instructions(self):
        """What to tell the service, in one block, for the whole stack.

        The reader's own words come first and the module's own sentence after,
        the same way the single document appends it: the identity of who is
        having the document read is not a setting here, it is what makes the
        parties come out the right way round.
        """
        self.ensure_one()
        parts = [
            (self.custom_instructions or '').strip(),
            self.env['easyocr.extractor']._receiver_context(self.company_id),
        ]
        return '\n\n'.join(part for part in parts if part)

    def _refuse(self, message):
        """Keep the reason on the batch, where the screen will read it."""
        self.error_message = message
        return {'sent': False, 'duplicates': [], 'skipped': [], 'message': message}

    def _service_state(self):
        """Whether this account can send a batch right now, and how many files.

        Two different questions with one answer each: what the plan allows
        (``batch_processing`` and its ceiling) and what the account is in a
        position to do (an overdue subscription reads nothing). Both are asked
        of the service, because the module cannot know either.
        """
        self.ensure_one()
        company = self.company_id
        if not company.easyocr_ai_enabled:
            return self._blocked(_("AI extraction is off. Turn it on in the EasyOCR settings."))
        if not company.easyocr_ai_apikey:
            return self._blocked(_("No API key is set in the EasyOCR settings."))

        try:
            account = self.env['easyocr.extractor'].account(company)
        except Exception as error:  # noqa: BLE001 - a service that is down reads nothing
            _logger.info('EasyOCR: could not ask about the account: %s', error)
            return self._blocked(str(error))

        features = account.get('features') or {}
        if not features.get('batch_processing'):
            return self._blocked(_(
                "The EasyOCR plan does not read files in batches. It reads them one "
                "at a time."
            ))

        limits = account.get('limits') or {}
        ceiling = int(limits.get('max_batch_size') or 0)
        if ceiling < 1:
            return self._blocked(_("The EasyOCR plan does not say how many files it reads at a time."))

        status = account.get('status') or {}
        if not status.get('can_process', True):
            known = {
                'SUBSCRIPTION_OVERDUE': _(
                    "The EasyOCR subscription is overdue, so the service will not read "
                    "anything until it is brought up to date."
                ),
                'WALLET_EMPTY': _("The EasyOCR account has no readings left."),
                'QUOTA_EXCEEDED': _("The monthly limit of the EasyOCR plan has been reached."),
                'ACCOUNT_DISABLED': _("The EasyOCR account is switched off. Contact support."),
            }
            return self._blocked(known.get(
                status.get('block_code'),
                _("The EasyOCR account cannot read documents right now."),
            ))

        return {'blocked': False, 'message': '', 'ceiling': ceiling}

    @staticmethod
    def _blocked(message):
        return {'blocked': True, 'message': message, 'ceiling': UNKNOWN_CEILING}

    # ------------------------------------------------------------------
    # Following it
    # ------------------------------------------------------------------
    def action_refresh(self):
        """Ask the service where the batch is, and take what it has read.

        Doing nothing when there is nothing to do is the point: a batch that has
        finished and been collected is not asked about again, however often the
        screen is opened.
        """
        self.ensure_one()
        if not self.service_uuid or self.state in ('completed', 'partial', 'failed', 'cancelled'):
            return {'state': self.state, 'message': ''}

        try:
            status = self.env['easyocr.extractor'].batch_status(
                self.company_id, self.service_uuid
            )
        except Exception as error:  # noqa: BLE001 - the batch keeps its last known state
            _logger.info('EasyOCR: could not ask about batch %s: %s', self.service_uuid, error)
            return {'state': self.state, 'message': str(error)}

        self._take_status(status)

        if self.state in ('completed', 'partial', 'failed'):
            try:
                results = self.env['easyocr.extractor'].batch_results(
                    self.company_id, self.service_uuid
                )
            except Exception as error:  # noqa: BLE001 - the status is already taken
                _logger.info('EasyOCR: could not read results of batch %s: %s',
                             self.service_uuid, error)
                return {'state': self.state, 'message': str(error)}
            self._take_results(results)

        return {'state': self.state, 'message': self.error_message or ''}

    def _take_status(self, status):
        """Copy the service's own state onto the batch."""
        self.ensure_one()
        state = status.get('status')
        if state not in dict(BATCH_STATES):
            return
        values = {'state': state}
        if state in ('completed', 'partial', 'failed', 'cancelled'):
            values['finished_at'] = fields.Datetime.now()
        self.write(values)

    def _take_results(self, results):
        """Give each document what the service read from its file.

        Documents are matched by the name of the file, which the answer carries,
        and by the identifier the service gave each one once it is known -- so a
        second look at the same batch lands on the same documents instead of
        filing them again.
        """
        self.ensure_one()
        documents = list(self.document_ids)
        by_service_id = {
            document.service_document_id: document
            for document in documents if document.service_document_id
        }

        for entry in results.get('documents') or []:
            if not isinstance(entry, dict):
                continue
            document = by_service_id.get(entry.get('document_id'))
            if not document:
                document = self._match_by_filename(documents, entry.get('filename'))
            if not document:
                # A document we never sent, which would be the service's mistake.
                # Nothing is invented for it.
                _logger.warning('EasyOCR: batch %s came back with an unknown file %r',
                                self.service_uuid, entry.get('filename'))
                continue
            documents.remove(document)
            if entry.get('document_id'):
                document.service_document_id = entry['document_id']
            self._settle(document, entry)

    @staticmethod
    def _match_by_filename(documents, filename):
        """The first document of the batch still waiting for that file name."""
        if not filename:
            return None
        for document in documents:
            if (document.attachment_id.name or document.name) == filename:
                return document
        return None

    def _settle(self, document, entry):
        """Write one document's outcome, whether it came out well or not."""
        structured = entry.get('structured_data')
        state = entry.get('status')

        # A document that came back without a complete reading carries the reason
        # in error_code, by the service's own definition: `partial` on a document
        # is never written, so the code is what says whether to send it again.
        if state == 'completed' and isinstance(structured, dict) and structured:
            document._apply_extraction(structured)
            document.state = 'processed'
            document.error_message = False
            document.extraction_confidence = entry.get('ocr_confidence') or 0.0
            return

        reason = entry.get('error') or self._result_reason(entry)
        document._fail_extraction(reason)

    @staticmethod
    def _result_reason(entry):
        code = entry.get('error_code') or ''
        if entry.get('status') == 'cancelled':
            return _("The batch was cancelled before this file was read.")
        message = _("The extraction service could not read this file.")
        if code:
            message += ' (%s)' % code
        return message

    # ------------------------------------------------------------------
    # What the service calls back with
    # ------------------------------------------------------------------
    # The webhook is the fast path and the cron is the one that cannot be lost.
    # Both end up here, and neither knows about the other: a document that
    # arrives twice is written twice with the same values, which is what makes
    # this safe to call from either side.
    @api.model
    def _settle_webhook(self, data, batch_ref=False):
        """Take one document of a batch as the service finishes with it.

        Answers with a sentence to keep in the log, or raises ValueError when
        the call cannot be used -- which the caller answers with 200, because
        sending the same body again would fail the same way.
        """
        data = data if isinstance(data, dict) else {}
        batch = self._batch_of_payload(data, batch_ref)
        document = self._document_of_payload(batch, data)
        if not document:
            raise ValueError(
                _("No document of this batch matches %(file)s.",
                  file=data.get('filename') or data.get('document_id') or '?')
            )

        if document.service_document_id != data.get('document_id'):
            document.service_document_id = data.get('document_id') or False
        batch._settle(document, data)
        return _("Document of batch %(batch)s updated.", batch=batch.display_name or '?')

    @api.model
    def _finish_webhook(self, data, batch_ref=False):
        """The whole batch is done: copy its final state and collect it."""
        data = data if isinstance(data, dict) else {}
        batch = self._batch_of_payload(data, batch_ref)
        if not batch:
            raise ValueError(_("No batch matches %(batch)s.", batch=batch_ref or '?'))
        batch._take_status(data)
        if batch.state in ('completed', 'partial', 'failed'):
            # The status is the news; the readings themselves are collected here
            # rather than trusted to a body that carries a summary and not the
            # documents.
            batch.action_refresh()
        return _("Batch %(batch)s is %(state)s.", batch=batch.display_name, state=batch.state)

    @api.model
    def _batch_of_payload(self, data, batch_ref=False):
        """Which batch the call is about, out of whichever field carries it."""
        reference = (
            batch_ref
            or data.get('batch_id')
            or (data.get('batch') or {}).get('batch_id')
        )
        if not reference:
            return self.browse()
        return self.search([('service_uuid', '=', reference)], limit=1)

    @api.model
    def _document_of_payload(self, batch, data):
        """Which document the call is about.

        The identifier the service gave it is what settles it, and the name of
        the file is the fallback: two files of one batch can share a name, so
        the name is only trusted inside a batch that is known.
        """
        service_id = data.get('document_id')
        if service_id:
            known = self.env['easyocr.document'].search(
                [('service_document_id', '=', service_id)], limit=1
            )
            if known:
                return known
        if not batch:
            return self.env['easyocr.document']
        return self._match_by_filename(
            list(batch.document_ids.filtered(lambda d: not d.service_document_id)),
            data.get('filename'),
        ) or self.env['easyocr.document']

    # ------------------------------------------------------------------
    # Letting it go
    # ------------------------------------------------------------------
    def action_cancel(self):
        """Stop a running batch, or drop a finished one and its documents.

        One call, two outcomes, and the service decides which: it cancels while
        there is something to cancel and deletes once there is not. The local
        records follow the same rule.
        """
        self.ensure_one()
        if not self.service_uuid:
            return {'state': self.state, 'message': ''}

        try:
            answer = self.env['easyocr.extractor'].batch_cancel(
                self.company_id, self.service_uuid
            )
        except Exception as error:  # noqa: BLE001 - said, not thrown
            _logger.warning('EasyOCR: could not cancel batch %s: %s', self.service_uuid, error)
            self.error_message = str(error)
            return {'state': self.state, 'message': str(error)}

        if answer.get('status') == 'deleted':
            self.state = 'cancelled'
            self.finished_at = fields.Datetime.now()
            return {'state': 'cancelled', 'deleted': True, 'message': ''}

        self.state = 'cancelled'
        self.finished_at = fields.Datetime.now()
        self.document_ids.filtered(lambda d: d.state == 'draft')._fail_extraction(
            _("The batch was cancelled before this file was read.")
        )
        return {'state': 'cancelled', 'deleted': False, 'message': ''}

    # ------------------------------------------------------------------
    # The cron that keeps an eye on it
    # ------------------------------------------------------------------
    @api.model
    def _cron_refresh(self):
        """Look again at the batches nothing has come back about.

        The webhook is the fast path and the cron is the one that cannot be
        lost: a service that cannot reach this server, or an account with no
        webhook set, still ends up with its readings filed.
        """
        limit = fields.Datetime.now() - timedelta(minutes=REFRESH_EVERY_MINUTES)
        give_up = fields.Datetime.now() - timedelta(hours=GIVE_UP_AFTER_HOURS)
        batches = self.search([
            ('state', 'in', ('pending', 'processing')),
            ('service_uuid', '!=', False),
            ('sent_at', '<=', limit),
            ('sent_at', '>=', give_up),
        ])
        for batch in batches:
            try:
                batch.action_refresh()
            except Exception:  # noqa: BLE001 - one bad batch must not stop the rest
                _logger.exception('EasyOCR: could not refresh batch %s', batch.id)

    # ------------------------------------------------------------------
    # The same three, for the buttons of the record's own form
    # ------------------------------------------------------------------
    # The batch screen reads the answers and draws them where they belong, next
    # to the files they are about. A form has nowhere to put them, so here each
    # one becomes the sentence Odoo shows at the top of the page.
    def action_send_button(self):
        self.ensure_one()
        answer = self.action_send()
        if answer.get('duplicates'):
            raise UserError(_(
                "These files have already been read:\n\n%(files)s\n\n"
                "Sending them again costs the same and changes nothing. Use the "
                "batch screen to send them anyway.",
                files='\n'.join(
                    '- %s' % entry['filename'] for entry in answer['duplicates']
                ),
            ))
        if not answer.get('sent'):
            raise UserError(answer.get('message') or _("The batch could not be sent."))
        return self._notice('success', answer['message'])

    # Answering with a message instead of with nothing is not free: a button that
    # returns an action is a button whose form is not reloaded, so the counts and
    # the state stay as they were painted. Both of these buttons exist to change
    # exactly those, so they answer with nothing and let the form read itself
    # again. The message is kept for the times there is nothing to see.
    def action_refresh_button(self):
        self.ensure_one()
        answer = self.action_refresh()
        if answer.get('message'):
            return self._notice('warning', answer['message'])
        return False

    def action_cancel_button(self):
        self.ensure_one()
        answer = self.action_cancel()
        if answer.get('message'):
            return self._notice('warning', answer['message'])
        if answer.get('deleted'):
            return self._notice('info', _(
                "The batch had already finished, so it and its documents were "
                "dropped at the service."
            ))
        return False

    @staticmethod
    def _notice(kind, message):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'type': kind, 'message': message, 'sticky': False},
        }

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    def action_open_documents(self):
        """The documents this batch filed, opened as their own list.

        ``views`` travels with the action and is not decoration: the web client
        reads the list of views before it can open anything, and an action
        without one is not "open it however you like", it is an error on the way
        in. That is what "See the documents" did the first time it was pressed.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Documents'),
            'res_model': 'easyocr.document',
            'view_mode': 'list,form',
            'views': [(False, 'list'), (False, 'form')],
            'domain': [('batch_id', '=', self.id)],
            'context': {'default_batch_id': self.id},
        }


class EasyocrDocument(models.Model):
    """What a document needs to know about the batch it travelled in."""

    _inherit = 'easyocr.document'

    batch_id = fields.Many2one(
        comodel_name='easyocr.batch',
        string='Batch',
        ondelete='set null',
        copy=False,
    )
    service_document_id = fields.Char(
        string='Document at the service',
        readonly=True,
        copy=False,
        help='What the service calls this file inside its batch. It is what lets '
             'a result be matched to the document it belongs to when two files '
             'of the same batch share a name.',
    )
