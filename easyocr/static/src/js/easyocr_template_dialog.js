import { Component, proxy, t, useProps } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

/**
 * The "save template" dialog: the name, the vendor and the extra instructions.
 *
 * Odoo has no prompt for a single line of text, so the name lives here instead
 * of in the viewer's column, the way the module this is a port of does it.
 * ``dialog.add`` hands back the function that closes the dialog, not what was
 * typed into it, so what was typed travels back through ``onSave``.
 */
export class TemplateDialog extends Component {
    static template = "easyocr.TemplateDialog";
    static components = { Dialog };
    // Owl 3 ignores a static ``props`` and wants the schema through ``useProps``
    // instead. What it checks is what is declared here and nothing else, so the
    // props this dialog does not name travel through as they are.
    props = useProps({
        title: t.string().optional(),
        name: t.string().optional(),
        suppliers: t.array().optional(),
        aiEnabled: t.boolean().optional(),
        onSave: t.function(),
        close: t.function(),
    });

    setup() {
        this.state = proxy({
            name: this.props.name || "",
            supplierId: "",
            instructions: "",
        });
    }

    /** What the dialog hands back when it is confirmed. */
    getPayload() {
        return {
            name: this.state.name,
            supplierId: Number(this.state.supplierId) || false,
            instructions: this.state.instructions,
        };
    }

    save() {
        this.props.onSave(this.getPayload());
        this.props.close();
    }

    onNameKeydown(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            this.save();
        }
    }
}
