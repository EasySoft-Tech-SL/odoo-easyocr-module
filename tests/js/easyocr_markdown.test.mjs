// Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
// License LGPL-3 (see LICENSE file).

/**
 * The changelog page's Markdown, on its own. Run with: node --test
 */

import assert from 'node:assert/strict';
import {test} from 'node:test';

import {markdownToHtml} from '../../addons/easyocr/static/src/js/easyocr_markdown.js';

test('headings, bullets with continuation lines, bold and code', () => {
    const html = markdownToHtml(
        '## [1.0.7]\n\n### Fixed\n\n- **Templates.** The `select` sent\n  text, not a number.\n- Second.\n',
    );

    assert.equal(html, [
        '<h2>[1.0.7]</h2>',
        '<h3>Fixed</h3>',
        '<ul>',
        '<li><strong>Templates.</strong> The <code>select</code> sent text, not a number.</li>',
        '<li>Second.</li>',
        '</ul>',
    ].join('\n'));
});

test('nothing in the file becomes markup it did not ask for', () => {
    const html = markdownToHtml('A <script>alert(1)</script> and [x](javascript:alert(1)).');

    assert.ok(!html.includes('<script>'));
    assert.ok(!html.includes('href="javascript'));
});

test('a plain link is a link', () => {
    assert.equal(
        markdownToHtml('See [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).'),
        '<p>See <a href="https://keepachangelog.com/en/1.1.0/" target="_blank" rel="noopener">Keep a Changelog</a>.</p>',
    );
});
