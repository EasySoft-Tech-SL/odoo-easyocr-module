import { Component, onMounted, onWillStart, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadPDFJSAssets } from "@web/core/utils/pdfjs";

/**
 * Full screen document viewer: the file on the left, the data panel on the right.
 *
 * The PDF is painted on canvas by the PDF.js copy that ships with Odoo core, one
 * canvas per page, stacked in a scrollable column. Drawing the boxes and reading
 * the text under them lives in the next step of phase 1.
 */
export class EasyocrDocumentViewer extends Component {
    static template = "easyocr.DocumentViewer";
    static props = {
        action: Object,
        actionId: { type: [Number, Boolean], optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.containerRef = useRef("pdfContainer");
        this.state = useState({
            loading: true,
            error: false,
            pages: 0,
            documentName: "",
        });
        this.pdfDocument = null;

        onWillStart(() => this.loadDocument());
        onMounted(() => this.renderPages());
    }

    get documentId() {
        return this.props.action.params?.document_id;
    }

    async loadDocument() {
        if (!this.documentId) {
            this.state.loading = false;
            this.state.error = true;
            return;
        }

        const [document] = await this.orm.read(
            "easyocr.document",
            [this.documentId],
            ["name", "attachment_id"],
        );
        this.state.documentName = document.name;

        if (!document.attachment_id) {
            this.state.loading = false;
            this.state.error = true;
            return;
        }

        await loadPDFJSAssets();
        const pdfjsLib = window.pdfjsLib;
        pdfjsLib.GlobalWorkerOptions.workerSrc = "/web/static/lib/pdfjs/build/pdf.worker.js";

        const fileUrl = `/web/content/${document.attachment_id[0]}?download=false`;
        this.pdfDocument = await pdfjsLib.getDocument(fileUrl).promise;

        this.state.pages = this.pdfDocument.numPages;
        this.state.loading = false;
    }

    async renderPages() {
        if (!this.pdfDocument || !this.containerRef.el) {
            return;
        }

        const container = this.containerRef.el;
        container.replaceChildren();

        for (let pageNumber = 1; pageNumber <= this.pdfDocument.numPages; pageNumber++) {
            const page = await this.pdfDocument.getPage(pageNumber);
            const viewport = page.getViewport({ scale: 1.5 });

            const canvas = document.createElement("canvas");
            canvas.className = "o_easyocr_page";
            canvas.dataset.pageNumber = pageNumber;
            canvas.width = viewport.width;
            canvas.height = viewport.height;

            container.appendChild(canvas);

            await page.render({
                canvasContext: canvas.getContext("2d"),
                viewport,
            }).promise;
        }
    }
}

registry.category("actions").add("easyocr.document_viewer", EasyocrDocumentViewer);
