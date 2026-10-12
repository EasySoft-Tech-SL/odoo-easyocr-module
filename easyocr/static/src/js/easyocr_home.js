import { Component, onWillStart, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";

// The colour each card carries, taken from the dashboard of the module this one
// comes from so the two screens are recognisably the same. An accent for the
// icon and the border, and a tint to sit behind the icon.
const PDF = { accent: "#1565c0", bg: "#e3f2fd" };
const DOCUMENTS = { accent: "#3949ab", bg: "#e8eaf6" };
const INBOX = { accent: "#2e7d32", bg: "#e8f5e9" };
const SCAN = { accent: "#5b3cc4", bg: "#ede7f6" };
const TEMPLATES = { accent: "#5e35b1", bg: "#ede7f6" };
const INVOICES = { accent: "#e65100", bg: "#fff3e0" };
const WEBHOOKS = { accent: "#00838f", bg: "#e0f7fa" };
const SETUP = { accent: "#546e7a", bg: "#eceff1" };

/**
 * Where the app lands: what is waiting, and the way to each screen.
 *
 * Odoo has no concept of a module dashboard -- an app opens its main view -- so
 * this was asked for on its own, and it is the dashboard of the Dolibarr module
 * this one is a port of, down to its order and its colours. It is the first
 * entry of the app's menu, which is also what makes the app open here instead
 * of on the document list.
 *
 * The counters are read, never cached: a number left over from the last visit
 * is worse than no number at all.
 */
export class EasyocrHome extends Component {
    static template = "easyocr.Home";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.logoSrc = "/easyocr/static/description/icon.png";
        this.title = _t("EasyOCR");
        this.subtitle = _t("Tool for extracting text content from PDF files for automatic creation of supplier invoices in Dolibarr.");
        this.sectionTitle = _t("Quick access");
        this.openLabel = _t("Open");

        this.state = useState({ counts: false, canConfigure: false });

        onWillStart(() => this.loadCounts());
    }

    async loadCounts() {
        const [documents, invoices, templates, canConfigure] = await Promise.all([
            this.orm.searchCount("easyocr.document", []),
            this.orm.searchCount("easyocr.document", [["move_id", "!=", false]]),
            this.orm.searchCount("easyocr.template", []),
            // Asked once, at the start: it is a promise, and a getter cannot
            // wait for one.
            user.hasGroup("easyocr.group_easyocr_manager"),
        ]);
        this.state.counts = { documents, invoices, templates };
        this.state.canConfigure = canConfigure;
    }

    get stats() {
        const counts = this.state.counts;
        return [
            {
                key: "invoices",
                icon: "fa-money",
                label: _t("Invoices"),
                count: counts ? counts.invoices : null,
                action: "easyocr.action_easyocr_invoice",
                accent: INVOICES.accent,
                bg: INVOICES.bg,
            },
            {
                key: "templates",
                icon: "fa-th-large",
                label: _t("Templates"),
                count: counts ? counts.templates : null,
                action: "easyocr.action_easyocr_template",
                accent: TEMPLATES.accent,
                bg: TEMPLATES.bg,
            },
        ];
    }

    get cards() {
        const cards = [
            {
                // First, as it is in the module this is a port of: uploading a
                // file and landing in the viewer is what most visits are for.
                key: "upload",
                icon: "fa-file-pdf-o",
                title: _t("Upload PDF"),
                note: _t("Import a PDF and visually extract supplier invoice data."),
                action: "easyocr.action_easyocr_new_document",
                ...PDF,
            },
            {
                key: "batch",
                icon: "fa-files-o",
                title: _t("Batch processing"),
                note: _t("Process multiple PDFs at once with AI-powered automatic extraction."),
                action: "easyocr.action_easyocr_batch",
                ...DOCUMENTS,
            },
            {
                key: "capture",
                icon: "fa-camera",
                title: _t("Scan expense"),
                note: _t("Scan an expense receipt from your phone and register it automatically."),
                url: "/easyocr/capture",
                ...SCAN,
            },
            {
                key: "templates",
                icon: "fa-th-large",
                title: _t("Templates"),
                note: _t("Manage zone selection templates linked to suppliers."),
                action: "easyocr.action_easyocr_template",
                ...TEMPLATES,
            },
            {
                key: "invoices",
                icon: "fa-money",
                title: _t("Invoices"),
                note: _t("View the history of invoices generated from imported PDFs."),
                action: "easyocr.action_easyocr_invoice",
                ...INVOICES,
            },
            {
                key: "webhooks",
                icon: "fa-exchange",
                title: _t("Webhook logs"),
                note: _t("Audit incoming webhook notifications and review processing failures."),
                action: "easyocr.action_easyocr_webhook_log",
                ...WEBHOOKS,
            },
        ];

        if (this.state.canConfigure) {
            cards.push({
                key: "settings",
                icon: "fa-cog",
                title: _t("Setup"),
                note: _t("Configure the API key, cloud service and module options."),
                url: "/odoo/settings#easyocr",
                ...SETUP,
            });
        }
        return cards;
    }

    open(entry) {
        if (entry.url) {
            this.action.doAction({
                type: "ir.actions.act_url",
                url: entry.url,
                target: "self",
            });
            return;
        }
        this.action.doAction(entry.action);
    }
}

registry.category("actions").add("easyocr.home", EasyocrHome);
