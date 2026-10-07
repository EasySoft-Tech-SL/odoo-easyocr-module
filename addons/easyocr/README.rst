======
EasyOCR
======

Extract supplier invoices and expense receipts from PDF and image files.

This module is the Odoo counterpart of EasyOCR for Dolibarr. It exists from the
moment a file is uploaded, so a document that fails extraction stays visible and
can be retried instead of vanishing.

Installation
============

Install the module from the Apps menu, or from the command line:

.. code-block:: bash

   docker compose exec odoo19 odoo -d <database> -i easyocr --stop-after-init

The module depends on ``account`` and ``mail``.

Configuration
=============

Go to *EasyOCR > Configuration* after installing and set the extraction
options. Settings are per company.

Known issues / Roadmap
======================

- Extraction engine (native PDF text and AI service) is not wired yet; only the
  document inbox, its status flow and its permissions are implemented.
- Supplier bill creation from an extracted document is pending.
- Spanish localisation cases (IRPF, recargo de equivalencia, IGIC) are pending.

Bug Tracker
===========

Bugs are tracked on `GitHub Issues <https://github.com/EasySoft-Tech-SL/odoo-easyocr-module/issues>`_.

Credits
=======

Authors
-------

* EasySoft Tech S.L. <https://easysoft.es>

Maintainers
-----------

This module is maintained by EasySoft Tech S.L.
