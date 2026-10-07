# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License OPL-1 (see LICENSE file).
{
    'name': 'EasyOCR',
    'version': '19.0.1.0.0',
    'summary': 'Extract supplier invoices and expense receipts from PDF and image files',
    'author': 'EasySoft Tech S.L.',
    'website': 'https://easysoft.es',
    'license': 'OPL-1',
    'category': 'Accounting/Accounting',
    'depends': [
        'base',
        'mail',
        'account',
    ],
    'data': [
        'security/easyocr_security.xml',
        'security/ir.model.access.csv',
        'views/easyocr_document_views.xml',
        'views/easyocr_template_views.xml',
        'views/easyocr_webhook_log_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'easyocr/static/src/xml/*.xml',
            'easyocr/static/src/js/*.js',
            'easyocr/static/src/scss/*.scss',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
