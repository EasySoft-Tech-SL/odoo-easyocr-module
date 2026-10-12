// Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
// License LGPL-3 (see LICENSE file).

/**
 * The changelog page's Markdown, on its own. Run with: node --test
 */

import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';

import {markdownToHtml, splitVersions} from '../../easyocr/static/src/js/easyocr_markdown.js';

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

test('the file comes apart at its version headings, the preamble on its own', () => {
    const {intro, versions} = splitVersions([
        '# Changelog',
        '',
        'All notable changes are documented here.',
        '',
        '## [1.0.9] - 2026-10-11',
        '',
        '### Fixed',
        '',
        '- **Last.** A thing.',
        '',
        '## [1.0.8] - 2026-10-10',
        '',
        '### Added',
        '',
        '- **Older.** Another.',
    ].join('\n'));

    assert.equal(intro, '# Changelog\n\nAll notable changes are documented here.');
    assert.deepEqual(
        versions.map((version) => version.header),
        ['[1.0.9] - 2026-10-11', '[1.0.8] - 2026-10-10'],
    );
    // A section inside a version is not a version: only `## ` cuts.
    assert.equal(versions[0].body, '### Fixed\n\n- **Last.** A thing.');
    assert.ok(!versions[0].body.includes('1.0.8'));
});

test('nothing to split is no version at all, not one empty one', () => {
    assert.deepEqual(splitVersions(''), {intro: '', versions: []});
    assert.deepEqual(splitVersions('# Changelog\n\nNothing yet.').versions, []);
});

test('the changelog the module ships carries every bullet inside a version', () => {
    // A bullet above the first version heading is a bullet no reader ever
    // sees: the page draws the preamble on its own and the versions folded.
    const source = readFileSync(
        new URL('../../easyocr/CHANGELOG.md', import.meta.url), 'utf8');
    const {intro, versions} = splitVersions(source);
    const bullets = (text) => (text.match(/^- /gm) || []).length;

    assert.ok(versions.length > 1, 'The changelog is not cut into versions.');
    assert.equal(bullets(intro), 0, 'A bullet sits above every version heading.');
    assert.equal(
        versions.reduce((total, version) => total + bullets(version.body), 0),
        bullets(source),
        'A bullet was left out of the blocks the page draws.',
    );

    const numbers = [];
    for (const version of versions) {
        const head = /^\[(\d+)\.(\d+)\.(\d+)\] - \d{4}-\d{2}-\d{2}$/.exec(version.header);
        assert.ok(head, `A version heading is not one: ${version.header}`);
        assert.ok(version.body.length, `Version ${version.header} shows nothing.`);
        numbers.push(head.slice(1).map(Number));
    }
    // The newest first: the page opens the first block and folds the rest.
    // Compared as numbers, not as text: 1.0.10 comes after 1.0.9.
    const weight = ([major, minor, patch]) => major * 10000 + minor * 100 + patch;
    for (let i = 1; i < numbers.length; i += 1) {
        assert.ok(
            weight(numbers[i - 1]) > weight(numbers[i]),
            `Version ${numbers[i].join('.')} comes after the one below it.`,
        );
    }
});
