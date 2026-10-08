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

## Phase 1 — Document viewer with rectangle templates · done

This is the screen the user recognises: the PDF on the left, the data panel on the right.

- [x] Client action with an OWL component (a full screen of our own, not a form view).
- [x] PDF rendered from the PDF.js copy that ships with Odoo core, one canvas per page.
- [x] Drag a rectangle over the page and assign it to a field
      (document date, document number, untaxed amount, total, vendor).
- [x] Read the text inside each rectangle from the PDF text layer, cut at
      character level so a box can take part of a line.
- [x] Save the set of rectangles as a template for that vendor.
- [x] Reapply a vendor template to a new document of the same vendor.
- [x] Apply a template automatically when the vendor is known.
- [x] Move and resize a box that has already been drawn.

**Why this is first:** it carries the module's identity, it is the biggest single piece
of the port, and everything else builds on the boxes it produces.

## Phase 2 — Supplier bill creation · done

- [x] Create an `account.move` (in_invoice) from a processed document.
- [x] Match the vendor against `res.partner` by tax number, then by name.
- [x] Refuse to book your own company's tax number as a vendor.
- [x] Refuse to bill the same document twice.
- [x] Put the taxes of the document on the lines, instead of leaving the
      amount untaxed for whoever reviews it. When the document was read line by
      line, each line carries the purchase tax of its own rate. When it came
      back with nothing but its two amounts, the rate is worked back from them
      and used only if the company has that exact tax: a bill whose total does
      not add up to the paper is worse than one left to be finished by hand.
- [x] Post the bill instead of leaving it in draft, per setting. The switch
      exists (`easyocr_bill_post`), and a posting that fails leaves the bill in
      draft with the reason written on it: a bill that could not be confirmed is
      worth a great deal more than no bill at all.
- [x] Vendor refunds (rectificativas) vs regular bills. A document whose reading
      comes back with a negative total is marked as a credit note by itself, and
      the bill is made as an `in_refund`: Odoo reports those amounts positive and
      turns the entries round instead, so the lines of the bill are written
      without the sign the paper carries.

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
- [x] Choose the engine per document instead of per company. The choice was
      always per document, made by what the reader does: the boxes read the
      file's own text layer for nothing, and the button reads it with the
      service and costs a reading. What was missing was the end of the free
      path, which filled nothing, so the document now takes what the boxes read
      and the rate, the date and the amounts become fields of their own. No PDF
      library had to be added on the server for it: the text layer is read where
      it is already read, in the browser.

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
- [x] Ability to leave created bills marked as paid. Off by default and only for
      the webhook: a bill in draft has nothing to pay against, so it is the
      company that decides, and a payment that cannot be registered says why
      instead of losing the bill.

## Phase 6 — Mobile expense capture · done

- [x] Installable PWA so an employee can photograph a receipt.
- [x] The photo is resized in the browser and lands in the inbox.
- [x] Attach it to a project. In Odoo a project has an analytic account of its
      own, and that account is what an expense and a bill line are charged to, so
      the document carries an analytic distribution and it is copied to whatever
      the receipt becomes. The Projects app is not a dependency of this module:
      a company that keeps no projects pays nothing for this, and one that does
      sees its projects by name. The field sits behind Odoo's analytic-accounting
      group, like the same field on a bill: without it the widget asks for plans
      the user may not read and the form answers with an access error, which is
      how it was found.

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

## Phase 9 — Parity with the Dolibarr module · done

Asked for on 7-oct-2026: *«quería una paridad total al 100%»*. Measured against
the Dolibarr module that day: **18 settings against 4**, and two screens that
have no counterpart here. This phase closes that.

State on 8-oct-2026: **the phase is closed.** Every setting is accounted for --
eleven of the fourteen are in, and the three that are not are the
miscellaneous-payment ones, which are not portable because the object they feed
does not exist in Odoo -- and both screens have their counterpart here.

Closed the same day, after using the module against the real service:

- **One screen for the whole job** (there, `extract.php`). It opens waiting for a
  file -- click or drop, which is how Dolibarr opens -- and becomes the viewer in
  place once one is chosen. Asked for on 8-oct-2026: *«el botón del hub de upload
  a document tiene que llevarme a esa página donde espera un botón para abrir pdf
  o arrastrarlo»*. The upload dialog that used to sit in the way is gone, and the
  rules about what can be read live on the server, where the tests are.
- **The controls are a column on the right**, under the headings Dolibarr uses --
  read with AI, fields, template, what was read -- instead of a row of buttons
  across the top. Asked for the same day: *«los botones no salen en columna a la
  derecha»*. The heading of the AI section says when the account cannot read
  (quota, overdue subscription) before anyone tries, out of the same account
  check the settings screen uses.
- **The viewer carries the two buttons that finish the job.** Reading with the
  service and creating the bill lived only on the record's form, so opening a
  document in the viewer meant leaving it to act on what you were looking at.
  Both are in the column now, with the same permission the form's button has,
  and it says what is being waited for while a scan is read.
- **The settings screen checks the key.** A key that the service does not
  recognise is indistinguishable from a key that was never sent -- both arrive
  as HTTP 401 -- and a reading that comes back refused has already been paid
  for. **Probar la conexión** asks the service who the key belongs to
  (`GET /api/v1/me`, behind the key check but not behind the plan limiter) and
  answers with the account, the plan and what is left. It costs nothing.
- **The message for a refused key was wrong.** `_http_error_message` mapped by
  HTTP status alone, so a key that was sent and rejected was reported as a key
  that was never set. The service names the reason in the body
  (`INVALID_API_KEY`, `QUOTA_EXCEEDED`, …); that is what is read now.
- **Every word a template paints needs a reference of its own.** The web client
  is handed the terms flagged as code, so a sentence written straight into an
  OWL template is looked up in a map that holds only those. "Read with AI" and
  "Create Bill" already existed in the `.po` as the form's button labels, which
  is a different kind of reference, and on a Spanish screen they came out in
  English. `tests/test_easyocr_translations.py` now walks the templates and
  demands a code reference for every literal in them -- **and their tails**,
  which is where "page(s)" and "Loading the document..." had been sitting in
  English since the beginning, out of sight of the check because they are
  written after a tag instead of inside one.
- **What the browser found that the suite could not.** Driving the batch screen
  for real turned up four things no unit test would have: `orm.create` answers
  with a *list* of ids and taking it for an id kills every call after it;
  `doAction` needs `views` in the action or it throws on the way in; a sentence
  glued together in the markup is never translated, however good the `.po` is;
  and the summary said "all of them were read" while the line under it said "1
  failed", because it was reading the service's word and the counts are ours.
  The summary is read off the counts now, and the picker does not give way to
  the progress screen until the send has actually been decided.
- **The duplicate question had two buttons that lied.** "Leave them out" threw
  the whole batch away, and the promise on the button was that it would send the
  rest. It does now: the files already read come out of the batch, stay in the
  documents list unread and unpaid, and the stack goes without them.
- **A box cannot be dragged off the page.** The original lets one go, and a box
  that has left the page reads nothing and cannot be grabbed back, because there
  is nothing under the mouse to grab. This one stops at the edge. The four
  corners are painted as small squares of the field's colour, which is what says
  a box can still be changed once it has been drawn.
- **The template was saved without a vendor, and so was never found again.** The
  record existed and the boxes were in it, but every one of them had
  `partner_id` empty: the screen saved the vendor from the document's own field,
  which is empty until a bill is made. The guide promises the boxes come back on
  the next invoice from that vendor, and they could not. The vendor is worked out
  on the server now -- tax number first, name after, the way the bill works it
  out -- and the same method is asked again after a reading, because a reading is
  what usually gives a nameless file a tax number. The only template in the
  development database had no vendor at all, which is how the gap was found.

Every row below was read in the Dolibarr source, in the file named, so what is
ported is what that setting actually does and not what its name suggests.

### Screens

- [x] **Home screen** (`index.php` there, no counterpart here). Dolibarr opens
      the module on a dashboard of shortcut cards with a few counters. Odoo has
      no such concept -- an app opens its main view -- so this is a first child
      menu of its own, **Inicio**, which is also where the app then lands.
      *Done 7-oct-2026.*
- [x] **The lines of the document** (there, the line table of `extract.php`).
      Read line by line, they are what the bill is built from, and they are
      editable so a bad reading is fixed before it becomes a bill. *Done
      7-oct-2026, with the product of each line looked up by the reference the
      document prints.*
- [x] **Batch processing** (`batch.php`, `webhook_batch.php`). Reading a folder
      of documents in one go, and the webhook's batch variant. *Done
      8-oct-2026: a screen that takes the files, a `easyocr.batch` record that
      follows them, the readings landing on their own documents, and the three
      events the service sends for a batch -- one document read, one failed, and
      the whole stack done.* What the module does **not** copy is how the
      original sends them: there, one file per call, because PHP's
      `max_file_uploads` forces it. Here they all travel in one request, which
      is what the service is built for. And the `language` option the original
      fills in is not sent at all: its own SDK drops it in silence, because it
      is not part of the batch contract.

**Known difference:** the viewer has no zoom. Dolibarr's has `+` / `−` buttons
and a page indicator in the toolbar; here the page is painted at a fixed scale
and the PDF area scrolls. Adding it means making the paint scale a thing the
component carries rather than a constant, which touches the arithmetic of every
box -- worth doing, but not folded into the rework above.

### Icons

Every icon the module names is checked against the FontAwesome Odoo actually
ships (`tests/test_easyocr_icons.py`). Odoo ships version 4 and the Dolibarr
module draws from version 5, so a name copied from there -- `fa-file-invoice-dollar`,
`fa-satellite-dish`, `fa-layer-group`, `fa-receipt` -- is not an error anywhere:
it paints nothing, and the card keeps an empty chip. Two of them shipped that
way on 8-oct-2026 before the check existed.

### UI: native views, not a copy of Dolibarr's screens

Asked on 7-oct-2026 whether Dolibarr's screens could be reproduced as they are.
They can -- Odoo renders whatever a client action draws, and the viewer, the
home screen and the batch screen are already that -- but the decision taken that
day is to keep the module on Odoo's own views and finish the *behaviour*
instead. Dolibarr's pages are hand-written PHP; here every screen would be a
bespoke component to keep alive across two series, and a Dolibarr-looking screen
inside Odoo reads as a foreign body to anyone who uses Odoo. So: native views,
everything Dolibarr does, and a custom screen only where native cannot express
it. Where that line falls has held: of the three screens of this phase, the
batch *list* is a plain Odoo list with its own search view, and only the picking
and the following of a live batch needed a screen of its own.

### Settings

The four of the AI service are already here. The fourteen that follow are not.

- [x] **Bill as draft** (`EASYOCR_INVOICE_DRAFT`, read in `lib/easyocr.lib.php`
      around line 1995). There it decides between creating the invoice as a
      draft and validating it on the spot. Here it is the other way round: the
      bill is always a draft, so the setting is what posts it.
- [x] **Create the product** (`EASYOCR_AI_AUTOCREATE_PRODUCT`, `lib` ~1900),
      off by default: when no existing product matches the line, make one, with
      its reference, label, price and tax, and type product or service.
- [x] **Allow your own tax number** (`EASYOCR_ALLOW_SELF_SUPPLIER`, `lib`
      ~1374): there, refusing is the default and this turns the refusal off.
      Here the refusal is unconditional, so the setting has to open it.
- [x] **Tell the service who receives the invoice** (`EASYOCR_AI_RECEIVER_CONTEXT`,
      `lib` ~621), off by default: an extra instruction block so the model does
      not read the receiver as the supplier. It changes the request sent, so it
      is off unless asked for.
- [x] **Duplicate check** (`EASYOCR_DUPLICATE_CHECK`, `lib` ~1043), on by
      default, and **the window in days** (`EASYOCR_DUPLICATE_WINDOW_DAYS`,
      `lib` ~1062), 0 meaning no limit: a file already read is not read again,
      so no credits are spent twice. The window is what lets a supplier's
      month after month identical invoice through.
- [x] **Mark the bill as paid** (`EASYOCR_WEBHOOK_MARK_PAID`,
      `EASYOCR_WEBHOOK_BANK_ID`, `EASYOCR_WEBHOOK_PAYMENT_TYPE`,
      `webhook_batch.php` ~363): the webhook registers the payment on a bank
      account with a payment method. It only applies to a posted bill, which is
      the same rule as there. *Done 8-oct-2026, with a switch of its own to
      create the bill from a webhook, because here a webhook filed a document
      and made no bill at all.*
- [x] **Where a photographed receipt goes** (`EASYOCR_EXPENSE_TARGET`,
      `ajax/ajax_easyocr.php` ~1074). There it has three values; only two have a
      counterpart here, and the third is **not ported**: Odoo has no
      miscellaneous payment, and the nearest thing -- a manual journal entry --
      is a different object that nobody can review or approve, which is what
      makes the original useful. Decided on 8-oct-2026. So: an employee expense
      (`hr_expense`) or a supplier bill, the bill by default. *Done 8-oct-2026.
      `hr_expense` became a dependency of the module: it ships with Odoo
      Community and costs nothing, and "expense receipts" is what the module's
      own summary promises, so it is not a stray dependency.*
- [x] **Let the phone validate it** (`EASYOCR_EXPENSE_ALLOW_VALIDATE`, same
      file): whether the capture page may confirm the expense and not only file
      it. *Done 8-oct-2026, as far as handing it over. There the phone could go
      all the way to validating it; here that would mean the person who spent
      the money approving it, which is the one thing Odoo's approval chain
      exists to prevent, so the phone submits and the approver approves.*
- [x] **The miscellaneous expense's bank, payment method and account**
      (`EASYOCR_EXPENSE_VARIOUS_*`): they only existed to feed the destination
      that is not ported, so they go with it. *Not ported, 8-oct-2026.*

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
