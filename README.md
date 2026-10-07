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
tools/check_module.py       manifest and layout checks, run by CI
docker-compose.yml          local Odoo 18 + 19 + PostgreSQL
```

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
docker compose exec odoo19 odoo -d odoo19 -i easyocr --test-enable --stop-after-init
```

## Status

Early. The document inbox, its status flow, its permissions and its translations are in place
and tested. The extraction engine and the creation of supplier bills from a document are **not**
implemented yet; see the roadmap in `addons/easysoft_ocr/README.rst`.

## Contributing

- One branch per Odoo series; never mix two series in one branch.
- Every new feature ships with its own test, and the test must fail when the feature is broken.
- Code and identifiers in English; user-facing strings translated through `i18n/`.
- Run `python tools/check_module.py --branch <series>` before pushing.

## License

**Odoo Proprietary License v1.0 (OPL-1).** See [`LICENSE`](LICENSE).

The source is readable, and a licence is what grants the right to run it. It is
not open source: publishing, redistributing or reselling it, modified or not, is
not allowed. Each customer gets the complete source of the version they are
entitled to, which is what makes the module auditable and adaptable on site.

Reading the code here does not grant a licence to use it. The extraction service
the module talks to is licensed separately and is what a subscription pays for.

## Support

Write to [info@easysoft.es](mailto:info@easysoft.es).
