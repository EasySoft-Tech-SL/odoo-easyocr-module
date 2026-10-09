import { Component, useState } from "@odoo/owl";

/**
 * The "save template" dialog: the name, the vendor and the extra instructions.
 *
 * Odoo has no prompt for a single line of text, so the name lives here instead
 * of in the viewer's column, the way the module this is a port of does it. The
 * component is dumb: it holds the values, and the viewer that opened it reads
 * them back from ``state`` when the dialog is confirmed.
 */
export class TemplateDialog extends Component {
    static template = "easyocr.TemplateDialog";
    static props = {
        name: { type: String, optional: true },
        suppliers: { type: Array, optional: true },
        aiEnabled: { type: Boolean, optional: true },
        close: Function,
    };

    setup() {
        this.state = useState({
            name: this.props.name || "",
            supplierId: null,
            instructions: "",
        });
    }

    /** What the dialog hands back when it is confirmed. */
    getPayload() {
        return this.state;
    }
}
