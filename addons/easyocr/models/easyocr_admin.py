# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

import os

from odoo import _, api, models
from odoo.exceptions import AccessError

from .easyocr_extractor import EasyocrServiceError

MODULE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class EasyocrAdmin(models.AbstractModel):
    """What the module's configuration tabs show, besides the settings.

    The module this is a port of keeps six tabs on its setup page: the setup
    itself, the service plan, the licence, telemetry and data protection, about
    and the changelog. The settings live where Odoo keeps settings; the other
    five are pages, and this is where each of them gets what it shows. All of
    it is read from the module's own files or from the service's account
    endpoint, which spends no reading.
    """

    _name = 'easyocr.admin'
    _description = 'EasyOCR configuration pages'

    def _check_manager(self):
        if not self.env.user.has_group('easyocr.group_easyocr_manager'):
            raise AccessError(_("Only EasyOCR managers can see the module's configuration."))

    @api.model
    def _read_file(self, name):
        path = os.path.join(MODULE_ROOT, name)
        if not os.path.isfile(path):
            return ''
        with open(path, encoding='utf-8') as handle:
            return handle.read()

    @api.model
    def _module_info(self):
        module = self.env['ir.module.module'].sudo().search([('name', '=', 'easyocr')], limit=1)
        return {
            'name': 'EasyOCR',
            'version': module.installed_version or module.latest_version or '',
            'author': 'EasySoft Tech S.L.',
            'vat': 'B16885766',
            'website': 'https://easysoft.es',
            'email': 'info@easysoft.es',
            'license': 'LGPL-3',
        }

    @api.model
    def _readme_html(self):
        """The module's README, as the page shows it: rendered, not raw."""
        text = self._read_file('README.rst')
        if not text:
            return ''
        from docutils.core import publish_parts
        parts = publish_parts(
            text,
            writer_name='html',
            settings_overrides={
                # Our own file, but a README is no place for these either way.
                'file_insertion_enabled': False,
                'raw_enabled': False,
                'report_level': 5,
                'doctitle_xform': False,
            },
        )
        return parts.get('html_body') or ''

    @api.model
    def action_admin_page(self, tab):
        """Everything one tab draws, in one answer."""
        self._check_manager()
        company = self.env.company
        answer = {'tab': tab, 'module': self._module_info()}
        if tab == 'about':
            answer['readme_html'] = self._readme_html()
        elif tab == 'license':
            answer['license_text'] = self._read_file('LICENSE')
        elif tab == 'changelog':
            answer['changelog'] = self._read_file('CHANGELOG.md')
        elif tab == 'telemetry':
            answer['ai_enabled'] = bool(company.easyocr_ai_enabled)
            answer['receiver_context'] = bool(company.easyocr_ai_receiver_context)
            answer['service_url'] = (company.easyocr_ai_url or '').strip()
        elif tab == 'plan':
            answer.update(self._plan(company))
        return answer

    @api.model
    def _plan(self, company):
        """The account as the service sees it, or why it cannot be shown."""
        if not company.easyocr_ai_enabled or not (company.easyocr_ai_apikey or '').strip():
            return {'state': 'not_configured', 'data': {}}
        try:
            data = self.env['easyocr.extractor'].account(company)
        except EasyocrServiceError as error:
            state = 'auth_error' if error.status in (401, 403) else 'api_error'
            return {'state': state, 'error': str(error), 'data': {}}
        if not data:
            return {'state': 'no_data', 'data': {}}
        return {'state': 'ok', 'data': data}
