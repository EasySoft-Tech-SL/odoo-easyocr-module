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
  read from the document, and a fingerprint of the file so a document that was
  already read is recognised when it comes back.
- **Reading it again, on purpose.** A file whose fingerprint was already read
  is not read a second time behind the reader's back, and it is not refused
  either: the module says what it knows about the earlier reading -- the file,
  the day and the bill it became -- and asks. Yes reads it again and costs one
  reading; leaving it alone costs nothing and leaves the document exactly as it
  was. The question is the same from the form and from the viewer.
- **Document inbox.** What another module hands over before anyone has looked at
  it, with its own list, form and search.
- **The workbench.** One screen for the whole job: it opens waiting for a file --
  open it or drop it, straight from the app's first card -- and becomes the
  viewer in place once one is chosen. The file on the left, and on the right the
  column the module this is a port of has: the AI banner with the plan and what
  is left of the monthly quota, read with AI (which says so when the account
  cannot read), the nine fields to draw a box over, the template, the values
  read from each box -- taken from the PDF's own text layer -- and a footer with
  the two actions that finish the job, save the template and make the bill. It
  keeps Odoo's own navigation around it, so the menus stay reachable, and it
  carries a way back to the document it belongs to.
- **Watching a reading work.** Reading a scan takes seconds and the button that
  started it goes dead while it runs, which used to leave the screen saying
  nothing at all. A bar walks the stages of a reading -- the file going out, the
  text coming back, the fields being worked out -- and stops short of the end,
  because a bar that fills before the answer arrives is a lie the reader catches.
- **What the reading found.** A reading ends on a screen, not on a toast: what
  the service was sure of, how long it took, what it cost in tokens and pages,
  and the vendor details that had been read and thrown away because the document
  has no field for them -- the address, the town, the phone, the email, the way
  they want to be paid. From there, one button opens the document to make the
  entry.
- **Vendor templates.** The boxes drawn over a vendor's paperwork are kept under
  that vendor, so the next invoice from the same vendor opens with them already
  painted and their text read from the new file. The vendor is worked out on the
  server, by tax number and then by name, since a document has none of its own
  until it becomes a bill.
- **Boxes that can be moved and resized.** A box already drawn is dragged from
  inside to move it, or pulled by one of the squares on its corners to change its
  size, and the text under it is read again on letting go. A box cannot leave the
  page: off it there is nothing to read and nothing left to grab.
- **Reading without the service.** The boxes drawn over a page fill the document
  with what they read, which costs nothing because the text was already in the
  file: an amount printed "320,77 EUR" and a date printed 30/09/2026 are read as
  such, and a box that read nothing leaves its field alone instead of emptying
  it. The date the vendor wants to be paid, which the service has always returned
  and nothing kept, is stored now and goes on the bill.
- **Reading with the service.** Client for the EasyOCR extraction service, with a
  `Test the connection` button in the settings that checks the key without
  spending a reading, and plain-language messages for every way the service can
  turn a document away.
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
  with the product, discount and rate of each. A document that came back with
  nothing but its two amounts still gets its tax: the rate is worked back from
  them, and used when the company has that exact tax. Optional confirmation, and
  the vendor matched by tax number.
- **Credit notes.** A rectificativa, which is the same document with negative
  amounts, becomes a vendor credit note instead of a bill, with its entries the
  other way round and the tax still on the line. The reading turns it on by
  itself when the total comes back negative, and it can be set by hand.
- **Photographed receipts.** A capture page for a phone, which files the photo and
  hands it to the module; the receipt can end up as a supplier bill or as an
  employee expense. Either of them can be charged to a project: the document
  carries the analytic account the project keeps, and no separate app is needed
  for it. The field shows on the document's form for companies that keep analytic
  accounting, which is what a project is made of in Odoo; a company that keeps
  none never sees it, and the form opens the same.
- **Webhooks.** A log of every call the service makes, and the option to create
  the bill and register its payment without anyone in front of the screen.
- **Settings.** Sixteen switches over the service, what a document becomes and
  what a webhook may do on its own.
- **Languages.** Spanish, Catalan, Galician, German, French, Italian and
  Portuguese, with a test that checks every term reaches the reader -- field
  labels, help texts, selection labels, model and action names, the sentences the
  module writes at runtime, the words its own templates paint, and the labels of
  the fields it borrows from Odoo and puts on the screen.
- **Tests.** 250 of them, covering each switch by its effect rather than by its
  value, each one proven to fail when the thing it guards is broken. That
  includes what a template asks a component for: a binding naming something the
  component does not have raises no error anywhere, and one of them left a button
  in the file and on no screen until it was measured.
- **CI.** Python syntax, manifest and layout check, and XML well-formedness on
  both branches.

### Fixed

- **A clean install of a published release stopped dead.** Every menu of the
  module hangs off the root menu that carries the module's name, and that menu
  was declared at the bottom of the document views. The home screen hangs off it
  too and is loaded earlier, so installing the released ZIP from scratch ended in
  a `ParseError` while parsing the first screen of the module. An upgrade never
  showed it, because the menu was already in the database from an earlier
  install. The root menu now lives in a file of its own and is the first thing
  the module loads.
- **The way back from the viewer was in the file and on no screen.** It hung off
  a name the component never puts on its state, so the condition was false for
  ever and nothing was painted. Found by looking at the screen, and kept found by
  a test that reads every binding of every template against the components.
- **The viewer hid Odoo's menus.** It opened full-screen, so the app's own
  navigation -- and with it every other screen -- was gone until the reader left
  the viewer. It now opens inside Odoo with the menus still there, and its
  sidebar is the one the module this is a port of has: the plan and what is left
  of the quota at the top of the column, and the keyboard spelled out at the
  bottom (1-8 pick a field, Ctrl+S saves the template, Ctrl+Enter makes the
  bill, Esc releases the field).
- **Lined up with the module it ports.** The home, the viewer, the reading
  result, the templates, the invoices, the webhook log, the batch screen and the
  settings now read like the Dolibarr module's, screen by screen: the same
  labels, the same sections, the same keyboard and the same order, in the seven
  languages. The reading result gained its collapsible cards and its raw payload,
  its editable lines and the payment, and the viewer its completeness checklist,
  the quota, the AI instructions, the supplier dropdown and undo.

- **Making the bill from the reading result said only that it failed.** A
  supplier nobody had on file stopped the bill, and the dialog swallowed the
  reason. The supplier is now created from what was read (name, tax number,
  address, town, postal code, country, phone and email), as the module this is
  a port of does, and when the server does refuse, the dialog says why.
- **The reading result, redone.** Every card is a grid of labelled fields; the
  ones that reach the bill (invoice number, dates, the supplier's details) can be
  corrected there and are written onto the document first. The supplier's tax
  number says whether the contact exists or will be created. The lines carry
  code, product, type, quantity, price, discount, VAT, RE, IRPF and their total,
  in the reader's own number format, and a warning shows when they do not add
  up to the document's totals. The footer groups status, journal and document
  type (bill or credit note), and the payment uses the method and bank picked,
  or the company's bank journal. The VAT, RE and IRPF typed on a line become
  the company's taxes with those rates, which the edited lines used to lose.
  The dialog can be used from the keyboard: Esc closes it, Ctrl+Enter makes the
  bill, Tab stays inside it, and every control has a name a screen reader says.

### Pending

- **Spanish localisation cases.** IRPF, recargo de equivalencia and IGIC.
- **The three `EASYOCR_EXPENSE_VARIOUS_*` settings** of the module this is a port
  of are not here: the object they file against does not exist in Odoo, so
  bringing them over would have been a switch that does nothing.
