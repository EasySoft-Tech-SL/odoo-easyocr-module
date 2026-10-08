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
- **The viewer.** Full screen, the file on the left and the data on the right.
  Nine fields to draw a box over, the text under each box read from the PDF's own
  text layer, boxes saved as a template for a vendor, and the two buttons that
  finish the job -- read with AI and create the bill -- without leaving the
  screen.
- **Uploading a document.** One file in, the viewer out, straight from the app's
  first screen.
- **Reading with the service.** Client for the EasyOCR extraction service, with a
  `Test the connection` button in the settings that checks the key without
  spending a reading, plain-language messages for every way the service can turn
  a document away, and a guard that refuses a file already read.
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
- **Tests.** 140 of them, covering each switch by its effect rather than by its
  value, each one proven to fail when the thing it guards is broken.
- **CI.** Python syntax, manifest and layout check, XML well-formedness, and the
  full suite on Odoo 18 and 19.

### Pending

- **Batch reading.** Handing a folder of documents over in one go has no screen
  yet.
- **Templates are saved but not applied.** The next invoice from a vendor does not
  pick up the boxes stored for that vendor; they have to be drawn again.
- **Spanish localisation cases.** IRPF, recargo de equivalencia and IGIC.
- **The three `EASYOCR_EXPENSE_VARIOUS_*` settings** of the module this is a port
  of are not here: the object they file against does not exist in Odoo, so
  bringing them over would have been a switch that does nothing.
