# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License OPL-1 (see LICENSE file).

import base64
import binascii
import contextlib
import hashlib
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# The largest file the tray takes, in megabytes. Other modules hand files over
# with nobody in front of a screen, so the limit lives here as well, and the
# name is public so a caller can refuse a file before sending it.
MAX_SIZE_MB = 10

# Every PDF starts with these four bytes. Checking them turns away a renamed
# .zip without pulling in a PDF parser.
PDF_MAGIC = b'%PDF'


class EasyocrInboxItem(models.Model):
    """A file another module handed over, waiting for someone to read it.

    Nothing is sent to the extraction service when the file arrives: it sits
    here until a person decides to spend the call. That is the point of the
    tray, and it is why receiving a file costs nothing.
    """

    _name = 'easyocr.inbox.item'
    _description = 'OCR Inbox Item'
    _inherit = ['mail.thread']
    _order = 'create_date desc, id desc'

    name = fields.Char(
        string='File Name',
        required=True,
        tracking=True,
    )
    datas = fields.Binary(
        string='File',
        attachment=True,
    )
    file_size = fields.Integer(
        string='Size',
        readonly=True,
        help='Size of the file in bytes.',
    )
    file_hash = fields.Char(
        string='Fingerprint',
        readonly=True,
        help='SHA-256 of the file. Lets the tray turn away a file sent twice.',
    )
    origin = fields.Char(
        string='Origin',
        help='Who handed the file over, for instance easyscan or a mail gateway.',
    )
    state = fields.Selection(
        selection=[
            ('pending', 'Pending'),
            ('processed', 'Processed'),
            ('discarded', 'Discarded'),
        ],
        string='Status',
        default='pending',
        required=True,
        tracking=True,
    )
    document_id = fields.Many2one(
        comodel_name='easyocr.document',
        string='Document',
        readonly=True,
        copy=False,
        ondelete='set null',
        help='The OCR document built from this file, once it was processed.',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )
    note = fields.Text(string='Notes')

    # The same file twice is always a mistake, and the fingerprint is what makes
    # it one: two scans of one invoice have different names and the same bytes.
    # Rows built by hand carry no fingerprint, and PostgreSQL lets a unique index
    # hold as many NULLs as it likes, so those never collide.
    _file_company_uniq = models.Constraint(
        'UNIQUE (company_id, file_hash)',
        'This file is already in the inbox.',
    )

    # ------------------------------------------------------------------
    # From another module into the tray
    # ------------------------------------------------------------------
    @api.model
    def _file_bytes(self, source):
        """The raw bytes of the file, from either of the two shapes it arrives in.

        Odoo carries binary values base64-encoded and hands them back that way,
        while a module holding a fresh file has plain bytes; both end up here.
        Neither is guessed from the type alone -- what tells them apart is which
        of the two is a PDF, and nothing but a PDF gets past this method.
        """
        if isinstance(source, str):
            source = source.encode('utf-8')
        if not isinstance(source, (bytes, bytearray)):
            return b''
        content = bytes(source)
        if content.startswith(PDF_MAGIC):
            return content
        with contextlib.suppress(binascii.Error, ValueError):
            decoded = base64.b64decode(content, validate=True)
            if decoded.startswith(PDF_MAGIC):
                return decoded
        return content

    @api.model
    def _as_user(self, user):
        """The user a file is delivered for: a record, an id, or whoever calls."""
        if not user:
            return self.env.user
        if isinstance(user, int):
            return self.env['res.users'].browse(user)
        return user

    @api.model
    def _outcome(self, ok, item_id=0, error=''):
        """The shape every call to :meth:`recibir` comes back in."""
        return {'ok': ok, 'id': item_id or 0, 'error': error}

    @api.model
    def _fingerprint(self, values):
        """Write the size and the fingerprint of the file into the values.

        The fingerprint is always worked out from the bytes, never taken from
        the caller, so it cannot disagree with the file it is supposed to
        describe. Called on create and on write, so a file uploaded by hand is
        kept out when it is a copy of one already in the tray, exactly like a
        file handed over by another module.
        """
        if 'datas' not in values:
            return values
        content = self._file_bytes(values.get('datas') or b'')
        values['file_hash'] = hashlib.sha256(content).hexdigest() if content else False
        values['file_size'] = len(content)
        return values

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            self._fingerprint(values)
        return super().create(vals_list)

    def write(self, values):
        if 'datas' in values:
            values = dict(values)
            self._fingerprint(values)
        return super().write(values)

    @api.model
    def recibir(self, file_bytes, filename, origin, user=None):
        """Hand a file to the tray. The way in for every other module.

        The name is Spanish because it is the published entry point other
        modules already call; everything behind it is in English.

        Never raises: the result comes back as ``{'ok', 'id', 'error'}`` so a
        caller behind an API or a cron can report what happened without a
        traceback. When the file is already in the tray, ``ok`` is False and
        ``id`` points at the item that holds it, so the caller can say where it
        went instead of just failing.
        """
        user = self._as_user(user)
        if not self.with_user(user).has_access('create'):
            return self._outcome(
                False, error=_('You are not allowed to add documents to the inbox.'),
            )

        filename = (filename or '').strip()
        if not filename:
            return self._outcome(False, error=_('The file has no name.'))

        content = self._file_bytes(file_bytes)
        if not content:
            return self._outcome(False, error=_('The file is empty.'))

        if len(content) > MAX_SIZE_MB * 1024 * 1024:
            return self._outcome(False, error=_(
                'The file is larger than the %(limit)s MB the inbox takes.',
                limit=MAX_SIZE_MB,
            ))

        if not content.startswith(PDF_MAGIC):
            return self._outcome(
                False, error=_('Only PDF files are accepted by the inbox.'),
            )

        fingerprint = hashlib.sha256(content).hexdigest()
        company = self.env.company
        duplicate = self.search([
            ('company_id', '=', company.id),
            ('file_hash', '=', fingerprint),
        ], limit=1)
        if duplicate:
            return self._outcome(
                False, duplicate.id, _('This file is already in the inbox.'),
            )

        try:
            item = self.with_user(user).create({
                'name': filename,
                'datas': base64.b64encode(content),
                'origin': origin or '',
                'company_id': company.id,
            })
        except Exception:
            # Two modules can send the same scan at the same moment, and every
            # other failure has to reach the caller as a message too.
            _logger.exception("Could not file %r in the EasyOCR inbox", filename)
            return self._outcome(
                False, error=_('The file could not be filed in the inbox.'),
            )

        return self._outcome(True, item.id)

    # ------------------------------------------------------------------
    # What a person does with the tray
    # ------------------------------------------------------------------
    def action_process(self):
        """Build the OCR document for the file and open its viewer.

        Processing only means taking the file out of the tray and looking at it:
        the call to the extraction service stays where it was, in the viewer, and
        is made when whoever is reading says so.
        """
        self.ensure_one()
        if self.state == 'discarded':
            raise UserError(_(
                "This item was discarded. Restore it before processing it."
            ))
        if not self.datas:
            raise UserError(_("There is no file on this item."))
        if self.document_id:
            # Already processed once: opening it again beats filing it twice.
            return self.document_id.action_open_viewer()

        document = self.env['easyocr.document'].create({
            'name': self.name,
            'company_id': self.company_id.id,
            'currency_id': self.company_id.currency_id.id,
        })
        attachment = self.env['ir.attachment'].create({
            'name': self.name,
            'datas': self.datas,
            'res_model': 'easyocr.document',
            'res_id': document.id,
        })
        document.attachment_id = attachment.id
        self.document_id = document.id
        self.state = 'processed'

        return document.action_open_viewer()

    def action_discard(self):
        """Put the item aside without deleting anything.

        The file stays on the record and the button asks for confirmation, so
        nothing leaves the tray on its own and nothing is lost by accident.
        """
        for item in self:
            item.state = 'discarded'

    def action_restore(self):
        """Put a discarded item back in the tray."""
        for item in self:
            item.state = 'pending'

    def action_open_document(self):
        """Open the OCR document built from this file."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'easyocr.document',
            'res_id': self.document_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
