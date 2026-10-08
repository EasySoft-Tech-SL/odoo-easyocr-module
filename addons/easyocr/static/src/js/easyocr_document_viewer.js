import { Component, onMounted, onPatched, onWillStart, useRef, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";
// Not a service: `user` is an object the web client fills from the session.
// Asking the service registry for it throws "Service user is not available"
// and takes the whole viewer down with it.
import { user } from "@web/core/user";

/**
 * The nine fields a box can be assigned to. The key is what gets stored and what
 * extraction matches on; the colour is only how it is painted.
 *
 * The labels are the same strings the model uses for its selection field, run
 * through _t so the toolbar reads in the user's language instead of English.
 */
export const BOX_FIELDS = [
    { key: "document_date", label: _t("Date"), color: "#6c3483" },
    { key: "document_number", label: _t("Invoice number"), color: "#2980b9" },
    { key: "amount_untaxed", label: _t("Untaxed total"), color: "#c0392b" },
    { key: "amount_total", label: _t("Total"), color: "#d4458b" },
    { key: "tax_amount", label: _t("Tax"), color: "#ff6b35" },
    { key: "description", label: _t("Description"), color: "#27ae60" },
    { key: "partner_vat", label: _t("Tax number"), color: "#16a085" },
    { key: "due_date", label: _t("Due date"), color: "#f39c12" },
    { key: "partner_name", label: _t("Vendor"), color: "#5d6d7e" },
];

const FIELD_BY_KEY = Object.fromEntries(BOX_FIELDS.map((field) => [field.key, field]));

/** Zoom the pages are painted at. Coordinates are divided by it before saving. */
const VIEW_SCALE = 1.5;

/** A drag shorter than this, in canvas pixels, is treated as a stray click. */
const MIN_BOX_SIZE = 10;

/**
 * Full screen document viewer: the file on the left, the data panel on the right.
 *
 * Draw a box over a part of the page, assign it to a field, and the text under
 * that box is read from the PDF text layer. The set of boxes is saved as a
 * template for the vendor, so the next invoice from them needs no drawing.
 *
 * Coordinates live in PDF points: the viewer divides by VIEW_SCALE on save and
 * multiplies on paint, so a template is independent of zoom and screen size.
 */
export class EasyocrDocumentViewer extends Component {
    static template = "easyocr.DocumentViewer";
    static props = {
        action: Object,
        actionId: { type: [Number, Boolean], optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.actionService = useService("action");
        this.containerRef = useRef("pdfContainer");
        this.fileInputRef = useRef("fileInput");

        this.state = useState({
            loading: true,
            error: false,
            // No document yet: the screen is waiting for a file. It opens this
            // way from the app's first card, and becomes the viewer in place
            // once a file is chosen -- one screen for the whole job, the way
            // the module this is a port of does it.
            empty: !this.documentId,
            dragging: false,
            documentName: "",
            partnerId: false,
            pages: [],
            boxes: [],
            activeField: null,
            templateName: "",
            saving: false,
            busy: false,
            busyLabel: "",
            // Why the account cannot read right now, in the reader's language,
            // or empty when it can.
            aiBlockMessage: "",
            // The same permission the form's button has: sending a document to
            // the service costs money, so it is not for everyone who can look
            // at one. Answered asynchronously further down -- hasGroup hands
            // back a promise, and a promise is true whatever it resolves to.
            canReadWithAI: false,
        });

        this.pdfDocument = null;
        this.baseImages = [];
        this.textCache = new Map();
        this.pendingBox = null;
        this.dragging = null;
        this.nextUid = 1;
        this.fields = BOX_FIELDS;
        // Set when a file is dropped on the screen, so the same component then
        // shows the document it just filed.
        this.openedDocumentId = null;

        onWillStart(() => this.loadPermission());
        onWillStart(() => this.loadDocument());
        onWillStart(() => this.loadAccountState());
        onMounted(() => this.paintPages());
        // The page container only exists once there is a document, so a file
        // dropped on the screen is painted after the render that opened it and
        // not before.
        onPatched(() => {
            if (this.pdfDocument && !this.painted) {
                this.paintPages();
            }
        });
    }

    /**
     * What the service says about the account, for the line above the button.
     *
     * An account out of readings, or one whose subscription lapsed, cannot read
     * anything -- and the service is the one that knows. Asking costs nothing,
     * and the answer is written by the server in the reader's language, so the
     * same sentence serves every screen.
     */
    async loadAccountState() {
        try {
            const answer = await this.orm.call("easyocr.document", "action_account_state", []);
            this.state.aiBlockMessage = answer.blocked ? answer.message : "";
        } catch {
            // No answer is not a reason to say the account is blocked.
            this.state.aiBlockMessage = "";
        }
    }

    /** Whether the reader may send documents to the service. */
    async loadPermission() {
        try {
            this.state.canReadWithAI = await user.hasGroup("easyocr.group_easyocr_manager");
        } catch {
            // A viewer that refuses to open because a permission could not be
            // asked about is worse than the same viewer without the button.
            this.state.canReadWithAI = false;
        }
    }

    get documentId() {
        // Opening the action from a button carries the id in params; reloading the
        // page rebuilds the action from the URL, where only the context survives.
        return this.openedDocumentId
            || this.props.action.params?.document_id
            || this.props.action.context?.active_id;
    }

    // ------------------------------------------------------------------
    // Waiting for a file
    // ------------------------------------------------------------------
    async onFileChosen(event) {
        const file = event.target.files && event.target.files[0];
        if (file) {
            await this.openFile(file);
        }
    }

    onDragOver(event) {
        event.preventDefault();
        this.state.dragging = true;
    }

    onDragLeave() {
        this.state.dragging = false;
    }

    async onDrop(event) {
        event.preventDefault();
        this.state.dragging = false;
        const file = event.dataTransfer?.files && event.dataTransfer.files[0];
        if (file) {
            await this.openFile(file);
        }
    }

    /**
     * Hand a chosen file to the server and show what comes back.
     *
     * The document and its attachment are made server-side: the rules about
     * what can be read and what the document is called live there, where they
     * are tested, and not in a second copy written in JavaScript.
     */
    async openFile(file) {
        // A second file dropped on top of the first while it is being filed
        // would make two documents out of one gesture.
        if (this.filing) {
            return;
        }
        this.filing = true;
        this.state.loading = true;
        let filed = false;
        try {
            const data = await this.readAsBase64(file);
            this.openedDocumentId = await this.orm.call(
                "easyocr.document", "action_file_upload", [file.name, data],
            );
            filed = true;
            this.state.error = false;
            // Swapped to the viewer first, so the container is there when the
            // pages arrive; onPatched does the painting.
            this.painted = false;
            this.state.empty = false;
            await this.loadDocument();
        } catch (error) {
            this.state.loading = false;
            if (filed) {
                // The document was filed and it is what cannot be shown. Saying
                // so beats a grey rectangle with nothing in it: that is a
                // failure nobody can tell from a slow load.
                this.state.error = true;
            } else {
                // Back to waiting for a file: the file never became a document.
                this.state.empty = true;
            }
            this.notification.add(this.failureMessage(error), { type: "danger" });
        } finally {
            this.filing = false;
        }
    }

    /** What to tell the reader when filing a file did not work. */
    failureMessage(error) {
        // A refusal the module wrote itself -- a file that cannot be read --
        // arrives as the message of the exception, which is the sentence to
        // show. Anything else is a technical string, and the reader gets the
        // sentence written for them instead.
        const refused = error?.data?.name === "odoo.exceptions.UserError";
        if (refused && error.data.message) {
            return error.data.message;
        }
        return _t("That file could not be opened.");
    }

    readAsBase64(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => {
                // The data URL carries the base64 after the comma.
                resolve(String(reader.result).split(",", 2)[1] || "");
            };
            reader.onerror = () => reject(new Error(_t("That file could not be read.")));
            reader.readAsDataURL(file);
        });
    }

    // ------------------------------------------------------------------
    // Loading and painting
    // ------------------------------------------------------------------
    async loadDocument() {
        if (!this.documentId) {
            // Nothing to show yet: the screen is the one that waits for a file.
            this.state.loading = false;
            this.state.empty = true;
            return;
        }

        const [document] = await this.orm.read(
            "easyocr.document",
            [this.documentId],
            ["name", "partner_id", "attachment_id"],
        );
        this.state.documentName = document.name;
        this.state.partnerId = document.partner_id ? document.partner_id[0] : false;

        if (!document.attachment_id) {
            this.state.loading = false;
            this.state.error = true;
            return;
        }

        // Odoo ships PDF.js in core on both series, but 18.0 has no
        // @web/core/utils/pdfjs wrapper, so the two files are loaded by hand.
        await loadJS("/web/static/lib/pdfjs/build/pdf.js");
        await loadJS("/web/static/lib/pdfjs/build/pdf.worker.js");
        const pdfjsLib = window.pdfjsLib;
        pdfjsLib.GlobalWorkerOptions.workerSrc = "/web/static/lib/pdfjs/build/pdf.worker.js";

        const fileUrl = `/web/content/${document.attachment_id[0]}?download=false`;
        this.pdfDocument = await pdfjsLib.getDocument(fileUrl).promise;

        const pages = [];
        for (let number = 1; number <= this.pdfDocument.numPages; number++) {
            // The scale-1 viewport is the page in PDF points, whatever zoom we paint at.
            const page = await this.pdfDocument.getPage(number);
            const points = page.getViewport({ scale: 1 });
            pages.push({ number, width: points.width, height: points.height });
        }
        this.state.pages = pages;

        this.state.loading = false;
    }

    /** Paint every page once, and keep the rendered image to repaint boxes over. */
    async paintPages() {
        if (!this.pdfDocument || !this.containerRef.el) {
            return;
        }
        const container = this.containerRef.el;
        container.replaceChildren();
        this.baseImages = [];
        this.painted = true;

        for (const pageInfo of this.state.pages) {
            const wrapper = document.createElement("div");
            wrapper.className = "o_easyocr_page_wrapper";

            const canvas = document.createElement("canvas");
            canvas.className = "o_easyocr_page";
            const page = await this.pdfDocument.getPage(pageInfo.number);
            const viewport = page.getViewport({ scale: VIEW_SCALE });
            canvas.width = viewport.width;
            canvas.height = viewport.height;

            const overlay = document.createElement("div");
            overlay.className = "o_easyocr_overlay";
            overlay.dataset.page = pageInfo.number;
            this.bindOverlay(overlay, pageInfo.number);

            wrapper.append(canvas, overlay);
            container.appendChild(wrapper);

            await page.render({ canvasContext: canvas.getContext("2d"), viewport }).promise;
            this.baseImages[pageInfo.number] = canvas.toDataURL();
        }
    }

    /** Repaint one page: the rendered image, then its boxes on top. */
    redrawPage(pageNumber) {
        const wrapper = this.containerRef.el?.querySelector(
            `.o_easyocr_page_wrapper:nth-child(${pageNumber})`,
        );
        if (!wrapper) {
            return;
        }
        const canvas = wrapper.querySelector("canvas");
        const context = canvas.getContext("2d");

        const base = this.baseImages[pageNumber];
        if (!base) {
            return;
        }
        const image = new Image();
        image.onload = () => {
            context.clearRect(0, 0, canvas.width, canvas.height);
            context.drawImage(image, 0, 0);
            for (const box of this.boxesOfPage(pageNumber)) {
                this.paintBox(context, box);
            }
            if (this.pendingBox && this.pendingBox.page === pageNumber) {
                this.paintBox(context, this.pendingBox, true);
            }
        };
        image.src = base;
    }

    paintBox(context, box, isDraft = false) {
        const field = FIELD_BY_KEY[box.field_key] || { color: "#000", label: box.field_key };
        const x = box.x * VIEW_SCALE;
        const y = box.y * VIEW_SCALE;
        const width = box.width * VIEW_SCALE;
        const height = box.height * VIEW_SCALE;

        context.save();
        context.globalAlpha = isDraft ? 0.15 : 0.25;
        context.fillStyle = field.color;
        context.fillRect(x, y, width, height);
        context.globalAlpha = 1;
        context.strokeStyle = field.color;
        context.lineWidth = 2;
        context.strokeRect(x, y, width, height);

        if (!isDraft) {
            const label = field.label;
            context.font = "12px sans-serif";
            const labelWidth = context.measureText(label).width + 8;
            context.fillStyle = field.color;
            context.fillRect(x, Math.max(0, y - 18), labelWidth, 18);
            context.fillStyle = "#fff";
            context.fillText(label, x + 4, Math.max(12, y - 5));
        }
        context.restore();
    }

    boxesOfPage(pageNumber) {
        return this.state.boxes.filter((box) => box.page === pageNumber);
    }

    labelFor(key) {
        return FIELD_BY_KEY[key]?.label || key;
    }

    /** How long the document is, in one sentence of its own. */
    pagesLabel() {
        return _t("%s page(s)", this.state.pages.length);
    }

    removeLabel(key) {
        return _t("Remove %s", this.labelFor(key));
    }

    // ------------------------------------------------------------------
    // Drawing
    // ------------------------------------------------------------------
    setActiveField(key) {
        this.state.activeField = this.state.activeField === key ? null : key;
    }

    bindOverlay(overlay, pageNumber) {
        overlay.addEventListener("mousedown", (event) => {
            if (!this.state.activeField) {
                return;
            }
            this.dragging = {
                page: pageNumber,
                origin: this.eventToPoints(event, pageNumber),
            };
            this.pendingBox = null;
            event.preventDefault();
        });

        overlay.addEventListener("mousemove", (event) => {
            if (!this.dragging || this.dragging.page !== pageNumber) {
                return;
            }
            const current = this.eventToPoints(event, pageNumber);
            this.pendingBox = {
                field_key: this.state.activeField,
                page: pageNumber,
                x: Math.min(this.dragging.origin.x, current.x),
                y: Math.min(this.dragging.origin.y, current.y),
                width: Math.abs(current.x - this.dragging.origin.x),
                height: Math.abs(current.y - this.dragging.origin.y),
            };
            this.redrawPage(pageNumber);
        });

        const finish = async (event) => {
            if (!this.dragging || this.dragging.page !== pageNumber) {
                return;
            }
            this.dragging = null;
            const box = this.pendingBox;
            this.pendingBox = null;

            if (!box || box.width < MIN_BOX_SIZE / VIEW_SCALE || box.height < MIN_BOX_SIZE / VIEW_SCALE) {
                this.redrawPage(pageNumber);
                return;
            }

            box.uid = this.nextUid++;
            box.text = await this.readText(box);
            this.state.boxes.push(box);
            this.redrawPage(pageNumber);
        };

        overlay.addEventListener("mouseup", finish);
        overlay.addEventListener("mouseleave", finish);
    }

    /** Screen coordinates to PDF points for a page. */
    eventToPoints(event, pageNumber) {
        const wrapper = event.currentTarget.closest(".o_easyocr_page_wrapper");
        const canvas = wrapper.querySelector("canvas");
        const rect = canvas.getBoundingClientRect();
        // The canvas may be shown smaller than its pixel size.
        const ratio = canvas.width / rect.width;
        return {
            page: pageNumber,
            x: ((event.clientX - rect.left) * ratio) / VIEW_SCALE,
            y: ((event.clientY - rect.top) * ratio) / VIEW_SCALE,
        };
    }

    // ------------------------------------------------------------------
    // Reading the text under a box
    // ------------------------------------------------------------------
    async textItems(pageNumber) {
        if (!this.textCache.has(pageNumber)) {
            const page = await this.pdfDocument.getPage(pageNumber);
            const content = await page.getTextContent();
            const viewport = page.getViewport({ scale: 1 });
            const items = [];
            for (const item of content.items) {
                const text = (item.str || "").trim();
                if (!text) {
                    continue;
                }
                // PDF user space puts the origin bottom left; the box uses top left.
                const left = item.transform[4];
                const baseline = item.transform[5];
                const width = (item.width || 0) || 0;
                items.push({
                    text,
                    left,
                    right: left + width,
                    top: viewport.height - baseline - Math.abs(item.transform[0]),
                    bottom: viewport.height - baseline,
                    charWidth: width / Math.max(text.length, 1),
                });
            }
            this.textCache.set(pageNumber, items);
        }
        return this.textCache.get(pageNumber);
    }

    /** The text whose characters fall inside the box, read in reading order. */
    async readText(box) {
        const items = await this.textItems(box.page);
        const left = Math.min(box.x, box.x + box.width);
        const right = Math.max(box.x, box.x + box.width);
        const top = Math.min(box.y, box.y + box.height);
        const bottom = Math.max(box.y, box.y + box.height);

        const hits = [];
        for (const item of items) {
            const overlapX = Math.min(right, item.right) - Math.max(left, item.left);
            const overlapY = Math.min(bottom, item.bottom) - Math.max(top, item.top);
            if (overlapX <= 0 || overlapY <= 0) {
                continue;
            }
            // Cut at character level so a box can take part of a line.
            let piece = "";
            for (let index = 0; index < item.text.length; index++) {
                const charLeft = item.left + index * item.charWidth;
                const charRight = charLeft + item.charWidth;
                if (charRight > left && charLeft < right) {
                    piece += item.text[index];
                }
            }
            piece = piece.trim();
            if (piece) {
                hits.push({ text: piece, top: item.top, left: item.left });
            }
        }

        hits.sort((a, b) => (Math.abs(a.top - b.top) > 5 ? a.top - b.top : a.left - b.left));
        return hits.map((hit) => hit.text).join(" ");
    }

    async refreshAllTexts() {
        for (const box of this.state.boxes) {
            box.text = await this.readText(box);
        }
    }

    // ------------------------------------------------------------------
    // What the document becomes
    // ------------------------------------------------------------------
    /** Send the file to the service and fill the document with what it reads. */
    async readWithAI() {
        await this.runDocumentAction(
            "action_extract",
            _t("Reading the document. A scanned page takes a while."),
        );
    }

    /** Turn what was read into a draft supplier bill, and open it. */
    async createBill() {
        await this.runDocumentAction("action_create_bill", _t("Preparing the bill."));
    }

    /**
     * Call a button of the document from here and show whatever it answers.
     *
     * Both methods return an action rather than raising: a notification when
     * something went wrong, the bill itself when it went right. Calling them
     * from a component means nothing runs that action for us, so it is run by
     * hand -- otherwise the call would look like it did nothing at all, which
     * is the worst way for a button to fail.
     *
     * The reading can take minutes on a long scan, so the toolbar says what it
     * is waiting for and stops taking clicks meanwhile.
     */
    async runDocumentAction(method, label) {
        if (this.state.busy || !this.documentId) {
            return;
        }
        this.state.busy = true;
        this.state.busyLabel = label;
        try {
            const result = await this.orm.call("easyocr.document", method, [[this.documentId]]);
            if (result) {
                await this.actionService.doAction(result);
            }
        } finally {
            this.state.busy = false;
            this.state.busyLabel = "";
        }
    }

    // ------------------------------------------------------------------
    // Template handling
    // ------------------------------------------------------------------
    clearBoxes() {
        this.state.boxes = [];
        for (const pageInfo of this.state.pages) {
            this.redrawPage(pageInfo.number);
        }
    }

    removeBox(uid) {
        const box = this.state.boxes.find((item) => item.uid === uid);
        this.state.boxes = this.state.boxes.filter((item) => item.uid !== uid);
        if (box) {
            this.redrawPage(box.page);
        }
    }

    async saveTemplate() {
        if (!this.state.boxes.length) {
            this.notification.add(_t("Draw at least one box before saving a template."), {
                type: "warning",
            });
            return;
        }
        if (!this.state.templateName.trim()) {
            this.notification.add(_t("Give the template a name."), { type: "warning" });
            return;
        }

        this.state.saving = true;
        try {
            await this.refreshAllTexts();
            await this.orm.create("easyocr.template", [{
                name: this.state.templateName,
                partner_id: this.state.partnerId || false,
                box_ids: this.state.boxes.map((box) => [0, 0, {
                    page: box.page,
                    field_key: box.field_key,
                    x: box.x,
                    y: box.y,
                    width: box.width,
                    height: box.height,
                    text: box.text || "",
                }]),
            }]);
            this.notification.add(_t("Template saved."), { type: "success" });
            this.state.templateName = "";
        } finally {
            this.state.saving = false;
        }
    }
}

registry.category("actions").add("easyocr.document_viewer", EasyocrDocumentViewer);
