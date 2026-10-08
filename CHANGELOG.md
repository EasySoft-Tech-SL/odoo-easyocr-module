# Changelog

All notable changes to this module are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the version numbering is Odoo's:
`<odoo series>.<major>.<minor>.<patch>`.

## [Unreleased]

The module reads supplier invoices and expense receipts and turns them into
accounting entries. What follows is everything in this version, in the order the
work was done.

### Added

- **Documents.** Model with the file, the vendor, the dates and the amounts, a
  status flow (pending / received / processed), a sequence, the supplier lines
  read from the document, and a fingerprint of the file so the same invoice is
  not read twice.
- **Document inbox.** What another module hands over before anyone has looked at
  it, with its own list, form and search.
- **The workbench.** One screen for the whole job: it opens waiting for a file --
  open it or drop it, straight from the app's first card -- and becomes the
  viewer in place once one is chosen. The file on the left, and on the right a
  column with everything that can be done to it: read with AI (which says so
  when the account cannot read), create the bill, the nine fields to draw a box
  over, the template, and the values read from each box, taken from the PDF's
  own text layer.
- **Vendor templates.** The boxes drawn over a vendor's paperwork are kept under
  that vendor, so the next invoice from the same vendor opens with them already
  painted and their text read from the new file. The vendor is worked out on the
  server, by tax number and then by name, since a document has none of its own
  until it becomes a bill.
- **Reading with the service.** Client for the EasyOCR extraction service, with a
  `Test the connection` button in the settings that checks the key without
  spending a reading, plain-language messages for every way the service can turn
  a document away, and a guard that refuses a file already read.
- **Batches.** A folder's worth of documents handed over in one call. The files
  are chosen and named on a screen of their own and stay in the page until Send
  is pressed, which is where the readings are paid for, all of them at once. The
  service takes the whole stack in a single request and answers straight away.
  The screen then follows the batch, says how far it has got and what came back
  for each file, and the readings land on the documents themselves, ready to
  review. A file already read is held back and asked about, with the two answers
  the buttons promise: send it anyway, or leave it out and send the rest. A batch
  nobody is watching is collected by a scheduled job, and a webhook on the batch
  is filed as soon as the service says so.
- **Bills.** A draft supplier bill from what was read, one line per line read,
  with the product, discount and rate of each; optional confirmation; and the
  vendor matched by tax number.
- **Photographed receipts.** A capture page for a phone, which files the photo and
  hands it to the module; the receipt can end up as a supplier bill or as an
  employee expense.
- **Webhooks.** A log of every call the service makes, and the option to create
  the bill and register its payment without anyone in front of the screen.
- **Settings.** Sixteen switches over the service, what a document becomes and
  what a webhook may do on its own.
- **Languages.** Spanish, Catalan, Galician, German, French, Italian and
  Portuguese, with a test that checks every term reaches the reader -- field
  labels, help texts, selection labels, model and action names, the sentences the
  module writes at runtime, and the words its own templates paint.
- **Tests.** 200 of them, covering each switch by its effect rather than by its
  value, each one proven to fail when the thing it guards is broken.
- **CI.** Python syntax, manifest and layout check, XML well-formedness, and the
  full suite on Odoo 18 and 19.

### Pending

- **Spanish localisation cases.** IRPF, recargo de equivalencia and IGIC.
- **The three `EASYOCR_EXPENSE_VARIOUS_*` settings** of the module this is a port
  of are not here: the object they file against does not exist in Odoo, so
  bringing them over would have been a switch that does nothing.
