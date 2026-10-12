# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

"""Sending a stack of documents at once.

A batch is where the readings are paid for together, and the two ways that goes
wrong are quiet: the same file sent twice pays twice and says nothing, and a
stack larger than the plan allows comes back refused with nothing read at all.
Both are checked here, by what the module does about them and not by what the
button says.
"""

import base64
from datetime import timedelta

from unittest import mock

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

POST = 'odoo.addons.easyocr.models.easyocr_extractor.requests.post'
GET = 'odoo.addons.easyocr.models.easyocr_extractor.requests.get'
DELETE = 'odoo.addons.easyocr.models.easyocr_extractor.requests.delete'

# The service's own view of an account that may read in batches, with room for
# ten files at a time. Every test that gets as far as sending starts from here.
ACCOUNT = {
    'success': True,
    'data': {
        'account': {'name': 'EasySoft Tech SL'},
        'plan': {'name': 'Professional'},
        'status': {'can_process': True, 'block_code': None, 'block_message': None},
        'quota': {'pages_available_now': 480},
        'features': {'batch_processing': True},
        'limits': {'max_batch_size': 10, 'max_file_size_mb': 10},
    },
}


def _pdf(marker=b''):
    return b'%PDF-1.4 ' + marker + b' the invoice'


@tagged('post_install', '-at_install')
class TestEasyocrBatch(TransactionCase):
    """One stack of files, from choosing them to reading what came back."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Batch = cls.env['easyocr.batch']
        cls.Document = cls.env['easyocr.document']
        cls.company = cls.env.company
        cls.company.write({
            'easyocr_ai_enabled': True,
            'easyocr_ai_url': 'https://ocr.example.test',
            'easyocr_ai_apikey': 'test-key',
            'easyocr_duplicate_check': True,
            'easyocr_duplicate_window_days': 0,
        })

    def setUp(self):
        super().setUp()
        self.env['ir.config_parameter'].sudo().set_param('easyocr.webhook_secret', '')
        self.env['ir.config_parameter'].sudo().set_param('web.base.url', 'https://erp.example.test')

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _files(*names):
        """A stack of files as the screen sends them: name and base64 content."""
        return [
            {
                'filename': name,
                'datas': base64.b64encode(_pdf(name.encode())).decode(),
            }
            for name in names
        ]

    @staticmethod
    def _response(body, status=200):
        response = mock.Mock()
        response.status_code = status
        response.headers = {}
        response.json.return_value = body
        return response

    def _account_ok(self, **changes):
        body = {**ACCOUNT, 'data': {**ACCOUNT['data'], **changes}}
        return self._response(body)

    def _batch(self, count=2, **values):
        batch = self.Batch.create({'name': 'Lote de prueba', **values})
        batch.action_add_files(self._files(*['f%d.pdf' % n for n in range(count)]))
        return batch

    def _send(self, batch, force=False, account=None):
        """Send it with the wire cut: only what the module decided is looked at."""
        with mock.patch(GET, return_value=account or self._account_ok()), \
                mock.patch(POST, return_value=self._response(
                    {'batch_id': 'b-1234', 'total_documents': batch.document_count,
                     'status': 'processing'})):
            return batch.action_send(force=force)

    # ------------------------------------------------------------------
    # Filing the stack
    # ------------------------------------------------------------------
    def test_every_file_becomes_a_document_of_the_batch(self):
        batch = self._batch(3)

        self.assertEqual(batch.document_count, 3)
        self.assertEqual(batch.document_ids.mapped('batch_id'), batch)
        self.assertEqual(
            sorted(batch.document_ids.mapped('name')),
            ['f0.pdf', 'f1.pdf', 'f2.pdf'],
        )
        for document in batch.document_ids:
            self.assertTrue(document.attachment_id, "Un archivo sin adjunto no se puede enviar.")
            self.assertTrue(document.file_hash, "Sin huella no hay guardia de duplicados.")

    def test_a_file_that_cannot_be_read_is_refused_and_says_why(self):
        """It never becomes a document: the service would refuse it anyway."""
        answer = self.Batch.create({'name': 'Con basura'}).action_add_files([
            {'filename': 'hoja.xlsx', 'datas': base64.b64encode(b'x').decode()},
            {'filename': 'vacio.pdf', 'datas': ''},
            {'filename': 'bueno.pdf', 'datas': base64.b64encode(_pdf()).decode()},
        ])

        self.assertEqual(answer['documents'], 1)
        self.assertEqual(len(answer['refused']), 2)
        self.assertEqual(
            sorted(entry['filename'] for entry in answer['refused']),
            ['hoja.xlsx', 'vacio.pdf'],
        )

    def test_the_same_file_twice_in_the_stack_is_reported(self):
        """Paying twice for one file is the mistake a batch makes easiest."""
        batch = self.Batch.create({'name': 'Repetido'})
        content = base64.b64encode(_pdf(b'same')).decode()
        answer = batch.action_add_files([
            {'filename': 'a.pdf', 'datas': content},
            {'filename': 'b.pdf', 'datas': content},
        ])

        self.assertEqual(answer['documents'], 2)
        self.assertEqual(len(answer['duplicates']), 1)
        self.assertIn('twice', answer['duplicates'][0]['reason'])

    def test_a_file_already_read_is_reported(self):
        read = self.env['easyocr.document'].create({
            'name': 'ya-leido.pdf',
            'attachment_id': self.env['ir.attachment'].create({
                'name': 'ya-leido.pdf', 'datas': base64.b64encode(_pdf(b'old')),
            }).id,
        })
        read.state = 'processed'
        read.extraction_date = fields.Datetime.now()

        answer = self.Batch.create({'name': 'Otro'}).action_add_files([
            {'filename': 'copia.pdf', 'datas': base64.b64encode(_pdf(b'old')).decode()},
        ])

        self.assertEqual(len(answer['duplicates']), 1)
        self.assertIn(read.display_name, answer['duplicates'][0]['reason'])

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------
    def test_sending_hands_the_whole_stack_over_in_one_call(self):
        batch = self._batch(3)

        with mock.patch(GET, return_value=self._account_ok()), \
                mock.patch(POST, return_value=self._response({'batch_id': 'b-9'})) as post:
            answer = batch.action_send()

        self.assertTrue(answer['sent'])
        self.assertEqual(batch.service_uuid, 'b-9')
        self.assertEqual(batch.state, 'processing')
        self.assertTrue(batch.sent_at)

        # One call, and every file of the stack inside it. Several parts called
        # `files` without brackets collapse into one on the way in, and the
        # service would read a single document out of the stack in silence.
        self.assertEqual(post.call_count, 1)
        sent = post.call_args.kwargs['files']
        self.assertEqual(len([entry for entry in sent if entry[0] == 'files[]']), 3)
        self.assertEqual(post.call_args.kwargs['headers'], {'X-API-Key': 'test-key'})

    def test_the_options_travel_with_the_batch(self):
        batch = self._batch(1, include_extracted_text=True, auto_correct=True,
                            custom_instructions='Son facturas de marzo.')

        with mock.patch(GET, return_value=self._account_ok()), \
                mock.patch(POST, return_value=self._response({'batch_id': 'b-9'})) as post:
            batch.action_send()

        options = dict(post.call_args.kwargs['files'])
        self.assertEqual(options['name'], 'Lote de prueba')
        self.assertEqual(options['include_extracted_text'], 'true')
        self.assertEqual(options['auto_correct'], 'true')
        # We already hold every file: asking for them back would send each one
        # across twice for nothing.
        self.assertEqual(options['include_original_document'], 'false')
        self.assertIn('Son facturas de marzo.', options['custom_instructions'])

    def test_a_file_already_read_stops_the_send_and_asks(self):
        """The whole stack is held back, because the answer is about the stack."""
        read = self.env['easyocr.document'].create({
            'name': 'leido.pdf',
            'attachment_id': self.env['ir.attachment'].create({
                'name': 'leido.pdf', 'datas': base64.b64encode(_pdf(b'dup')),
            }).id,
        })
        read.state = 'processed'
        read.extraction_date = fields.Datetime.now()

        batch = self.Batch.create({'name': 'Con repetido'})
        batch.action_add_files([
            {'filename': 'dup.pdf', 'datas': base64.b64encode(_pdf(b'dup')).decode()},
        ])

        with mock.patch(GET, return_value=self._account_ok()), \
                mock.patch(POST, return_value=self._response({'batch_id': 'b-9'})) as post:
            answer = batch.action_send()

        self.assertFalse(answer['sent'])
        self.assertEqual(len(answer['duplicates']), 1)
        self.assertEqual(post.call_count, 0, "No se puede enviar nada antes de preguntar.")
        self.assertFalse(batch.service_uuid)

    def test_leaving_the_duplicates_out_sends_the_rest(self):
        """What the answer says it does: those files do not go, the others do."""
        read = self.env['easyocr.document'].create({
            'name': 'leido.pdf',
            'attachment_id': self.env['ir.attachment'].create({
                'name': 'leido.pdf', 'datas': base64.b64encode(_pdf(b'dup')),
            }).id,
        })
        read.state = 'processed'
        read.extraction_date = fields.Datetime.now()

        batch = self.Batch.create({'name': 'Con repetido'})
        batch.action_add_files([
            {'filename': 'dup.pdf', 'datas': base64.b64encode(_pdf(b'dup')).decode()},
            {'filename': 'nuevo.pdf', 'datas': base64.b64encode(_pdf(b'new')).decode()},
        ])
        self.assertEqual(batch.document_count, 2)

        with mock.patch(GET, return_value=self._account_ok()), \
                mock.patch(POST, return_value=self._response({'batch_id': 'b-9'})) as post:
            answer = batch.action_send(leave_out_duplicates=True)

        self.assertTrue(answer['sent'])
        self.assertEqual(answer['skipped'], ['dup.pdf'])
        # Fuera del lote, y no borrado: el archivo se archivó y alguien dijo que
        # no se enviara. Sigue en la lista de documentos, sin leer.
        self.assertEqual(batch.document_count, 1)
        self.assertEqual(batch.document_ids.name, 'nuevo.pdf')
        left = self.env['easyocr.document'].search([('name', '=', 'dup.pdf')])
        self.assertTrue(left.exists())
        self.assertFalse(left.batch_id)
        self.assertFalse(left.extraction_date, "Lo que no se envía no se ha pagado.")
        self.assertEqual(len([f for f in post.call_args.kwargs['files'] if f[0] == 'files[]']), 1)

    def test_leaving_out_the_only_file_leaves_nothing_to_send(self):
        read = self.env['easyocr.document'].create({
            'name': 'leido.pdf',
            'attachment_id': self.env['ir.attachment'].create({
                'name': 'leido.pdf', 'datas': base64.b64encode(_pdf(b'solo')),
            }).id,
        })
        read.state = 'processed'
        read.extraction_date = fields.Datetime.now()

        batch = self.Batch.create({'name': 'Uno repetido'})
        batch.action_add_files([
            {'filename': 'solo.pdf', 'datas': base64.b64encode(_pdf(b'solo')).decode()},
        ])

        with mock.patch(GET, return_value=self._account_ok()), mock.patch(POST) as post:
            answer = batch.action_send(leave_out_duplicates=True)

        self.assertFalse(answer['sent'])
        self.assertEqual(post.call_count, 0)

    def test_sending_anyway_is_what_the_answer_unlocks(self):
        read = self.env['easyocr.document'].create({
            'name': 'leido.pdf',
            'attachment_id': self.env['ir.attachment'].create({
                'name': 'leido.pdf', 'datas': base64.b64encode(_pdf(b'dup')),
            }).id,
        })
        read.state = 'processed'
        read.extraction_date = fields.Datetime.now()

        batch = self.Batch.create({'name': 'Con repetido'})
        batch.action_add_files([
            {'filename': 'dup.pdf', 'datas': base64.b64encode(_pdf(b'dup')).decode()},
        ])

        with mock.patch(GET, return_value=self._account_ok()), \
                mock.patch(POST, return_value=self._response({'batch_id': 'b-9'})):
            answer = batch.action_send(force=True)

        self.assertTrue(answer['sent'])
        self.assertEqual(batch.service_uuid, 'b-9')

    def test_the_send_is_noted_on_the_documents_themselves(self):
        """The duplicate window counts readings, and the batch was paid for now."""
        batch = self._batch(2)

        self._send(batch)

        for document in batch.document_ids:
            self.assertTrue(
                document.extraction_date,
                "Un lote pagado y sin fecha no protege de volver a enviarlo.",
            )

    def test_a_batch_that_was_already_sent_is_not_sent_again(self):
        batch = self._batch(1)
        self._send(batch)

        with self.assertRaises(UserError):
            batch.action_send()

    def test_an_empty_batch_is_not_sent(self):
        with self.assertRaises(UserError):
            self.Batch.create({'name': 'Vacío'}).action_send()

    # ------------------------------------------------------------------
    # What the account allows
    # ------------------------------------------------------------------
    def test_a_plan_without_batches_is_refused_before_anything_is_sent(self):
        batch = self._batch(1)
        account = self._account_ok(features={'batch_processing': False})

        with mock.patch(GET, return_value=account), mock.patch(POST) as post:
            answer = batch.action_send()

        self.assertFalse(answer['sent'])
        self.assertIn('one at a time', answer['message'])
        self.assertEqual(post.call_count, 0)
        self.assertEqual(batch.error_message, answer['message'])

    def test_a_stack_larger_than_the_plan_allows_is_refused_here(self):
        """Refused here and not there: the call would come back with nothing read."""
        batch = self._batch(3)
        account = self._account_ok(limits={'max_batch_size': 2, 'max_file_size_mb': 10})

        with mock.patch(GET, return_value=account), mock.patch(POST) as post:
            answer = batch.action_send()

        self.assertFalse(answer['sent'])
        self.assertIn('2', answer['message'])
        self.assertIn('3', answer['message'])
        self.assertEqual(post.call_count, 0)

    def test_an_account_that_cannot_read_says_which_block_it_is(self):
        """The three blocks send the reader to three different places."""
        blocks = {
            'SUBSCRIPTION_OVERDUE': 'overdue',
            'WALLET_EMPTY': 'no readings left',
            'ACCOUNT_DISABLED': 'switched off',
        }
        for code, expected in blocks.items():
            batch = self._batch(1)
            account = self._account_ok(status={'can_process': False, 'block_code': code})

            with mock.patch(GET, return_value=account), mock.patch(POST) as post:
                answer = batch.action_send()

            self.assertFalse(answer['sent'], code)
            self.assertIn(expected, answer['message'], code)
            self.assertEqual(post.call_count, 0, code)

    def test_without_a_key_nothing_is_asked_of_the_service(self):
        self.company.easyocr_ai_apikey = False

        with mock.patch(GET) as get, mock.patch(POST) as post:
            answer = self._batch(1).action_send()

        self.assertFalse(answer['sent'])
        self.assertEqual(get.call_count, 0)
        self.assertEqual(post.call_count, 0)

    def test_a_service_that_does_not_answer_is_said_and_not_thrown(self):
        import requests

        batch = self._batch(1)
        with mock.patch(GET, side_effect=requests.ConnectionError('sin ruta')):
            answer = batch.action_send()

        self.assertFalse(answer['sent'])
        self.assertTrue(answer['message'])
        self.assertEqual(batch.state, 'pending')

    # ------------------------------------------------------------------
    # What comes back
    # ------------------------------------------------------------------
    def test_the_results_land_on_the_document_of_each_file(self):
        batch = self._batch(2)
        self._send(batch)
        first, second = batch.document_ids

        results = {
            'batch_id': 'b-1234',
            'status': 'completed',
            'documents': [
                {
                    'document_id': 'd-1',
                    'filename': first.attachment_id.name,
                    'status': 'completed',
                    'ocr_confidence': 0.93,
                    'structured_data': {
                        'document_number': 'A/1',
                        'supplier': {'name': 'Proveedor SL', 'tax_id': 'B3186006'},
                        'totals': {'total': 121.0},
                    },
                },
                {
                    'document_id': 'd-2',
                    'filename': second.attachment_id.name,
                    'status': 'failed',
                    'error': 'El archivo no se pudo abrir.',
                },
            ],
        }
        # Two calls and no more: asking about a batch is not the same question
        # as asking what the account may do, and the second one is only asked
        # when a stack is about to be sent.
        with mock.patch(GET, side_effect=[
            self._response({'status': 'completed', 'batch_id': 'b-1234'}),
            self._response(results),
        ]):
            batch.action_refresh()

        self.assertEqual(batch.state, 'completed')
        self.assertEqual(first.state, 'processed')
        self.assertEqual(first.ref, 'A/1')
        self.assertEqual(first.partner_name, 'Proveedor SL')
        self.assertEqual(first.service_document_id, 'd-1')
        self.assertEqual(first.extraction_confidence, 0.93)

        self.assertEqual(second.state, 'error')
        self.assertIn('no se pudo abrir', second.error_message)
        self.assertEqual(batch.completed_count, 1)
        self.assertEqual(batch.failed_count, 1)
        self.assertEqual(batch.progress, 100.0)

    def test_a_file_the_service_does_not_know_is_left_alone(self):
        """Nothing is invented for a document we never sent."""
        batch = self._batch(1)
        self._send(batch)

        with mock.patch(GET, side_effect=[
            self._response({'status': 'completed', 'batch_id': 'b-1234'}),
            self._response({'status': 'completed', 'documents': [
                {'document_id': 'd-9', 'filename': 'otro.pdf', 'status': 'completed',
                 'structured_data': {'document_number': 'Z/9'}},
            ]}),
        ]):
            batch.action_refresh()

        self.assertEqual(batch.document_ids.state, 'draft')
        self.assertFalse(batch.document_ids.ref)

    def test_a_finished_batch_is_not_asked_about_again(self):
        """Every time the screen opens would otherwise be another call."""
        batch = self._batch(1)
        self._send(batch)
        batch.state = 'completed'

        with mock.patch(GET) as get:
            batch.action_refresh()

        self.assertEqual(get.call_count, 0)

    def test_the_progress_is_worked_out_from_the_documents(self):
        batch = self._batch(4)
        self._send(batch)
        batch.document_ids[0].state = 'processed'
        batch.document_ids[1].state = 'error'

        self.assertEqual(batch.completed_count, 1)
        self.assertEqual(batch.failed_count, 1)
        self.assertEqual(batch.progress, 50.0)

    # ------------------------------------------------------------------
    # The call from the service
    # ------------------------------------------------------------------
    def test_a_document_that_comes_back_is_filed_on_its_own_document(self):
        batch = self._batch(2)
        self._send(batch)
        first = batch.document_ids[0]

        note = self.Batch._settle_webhook({
            'document_id': 'd-7',
            'filename': first.attachment_id.name,
            'status': 'completed',
            'structured_data': {'document_number': 'B/7'},
        }, batch.service_uuid)

        self.assertTrue(note)
        self.assertEqual(first.ref, 'B/7')
        self.assertEqual(first.service_document_id, 'd-7')
        self.assertEqual(first.state, 'processed')

    def test_a_second_call_about_the_same_document_lands_on_the_same_row(self):
        """Webhook and cron both arrive; the same reading must not double."""
        batch = self._batch(1)
        self._send(batch)
        document = batch.document_ids[0]
        payload = {
            'document_id': 'd-7',
            'filename': document.attachment_id.name,
            'status': 'completed',
            'structured_data': {'document_number': 'B/7'},
        }

        self.Batch._settle_webhook(payload, batch.service_uuid)
        self.Batch._settle_webhook(payload, batch.service_uuid)

        self.assertEqual(len(batch.document_ids), 1)
        self.assertEqual(document.ref, 'B/7')

    def test_a_file_the_batch_never_had_is_refused_by_name(self):
        batch = self._batch(1)
        self._send(batch)

        with self.assertRaises(ValueError):
            self.Batch._settle_webhook(
                {'document_id': 'd-9', 'filename': 'fantasma.pdf', 'status': 'completed'},
                batch.service_uuid,
            )

    def test_the_end_of_the_batch_takes_its_state(self):
        batch = self._batch(1)
        self._send(batch)

        with mock.patch(GET, side_effect=[
            self._response({'status': 'partial', 'batch_id': 'b-1234'}),
            self._response({'status': 'partial', 'documents': []}),
        ]):
            note = self.Batch._finish_webhook(
                {'batch_id': 'b-1234', 'status': 'partial'}, batch.service_uuid
            )

        self.assertTrue(note)
        self.assertEqual(batch.state, 'partial')
        self.assertTrue(batch.finished_at)

    def test_a_batch_nobody_knows_is_refused(self):
        with self.assertRaises(ValueError):
            self.Batch._finish_webhook({'batch_id': 'no-existe', 'status': 'completed'})

    # ------------------------------------------------------------------
    # Letting it go
    # ------------------------------------------------------------------
    def test_cancelling_a_running_batch_stops_it(self):
        batch = self._batch(1)
        self._send(batch)

        with mock.patch(DELETE, return_value=self._response({'status': 'cancelled'})):
            answer = batch.action_cancel()

        self.assertEqual(batch.state, 'cancelled')
        self.assertFalse(answer['deleted'])
        self.assertEqual(batch.document_ids.state, 'error')

    def test_cancelling_a_finished_batch_drops_it_at_the_service(self):
        """One call, two outcomes, and the service is the one that decides."""
        batch = self._batch(1)
        self._send(batch)

        with mock.patch(DELETE, return_value=self._response(
                {'status': 'deleted', 'message': 'gone'})):
            answer = batch.action_cancel()

        self.assertTrue(answer['deleted'])
        self.assertEqual(batch.state, 'cancelled')

    # ------------------------------------------------------------------
    # The job that keeps an eye on them
    # ------------------------------------------------------------------
    def test_the_job_only_looks_at_batches_that_are_still_going(self):
        running = self._batch(1)
        self._send(running)
        running.sent_at = fields.Datetime.now() - timedelta(minutes=30)

        finished = self._batch(1)
        self._send(finished)
        finished.sent_at = fields.Datetime.now() - timedelta(minutes=30)
        finished.state = 'completed'

        waiting = self._batch(1)
        self._send(waiting)
        waiting.sent_at = fields.Datetime.now() - timedelta(minutes=1)

        forgotten = self._batch(1)
        self._send(forgotten)
        forgotten.sent_at = fields.Datetime.now() - timedelta(days=3)

        looked_at = []
        with mock.patch.object(type(self.Batch), 'action_refresh',
                               lambda self: looked_at.append(self)) as _refresh:
            self.Batch._cron_refresh()

        self.assertEqual(looked_at, [running])

    # ------------------------------------------------------------------
    # Where it is told
    # ------------------------------------------------------------------
    def test_without_a_secret_the_service_is_told_nothing(self):
        """An address the endpoint would refuse is worse than no address."""
        self.assertFalse(self._batch(1)._default_notify_url())

    def test_with_a_secret_the_address_carries_the_batch(self):
        self.env['ir.config_parameter'].sudo().set_param('easyocr.webhook_secret', 's3cr3t')
        batch = self._batch(1)

        url = batch._default_notify_url()

        self.assertIn('/easyocr/webhook', url)
        self.assertIn('batch=%s' % batch.id, url)
        self.assertIn('secret=s3cr3t', url)

    def test_the_address_travels_with_the_send(self):
        self.env['ir.config_parameter'].sudo().set_param('easyocr.webhook_secret', 's3cr3t')
        batch = self._batch(1)

        with mock.patch(GET, return_value=self._account_ok()), \
                mock.patch(POST, return_value=self._response({'batch_id': 'b-9'})) as post:
            batch.action_send()

        options = dict(post.call_args.kwargs['files'])
        self.assertIn('batch=%s' % batch.id, options['webhook_url'])

    def test_an_address_of_our_own_is_used_instead(self):
        batch = self._batch(1, notify_url='https://otro.example.test/aviso')

        with mock.patch(GET, return_value=self._account_ok()), \
                mock.patch(POST, return_value=self._response({'batch_id': 'b-9'})) as post:
            batch.action_send()

        options = dict(post.call_args.kwargs['files'])
        self.assertEqual(options['webhook_url'], 'https://otro.example.test/aviso')


@tagged('post_install', '-at_install')
class TestEasyocrBatchPlumbing(TransactionCase):
    """The pieces that make the screen reachable and the model usable."""

    def test_the_screen_is_a_client_action_of_its_own(self):
        action = self.env.ref('easyocr.action_easyocr_new_batch')
        self.assertEqual(action.tag, 'easyocr.batch')

    def test_the_batches_are_reachable_from_the_app(self):
        menu = self.env.ref('easyocr.menu_easyocr_batch')
        self.assertEqual(menu.action.res_model, 'easyocr.batch')

    def test_a_manager_may_delete_a_batch_and_a_user_may_not(self):
        """The same split the documents have: looking is not deleting."""
        access = self.env['ir.model.access'].search([
            ('model_id.model', '=', 'easyocr.batch'),
        ])
        by_group = {
            entry.group_id: entry
            for entry in access
        }
        user = self.env.ref('easyocr.group_easyocr_user')
        manager = self.env.ref('easyocr.group_easyocr_manager')

        self.assertIn(user, by_group)
        self.assertIn(manager, by_group)
        self.assertFalse(by_group[user].perm_unlink)
        self.assertTrue(by_group[manager].perm_unlink)

    def test_the_job_that_collects_the_batches_is_installed(self):
        cron = self.env.ref('easyocr.ir_cron_easyocr_batch')
        self.assertTrue(cron.active)
        self.assertEqual(cron.model_id.model, 'easyocr.batch')
        self.assertIn('_cron_refresh', cron.code)

    def test_the_action_that_opens_the_documents_carries_its_views(self):
        """Without them the client cannot open it at all: it is an error, not a
        default. The button was dead the first time it was pressed."""
        batch = self.env['easyocr.batch'].create({'name': 'Con acción'})
        batch.action_add_files([
            {'filename': 'a.pdf', 'datas': base64.b64encode(_pdf(b'a')).decode()},
        ])

        action = batch.action_open_documents()

        self.assertEqual(action['res_model'], 'easyocr.document')
        self.assertTrue(action['views'], "El cliente lee esta lista antes de abrir nada.")
        self.assertEqual(action['domain'], [('batch_id', '=', batch.id)])

    def test_the_states_the_service_uses_are_the_states_we_know(self):
        """An unknown state would leave a batch stuck for ever in 'processing'."""
        selection = dict(self.env['easyocr.batch']._fields['state'].selection)
        self.assertEqual(
            sorted(selection),
            ['cancelled', 'completed', 'failed', 'partial', 'pending', 'processing'],
        )
