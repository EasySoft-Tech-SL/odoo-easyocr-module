# Roadmap

EasyOCR reads supplier invoices and expense receipts from files and turns them into
accounting entries. This roadmap is the port of EasyOCR for Dolibarr (v2.8.0) to Odoo
Community.

One branch per Odoo series (`18.0`, `19.0`). Every phase below applies to both branches;
when a phase needs different code per series it says so explicitly.

Status: `done` · `in progress` · `pending`

---

## Phase 0 — Skeleton · done

- [x] Module `easyocr` installs on 18.0 and 19.0.
- [x] Document model with its status flow (pending / processed / error).
- [x] Access groups (User, Manager) and their access rules.
- [x] List, form and search views, with menu.
- [x] Spanish translation.
- [x] Tests that fail when the status flow breaks.
- [x] Branch checks in CI: manifest, layout, Python syntax, XML well-formedness.

## Phase 1 — Document viewer with rectangle templates · in progress

This is the screen the user recognises: the PDF on the left, the data panel on the right.

- [x] Client action with an OWL component (a full screen of our own, not a form view).
- [x] PDF rendered from the PDF.js copy that ships with Odoo core, one canvas per page.
- [x] Drag a rectangle over the page and assign it to a field
      (document date, document number, untaxed amount, total, vendor).
- [x] Read the text inside each rectangle from the PDF text layer, cut at
      character level so a box can take part of a line.
- [x] Save the set of rectangles as a template for that vendor.
- [ ] Reapply a vendor template to a new document of the same vendor.
- [ ] Apply a template automatically when the vendor is known.
- [ ] Move and resize a box that has already been drawn.

**Why this is first:** it carries the module's identity, it is the biggest single piece
of the port, and everything else builds on the boxes it produces.

## Phase 2 — Supplier bill creation · done

- [x] Create an `account.move` (in_invoice) from a processed document.
- [x] Match the vendor against `res.partner` by tax number, then by name.
- [x] Refuse to book your own company's tax number as a vendor.
- [x] Refuse to bill the same document twice.
- [ ] Put the taxes of the document on the lines, instead of leaving the
      amount untaxed for whoever reviews it.
- [ ] Vendor refunds (rectificativas) vs regular bills.
- [ ] Post the bill instead of leaving it in draft, per setting.

### The extraction service, as measured

The module talks to the same service the Dolibarr module uses
(`POST /api/v1/ocr/file`, multipart, header `X-API-Key`). Two things to remember:

- **A partial extraction still comes back as HTTP 200.** The body carries
  `status: "partial"` and an `error_code`. Reading the HTTP code alone treats a
  failure as a success.
- `error_code` says whether retrying is worth it: `OCR_EMPTY` and
  `PARTIAL_DEGRADATION` are worth a retry, `STRUCTURING_TRUNCATED` is not.

## Phase 3 — Extraction engines · pending

Two engines, exactly as the Dolibarr module has:

- [ ] Native: text taken from the PDF text layer (no AI, no cost, everything local).
- [ ] AI: a call to the EasyOCR microservice for scans and images without a text layer.
- [ ] Per-company settings: service URL, credentials, engine choice.
- [ ] The document keeps the reason when extraction fails, so it can be retried.

## Phase 4 — Inbox for documents from other modules · pending

- [ ] Model for documents handed over by other modules, with their origin.
- [ ] Nothing is sent to the AI service on arrival; the user decides when.
- [ ] Discard unwanted documents, with confirmation.
- [ ] Public helper so another module can drop a file in the inbox.

## Phase 5 — Inbound API · pending

- [ ] Webhook endpoint that accepts a document and creates the record.
- [ ] Log of received calls, with the outcome of each.
- [ ] Ability to leave created bills marked as paid.

## Phase 6 — Mobile expense capture · pending

- [ ] Installable PWA so an employee can photograph a receipt.
- [ ] Record it as an expense or as a purchase bill, per configuration.
- [ ] Attach it to a project.

## Phase 7 — Settings, permissions, translations · pending

- [ ] Settings screen; every option must change real behaviour.
- [ ] Per-record rules on top of the group rules.
- [ ] Full translations, matching the eight languages of the Dolibarr module.

## Phase 8 — Packaging and release · pending

- [ ] Release ZIP per Odoo series, module folder at the root of the zip.
- [ ] Packaging skill, so a release is one command and not a checklist.
- [ ] Publish on the Odoo Apps Store (Enterprise is not required).
- [ ] User guide published with every version.

---

## Differences from the Dolibarr module

These are deliberate, not gaps:

- **Access groups** use `res.groups.privilege` on 19.0 and `category_id` on 18.0.
  Same feature, different API.
- **The PDF.js library** is not bundled: Odoo core already ships one. The version is
  newer than the one the Dolibarr module used, so initialisation differs.
- **Rectangle coordinates** are stored in PDF user space, not in screen pixels, so a
  template saved on one screen size works on another.

## Not planned

- Anything requiring Odoo Enterprise. The module targets Community.
- Importing XML invoices (UBL, CII, Factur-X): Odoo core already does that for free,
  and better than we would.
