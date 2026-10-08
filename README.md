# odoo-easyocr-module

EasySoft OCR for Odoo Community: reads supplier invoices and expense receipts from PDF and
image files, and turns them into accounting entries.

This is the Odoo counterpart of EasyOCR for Dolibarr. Maintained by
[EasySoft Tech S.L.](https://easysoft.es).

## Supported versions

One branch per Odoo series, as is the norm in the Odoo ecosystem:

| Branch | Odoo series | Module version |
| --- | --- | --- |
| `19.0` (default) | Odoo Community 19.0 | `19.0.1.0.0` |
| `18.0` | Odoo Community 18.0 | `18.0.1.0.0` |

The branch name and the first two digits of the module version always match; the CI checks it.

Odoo Enterprise is **not** required.

## Repository layout

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

## The user guide

[`docs/manual/manual-easyocr-es.md`](docs/manual/manual-easyocr-es.md) is the guide a
customer reads: installing the module, configuring the service, drawing the fields on a
document, turning one into a supplier bill, and the mobile capture page. Its screenshots
were taken from a running instance, not drawn.

The same text is published on the company wiki. **A release is not finished until the
guide matches it**, and the guide is updated in the same batch as the version it
describes.

## Local development

Requires Docker. Two Odoo instances and one PostgreSQL share a single compose file:

```bash
docker compose up -d
```

| Service | URL | Database |
| --- | --- | --- |
| Odoo 19.0 | http://127.0.0.1:8069 | `odoo19` |
| Odoo 18.0 | http://127.0.0.1:8070 | `odoo18` |

Default credentials are `admin` / `admin`. Ports are deliberately unusual: on the machine this
was built on, 8069 and 8070 were free while 8080, 8081 and 5433 were taken.

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
module installed and its translations reloaded.

The database has to be named `odoo19`: the local configuration sets a `dbfilter` for it,
which is what lets the web app's manifest be served without a session. The comment in
`config/odoo19.conf` explains what happens if you point the suite somewhere else.

## Status

Feature complete for a first release, and tested on both series. What works: the document
viewer with its rectangle templates, extraction from the text layer of a PDF, extraction
through the EasyOCR service, creating a supplier bill from a document, the inbox other modules
hand files to, the inbound webhook with its log, and the mobile capture page.

`ROADMAP.md` lists what is deliberately left out of this version.

Templates are saved under the vendor they belong to, and come back painted on that vendor's
next document, with their text read again from the file in front of you.

## Contributing

- One branch per Odoo series; never mix two series in one branch.
- Every new feature ships with its own test, and the test must fail when the feature is broken.
- Code and identifiers in English; user-facing strings translated through `i18n/`.
- Run `python tools/check_module.py --branch <series>` before pushing.

## License

**GNU Lesser General Public License v3.0 (LGPL-3).** See [`LICENSE`](LICENSE).

The module is free: you can use, modify and redistribute it, under the same
license the Odoo core itself ships under. There is nothing to pay for it, and
the complete source goes with every version.

What a subscription pays for is the **extraction service** the module talks to.
Without it the module still installs and still reads text out of digital PDFs
that already carry a text layer; scanning paper, photographs and email
attachments is what needs the service.

`EasyOCR` is a trademark of EasySoft Tech S.L.

## Support

Write to [info@easysoft.es](mailto:info@easysoft.es).
