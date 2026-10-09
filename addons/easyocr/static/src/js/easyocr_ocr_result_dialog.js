import { Component, onWillStart, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * The reading result, as the sectioned dialog the module this is a port of
 * shows: one collapsible card per part of the answer, the raw payload behind a
 * JSON button, and a footer that makes the bill from what was read.
 *
 * The server hands back the cards as ready label/value rows, so this component
 * only paints them. Nothing is invented: an empty card is not painted at all.
 */
export class OCRResultDialog extends Component {
    static template = "easyocr.OCRResultDialog";
    static props = {
        action: Object,
        actionId: { type: [Number, Boolean], optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            showPayload: false,
            data: null,
            busy: false,
            collapsed: {},
            // Whether the bill is posted straight away or left in draft.
            draft: false,
            // The journal the bill is posted to, when the reader picks one.
            journals: [],
            journalId: null,
        });
        onWillStart(() => this.load());
    }

    get documentId() {
        return this.props.action.params?.document_id;
    }

    async load() {
        try {
            this.state.data = await this.orm.call(
                "easyocr.document", "action_result_data", [[this.documentId]],
            );
        } catch {
            this.state.data = null;
        } finally {
            this.state.loading = false;
        }
        try {
            this.state.journals = await this.orm.call(
                "easyocr.document", "action_list_journals", [],
            );
        } catch {
            this.state.journals = [];
        }
    }

    toggleCard(key) {
        this.state.collapsed[key] = !this.state.collapsed[key];
    }

    isCollapsed(key) {
        return this.state.collapsed[key];
    }

    togglePayload() {
        this.state.showPayload = !this.state.showPayload;
    }

    payloadText() {
        return JSON.stringify(this.state.data?.raw || {}, null, 2);
    }

    pills() {
        return this.state.data?.meta_pills || [];
    }

    /** The label/value rows of one card, already translated by the server. */
    sectionRows(key) {
        return this.state.data?.sections?.[key] || [];
    }

    hasSection(key) {
        if (key === "lines") {
            return (this.state.data?.items || []).length > 0;
        }
        if (key === "notes") {
            return Boolean(this.state.data?.notes);
        }
        return this.sectionRows(key).length > 0;
    }

    items() {
        return this.state.data?.items || [];
    }

    notes() {
        return this.state.data?.notes || "";
    }

    close() {
        this.actionService.doAction({ type: "ir.actions.act_window_close" });
    }

    async createInvoice() {
        this.state.busy = true;
        try {
            const result = await this.orm.call(
                "easyocr.document", "action_create_bill",
                [[this.documentId], this.state.draft, this.state.journalId],
            );
            if (result) {
                await this.actionService.doAction(result);
            } else {
                this.close();
            }
        } catch {
            this.notification.add(_t("The bill could not be created."), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }
}

registry.category("actions").add("easyocr.ocr_result_dialog", OCRResultDialog);
