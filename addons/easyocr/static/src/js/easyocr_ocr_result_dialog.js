import { Component, onMounted, onWillStart, useExternalListener, useRef, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { formatFloat } from "@web/core/utils/numbers";
import { parseFloat as parseLocalFloat } from "@web/views/fields/parsers";

// What the reader may correct on each card, and hand back with the bill. The
// rest is shown read-only: a box that accepts typing and then ignores it is
// worse than one that says plainly it cannot be changed.
const EDITABLE = {
    document: ["document_number", "issue_date", "due_date"],
    supplier: ["name", "tax_id", "address", "city", "postal_code", "country", "phone", "email"],
    totals: ["subtotal", "tax"],
};
// Fields that take a whole row of the two-column grid.
const WIDE = ["name", "address", "bank_account"];
const MONEY_SECTIONS = ["totals"];
const LINE_NUMBERS = ["quantity", "unit_price", "discount_percent", "tax_rate", "re_rate", "irpf_rate"];
// Per-line rounding is forgiven; anything above this is a misread.
const MISMATCH_TOLERANCE = 0.05;

let nextDialogId = 0;

/**
 * The reading result, as the sectioned dialog the module this is a port of
 * shows: one collapsible card per part of the answer, every value in a field
 * the reader can check (and, where it feeds the bill, correct), the lines in
 * an editable table, a warning when the lines do not add up to the totals,
 * the raw payload behind a JSON button, and a footer that makes the bill.
 */
export class OCRResultDialog extends Component {
    static template = "easyocr.OCRResultDialog";
    static props = {
        action: Object,
        actionId: { type: [Number, Boolean], optional: true },
        "*": true,
    };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.modalRef = useRef("modal");
        this.uid = `o_easyocr_result_${++nextDialogId}`;
        this.itemTypes = [
            ["product", _t("Product")],
            ["service", _t("Service")],
            ["shipping", _t("Shipping")],
            ["surcharge", _t("Surcharge")],
            ["fee", _t("Fee")],
            ["discount", _t("Discount")],
            ["other", _t("Other")],
        ];
        this.state = useState({
            loading: true,
            showPayload: false,
            data: null,
            busy: false,
            error: "",
            collapsed: {},
            // One {key, label, value} list per card, the values as typed.
            fields: {},
            draft: false,
            isRefund: false,
            journals: [],
            journalId: "",
            items: [],
            products: {},
            supplierMatch: null,
            createPayment: false,
            paymentModes: [],
            banks: [],
            paymentModeId: "",
            bankId: "",
        });
        useExternalListener(window, "keydown", this.onKeydown.bind(this));
        onWillStart(() => this.load());
        onMounted(() => this.modalRef.el?.focus());
    }

    get documentId() {
        return this.props.action.params?.document_id;
    }

    // ------------------------------------------------------------------
    // Loading
    // ------------------------------------------------------------------

    async load() {
        try {
            const data = await this.orm.call(
                "easyocr.document", "action_result_data", [[this.documentId]],
            );
            this.state.data = data;
            const fields = {};
            for (const [section, rows] of Object.entries(data?.sections || {})) {
                fields[section] = rows.map(([key, label, value]) => ({
                    key,
                    label,
                    value: MONEY_SECTIONS.includes(section) ? this.formatNumber(value) : String(value ?? ""),
                }));
            }
            // The fields that feed the bill are offered even when the reading
            // left them empty, so a missing invoice number can still be typed.
            for (const [section, keys] of Object.entries({ document: EDITABLE.document, supplier: ["name", "tax_id"] })) {
                fields[section] = fields[section] || [];
                for (const key of keys) {
                    if (!fields[section].some((field) => field.key === key)) {
                        fields[section].push({ key, label: this.defaultLabel(key), value: "" });
                    }
                }
            }
            this.state.fields = fields;
            this.state.items = (data?.items || []).map((item) => this.editableItem(item));
            this.state.supplierMatch = data?.supplier_match || null;
            this.state.draft = Boolean(data?.invoice_draft);
            this.state.isRefund = Boolean(data?.is_refund);
        } catch {
            this.state.data = null;
        } finally {
            this.state.loading = false;
        }
        const [journals, modes, banks] = await Promise.all([
            this.safeCall("action_list_journals"),
            this.safeCall("action_list_payment_modes"),
            this.safeCall("action_list_banks"),
        ]);
        this.state.journals = journals;
        this.state.paymentModes = modes;
        this.state.banks = banks;
        this.resolveProducts();
    }

    async safeCall(method, args = []) {
        try {
            return (await this.orm.call("easyocr.document", method, args)) || [];
        } catch {
            return [];
        }
    }

    defaultLabel(key) {
        return {
            document_number: _t("Invoice number"),
            issue_date: _t("Date"),
            due_date: _t("Due date"),
            name: _t("Name"),
            tax_id: _t("Tax ID"),
        }[key] || key;
    }

    editableItem(item) {
        const editable = {
            code: item.code || "",
            description: item.description || "",
            item_type: item.item_type || "product",
        };
        for (const key of LINE_NUMBERS) {
            const value = Number(item[key]) || 0;
            // A rate that is not there reads as an empty box, not as a zero.
            editable[key] = key === "quantity" || key === "unit_price" || value
                ? this.formatNumber(value, key === "unit_price" ? 2 : 0)
                : "";
        }
        return editable;
    }

    // ------------------------------------------------------------------
    // Numbers, the way the reader's language writes them
    // ------------------------------------------------------------------

    formatNumber(value, minDigits = 2) {
        if (value === null || value === undefined || value === "") {
            return "";
        }
        const number = Number(value);
        if (Number.isNaN(number)) {
            return String(value);
        }
        return formatFloat(number, { digits: [false, Math.max(minDigits, this.decimals(number))] });
    }

    decimals(number) {
        const text = String(number);
        const dot = text.indexOf(".");
        return dot === -1 ? 0 : Math.min(text.length - dot - 1, 4);
    }

    parseNumber(text) {
        const clean = String(text ?? "").trim();
        if (!clean) {
            return 0;
        }
        try {
            return parseLocalFloat(clean);
        } catch {
            const number = Number(clean.replace(/\s/g, "").replace(",", "."));
            return Number.isNaN(number) ? 0 : number;
        }
    }

    // ------------------------------------------------------------------
    // Cards
    // ------------------------------------------------------------------

    toggleCard(key) {
        this.state.collapsed[key] = !this.state.collapsed[key];
    }

    isCollapsed(key) {
        return Boolean(this.state.collapsed[key]);
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

    sectionFields(key) {
        return this.state.fields[key] || [];
    }

    hasSection(key) {
        if (key === "lines") {
            return true;
        }
        if (key === "notes") {
            return Boolean(this.state.data?.notes);
        }
        return this.sectionFields(key).length > 0;
    }

    isEditable(section, key) {
        return (EDITABLE[section] || []).includes(key);
    }

    isWide(key) {
        return WIDE.includes(key);
    }

    isMoney(section) {
        return MONEY_SECTIONS.includes(section);
    }

    fieldId(section, key) {
        return `${this.uid}_${section}_${key}`;
    }

    fieldValue(section, key) {
        return this.sectionFields(section).find((field) => field.key === key)?.value || "";
    }

    onFieldChange(section, field, ev) {
        field.value = ev.target.value;
        if (section === "supplier" && (field.key === "tax_id" || field.key === "name")) {
            this.checkSupplier();
        }
    }

    async checkSupplier() {
        try {
            this.state.supplierMatch = await this.orm.call(
                "easyocr.document", "action_check_supplier",
                [this.fieldValue("supplier", "tax_id"), this.fieldValue("supplier", "name")],
            );
        } catch {
            this.state.supplierMatch = null;
        }
        this.resolveProducts();
    }

    supplierHint() {
        const match = this.state.supplierMatch;
        if (!match) {
            return null;
        }
        if (match.status === "found") {
            return { cls: "is-found", icon: "fa-check-circle", text: _t("Supplier on file: %s", match.name) };
        }
        if (match.status === "new") {
            return { cls: "is-new", icon: "fa-plus-circle", text: _t("New supplier: it will be created from this data") };
        }
        if (match.status === "own") {
            return { cls: "is-own", icon: "fa-exclamation-triangle", text: _t("This tax ID is your own company's") };
        }
        return null;
    }

    // ------------------------------------------------------------------
    // Lines
    // ------------------------------------------------------------------

    items() {
        return this.state.items;
    }

    lineNet(item) {
        const quantity = item.quantity === "" ? 1 : this.parseNumber(item.quantity);
        const discount = this.parseNumber(item.discount_percent);
        return quantity * this.parseNumber(item.unit_price) * (1 - discount / 100);
    }

    /** What a screen reader says for one box of the table: column and row. */
    cellLabel(key, index) {
        const columns = {
            code: _t("Code"),
            description: _t("Description"),
            item_type: _t("Type"),
            quantity: _t("Qty"),
            unit_price: _t("Price"),
            discount_percent: _t("Disc%"),
            tax_rate: _t("Tax%"),
            re_rate: _t("RE%"),
            irpf_rate: _t("IRPF%"),
        };
        return _t("%(column)s, line %(line)s", { column: columns[key], line: index + 1 });
    }

    paymentHint() {
        return this.state.draft ? _t("Only a validated invoice can be paid") : "";
    }

    lineTotal(item) {
        return this.formatNumber(this.lineNet(item));
    }

    removeLine(index) {
        this.state.items.splice(index, 1);
    }

    addLine() {
        this.state.items.push(this.editableItem({ quantity: 1, unit_price: 0 }));
    }

    async resolveProducts() {
        const codes = [...new Set(this.state.items.map((item) => item.code.trim()).filter(Boolean))];
        if (!codes.length) {
            this.state.products = {};
            return;
        }
        try {
            this.state.products = await this.orm.call(
                "easyocr.document", "action_resolve_codes",
                [this.state.supplierMatch?.id || false, codes],
            ) || {};
        } catch {
            this.state.products = {};
        }
    }

    productOf(item) {
        return this.state.products[item.code.trim()] || "";
    }

    /** The gap between the lines and the totals printed on the document. */
    mismatch() {
        if (!this.state.items.length) {
            return "";
        }
        let sumNet = 0;
        let sumTax = 0;
        for (const item of this.state.items) {
            const net = this.lineNet(item);
            sumNet += net;
            sumTax += net * this.parseNumber(item.tax_rate) / 100;
        }
        const pieces = [];
        const docNet = this.fieldValue("totals", "subtotal");
        const docTax = this.fieldValue("totals", "tax");
        if (docNet !== "") {
            const value = this.parseNumber(docNet);
            if (Math.abs(value) > 0.005 && Math.abs(sumNet - value) > MISMATCH_TOLERANCE) {
                pieces.push(`${_t("Subtotal")}: ${this.formatNumber(sumNet)} ≠ ${this.formatNumber(value)}`);
            }
        }
        if (docTax !== "") {
            const value = this.parseNumber(docTax);
            if (Math.abs(value) > 0.005 && Math.abs(sumTax - value) > MISMATCH_TOLERANCE) {
                pieces.push(`${_t("Tax")}: ${this.formatNumber(sumTax)} ≠ ${this.formatNumber(value)}`);
            }
        }
        return pieces.join(" · ");
    }

    notes() {
        return this.state.data?.notes || "";
    }

    // ------------------------------------------------------------------
    // Footer
    // ------------------------------------------------------------------

    setDraft(draft) {
        this.state.draft = draft;
        if (draft) {
            // A draft is not paid: Odoo pays posted bills only.
            this.state.createPayment = false;
        }
    }

    onKeydown(ev) {
        if (ev.key === "Escape" && !this.state.busy) {
            ev.preventDefault();
            this.close();
        } else if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey)) {
            ev.preventDefault();
            this.createInvoice();
        } else if (ev.key === "Tab") {
            this.trapFocus(ev);
        }
    }

    /** Keep the keyboard inside the dialog while it is open. */
    trapFocus(ev) {
        const modal = this.modalRef.el;
        if (!modal) {
            return;
        }
        const focusable = [...modal.querySelectorAll(
            "button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex='0']",
        )].filter((el) => el.offsetParent !== null);
        if (!focusable.length) {
            return;
        }
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (ev.shiftKey && (document.activeElement === first || document.activeElement === modal)) {
            ev.preventDefault();
            last.focus();
        } else if (!ev.shiftKey && document.activeElement === last) {
            ev.preventDefault();
            first.focus();
        }
    }

    /**
     * Back to where the reader came from. The dialog is a client action in
     * the main area, where ``act_window_close`` does nothing at all, so the
     * way out is the previous breadcrumb, or the document when there is none.
     */
    close() {
        const breadcrumbs = this.env.config?.breadcrumbs || [];
        if (breadcrumbs.length > 1) {
            breadcrumbs[breadcrumbs.length - 2].onSelected();
            return;
        }
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "easyocr.document",
            res_id: this.documentId,
            views: [[false, "form"]],
            target: "current",
        }, { clearBreadcrumbs: true });
    }

    overrides() {
        const pick = (section) => Object.fromEntries(
            this.sectionFields(section)
                .filter((field) => this.isEditable(section, field.key))
                .map((field) => [field.key, field.value.trim()]),
        );
        return { document: pick("document"), supplier: pick("supplier") };
    }

    lineValues() {
        return this.state.items.map((item) => ({
            code: item.code.trim(),
            description: item.description,
            item_type: item.item_type,
            quantity: item.quantity === "" ? 1 : this.parseNumber(item.quantity),
            unit_price: this.parseNumber(item.unit_price),
            discount_percent: this.parseNumber(item.discount_percent),
            tax_rate: this.parseNumber(item.tax_rate),
            re_rate: this.parseNumber(item.re_rate),
            irpf_rate: this.parseNumber(item.irpf_rate),
        }));
    }

    async createInvoice() {
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        this.state.error = "";
        try {
            const result = await this.orm.call(
                "easyocr.document", "action_create_bill", [[this.documentId]], {
                    draft: this.state.draft,
                    journal_id: Number(this.state.journalId) || false,
                    items: this.state.items.length ? this.lineValues() : null,
                    register_payment: this.state.createPayment,
                    bank_id: Number(this.state.bankId) || false,
                    payment_method_id: Number(this.state.paymentModeId) || false,
                    overrides: this.overrides(),
                    is_refund: this.state.isRefund,
                },
            );
            this.state.busy = false;
            if (result) {
                // The bill exists by now: a screen that fails to open must not
                // be reported as a bill that failed to be made.
                await this.actionService.doAction(result).catch(() => this.close());
            } else {
                this.close();
            }
        } catch (error) {
            // The server says why; the reader is told that, not a generic line.
            const reason = error?.data?.message || error?.message || "";
            this.state.error = reason
                ? _t("The invoice could not be created: %s", reason)
                : _t("The bill could not be created.");
            this.notification.add(this.state.error, { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }
}

registry.category("actions").add("easyocr.ocr_result_dialog", OCRResultDialog);
