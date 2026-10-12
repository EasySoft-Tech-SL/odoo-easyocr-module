import { Component, markup, onWillStart, proxy, signal, t, useEffect, useProps } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { formatDate, formatDateTime } from "@web/core/l10n/dates";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { formatFloat } from "@web/core/utils/numbers";
import { markdownToHtml, splitVersions } from "./easyocr_markdown";

const { DateTime } = luxon;

/**
 * The tabs of the module's configuration, the ones the module this is a port
 * of has on its setup page. The first one is Odoo's own settings screen, which
 * the bar sits on top of; the other five are pages.
 */
export function adminTabs() {
    return [
        { key: "setup", label: _t("Setup"), icon: "tune", color: "#6c5ce7" },
        { key: "plan", label: _t("Service Plan"), icon: "star", color: "#f39c12" },
        { key: "license", label: _t("License Agreement"), icon: "description", color: "#34495e" },
        { key: "telemetry", label: _t("Telemetry & Data Protection"), icon: "security", color: "#3498db" },
        { key: "about", label: _t("About"), icon: "info", color: "#3498db" },
        { key: "changelog", label: _t("ChangeLog"), icon: "format_list_bulleted", color: "#52c41a" },
    ];
}

/** One of the five pages other than the settings. */
export class EasyocrAdminPage extends Component {
    static template = "easyocr.AdminPage";
    props = useProps({
        tab: t.string(),
        onNavigate: t.function().optional(),
    });

    setup() {
        this.orm = useService("orm");
        this.state = proxy({ loading: true, page: null, error: "" });
        onWillStart(() => this.load());
    }

    get tab() {
        return this.props.tab;
    }

    async load() {
        try {
            this.state.page = await this.orm.call("easyocr.admin", "action_admin_page", [this.tab]);
        } catch (error) {
            this.state.error = error?.data?.message || error?.message || _t("Error");
        } finally {
            this.state.loading = false;
        }
    }

    get page() {
        return this.state.page || {};
    }

    get data() {
        return this.page.data || {};
    }

    goToSetup() {
        this.props.onNavigate?.("setup");
    }

    // -------------------------------------------------------------- formats
    dateTime(value) {
        if (!value) {
            return "";
        }
        const parsed = DateTime.fromISO(String(value).replace(" ", "T"), { zone: "utc" });
        return parsed.isValid ? formatDateTime(parsed.setZone("default")) : String(value);
    }

    date(value) {
        if (!value) {
            return "";
        }
        const parsed = DateTime.fromISO(String(value).replace(" ", "T"), { zone: "utc" });
        return parsed.isValid ? formatDate(parsed.setZone("default")) : String(value);
    }

    number(value) {
        return formatFloat(Number(value) || 0, { digits: [false, 0] });
    }

    price(value) {
        return `${formatFloat(Number(value) || 0, { digits: [false, 2] })} €`;
    }

    capitalize(value) {
        const text = String(value || "");
        return text.charAt(0).toUpperCase() + text.slice(1);
    }

    isSet(value) {
        return value !== undefined && value !== null;
    }

    has(value) {
        if (Array.isArray(value)) {
            return value.length > 0;
        }
        if (value && typeof value === "object") {
            return Object.keys(value).length > 0;
        }
        return Boolean(value);
    }

    /** The bar under a quota: green, then orange from 75 %, red from 100 %. */
    bar(used, limit) {
        const total = Number(limit) || 0;
        if (total <= 0) {
            return null;
        }
        const pct = Math.round((Number(used) || 0) / total * 1000) / 10;
        return {
            pct,
            width: Math.min(pct, 100),
            color: pct < 75 ? "#27ae60" : pct < 100 ? "#f39c12" : "#e74c3c",
        };
    }

    badge(status) {
        const known = {
            active: ["is-ok", _t("Active")],
            inactive: ["is-bad", _t("Inactive")],
            trial: ["is-warn", _t("Trial")],
            cancelled: ["is-bad", _t("Cancelled")],
            expired: ["is-bad", _t("Expired")],
            live: ["is-ok", _t("Production")],
            sandbox: ["is-warn", _t("Sandbox")],
        };
        const [cls, label] = known[status] || ["is-neutral", this.capitalize(status)];
        return { cls, label };
    }

    billingCycle(value) {
        const extra = { monthly: _t("monthly"), yearly: _t("yearly") }[value];
        return { text: this.capitalize(value), extra };
    }

    // ------------------------------------------------------------ the plan
    get account() { return this.data.account || {}; }
    get subscription() { return this.data.subscription || {}; }
    get plan() { return this.data.plan || {}; }
    get quota() { return this.data.quota || {}; }
    get wallet() { return this.data.wallet || {}; }
    get apiKey() { return this.data.current_api_key || {}; }
    get status() { return this.data.status || {}; }

    get canProcess() {
        return this.isSet(this.status.can_process) ? Boolean(this.status.can_process) : true;
    }

    /** The banner on top when the account cannot read, or will not soon. */
    get banner() {
        const overdue = Boolean(this.subscription.is_overdue);
        if (this.canProcess && !overdue) {
            return null;
        }
        const titles = {
            SUBSCRIPTION_OVERDUE: _t("Subscription expired without renewal"),
            WALLET_EMPTY: _t("Wallet empty"),
            QUOTA_EXCEEDED: _t("Monthly quota exhausted"),
            ACCOUNT_DISABLED: _t("Account disabled"),
        };
        let title = titles[this.status.block_code];
        if (!title) {
            title = overdue && this.canProcess ? _t("Warning: renewal pending") : _t("Processing blocked");
        }
        let body = this.status.block_message || "";
        if (!body && overdue && this.subscription.current_period_end) {
            body = _t(
                "Your subscription expired on %s and renewal has not been processed yet. Update billing or contact support.",
                this.date(this.subscription.current_period_end),
            );
        }
        return { blocked: !this.canProcess, title, body };
    }

    get pagesRemaining() {
        const q = this.quota;
        return this.isSet(q.pages_remaining) ? q.pages_remaining : (q.pages_limit || 0) - (q.pages_used || 0);
    }

    get pagesPercentage() {
        const q = this.quota;
        if (this.isSet(q.usage_percentage)) {
            return q.usage_percentage;
        }
        return q.pages_limit > 0 ? Math.round(q.pages_used / q.pages_limit * 1000) / 10 : 0;
    }

    get docsRemaining() {
        const q = this.quota;
        return this.isSet(q.documents_remaining) ? q.documents_remaining : (q.documents_limit || 0) - (q.documents_used || 0);
    }

    get limitRows() {
        const limits = this.data.limits || {};
        const rows = [
            ["max_pages_per_month", _t("Maximum pages per month"), ""],
            ["max_documents_per_month", _t("Maximum documents per month"), ""],
            ["max_pages_per_document", _t("Maximum pages per document"), ""],
            ["max_file_size_mb", _t("Maximum file size"), " MB"],
            ["max_batch_size", _t("Maximum batch size"), ""],
            ["max_api_keys", _t("Maximum API keys"), ""],
            ["rate_limit_per_minute", _t("Request limit"), " " + _t("per minute")],
            ["max_concurrent_requests", _t("Maximum concurrent requests"), ""],
            ["document_retention_days", _t("Document retention"), " " + _t("days")],
        ];
        return rows
            .filter(([key]) => this.isSet(limits[key]))
            .map(([key, label, suffix]) => ({ key, label, value: `${limits[key]}${suffix}` }));
    }

    get featureRows() {
        const features = this.data.features || {};
        const labels = {
            api_access: _t("API access"),
            streaming: _t("Real-time streaming"),
            batch_processing: _t("Batch processing"),
            custom_instructions: _t("Custom instructions"),
            webhooks: _t("Webhooks"),
            priority_queue: _t("Priority queue"),
            document_storage: _t("Document storage"),
            include_text: _t("Include extracted text"),
            auto_correct: _t("Text auto-correction"),
            vision: _t("Image analysis (Vision)"),
        };
        return Object.entries(features).map(([key, value]) => {
            const label = labels[key] || this.capitalize(key.replace(/_/g, " "));
            const yesNo = typeof value === "boolean" || value === 0 || value === 1;
            return {
                key,
                label,
                yesNo,
                yes: Boolean(value),
                numeric: !yesNo && typeof value === "number",
                value: String(value),
            };
        });
    }

    // ------------------------------------------------------- other pages
    get changelogIntroHtml() {
        const { intro } = splitVersions(this.page.changelog || "");
        return markup(markdownToHtml(intro));
    }

    /** One block per version, the newest first and open. */
    get changelogVersions() {
        const { versions } = splitVersions(this.page.changelog || "");
        return versions.map((version, index) => ({
            header: version.header,
            open: index === 0,
            html: markup(markdownToHtml(version.body)),
        }));
    }

    get readmeHtml() {
        return markup(this.page.readme_html || "");
    }
}

/** The tab bar, on the settings screen. */
export class EasyocrAdminTabs extends Component {
    static template = "easyocr.AdminTabs";
    static components = { EasyocrAdminPage };
    props = useProps({ active: t.string().optional() });

    rootRef = signal.ref();

    setup() {
        this.tabs = adminTabs();
        this.state = proxy({ tab: this.props.active || "setup" });
        // The five pages are drawn here, inside the settings screen, and not as
        // an action of their own. A screen of their own would leave the settings
        // form behind, and the left panel of the settings lives in that form:
        // it went away with it. Here the panel stays, and the scroll is the
        // screen's own, so a page longer than the window scrolls like any other.
        //
        // Odoo wraps each app of the screen in a block of its own, settings
        // fields and all; while a page of ours is showing, those fields step
        // aside, so the page is what the block shows.
        //
        // Owl 3's `useEffect` has no dependency list: it follows whatever the
        // body reads, which here is the tab and the root element. That is
        // enough, and leaving the list in would read as if it did something.
        useEffect(() => {
            const block = this.rootRef()?.closest(".app_settings_block");
            if (!block) {
                return;
            }
            block.classList.toggle("o_easyocr_admin_page_mode", this.state.tab !== "setup");
            return () => block.classList.remove("o_easyocr_admin_page_mode");
        });
    }

    get active() {
        return this.state.tab;
    }

    open(key) {
        if (key !== this.state.tab) {
            this.state.tab = key;
        }
    }
}

registry.category("view_widgets").add("easyocr_admin_tabs", { component: EasyocrAdminTabs });
