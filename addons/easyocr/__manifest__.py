# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).
{
    'name': 'EasyOCR',
    'version': '19.0.1.0.7',
    'summary': 'Extract supplier invoices and expense receipts from PDF and image files',
    'author': 'EasySoft Tech S.L.',
    'website': 'https://easysoft.es',
    'license': 'LGPL-3',
    'category': 'Accounting/Accounting',
    'support': 'info@easysoft.es',
    # Lo que la tienda de Odoo ensena: la primera es la portada de la ficha en el
    # catalogo, y las demas van en la galeria. Los ficheros viven dentro del
    # modulo (rutas relativas): la tienda lee el repositorio, no el ZIP.
    'images': [
        'static/description/cover.png',
        'static/description/shot-1-workbench.jpg',
        'static/description/shot-2-reading.jpg',
        'static/description/shot-3-document.jpg',
        'static/description/shot-4-bill.jpg',
        'static/description/shot-5-settings.jpg',
    ],
    'depends': [
        'base',
        'mail',
        'account',
        # Ships with Odoo Community, so it costs nothing to depend on, and it is
        # what an employee's photographed receipt becomes -- which the module's
        # own summary promises. It is what "Expense receipts" means in Odoo.
        'hr_expense',
    ],
    'data': [
        'security/easyocr_security.xml',
        'security/ir.model.access.csv',
        # El menu raiz, antes que nada: todo lo demas cuelga de el y Odoo
        # resuelve un xmlid mientras lee el fichero que lo usa.
        'views/easyocr_menu_views.xml',
        'views/easyocr_home_views.xml',
        'views/easyocr_document_views.xml',
        'views/easyocr_reprocess_wizard_views.xml',
        'views/easyocr_reading_result_views.xml',
        'views/easyocr_batch_views.xml',
        'views/easyocr_inbox_views.xml',
        'views/easyocr_template_views.xml',
        'views/easyocr_webhook_log_views.xml',
        'views/easyocr_invoice_views.xml',
        'views/easyocr_upload_views.xml',
        'views/expense_capture_views.xml',
        'views/res_config_settings_views.xml',
        'data/easyocr_cron.xml',
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
