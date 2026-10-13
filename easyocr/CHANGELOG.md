# Changelog

All notable changes to this module are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the version numbering is Odoo's:
`<odoo series>.<major>.<minor>.<patch>`.

One section per published version, the newest first. The heading carries the module
version without the series (1.0.9 is 19.0.1.0.9 on 19.0 and 18.0.1.0.9 on 18.0, both
published the same day) and the day it was published.

This file ships inside the module: it is what the ChangeLog page of the module's
configuration shows. A Spanish translation sits next to it, in `CHANGELOG.es.md`.

## [1.0.16] - 2026-10-13

### Fixed

- **The published description was showing its own headline in white on white.** The Odoo
  Apps Store sanitises the description and drops every `background` written inside a
  `style` attribute while keeping `color`, so the black band of the header arrived without
  its fill and the 34px white headline sat on the store's white page, invisible. The amber
  rule and the black labels went the same way. The dark blocks and the light panels now
  take their fill from classes (`bg-black`, `bg-light`), which survive the sanitiser, and
  the amber rule is drawn as a border, which also survives. The rest of what the sheet
  relies on, the padding, the radius, the colours and the other borders, was already coming
  through untouched.

## [1.0.15] - 2026-10-13

### Changed

- **The page in the Odoo Apps Store says, at the top, that the module is free.** The
  README says it, the licence says it and the settings say it, but the description the
  store shows opened with what the module does and left the price for the reader to work
  out on their own. It opens with it now: nothing to pay, and a PDF that already carries
  its text is read with no account, no API key, no quota and no subscription. The reading
  service, which is the one thing a subscription pays for, is presented as what it is: the
  way to read scans and photographs, with a free plan to start on.
- **That description now follows the visual scheme of the company's own product sheets**:
  the same black header, the same amber accents and the same type scale its Dolibarr
  modules use, so both catalogues read as one brand.

## [1.0.14] - 2026-10-13

### Added

- **The module says where the key comes from.** Reading a scan needs the service, and the
  service needs a key, which is the one thing somebody who has just installed the module
  does not have. The three screens that ask for it (the settings, the document viewer and
  the Plan tab) now offer to open a free account and say what it costs: 10 pages a month,
  no card.

### Fixed

- **The page for photographing a receipt promised a reading the company could not pay
  for.** With the AI switch on and no key pasted, the page told the employee their photo
  would be read. It is saved to the inbox and read by hand, and that is what the page says
  now. Nobody lands there on purpose: the switch is turned on first and the key arrives
  afterwards, from an account that may not be open yet.

## [1.0.13] - 2026-10-12

### Changed

- **The module runs on five Odoo series, 16.0 to 20.0.** One branch per series, the same
  code in all of them except where a series genuinely differs: the tag a list view is
  written with, how a view declares its modifiers, how the webhook route reads its body,
  and the templates of Odoo 20, which are Owl 3 and no longer Owl 2. `docs/SERIES.md` is
  the list of those differences, measured on each series. Until now the module covered
  18.0 and 19.0.
- **It is called EasyOCR Invoice Capture.** That is the name the Apps Store card, the
  Apps list and the module's own screens show. The technical name and the folder stay
  `easyocr`: they are what an installed instance holds in its database, and renaming
  them would leave an update looking for a module that is not there.
- **The store page opens with the whole flow in one animation.** Three steps, from the
  file to the entry, in a few seconds, instead of a paragraph asking the reader to
  picture them.

### Fixed

- **The Invoices screen asked for a view type its series does not have.** The action
  declared its list as a `tree` on 18 and 19, where the tag has been `list` since 18,
  and the arch carried the `list` tag on 16 and 17, where only `tree` exists. Each
  series names now the view its own version of Odoo looks for.
- **A webhook body that is not JSON came back as a server error.** Something posting to
  the webhook with a body nobody can parse was answered with a 500, which invites the
  sender to retry the same unreadable call. It is answered with a 400 now, and nothing
  is written to the log.
- **The buttons on a batch did not know whether it had already been sent.** They asked
  about the batch's reference at the service, a field the same form hides from anybody
  who is not in the technical group. Odoo 16 refused to load the view over it, 17
  refused it on `readonly`, and 18 to 20 loaded it and decided on a field the reader had
  not been given. They ask about the date it went out instead, which is written at the
  same moment and only once the service has taken the files, so it says the same thing.
  A test reads the views and fails when a condition names a field its own view hides.
- **The web client did not start at all on 16 and 17.** Up to 17 the backend bundle reaches
  the browser as a classic script, and a file is only made a module by `/** @odoo-module **/`
  at the very top. Every script of the module opened with its `import`s and nothing else,
  so the browser stopped at the first one and left a blank screen with nothing in the log
  to say why. The marker now opens all nine of them on those two series; from 18 the bundle
  is a module already and the marker buys nothing.
- **The templates of 16 never reached the app.** Odoo 16 collects them with the
  `[t-name][owl]` selector and no other, so a template written like every other series'
  arrives nowhere and the first screen that asks for it dies with "Missing template". The
  attribute is on the 13 templates of that branch alone; from 17 on it is not read, and the
  file is written as on the rest.
- **The screens that ask about the reader's group asked the wrong way.** Up to 17 the user
  is a service whose `hasGroup` answers with a promise, and there is no `@web/core/user` at
  all: importing it left the module with an unmet dependency and neither screen loaded.
  From 18 it is the other way round. Each branch takes the user where its own series keeps
  it.
- **The configuration screen did not render on 16.** The registry of view widgets holds the
  component itself up to 16 and a `{ component: ... }` wrapper from 17 on, and written the
  other way the screen does not render: 16 throws "C is not a constructor" and the newer
  series say nothing at all.
- **A test reads the four of those off the files.** `tests/test_easyocr_assets.py` is the
  same file on all five branches and checks only what the series it runs on reads, so a rule
  borrowed from a neighbouring series fails there instead of in a blank screen.

## [1.0.12] - 2026-10-12

### Changed

- **The module folder sits at the root of the repository now, which is where the Odoo
  Apps Store looks for it.** The store reads the direct children of the repository root
  and does not go any deeper, so `addons/easyocr/` came back from it as "No module found
  in repository". The tooling that pointed at `addons/` moved with the module: the
  packager, the two workflows, the local `docker-compose.yml` and the README. Nothing of
  what the module does changed, and the only thing different inside the release archive
  is the version number.

## [1.0.11] - 2026-10-12

### Changed

- **The About page is read in the reader's language.** It drew the module's README
  in English whatever the screen spoke, which left the one page that explains the
  module as the one page a Spanish reader had to work through in a language that is
  not theirs. The file now ships in the same pair the changelog comes in, and a test
  keeps the two in step.

### Fixed

- **Two fields of a model shared a label, and Odoo warned at every install for it.**
  A document's line count and its lines both showed as "Lines", and a batch's
  document count and its documents both showed as "Documents". They are "Number of
  lines" and "Number of documents" now, which is also what lets the two be told
  apart on screen.
- **The repository's README pointed at a screenshot that is not there.** The file
  was renamed in the user guide and the README kept the old name, so GitHub drew the
  caption over an empty box.

## [1.0.10] - 2026-10-11

### Changed

- **The configuration pages carry Odoo's chrome, not the Dolibarr module's.** The
  headings of the changelog and of the README came out drawn with the weights and
  the colours of the module this ports, which left each one smaller and lighter
  than the text under it, and the header row of the tables kept its grey bar. Both
  are now what Odoo gives a heading and a table on any other screen of its
  settings.
- **The changelog is one section per published version.** It was a single block
  holding everything since the first release, so the page had no version and no
  day to hang a reading on. It is rebuilt from the repository's own history: one
  section per version, the newest first, each with the day it went out.
- **The changelog folds, one block per version, the newest one open.** A file
  that grows with every release is read from the top; the rest is one click away.

### Fixed

- **The licence page sent the reader to a website that never answered.** The
  product's address was written as a subdomain of the company's. It is
  `easyocr.es`.
- **The changelog was read in English whatever the reader's language.** It now
  ships in English and in Spanish, and a test keeps the two in step, so a version
  cannot land in one file and not in the other.

## [1.0.9] - 2026-10-11

### Fixed

- **The five configuration pages left the settings screen behind.** Each page
  opened as a screen of its own, and the menu on the left belongs to the settings
  screen, so it went away with it. The pages are drawn inside the settings screen
  now, under the tab bar, and the menu stays where it is.
- **Those pages could not be scrolled.** Odoo fixes the height of a screen and
  leaves the scrolling to the settings pane; a screen of its own has no such pane.
  A page longer than the window showed the part that fitted and nothing below it.
  The page is drawn inside that pane now, so the pane is what scrolls it.
- **A page showed what the tab before it had asked for.** Opening the changelog
  right after the plan said "ChangeLog file not found", because the tab bar reused
  the page instead of drawing a new one and what it held was still the plan's
  answer. Each tab is a page of its own now.

## [1.0.8] - 2026-10-10

### Added

- **Configuration pages.** The tabs the module this is a port of has over its
  setup: Setup, Service Plan, License Agreement, Telemetry & Data Protection,
  About and ChangeLog, under a Configuration menu of their own and only for
  EasyOCR managers. The plan page asks the service for the account, the
  subscription, the monthly quota, the statistics, the limits and the wallet, and
  tells a rejected key apart from a service that is down. The telemetry page says
  what this module actually sends, including whether our own name goes along.
- **Tests.** 274 of them, covering each switch by its effect rather than by its
  value, each one proven to fail when the thing it guards is broken. That
  includes what a template asks a component for: a binding naming something the
  component does not have raises no error anywhere, and one of them left a button
  in the file and on no screen until it was measured.

### Fixed

- **The AI block and the footer scrolled away with the fields.** In the viewer's
  right column only the middle part scrolls now, as in the module this ports:
  the AI banner stays on top, and the actions, help and shortcuts at the bottom.
- **Saving a template over the one in use proposed a new name.** The dialog now
  offers the name of the template that was applied.

## [1.0.7] - 2026-10-09

### Fixed

- **A template picked from the dropdown came back with no boxes.** The dropdown
  hands its value over as text, and the server looked the template up by that
  text and found nothing. Ids are now read as numbers on both sides, and the
  supplier dropdown had the same fault.
- **Name tags covered the neighbouring box.** On fields printed a line apart,
  the tag above a box sat on the box above. Each tag now goes where it covers no
  other box and no other tag: above, below, or beside.
- **A box read the line under it.** A field drawn round one line also took the
  line it only grazed ("01/07/2026 02/07/2026"). A line now counts only when most
  of it is inside the box.
- **Drawing next to a box took hold of its corner.** With a field picked, only
  the painted corner square still grabs; anywhere else, the press draws.

## [1.0.6] - 2026-10-09

### Fixed

- **The module's own description said it could not read anything.** The
  README shipped inside the module still listed extraction and bill creation as
  pending. It now says what the module does and how to set it up.

## [1.0.5] - 2026-10-09

### Fixed

- **Screenshots retaken on a made-up invoice.** The Apps Store gallery and the
  user guide showed a real quote, with a real customer's name and tax number,
  and an interface that is no longer the module's. Every screenshot is now taken
  from the current screens on a fictitious supplier.
- **Words written straight into the views reached the screen in English.** A
  view's own help or label is a term of its own, looked up under that view: the
  draft setting's explanation, the batch history and its buttons, and the AI
  instructions' example stayed in English on a Spanish screen. Every one of them
  is now checked by a test.

## [1.0.4] - 2026-10-09

### Fixed

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
- **The reading-result dialog would not close.** It opens in the main area,
  where Odoo's own "close" does nothing, so the cross, Cancel, Esc and a click
  outside all left it on screen. It now goes back to the screen it came from.
- **Saving a template never asked for its name.** The viewer read the function
  that closes the dialog as if it were the answer, so every template was saved
  without showing the dialog and under the name "removeCurrentOverlay". The
  dialog now opens, and its name, supplier and instructions are what is saved.
  The template dropdown also shows the template in use instead of "No template".
- **Four of the viewer's labels stayed in English.** "Invoice date", "Total
  excl. tax", "Total price" and "Tax amount" had their translation, but Odoo only
  sends the browser the terms a script or template points to, and these only
  pointed to a model. Every term a script asks for is now checked by a test.
- **The viewer and the batch screen did not open in debug mode.** Odoo hands a
  client action more properties than they listed, and in debug mode that stops
  them dead.
- **A box pulled past its opposite corner became a line.** Starting a new box
  next to an old one could grab its corner and squash it to nothing. A pull that
  leaves a box smaller than the minimum is now undone, and drawing a box lets go
  of the field, as Dolibarr does.
- **Small wording.** The document's button reads "Extract with AI" like the
  viewer's; the note under the AI banner no longer points to a button that is
  not there when the service is off; and a name ending in a full stop no longer
  reads "S.L.." in the already-read warning.

## [1.0.3] - 2026-10-09

### Fixed

- **Lined up with the module it ports.** The home, the viewer, the reading
  result, the templates, the invoices, the webhook log, the batch screen and the
  settings now read like the Dolibarr module's, screen by screen: the same
  labels, the same sections, the same keyboard and the same order, in the seven
  languages. The reading result gained its collapsible cards and its raw payload,
  its editable lines and the payment, and the viewer its completeness checklist,
  the quota, the AI instructions, the supplier dropdown and undo.

## [1.0.2] - 2026-10-08

### Added

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

### Fixed

- **The viewer hid Odoo's menus.** It opened full-screen, so the app's own
  navigation -- and with it every other screen -- was gone until the reader left
  the viewer. It now opens inside Odoo with the menus still there, and its
  sidebar is the one the module this is a port of has: the plan and what is left
  of the quota at the top of the column, and the keyboard spelled out at the
  bottom (1-8 pick a field, Ctrl+S saves the template, Ctrl+Enter makes the
  bill, Esc releases the field).

## [1.0.1] - 2026-10-08

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
