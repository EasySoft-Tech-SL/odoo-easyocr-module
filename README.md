<h1 align="center">EasyOCR for Odoo</h1>

<p align="center">
  <b>Reads supplier invoices and expense receipts from PDF and image files, and turns them into accounting entries in <a href="https://www.odoo.com">Odoo Community</a>.</b><br>
  Draw the fields on the document, or let the EasyOCR service read it for you.
</p>

<p align="center">
  <a href="https://github.com/EasySoft-Tech-SL/odoo-easyocr-module/releases"><img src="https://img.shields.io/github/v/release/EasySoft-Tech-SL/odoo-easyocr-module?filter=v19*&label=release%2019.0&style=for-the-badge&color=43ff7d" alt="Release 19.0"></a>
  <a href="https://github.com/EasySoft-Tech-SL/odoo-easyocr-module/releases"><img src="https://img.shields.io/github/v/release/EasySoft-Tech-SL/odoo-easyocr-module?filter=v18*&label=release%2018.0&style=for-the-badge&color=43ff7d" alt="Release 18.0"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-LGPL--3.0-green?style=for-the-badge" alt="License: LGPL-3"></a>
  <img src="https://img.shields.io/badge/Odoo-18.0%20%7C%2019.0-714B67?style=for-the-badge&logo=odoo&logoColor=white" alt="Odoo 18.0 and 19.0">
  <img src="https://img.shields.io/badge/i18n-ES%20CA%20GL%20DE%20FR%20IT%20PT-43ff7d?style=for-the-badge" alt="Languages">
  <a href="https://easysoft.es"><img src="https://img.shields.io/badge/Built%20by-EasySoft%20Tech%20S.L.-8a2be2?style=for-the-badge" alt="Built by EasySoft Tech S.L."></a>
</p>

---

A supplier invoice arrives as a PDF, or an employee photographs a receipt with their
phone. Either way somebody ends up reading a document and typing it into Odoo. EasyOCR
does the reading: it keeps the file on screen, pulls the vendor, the number, the dates
and the amounts out of it, and builds the supplier bill (or the employee expense) from
what it read.

**The module is free and complete, under LGPL-3.** What the subscription pays for is the
**extraction service** it can talk to. The module works without it for any PDF that
already carries a text layer, which is what most suppliers send by email; scans,
photographs and handwritten paper are what needs the service.

This is the Odoo counterpart of EasyOCR for Dolibarr. Maintained by
[EasySoft Tech S.L.](https://easysoft.es).

## 📸 What it looks like

Draw a rectangle over each field. The colour tells you which field it is, and the text
under the rectangle is read from the PDF's own text layer as you draw it.

![The workbench: the file on the left, the drawn fields and what was read from each one on the right](docs/manual/img/07-visor-campos.png)

The document keeps what was read, next to the fields it came from, so it can be corrected
before anything is created.

![A document with the values read from it](docs/manual/img/11-ficha-rellena.png)

One click and it is a supplier bill, with the lines, the tax and the vendor the reading
found.

![The supplier bill created from the document](docs/manual/img/12-factura-borrador.png)

The same thing from a phone: an installable page where an employee photographs a receipt
and it lands in Odoo as a bill or as an expense claim.

![The capture page on a phone](docs/manual/img/14-movil.png)

## ✨ What it does

<table>
<tr><td>📄 <b>Workbench</b></td><td>One screen for the whole job: open or drop a file, read it, review it, turn it into an entry. The document never leaves the screen, and the screen carries its own way back to it.</td></tr>
<tr><td>✏️ <b>Rectangle templates</b></td><td>Draw a rectangle over each field once and save it under that vendor. Their next invoice opens with the rectangles already painted and their text read from the new file.</td></tr>
<tr><td>🖱️ <b>Rectangles you can move</b></td><td>Drag one to move it, or pull a corner to resize it, and the text under it is read again on letting go. A rectangle cannot leave the page.</td></tr>
<tr><td>🆓 <b>Read without the service</b></td><td>The text layer of a digital PDF is read in the browser and costs nothing. An amount printed <code>320,77 EUR</code> and a date printed <code>30/09/2026</code> are read as such, and a rectangle that read nothing leaves its field alone instead of emptying it.</td></tr>
<tr><td>🤖 <b>Read with the service</b></td><td>Scans and photographs are sent to the EasyOCR extraction service and come back as lines, taxes and dates. A <b>Test the connection</b> button checks your key without spending a reading.</td></tr>
<tr><td>👀 <b>What the reading found</b></td><td>A reading ends on a screen, not on a toast: how sure the service was, how long it took, what it cost in tokens and pages, and the vendor details the document has no field for. One button from there to the entry.</td></tr>
<tr><td>🔁 <b>Read again, on purpose</b></td><td>A file that was already read is recognised by its content, and the module asks before spending a second reading, saying which document it came from and when. Saying yes reads it; leaving the question alone costs nothing.</td></tr>
<tr><td>🗂️ <b>Batches</b></td><td>Hand over a folder's worth of documents in one call. Choose the files on their own screen, press Send once, and follow the batch while it is read, file by file.</td></tr>
<tr><td>🧾 <b>Supplier bills</b></td><td>A draft bill from what was read, one line per line, with the product, discount and rate of each. A document that came back with nothing but its two amounts still gets its tax: the rate is worked back from them.</td></tr>
<tr><td>↩️ <b>Credit notes</b></td><td>A rectificativa becomes a vendor credit note instead of a bill, with its entries the other way round. The reading notices the negative total by itself.</td></tr>
<tr><td>📸 <b>Photographed receipts</b></td><td>An installable capture page for a phone. The receipt becomes a supplier bill or an employee expense, with the photo attached.</td></tr>
<tr><td>🏗️ <b>Charged to a project</b></td><td>The document carries the analytic account, so a receipt or a bill line lands on the project it belongs to. No separate app is needed for it.</td></tr>
<tr><td>🔔 <b>Webhooks</b></td><td>The service can call Odoo when a reading finishes, and the call is logged. A company that wants to can let it create the bill and register the payment with nobody in front of the screen.</td></tr>
<tr><td>📥 <b>Inbox</b></td><td>Another module can hand documents over before anyone has looked at them, with its own list and its own pending count.</td></tr>
<tr><td>⚙️ <b>Settings</b></td><td>Sixteen switches over the service, over what a document becomes, and over what a webhook may do on its own. Off by default where the safe answer is off.</td></tr>
<tr><td>🌐 <b>Languages</b></td><td>Spanish, Catalan, Galician, German, French, Italian and Portuguese, with a test that checks every label, help text and runtime message actually reaches the reader.</td></tr>
<tr><td>✅ <b>Tests</b></td><td>250 of them, each one proven to fail when the thing it guards is broken. A test for a switch checks what the switch does, so a switch that stores the right value and changes nothing still fails; a test for a template checks every binding against the component, because a name that is not there raises no error and paints nothing.</td></tr>
</table>

## 📦 What you need

| | |
|---|---|
| **Odoo** | Community 18.0 or 19.0. Enterprise is **not** required. |
| **Other modules** | None to buy. It depends only on what Community ships with (`base`, `mail`, `account`, `hr_expense`). |
| **Database** | Whatever your Odoo already runs on: PostgreSQL, or MySQL/MariaDB. |
| **For scans and photographs** | The EasyOCR extraction service, with its URL and an API key. Digital PDFs need nothing. |

## 🚀 Install

1. Download the ZIP from the [Releases page](https://github.com/EasySoft-Tech-SL/odoo-easyocr-module/releases), taking the one that starts with your Odoo series.
2. Unzip it into your addons path, so that the module sits at `easyocr/` (the archive
   already carries the folder, with no wrapper around it).
3. Restart Odoo and pick **Apps → Update Apps List**.
4. Install **EasyOCR**. It brings its own menu, its own groups and its own settings page.

Nothing else to install: no external library, no second module.

> An Odoo Apps Store listing is on the way. Until then the release ZIP is the way to
> install it, and the only thing the ZIP has that the store listing will not is the
> screenshots in `docs/`.

## 🔑 Configure

Everything lives in **Settings → EasyOCR**:

- **Extraction with AI**: turn the service on, paste its URL, paste your API key, and set
  the timeout. **Test the connection** checks the key without spending a reading.
- **What a document becomes**: a supplier bill, or an employee expense when it came from
  a phone.
- **Whether the bill is posted**: off by default, so a person validates the bill. The
  webhook can be allowed to post and pay on its own, which is the exception and says so.
- **Duplicates**: the same file is not read twice, and the window is yours to set.

## 🔄 From a file to an accounting entry

1. **Drop the file** in the workbench. It is stored as a document with its vendor, its
   dates and its amounts, and it keeps its state (pending, received, processed, error).
2. **Read it**: draw the rectangles by hand, which costs nothing, or press **Read with
   AI** for a scan or a photograph.
3. **Review it.** What was read sits next to the field it came from, and reading a
   document wrong is normal, so it is corrected on the document and not on the bill
   afterwards.
4. **Create the bill.** It lands in draft (or posted, if you asked for that), with the
   vendor matched by tax number, the lines, the tax, and the analytic account of the
   project if the document carries one.

## 🌐 Languages

The interface speaks Spanish, Catalan, Galician, German, French, Italian and Portuguese.
The **user guide is in Spanish** for now:
[`docs/manual/manual-easyocr-es.md`](docs/manual/manual-easyocr-es.md), written from the
screens themselves, and published on the
[company wiki](https://wiki.easysoft.es).

A translation is checked by a test: it reads the `.po` files and fails if a label, a help
text or a sentence the module writes at runtime is missing from any language, or if the
entry points somewhere Odoo will not look for it.

## 🧭 Versions

One branch per Odoo series, as is the norm in the Odoo ecosystem:

| Branch | Odoo series | Module version |
| --- | --- | --- |
| `19.0` (default) | Odoo Community 19.0 | `19.0.1.0.0` |
| `18.0` | Odoo Community 18.0 | `18.0.1.0.0` |

The branch name and the first two digits of the module version always match, and the CI
checks it. One module covers one series: the code is the same on both, except where the
two series genuinely differ.

## 🗺️ Status

Feature complete for a first release, and tested on both series.

[`ROADMAP.md`](ROADMAP.md) is the map: what each phase added and what is deliberately left
out. The differences from the Dolibarr module, and why, are written down there too.

## 🛠️ Development

Requires Docker. Two Odoo instances and one PostgreSQL share a single compose file:

```bash
docker compose up -d
```

| Service | URL | Database |
| --- | --- | --- |
| Odoo 19.0 | http://127.0.0.1:8069 | `odoo19` |
| Odoo 18.0 | http://127.0.0.1:8070 | `odoo18` |

Default credentials are `admin` / `admin`. Ports are deliberately unusual: on the machine
this was built on, 8069 and 8070 were free while 8080, 8081 and 5433 were taken.

Install the module into a database:

```bash
docker compose exec odoo19 odoo -d odoo19 -i easyocr --stop-after-init
```

Run the tests:

```bash
docker compose exec odoo19 odoo -d odoo19 -u easyocr --test-enable --test-tags /easyocr --stop-after-init
```

`--test-tags /easyocr` is not optional in practice: without it Odoo also runs the core
suites, and one of them (`base`'s `test_http_case`) hangs. `-u` rather than `-i` keeps the
module installed and its translations reloaded. After changing a view or a `.po`, restart
the container before looking at the screen: the running server keeps the registry it read
when it started.

The database has to be named `odoo19`: the local configuration sets a `dbfilter` for it,
which is what lets the web app's manifest be served without a session. The comment in
`config/odoo19.conf` explains what happens if you point the suite somewhere else.

### Repository layout

```
addons/easyocr/             the module itself
  models/                   models
  views/                    list, form, search and menus
  security/                 groups and access rules
  static/description/       icon and the description shown in the Apps store
  tests/                    tests
  i18n/                     translations
config/                     Odoo configuration for the local environment
docs/manual/                the user guide, with the screenshots it shows
tools/check_module.py       manifest and layout checks, run by CI
docker-compose.yml          local Odoo 18 + 19 + PostgreSQL
```

## 🤝 Contributing

- One branch per Odoo series; never mix two series in one branch.
- Every new feature ships with its own test, and the test must fail when the feature is broken.
- Code and identifiers in English; user-facing strings translated through `i18n/`.
- The guide is updated in the same batch as the version it describes: a release is not
  finished until the guide matches it.
- Run `python tools/check_module.py --branch <series>` before pushing.

## 📄 License

**GNU Lesser General Public License v3.0 (LGPL-3).** See [`LICENSE`](LICENSE).

The module is free: you can use, modify and redistribute it, under the same license the
Odoo core itself ships under. There is nothing to pay for it, and the complete source
goes with every version.

What a subscription pays for is the **extraction service** the module talks to. Without it
the module still installs and still reads text out of digital PDFs that already carry a
text layer; scanning paper, photographs and email attachments is what needs the service.

`EasyOCR` is a trademark of EasySoft Tech S.L.

## 💬 Support

Write to [info@easysoft.es](mailto:info@easysoft.es).
