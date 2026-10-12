=======
EasyOCR
=======

Extract supplier invoices and expense receipts from PDF and image files.

This module is the Odoo counterpart of EasyOCR for Dolibarr, by EasySoft Tech
S.L. A document exists from the moment its file is uploaded, so one that fails
to be read stays visible and can be retried instead of vanishing.

What it does
============

- Reads PDFs that already carry their text for free, by drawing boxes over the
  page in a viewer, and keeps those boxes as a template per supplier.
- Reads scans and photographs with the EasyOCR extraction service, and shows
  the result in a dialog where every value can be checked and corrected.
- Creates the supplier bill or credit note, with one line per line read and
  the company's taxes for the rates read (VAT, equivalence surcharge and
  withholding). A supplier that is not on file is created from the reading.
- Optionally registers the payment, sends whole batches to the service, files
  photographed receipts from a phone page and logs the service's webhooks.

Installation
============

Install the module from the Apps menu, or from the command line:

::

   odoo -d <database> -i easyocr --stop-after-init

The module depends on ``base``, ``mail``, ``account`` and ``hr_expense``, all of
them part of Odoo Community.

Configuration
=============

Go to *Settings > EasyOCR*. Reading PDFs that carry their text needs nothing.
Reading scans and photographs needs the EasyOCR service: switch on the AI
extraction, fill in the service address and the API key, and use *Test the
connection*, which spends no reading. Settings are per company.

Known issues / Roadmap
======================

- IGIC (Canary Islands) is not handled yet.
- A rate the company has no purchase tax for leaves the line without tax: the
  module does not invent one.

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
