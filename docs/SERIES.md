# The five series, and what each one needs

The repository carries one branch per Odoo series: `16.0`, `17.0`, `18.0`, `19.0` and
`20.0` (`19.0` is the default branch). They are not copies of one another: Odoo moved a
few things between them, and a line that is right on the series it was written for is a
bug on the next one. This is the list of what actually differs, measured on the running
containers of each series and not read off a changelog.

## What differs, series by series

| | 16.0 | 17.0 | 18.0 | 19.0 | 20.0 |
|---|---|---|---|---|---|
| List view tag | `<tree>` | `<tree>` | `<list>` | `<list>` | `<list>` |
| `view_mode` | `tree,form` | `tree,form` | `list,form` | `list,form` | `list,form` |
| View modifiers | `attrs="{'invisible': [('x', '=', y)]}"` | `invisible="x == y"` | same as 17 | same as 17 | same as 17 |
| A condition on a field the same view hides with `groups` | the view does not load | the view does not load if the modifier is `readonly` | accepted | same as 18 | same as 18 |
| Webhook route | `type='http'` | `type='http'` | `type='http'` | `type='json2'` | `type='json2'` |
| Reading the body | `request.get_json_data()` | `request.httprequest.get_json(silent=True)` | same as 17 | same as 17 | same as 17 |
| A body that is not JSON | 400 from the route | 400 from the route | 400 from the route | 400 from the dispatcher, before the route | same as 19 |
| Batch cron | needs `numbercall = -1` | same as 16 | runs while installed | same as 18 | same as 18 |
| Sending an expense report | builds and submits the sheet by hand | `action_submit_expenses()` | same as 17 | same as 17 | same as 17 |
| `Last Modified on` label | carried by `__last_update`, its own `.po` term | not a field | not a field | not a field | not a field |
| OWL state | `useState` | `useState` | `useState` | `useState` | `proxy` |
| Icons | Font Awesome (`fa-money`, `fa-th-large`) | same as 16 | same as 16 | same as 16 | the new set (`payments`, `grid_view`, `picture_as_pdf`) |
| A file under `static/src/js/` | has to open with `/** @odoo-module **/` | same as 16 | is a module already | same as 18 | same as 18 |
| Asset templates (`static/src/xml/`) | each top-level `<t t-name=…>` needs `owl="1"` | the attribute is not used | same as 17 | same as 17 | same as 17 |
| Reaching the user | the `user` service, its `hasGroup` awaited | same as 16 | `import { user } from "@web/core/user"` | same as 18 | same as 18 |
| What `view_widgets` holds | the component itself | `{ component: X }` | same as 17 | same as 17 | same as 17 |

Eight of these are traps worth spelling out.

**A condition on a field the view hides.** A field with `groups="base.group_no_one"` is
not in the view for anybody outside that group, and the same view may not then name it
in a modifier. Odoo 16 refuses the whole file (`Field 'service_uuid' used in attrs ...
is restricted to the group(s) base.group_no_one`), 17 accepts it in `invisible` and
refuses it in `readonly`, and 18 to 20 load it and leave the condition to be worked out
in the browser against a field the reader was never given, which is the quiet one. The
batch form keeps its UUID behind that group, so it asks about `sent_at` instead: the
date is written in the same transaction as the UUID and only once the service has taken
the files, so the two say the same thing. `tests/test_easyocr_views.py` reads the views
and fails when a condition names a field its own view hides.

**The body of the webhook.** Odoo 16 bundles werkzeug 1.0.1, where the request
has no `get_json()`: calling it raises `AttributeError` and the caller gets a
500. `request.get_json_data()` is Odoo's own, it exists on all five series and it
parses the same way, but it raises on a body it cannot read, which is why 16
wraps it. From 17 up the werkzeug is new enough. On 19 and 20 the body is parsed
by the `json2` dispatcher before the route is reached at all, so garbage gets the
dispatcher's own 400 and the route's `{'status': 'error'}` never appears: the
test asserts the status code and that nothing was written, and says why.

**The batch cron.** `ir.cron` carries `numbercall` up to 17 and defaults it to 1:
a job without it runs once, switches itself off and leaves the batches to the
webhook alone from then on. The 16 and 17 branches set it to `-1`, which is "no
limit". From 18 the field is gone and a job runs while the module is installed.

**Sending an expense report.** On 16 `hr.expense.action_submit_expenses()` does
not submit anything: it opens the "New Expense Report" form for whoever is at the
screen to confirm. A call to it from code leaves the receipt in draft and tells
nobody. That branch builds the sheet and submits it by hand.

**The first line of a backend script.** Up to 17 the backend bundle is handed to
the browser as a classic script, and a file only becomes a module if it says so
at the very top. Without `/** @odoo-module **/` its `import` statements go to the
browser as they stand and the whole client dies with `SyntaxError: Cannot use
import statement outside a module`: a blank page, and nothing anywhere to say
why. The marker opens all nine files of the 16 and 17 branches. From 18 the
bundle is a module already and the marker buys nothing, so those branches do not
carry it.

**The templates on 16.** Odoo 16 collects the asset templates with the selector
`templates > [t-name][owl]` (`web/static/src/core/assets.js`) and takes the
attribute off before handing them to the app. A template without it never
arrives, and the first screen that asks for it dies with `Missing template:
"easyocr.Home"`. From 17 the selector is `templates > [t-name]`, and the
attribute is neither needed nor removed: it is on the 16 branch only, on all 13
templates of the six files.

**Where the user comes from.** 16 and 17 register a `user` service
(`web/static/src/core/user_service.js`, `registry.category("services").add("user",
userService)`) and have no `@web/core/user` at all, so a script that imports it
is left with an unmet dependency and does not load. Its `hasGroup` answers with a
promise, which is why its two callers await it. From 18 the module is
`web/static/src/core/user.js`, which exports the `user` object filled from the
session and registers no service: there it is imported and `hasGroup` answers on
the spot. Written the same way on both, one of the two is broken.

**What a view widget holds.** Up to 16 the registry value is the component
itself: the widget template reads `<t t-component="Widget">` and hands the value
straight over. From 17 it is `{ component, extractProps }`, which is what 19
checks for (`component: { validate: (c) => c.prototype instanceof Component }`).
Registered the other way the settings screen does not render, and 16 throws
`TypeError: C is not a constructor` while the newer series say nothing at all.

`tests/test_easyocr_assets.py` is the same file on all five branches and reads the
version it is running on: the first line rule, the `owl` attribute, where the user
comes from and what the registry holds, each one only on the series that reads it
that way. It is read off the files, so it catches the mistake where it is made.

## Running the suite of one series

### Do not run it inside the container that is already serving the series

The test client and the dev server want the same port. Inside the live container
the test server cannot bind 8069 (`OSError: [Errno 98] Address already in use`,
in the `odoo.service.httpd` thread), every `url_open` then reaches the running dev
server, which knows nothing about the test, and the suite fills up with 403s and
failures that only exist because of where it was launched from.

Run it in a container of its own, on the same network, with the series container
left alone. The two share the database and the filestore, and the throwaway one
binds its own 8069.

From the tree that holds `docker-compose.yml`, the short way is a service of its
own (measured on 12-oct-2026, `run` and not `exec`):

```bash
docker compose run --rm odoo<NN> odoo -c /etc/odoo/odoo.conf -d odoo<NN> \
  -u easyocr --test-enable --test-tags /easyocr --stop-after-init
```

Without compose, the same thing by hand:

```bash
docker run --rm --network odoo-easyocr_default \
  -v D:/GIT/odoo-easyocr-<NN>:/mnt/extra-addons \
  -v D:/GIT/odoo-easyocr-<NN>/config/odoo<NN>.conf:/etc/odoo/odoo.conf:ro \
  -v odoo-easyocr_odoo<NN>-data:/var/lib/odoo \
  odoo:<NN>.0 odoo -c /etc/odoo/odoo.conf -d odoo<NN> \
  --test-enable --test-tags /easyocr --stop-after-init
```

`MSYS_NO_PATHCONV=1` is needed on this machine, or the paths arrive mangled.

### A data record is not rewritten by `-u`

The cron record lives under `<data noupdate="1">`: updating the module leaves it
as it is. A change to it only lands on a fresh install, so the way to test one is
to drop the database and install again (`DROP DATABASE odoo<NN>` after
`pg_terminate_backend`, then `-i easyocr,l10n_generic_coa --without-demo=all`).

## What is the same in all five

`docker-compose.yml`, `docs/` and the README describe the whole project, not one
series, and are kept byte for byte identical. A change to any of them belongs in
every branch.
