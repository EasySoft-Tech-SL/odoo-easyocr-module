/**
 * The phone page of EasyOCR: photograph a receipt and send it.
 *
 * Plain JavaScript and no Odoo module on purpose. The page is opened on a
 * phone, often on a bad connection, so it loads only its own file: the camera,
 * the resize and the upload are the whole of it, and none of it needs the web
 * client. It still lives under static/src, so Odoo bundles it with the rest of
 * the module; nothing imports it, so it does nothing on a backend page.
 *
 * Everything the page needs is read off its own markup: the store never guesses
 * an id, and there is exactly one place — the QWeb template — that names them.
 */

/** The longest side a photo keeps. A receipt is legible well below this, and
 * the phone camera's 12 megapixels are a slow upload for nothing. */
const MAX_SIDE = 1600;

/** JPEG quality. 0.8 is the knee of the curve: half the bytes of 0.95 for a
 * photograph nobody can tell apart on a screen. */
const JPEG_QUALITY = 0.8;

/** How long to wait for the answer before telling the employee to try again.
 * The extraction service is allowed two minutes on its own. */
const SEND_TIMEOUT = 180000;

const root = document.getElementById('easyocr_capture_root');

if (root) {
    start(root);
}

/**
 * @param {HTMLElement} root the page container, with the URLs and the settings
 *      the server put on it as data attributes.
 */
function start(root) {
    const byId = (id) => root.querySelector(`#${id}`);

    const uploadUrl = root.dataset.uploadUrl;
    // The ceiling the server applies, taken from the page so the two can never
    // disagree. Over it, the photo never leaves the phone: there is no point in
    // spending a slow upload on an answer that is already no.
    const maxSizeMb = Number(root.dataset.maxSizeMb) || 0;
    const maxSizeBytes = maxSizeMb * 1024 * 1024;
    const form = byId('easyocr_capture_form');
    const input = byId('easyocr_capture_input');
    const video = byId('easyocr_capture_video');
    const camera = byId('easyocr_capture_camera');
    const preview = byId('easyocr_capture_preview');
    const thumb = byId('easyocr_capture_thumb');
    const status = byId('easyocr_capture_status');
    const result = byId('easyocr_capture_result');
    const resultTitle = byId('easyocr_capture_result_title');
    const fields = byId('easyocr_capture_fields');
    const failure = byId('easyocr_capture_error');

    /** The stream of the live camera, while it is open. */
    let stream = null;
    /** The resized photo, waiting to be sent. */
    let photo = null;

    const toggle = (node, visible) => node.toggleAttribute('hidden', !visible);
    const say = (message) => {
        status.textContent = message;
        toggle(status, Boolean(message));
    };
    const complain = (message) => {
        failure.textContent = message;
        toggle(failure, Boolean(message));
    };

    registerServiceWorker(root.dataset.serviceWorkerUrl);

    // ------------------------------------------------------------------
    // Getting a photo
    // ------------------------------------------------------------------
    byId('easyocr_capture_shoot').addEventListener('click', () => {
        if (canUseLiveCamera()) {
            openCamera();
        } else {
            input.click();
        }
    });

    byId('easyocr_capture_pick').addEventListener('click', () => input.click());
    byId('easyocr_capture_retry').addEventListener('click', reset);
    byId('easyocr_capture_snap').addEventListener('click', takeFrame);
    byId('easyocr_capture_cancel').addEventListener('click', () => {
        closeCamera();
        reset();
    });
    byId('easyocr_capture_send').addEventListener('click', send);
    byId('easyocr_capture_again').addEventListener('click', reset);

    input.addEventListener('change', async () => {
        const file = input.files && input.files[0];
        if (file) {
            await showPhoto(await shrink(file));
        }
    });

    async function openCamera() {
        try {
            stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: 'environment' },
                audio: false,
            });
        } catch (reason) {
            // Refused, busy, or no camera at all: the file input is the one way
            // every phone understands, and it opens the camera itself.
            input.click();
            return;
        }
        video.srcObject = stream;
        toggle(camera, true);
        complain('');
    }

    function closeCamera() {
        if (stream) {
            for (const track of stream.getTracks()) {
                track.stop();
            }
            stream = null;
        }
        video.srcObject = null;
        toggle(camera, false);
    }

    /** The frame the camera is showing right now, at the size we keep. */
    function takeFrame() {
        const width = video.videoWidth;
        const height = video.videoHeight;
        if (!width || !height) {
            complain('The camera is not ready yet. Give it a second.');
            return;
        }
        const canvas = drawInto(width, height, video);
        closeCamera();
        canvasToBlob(canvas).then(showPhoto);
    }

    /** Read the file the phone handed over, shrunk to what we upload. */
    async function shrink(file) {
        let image;
        try {
            image = await decode(file);
        } catch (reason) {
            complain('That file could not be read as a photo.');
            return null;
        }
        return canvasToBlob(drawInto(image.naturalWidth, image.naturalHeight, image));
    }

    /** Draw something into a canvas, scaled down to MAX_SIDE. */
    function drawInto(width, height, source) {
        const scale = Math.min(1, MAX_SIDE / Math.max(width, height));
        const canvas = document.createElement('canvas');
        canvas.width = Math.max(1, Math.round(width * scale));
        canvas.height = Math.max(1, Math.round(height * scale));
        canvas.getContext('2d').drawImage(source, 0, 0, canvas.width, canvas.height);
        return canvas;
    }

    function showPhoto(blob) {
        if (!blob) {
            complain('The photo could not be prepared. Try again.');
            return;
        }
        if (maxSizeBytes && blob.size > maxSizeBytes) {
            complain(`The photo is still larger than the ${maxSizeMb} MB the inbox takes. `
                + 'Take it from a little further away.');
            return;
        }
        photo = blob;
        thumb.src = URL.createObjectURL(blob);
        complain('');
        say('');
        toggle(preview, true);
        toggle(result, false);
    }

    // ------------------------------------------------------------------
    // Sending it
    // ------------------------------------------------------------------
    async function send() {
        if (!photo) {
            return;
        }
        setBusy(true);
        complain('');
        say('Sending the photo…');

        const body = new FormData(form);
        body.set('image', photo, photoName());

        let response;
        try {
            response = await withTimeout(
                fetch(uploadUrl, { method: 'POST', body, credentials: 'same-origin' }),
                SEND_TIMEOUT,
            );
        } catch (reason) {
            setBusy(false);
            say('');
            complain('The photo could not be sent. Check the connection and try again.');
            return;
        }

        let answer = {};
        try {
            answer = await response.json();
        } catch (reason) {
            answer = {};
        }
        setBusy(false);
        say('');

        if (!answer.ok) {
            // The server always explains itself in words: show them as they are.
            complain(answer.message || 'The photo could not be sent.');
            return;
        }
        render(answer);
    }

    /** What came back: what was read, or why nothing was. */
    function render(answer) {
        const document_ = answer.document || {};
        const read = Boolean(answer.read);

        resultTitle.textContent = read ? 'Read from the receipt' : 'Saved to the inbox';
        fields.replaceChildren();

        if (read) {
            const rows = [
                ['Vendor', document_.vendor],
                ['Date', document_.date],
                ['Total', formatTotal(document_)],
                ['Number', document_.reference],
            ];
            for (const [label, value] of rows) {
                if (value) {
                    fields.append(row(label, value));
                }
            }
        } else {
            fields.append(row('', answer.message));
        }

        toggle(preview, false);
        toggle(result, true);
    }

    // ------------------------------------------------------------------
    // Small things
    // ------------------------------------------------------------------
    function reset() {
        photo = null;
        input.value = '';
        thumb.removeAttribute('src');
        toggle(preview, false);
        toggle(result, false);
        complain('');
        say('');
    }

    function setBusy(busy) {
        for (const button of root.querySelectorAll('button')) {
            button.toggleAttribute('disabled', busy);
        }
        if (busy) {
            toggle(result, false);
        }
    }

    // The camera must not stay on while the employee is doing something else:
    // it is the phone's battery and its privacy both.
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            closeCamera();
        }
    });
}

/** Whether the browser can give us a live camera at all.
 *
 * Without a secure origin — an http:// address on the local network, which is
 * how the page gets tried out — there is no getUserMedia, and the file input is
 * what is left. */
function canUseLiveCamera() {
    return Boolean(window.isSecureContext && navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
}

/** Decode an image file into something drawable.
 *
 * A photo straight from a phone carries the rotation in its EXIF header. The
 * browser applies it when it renders an <img>, so drawing that image into a
 * canvas bakes the correction into the pixels and the receipt never arrives
 * sideways. */
function decode(file) {
    return new Promise((resolve, reject) => {
        const url = URL.createObjectURL(file);
        const image = new Image();
        image.addEventListener('load', () => {
            URL.revokeObjectURL(url);
            resolve(image);
        });
        image.addEventListener('error', () => {
            URL.revokeObjectURL(url);
            reject(new Error('The file is not an image the browser can read.'));
        });
        image.src = url;
    });
}

function canvasToBlob(canvas) {
    return new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', JPEG_QUALITY));
}

/** A name that says when the photo was taken, so the inbox reads as a diary. */
function photoName() {
    const now = new Date();
    const pad = (value) => String(value).padStart(2, '0');
    const stamp = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}`
        + `-${pad(now.getHours())}${pad(now.getMinutes())}`;
    return `receipt-${stamp}.jpg`;
}

function formatTotal(document_) {
    if (!document_.total) {
        return '';
    }
    const amount = Number(document_.total).toFixed(2);
    return document_.currency ? `${amount} ${document_.currency}` : amount;
}

function row(label, value) {
    const wrapper = document.createElement('div');
    wrapper.className = 'o_easyocr_capture_field';
    if (label) {
        const term = document.createElement('dt');
        term.textContent = label;
        wrapper.append(term);
    }
    const detail = document.createElement('dd');
    // Text, never markup: a vendor name comes from a photograph.
    detail.textContent = value;
    wrapper.append(detail);
    return wrapper;
}

function withTimeout(promise, milliseconds) {
    return new Promise((resolve, reject) => {
        const timer = setTimeout(() => reject(new Error('timeout')), milliseconds);
        promise.then(
            (value) => { clearTimeout(timer); resolve(value); },
            (reason) => { clearTimeout(timer); reject(reason); },
        );
    });
}

/** Install the page as an app, when the browser is allowed to.
 *
 * A worker only runs on a secure origin. Over plain HTTP the page is expected
 * to work all the same, so nothing is registered and nothing is logged. */
function registerServiceWorker(url) {
    if (!url || !('serviceWorker' in navigator) || !window.isSecureContext) {
        return;
    }
    navigator.serviceWorker.register(url, { scope: '/easyocr/capture' }).catch(() => {});
}
