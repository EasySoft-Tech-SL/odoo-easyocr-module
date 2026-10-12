import { Component, onWillUnmount, useRef, useState } from "@odoo/owl";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * How often a running batch is asked about while its screen is open.
 *
 * The service reads the files one after another and says nothing in between, so
 * the screen polls. It is a courtesy: the same question is asked by a cron when
 * nobody is looking, and the webhook answers first when the account has one.
 */
const POLL_EVERY_MS = 8000;

/**
 * Send a stack of documents at once and follow what comes back.
 *
 * Nothing is sent until Send is pressed: choosing the files only files them, so
 * the reader can see the stack -- and be told which of them has already been
 * read -- before anything is paid for. A batch is where the readings are paid
 * for together, so the decision is made once, here.
 */
export class EasyocrBatch extends Component {
    static template = "easyocr.Batch";
    static props = {
        action: { type: Object, optional: true },
        actionId: { type: [Number, Boolean], optional: true },
        // Odoo hands every client action more than these (updateActionState,
        // className...), and in debug mode a component that does not accept
        // them refuses to open.
        "*": true,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.actionService = useService("action");
        this.dialog = useService("dialog");
        this.fileInputRef = useRef("fileInput");

        this.state = useState({
            files: [],
            name: "",
            customInstructions: "",
            includeText: false,
            autoCorrect: false,
            dragging: false,
            busy: false,
            busyLabel: "",
            // Why the account cannot read a batch right now, or empty.
            blockMessage: "",
            // The batch the stack was filed as, and whether it is on its way.
            // The picker stays until it is, so a question that has not been
            // answered does not look like a batch that has already started.
            batchId: false,
            sent: false,
            summary: "",
            progress: 0,
            total: 0,
            read: 0,
            failed: 0,
            done: false,
            errorMessage: "",
        });

        this.nextUid = 1;
        this.pollTimer = null;
        onWillUnmount(() => this.stopPolling());
    }

    // ------------------------------------------------------------------
    // Choosing the files
    // ------------------------------------------------------------------
    onFilesChosen(event) {
        this.addFiles(event.target.files);
        // So that choosing the same file again after removing it still fires.
        event.target.value = "";
    }

    onDragOver(event) {
        event.preventDefault();
        this.state.dragging = true;
    }

    onDragLeave() {
        this.state.dragging = false;
    }

    onDrop(event) {
        event.preventDefault();
        this.state.dragging = false;
        this.addFiles(event.dataTransfer?.files);
    }

    /**
     * Keep the chosen files in the page until Send is pressed.
     *
     * They are held in memory and not filed yet: filing them makes documents,
     * and the reader is still deciding. Two files with the same name are both
     * kept, because two different invoices can share one -- which is exactly
     * what the duplicate guard is for.
     */
    addFiles(fileList) {
        if (!fileList) {
            return;
        }
        for (const file of fileList) {
            this.state.files.push({
                uid: this.nextUid++,
                name: file.name,
                size: file.size,
                file,
            });
        }
        if (!this.state.name) {
            this.state.name = _t("Batch of %s", new Date().toLocaleDateString());
        }
    }

    removeFile(uid) {
        this.state.files = this.state.files.filter((entry) => entry.uid !== uid);
    }

    clearFiles() {
        this.state.files = [];
    }

    /** How many files and what they weigh, in one sentence of its own. */
    filesLabel() {
        const total = this.state.files.reduce((sum, entry) => sum + entry.size, 0);
        return _t("%(count)s file(s), %(size)s", {
            count: this.state.files.length,
            size: this.sizeLabel(total),
        });
    }

    removeLabel(name) {
        return _t("Remove %s", name);
    }

    countsLabel() {
        return _t("%(read)s of %(total)s read, %(failed)s failed", {
            read: this.state.read,
            total: this.state.total,
            failed: this.state.failed,
        });
    }

    sizeLabel(bytes) {
        if (bytes >= 1024 * 1024) {
            return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
        }
        return `${Math.max(1, Math.round(bytes / 1024))} KB`;
    }

    // ------------------------------------------------------------------
    // Sending
    // ------------------------------------------------------------------
    async send() {
        if (this.state.busy || !this.state.files.length) {
            return;
        }
        this.state.busy = true;
        this.state.blockMessage = "";
        try {
            // A second press over a stack that is already filed does not file it
            // again: the batch that was made for it is still there, waiting for
            // the send to be decided. Otherwise every refusal would leave another
            // batch behind with the same files in it.
            let batchId = this.state.batchId;
            if (!batchId) {
                const payload = [];
                for (const entry of this.state.files) {
                    payload.push({ filename: entry.name, datas: await this.readAsBase64(entry.file) });
                }

                // `create` answers with the ids it made, not with one id. Taking
                // it for an id builds a recordset out of a list and every call
                // after it dies on the way in, before anything of this screen is
                // looked at.
                const created = await this.orm.create("easyocr.batch", [{
                    name: this.state.name || _t("New"),
                    include_extracted_text: this.state.includeText,
                    auto_correct: this.state.autoCorrect,
                    custom_instructions: this.state.customInstructions,
                }]);
                batchId = Array.isArray(created) ? created[0] : created;
                this.state.batchId = batchId;

                const added = await this.orm.call("easyocr.batch", "action_add_files", [
                    [batchId], payload,
                ]);
                if (added.refused.length) {
                    this.notification.add(
                        added.refused.map((e) => `${e.filename}: ${e.reason}`).join("\n"),
                        { type: "warning" },
                    );
                }
                if (!added.documents) {
                    // Nothing of the stack could be filed, so there is nothing
                    // to send and no batch worth keeping.
                    await this.orm.unlink("easyocr.batch", [batchId]);
                    this.state.batchId = false;
                    return;
                }
                this.state.name = (await this.orm.read(
                    "easyocr.batch", [batchId], ["name"],
                ))[0].name;
            }

            await this.dispatchSend(batchId, "ask");
        } catch (error) {
            this.notification.add(this.failureMessage(error), { type: "danger" });
            // Back to the stack, which never left the page, with the batch that
            // was started for it. Pressing again picks that same one up.
        } finally {
            this.state.busy = false;
            this.state.busyLabel = "";
        }
    }

    /**
     * Send, and ask before paying twice for a file that has already been read.
     *
     * The server answers with the duplicates instead of sending when it finds
     * any, so the question is asked with the real list in front of the reader
     * and the files still in the page. The two answers are the two things the
     * buttons say: send the stack anyway, or leave those files out and send the
     * rest. Neither is chosen for the reader, because either one spends money.
     *
     * ``mode`` is ``ask`` the first time, and the answer after that.
     */
    async dispatchSend(batchId, mode) {
        const answer = await this.orm.call("easyocr.batch", "action_send", [[batchId]], {
            force: mode === "force",
            leave_out_duplicates: mode === "skip",
        });

        if (answer.duplicates && answer.duplicates.length) {
            const sendAnyway = await this.askAboutDuplicates(answer.duplicates);
            return this.dispatchSend(batchId, sendAnyway ? "force" : "skip");
        }

        if (answer.skipped && answer.skipped.length) {
            this.notification.add(
                _t("%s file(s) were left out: they had already been read.", answer.skipped.length),
                { type: "warning" },
            );
        }

        if (!answer.sent) {
            // Refused, which is not the same as failed: nothing was sent and
            // nothing was paid for, so the batch made for this stack goes, the
            // files stay in the page, and the reason is shown where the button
            // that hit it is.
            this.state.blockMessage = answer.message;
            await this.orm.unlink("easyocr.batch", [batchId]).catch(() => {});
            this.state.batchId = false;
            return;
        }

        this.state.sent = true;
        this.state.summary = _t("The service is reading them.");
        await this.refresh();
        this.schedulePolling();
    }

    askAboutDuplicates(duplicates) {
        return new Promise((resolve) => {
            this.dialog.add(ConfirmationDialog, {
                title: _t("Some of these files have already been read"),
                body: [
                    duplicates.map((entry) => `${entry.filename}: ${entry.reason}`).join("\n"),
                    _t("Reading them again costs the same and will not change anything."),
                ].join("\n\n"),
                confirmLabel: _t("Send them anyway"),
                cancelLabel: _t("Leave them out"),
                confirm: () => resolve(true),
                cancel: () => resolve(false),
            });
        });
    }

    readAsBase64(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(String(reader.result).split(",", 2)[1] || "");
            reader.onerror = () => reject(new Error(_t("That file could not be read.")));
            reader.readAsDataURL(file);
        });
    }

    failureMessage(error) {
        const refused = error?.data?.name === "odoo.exceptions.UserError";
        if (refused && error.data.message) {
            return error.data.message;
        }
        return _t("The batch could not be sent.");
    }

    // ------------------------------------------------------------------
    // Following it
    // ------------------------------------------------------------------
    async refresh() {
        if (!this.state.batchId) {
            return;
        }
        try {
            await this.orm.call("easyocr.batch", "action_refresh", [[this.state.batchId]]);
        } catch {
            // A batch that cannot be asked about keeps the last thing it said.
        }
        const [batch] = await this.orm.read("easyocr.batch", [this.state.batchId], [
            "state", "progress", "document_count", "completed_count", "failed_count",
            "error_message",
        ]);
        this.state.progress = batch.progress;
        this.state.total = batch.document_count;
        this.state.read = batch.completed_count;
        this.state.failed = batch.failed_count;
        this.state.errorMessage = batch.error_message || "";
        this.state.done = ["completed", "partial", "failed", "cancelled"].includes(batch.state);

        if (this.state.done) {
            this.state.summary = this.doneSummary(batch);
        }
    }

    /**
     * What to say when it is over, worked out from the counts and not from the
     * state the service reported.
     *
     * The state is the service's word and the counts are ours, and they can
     * disagree -- the screen said "all of them were read" right above "1
     * failed", which is the one thing a summary must never do. The counts are
     * painted next to the sentence, so the sentence is read off them.
     */
    doneSummary(batch) {
        if (batch.state === "cancelled") {
            return _t("The batch was cancelled.");
        }
        if (batch.failed_count && batch.completed_count) {
            return _t("Some files could not be read. The rest are ready to review.");
        }
        if (batch.failed_count) {
            return _t("None of these files could be read.");
        }
        return _t("All of them were read. Review them before they become bills.");
    }

    schedulePolling() {
        this.stopPolling();
        this.pollTimer = setTimeout(async () => {
            await this.refresh();
            if (!this.state.done) {
                this.schedulePolling();
            }
        }, POLL_EVERY_MS);
    }

    stopPolling() {
        if (this.pollTimer) {
            clearTimeout(this.pollTimer);
            this.pollTimer = null;
        }
    }

    async cancelBatch() {
        this.stopPolling();
        try {
            await this.orm.call("easyocr.batch", "action_cancel", [[this.state.batchId]]);
        } finally {
            await this.refresh();
        }
    }

    /**
     * Open the documents this batch filed.
     *
     * The action is asked of the server and not built here: the same one the
     * batch's own form opens, so the two cannot drift apart, and the shape a
     * client action has to have stays in the place that is tested.
     */
    async openDocuments() {
        const action = await this.orm.call(
            "easyocr.batch", "action_open_documents", [[this.state.batchId]],
        );
        await this.actionService.doAction(action);
    }

    startAnother() {
        this.stopPolling();
        Object.assign(this.state, {
            files: [], name: "", customInstructions: "", includeText: false,
            autoCorrect: false, batchId: false, sent: false, summary: "",
            progress: 0, total: 0, read: 0, failed: 0, done: false,
            errorMessage: "", blockMessage: "",
        });
    }
}

registry.category("actions").add("easyocr.batch", EasyocrBatch);
