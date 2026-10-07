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

## Phase 3 — Extraction engines · done

- [x] Native: text taken from the PDF text layer, per box (no AI, no cost).
- [x] AI: a call to the EasyOCR microservice for scans and images without a text layer.
- [x] Per-company settings: enabled, service URL, key and timeout, on the settings screen.
- [x] The document keeps the reason when extraction fails, so it can be retried,
      and says whether sending it again is worth it.
- [ ] Choose the engine per document instead of per company.

## Phase 4 — Inbox for documents from other modules · done

- [x] Model for documents handed over by other modules, with their origin.
- [x] Nothing is sent to the AI service on arrival; the user decides when.
- [x] The same file is refused twice, by fingerprint.
- [x] Discarded documents can be brought back.
- [x] Public helper (`recibir`) so another module can drop a file in.

## Phase 5 — Inbound API · done

- [x] Webhook endpoint that accepts a document and creates the record.
- [x] Log of received calls, with the outcome of each.
- [x] Shared secret compared in constant time; the endpoint is closed when no
      secret is set, rather than open.
- [ ] Ability to leave created bills marked as paid.

## Phase 6 — Mobile expense capture · done

- [x] Installable PWA so an employee can photograph a receipt.
- [x] The photo is resized in the browser and lands in the inbox.
- [ ] Attach it to a project.

## Phase 7 — Settings, permissions, translations · done

- [x] Settings screen; every option changes real behaviour.
- [x] Per-record rules on top of the group rules.
- [x] Eight languages, matching the Dolibarr module.

## Phase 8 — Packaging and release · in progress

- [x] Release ZIP per Odoo series, module folder at the root of the zip.
- [x] Packaging skill, so a release is one command and not a checklist.
- [x] Release workflow that attaches the ZIP to a GitHub Release (never an
      artifact: the organization's artifact quota is shared and small).
- [x] `LICENSE` file: LGPL-3, shipped at the root and inside the module.
- [x] The module is free; what is sold is the extraction service.
- [ ] Publish on the Odoo Apps Store. Note it is fed from the **repository**,
      not from the ZIP: the ZIP is for the release and for installing by hand.
- [x] User guide written from the screens themselves, in `docs/manual/`, with
      its screenshots. Every version from now on carries its updated guide:
      the source lives in the repository and the same text goes to the company
      wiki, so a release is not finished until the guide matches it.

## Phase 9 — Parity with the Dolibarr module · in progress

Asked for on 7-oct-2026: *«quería una paridad total al 100%»*. Measured against
the Dolibarr module that day: **18 settings against 4**, and two screens that
have no counterpart here. This phase closes that.

Every row below was read in the Dolibarr source, in the file named, so what is
ported is what that setting actually does and not what its name suggests.

### Screens

- [ ] **Home screen** (`index.php` there, no counterpart here). Dolibarr opens
      the module on a dashboard of shortcut cards with a few counters. Odoo has
      no such concept -- an app opens its main view -- so this is a first child
      menu of its own, **Inicio**, which is also where the app then lands.
- [ ] **Batch processing** (`batch.php`, `webhook_batch.php`). Reading a folder
      of documents in one go, and the webhook's batch variant.

### Settings

The four of the AI service are already here. The fourteen that follow are not.

- [ ] **Bill as draft** (`EASYOCR_INVOICE_DRAFT`, read in `lib/easyocr.lib.php`
      around line 1995). There it decides between creating the invoice as a
      draft and validating it on the spot. Here it is the other way round: the
      bill is always a draft, so the setting is what posts it.
- [ ] **Create the product** (`EASYOCR_AI_AUTOCREATE_PRODUCT`, `lib` ~1900),
      off by default: when no existing product matches the line, make one, with
      its reference, label, price and tax, and type product or service.
- [ ] **Allow your own tax number** (`EASYOCR_ALLOW_SELF_SUPPLIER`, `lib`
      ~1374): there, refusing is the default and this turns the refusal off.
      Here the refusal is unconditional, so the setting has to open it.
- [ ] **Tell the service who receives the invoice** (`EASYOCR_AI_RECEIVER_CONTEXT`,
      `lib` ~621), off by default: an extra instruction block so the model does
      not read the receiver as the supplier. It changes the request sent, so it
      is off unless asked for.
- [ ] **Duplicate check** (`EASYOCR_DUPLICATE_CHECK`, `lib` ~1043), on by
      default, and **the window in days** (`EASYOCR_DUPLICATE_WINDOW_DAYS`,
      `lib` ~1062), 0 meaning no limit: a file already read is not read again,
      so no credits are spent twice. The window is what lets a supplier's
      month after month identical invoice through.
- [ ] **Mark the bill as paid** (`EASYOCR_WEBHOOK_MARK_PAID`,
      `EASYOCR_WEBHOOK_BANK_ID`, `EASYOCR_WEBHOOK_PAYMENT_TYPE`,
      `webhook_batch.php` ~363): the webhook registers the payment on a bank
      account with a payment method. It only applies to a posted bill, which is
      the same rule as there.
- [ ] **Where a photographed receipt goes** (`EASYOCR_EXPENSE_TARGET`,
      `ajax/ajax_easyocr.php` ~1074): to an expense report or to a supplier
      bill. In Odoo that is `hr_expense`, a different app, so this one is a
      decision and not a copy.
- [ ] **Let the phone validate it** (`EASYOCR_EXPENSE_ALLOW_VALIDATE`, same
      file): whether the capture page may confirm the expense and not only file
      it.
- [ ] **The miscellaneous expense's bank, payment method and account**
      (`EASYOCR_EXPENSE_VARIOUS_*`): where a receipt with no supplier goes.

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
