// Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
// License LGPL-3 (see LICENSE file).

/**
 * The changelog, from Markdown to HTML, for the configuration page.
 *
 * Odoo ships no Markdown library, and the changelog only uses a handful of
 * things: headings, bullet lists with indented continuation lines, paragraphs,
 * bold, inline code and links. That is all this understands. Everything is
 * escaped first, so nothing in the file can become markup it did not ask for,
 * and a link only becomes one when it points to http(s) or to a relative path.
 */

function escape(text) {
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

function inline(text) {
    let html = escape(text);
    html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
    html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (match, label, href) => {
        const safe = /^(https?:\/\/|[\w./-]+$)/.test(href) && !/^javascript:/i.test(href);
        return safe ? `<a href="${href}" target="_blank" rel="noopener">${label}</a>` : label;
    });
    return html;
}

export function markdownToHtml(source) {
    const lines = (source || "").replace(/\r\n/g, "\n").split("\n");
    const out = [];
    let paragraph = [];
    let item = null;
    let inList = false;

    const flushParagraph = () => {
        if (paragraph.length) {
            out.push(`<p>${inline(paragraph.join(" "))}</p>`);
            paragraph = [];
        }
    };
    const flushItem = () => {
        if (item !== null) {
            out.push(`<li>${inline(item)}</li>`);
            item = null;
        }
    };
    const closeList = () => {
        flushItem();
        if (inList) {
            out.push("</ul>");
            inList = false;
        }
    };

    for (const raw of lines) {
        const line = raw.replace(/\s+$/, "");
        const heading = /^(#{1,4})\s+(.*)$/.exec(line);
        const bullet = /^[-*]\s+(.*)$/.exec(line);
        if (heading) {
            flushParagraph();
            closeList();
            const level = heading[1].length;
            out.push(`<h${level}>${inline(heading[2])}</h${level}>`);
        } else if (bullet) {
            flushParagraph();
            flushItem();
            if (!inList) {
                out.push("<ul>");
                inList = true;
            }
            item = bullet[1];
        } else if (!line.trim()) {
            flushParagraph();
            closeList();
        } else if (item !== null && /^\s+/.test(raw)) {
            // An indented line carries on the bullet above it.
            item += " " + line.trim();
        } else {
            closeList();
            paragraph.push(line.trim());
        }
    }
    flushParagraph();
    closeList();
    return out.join("\n");
}
