import { Component, onWillStart, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";

// The colour each card carries, taken from the dashboard of the module this one
// comes from so the two screens are recognisably the same. An accent for the
// icon and the border, and a tint to sit behind the icon.
const PDF = { accent: "#1565c0", bg: "#e3f2fd" };
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
        this.subtitle = _t("Read supplier invoices and expense receipts, and turn them into accounting entries.");
        this.sectionTitle = _t("Sections");
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
                key: "documents",
                icon: "fa-file-text-o",
                label: _t("Documents"),
                count: counts ? counts.documents : null,
                action: "easyocr.action_easyocr_document",
                accent: PDF.accent,
                bg: PDF.bg,
            },
            {
                key: "invoices",
                icon: "fa-money",
                label: _t("Bills"),
                count: counts ? counts.invoices : null,
                action: "account.action_move_in_invoice_type",
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
                key: "documents",
                icon: "fa-file-pdf-o",
                title: _t("Documents"),
                note: _t("Invoices and receipts read, or waiting to be"),
                action: "easyocr.action_easyocr_document",
                ...PDF,
            },
            {
                key: "inbox",
                icon: "fa-inbox",
                title: _t("Inbox"),
                note: _t("Waiting to be looked at, handed over by other modules"),
                action: "easyocr.action_easyocr_inbox",
                ...INBOX,
            },
            {
                key: "capture",
                icon: "fa-camera",
                title: _t("Capture a receipt"),
                note: _t("Photograph one from a phone"),
                url: "/easyocr/capture",
                ...SCAN,
            },
            {
                key: "templates",
                icon: "fa-th-large",
                title: _t("Templates"),
                note: _t("The boxes saved for each vendor"),
                action: "easyocr.action_easyocr_template",
                ...TEMPLATES,
            },
            {
                key: "invoices",
                icon: "fa-money",
                title: _t("Vendor bills"),
                note: _t("What the documents became"),
                action: "account.action_move_in_invoice_type",
                ...INVOICES,
            },
            {
                key: "webhooks",
                icon: "fa-exchange",
                // Spelled as the menu is, so the two share one translation.
                title: _t("Webhook Log"),
                note: _t("The calls the extraction service has made"),
                action: "easyocr.action_easyocr_webhook_log",
                ...WEBHOOKS,
            },
        ];

        if (this.state.canConfigure) {
            cards.push({
                key: "settings",
                icon: "fa-cog",
                title: _t("Settings"),
                note: _t("The extraction service and what a document becomes"),
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
