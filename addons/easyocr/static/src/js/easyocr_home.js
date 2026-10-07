import { Component, onWillStart, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";

/**
 * Where the app lands: what is waiting, and the way to each screen.
 *
 * Odoo has no concept of a module dashboard -- an app opens its main view -- so
 * this was asked for on its own (see the Dolibarr module's index.php, which is
 * the same idea). It is the first entry of the app's menu, which is also what
 * makes the app open here instead of on the document list.
 *
 * The counters are read, never cached: a number left over from the last visit
 * is worse than no number at all.
 */
export class EasyocrHome extends Component {
    static template = "easyocr.Home";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.title = _t("EasyOCR");
        this.subtitle = _t("Read supplier invoices and expense receipts, and turn them into accounting entries.");

        this.state = useState({ counts: false, canConfigure: false });

        onWillStart(() => this.loadCounts());
    }

    async loadCounts() {
        const [documents, pending, templates, inbox, logs, canConfigure] = await Promise.all([
            this.orm.searchCount("easyocr.document", []),
            this.orm.searchCount("easyocr.document", [["state", "=", "draft"]]),
            this.orm.searchCount("easyocr.template", []),
            this.orm.searchCount("easyocr.inbox.item", [["state", "=", "pending"]]),
            this.orm.searchCount("easyocr.webhook.log", []),
            // Asked once, at the start: it is a promise, and a getter cannot
            // wait for one.
            user.hasGroup("easyocr.group_easyocr_manager"),
        ]);
        this.state.counts = { documents, pending, templates, inbox, logs };
        this.state.canConfigure = canConfigure;
    }

    get cards() {
        const counts = this.state.counts;
        const cards = [
            {
                key: "documents",
                icon: "fa-file-text-o",
                title: _t("Documents"),
                note: _t("Invoices and receipts read, or waiting to be"),
                count: counts ? counts.documents : null,
                action: "easyocr.action_easyocr_document",
                tone: counts && counts.pending ? "attention" : "",
            },
            {
                key: "inbox",
                icon: "fa-inbox",
                title: _t("Inbox"),
                note: _t("Waiting to be looked at, handed over by other modules"),
                count: counts ? counts.inbox : null,
                action: "easyocr.action_easyocr_inbox",
            },
            {
                key: "templates",
                icon: "fa-th-large",
                title: _t("Templates"),
                note: _t("The boxes saved for each vendor"),
                count: counts ? counts.templates : null,
                action: "easyocr.action_easyocr_template",
            },
            {
                key: "capture",
                icon: "fa-camera",
                title: _t("Capture a receipt"),
                note: _t("Photograph one from a phone"),
                count: null,
                url: "/easyocr/capture",
            },
            {
                key: "webhooks",
                icon: "fa-exchange",
                // Spelled as the menu is, so the two share one translation.
                title: _t("Webhook Log"),
                note: _t("The calls the extraction service has made"),
                count: counts ? counts.logs : null,
                action: "easyocr.action_easyocr_webhook_log",
            },
        ];

        if (this.state.canConfigure) {
            cards.push({
                key: "settings",
                icon: "fa-sliders",
                title: _t("Settings"),
                note: _t("The extraction service and what a document becomes"),
                count: null,
                url: "/odoo/settings#easyocr",
            });
        }
        return cards;
    }

    open(card) {
        if (card.url) {
            this.action.doAction({
                type: "ir.actions.act_url",
                url: card.url,
                target: "self",
            });
            return;
        }
        this.action.doAction(card.action);
    }
}

registry.category("actions").add("easyocr.home", EasyocrHome);
