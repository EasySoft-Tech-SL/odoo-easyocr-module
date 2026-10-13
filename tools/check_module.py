#!/usr/bin/env python
# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).
"""Sanity checks for every module of this repository before it reaches a release.

Runs without Odoo installed: reads the manifests, not the framework.
Usage: python tools/check_module.py [--branch 19.0]
"""

import argparse
import ast
import os
import pathlib
import re
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
# Where the module folders are looked for, in order: the repository root first
# (what the Odoo Apps Store scans), then addons/ (the OCA layout this repo used
# to have). Kept in step with tools/build_zip.py.
MODULE_ROOTS = (REPO_ROOT, REPO_ROOT / 'addons')

# A screenshot as markdown shows it. Only the image form: a plain link is often
# a file that is meant to be absent (a release asset, a page of the wiki).
MARKDOWN_IMAGE = re.compile(r'!\[[^\]]*\]\(\s*<?([^)>\s]+)')

# The sheet the store shows. The Odoo Apps Store sanitises
# static/description/index.html and strips the `background` property out of every
# inline style while keeping `color` and the rest, so a fill that lives only in
# `style` arrives colourless. See check_store_description.
DESCRIPTION_INDEX = ('static', 'description', 'index.html')
TAG = re.compile(r'<(\w+)([^>]*)>')
STYLE_ATTRIBUTE = re.compile(r'style="([^"]*)"')
CLASS_ATTRIBUTE = re.compile(r'class="([^"]*)"')
INLINE_BACKGROUND = re.compile(r'background(?:-color)?\s*:\s*([^;"]+)')
WHITE_BACKGROUND = re.compile(r'^\s*(#fff|#ffffff|white)\s*$', re.IGNORECASE)
BACKGROUND_CLASS = re.compile(r'\bbg-[a-z-]+\b')

REQUIRED_KEYS = (
    'name',
    'version',
    'author',
    'license',
    'depends',
    'installable',
)


def find_modules():
    """The module folders, sorted. Empty list if there are none.

    Root first, then addons/: only the first root that has a module is read, so
    a half-finished move cannot check the same module twice.
    """
    for root in MODULE_ROOTS:
        if not root.is_dir():
            continue
        modules = sorted(
            path for path in root.iterdir()
            if path.is_dir() and (path / '__manifest__.py').is_file()
        )
        if modules:
            return modules
    return []


def read_manifest(path):
    """Return the manifest dict, or raise ValueError with a readable reason."""
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'))
    except SyntaxError as error:
        raise ValueError(f'{path}: {error}') from error

    for node in tree.body:
        # A manifest is a single expression statement whose value is the dict,
        # not a bare dict node sitting in the module body.
        value = node.value if isinstance(node, ast.Expr) else node
        if isinstance(value, ast.Dict):
            return ast.literal_eval(value)
    raise ValueError(f'{path}: no dictionary literal found')


def check_module(module_dir, expected_branch):
    errors = []

    manifest_path = module_dir / '__manifest__.py'
    init_path = module_dir / '__init__.py'

    if not manifest_path.is_file():
        return [f'{module_dir.name}: missing __manifest__.py']
    if not init_path.is_file():
        errors.append(f'{module_dir.name}: missing __init__.py')

    try:
        manifest = read_manifest(manifest_path)
    except ValueError as error:
        return [str(error)]

    for key in REQUIRED_KEYS:
        if key not in manifest:
            errors.append(f'{module_dir.name}: manifest has no "{key}"')

    version = manifest.get('version', '')
    if expected_branch and not version.startswith(f'{expected_branch}.'):
        errors.append(
            f'{module_dir.name}: version "{version}" does not start with '
            f'"{expected_branch}." (the branch this commit lives on)'
        )

    if manifest.get('installable') is not True:
        errors.append(f'{module_dir.name}: installable is not True')

    if not (module_dir / 'static' / 'description' / 'icon.png').is_file():
        errors.append(f'{module_dir.name}: no static/description/icon.png')

    return errors


def check_documentation_images(root):
    """Every screenshot the documentation shows has to be there.

    A path that stops pointing at a file is invisible from both ends. GitHub
    draws the caption over an empty box and says nothing, the wiki shows a gap,
    and nothing in the repository reads that path, so no test turns red. It got
    as far as the front page of a released version once: the file was renamed
    while writing the user guide and the README kept the old name.
    """
    errors = []
    for page in sorted(root.rglob('*.md')):
        if '.git' in page.parts:
            continue
        text = page.read_text(encoding='utf-8')
        for target in MARKDOWN_IMAGE.findall(text):
            if '://' in target or target.startswith(('#', '<', 'mailto:')):
                continue
            if not (page.parent / target).is_file():
                errors.append(
                    f'{page.relative_to(root).as_posix()} shows {target}, '
                    f'which is not there'
                )
    return errors


def check_store_description(module_dir):
    """A block that paints itself in `style` also has to paint itself with a class.

    The store drops the `background` property from inline styles and keeps the
    rest, so a black band written only as `background:#000000` loses its fill and
    the white text over it turns invisible on the store's white page. It happened
    with the 1.0.15 sheet: the headline of the published page was white on white
    and the page could not be read, and nothing else noticed, because the file is
    perfectly valid HTML and no other check reads it. The fill therefore goes in a
    class (`bg-black`, `bg-light`) as well, and this is what notices when a new
    block forgets to. White needs no class: it is white on white either way.
    """
    index = module_dir.joinpath(*DESCRIPTION_INDEX)
    if not index.is_file():
        return []

    errors = []
    for tag in TAG.finditer(index.read_text(encoding='utf-8')):
        attributes = tag.group(2)
        style = STYLE_ATTRIBUTE.search(attributes)
        if not style:
            continue
        background = INLINE_BACKGROUND.search(style.group(1))
        if not background or WHITE_BACKGROUND.match(background.group(1)):
            continue
        classes = CLASS_ATTRIBUTE.search(attributes)
        if classes and BACKGROUND_CLASS.search(classes.group(1)):
            continue
        errors.append(
            f'{index.relative_to(REPO_ROOT).as_posix()}: a block with '
            f'background:{background.group(1).strip()} carries no bg-* class, '
            'and the store drops the inline one'
        )
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--branch',
        default=os.environ.get('GITHUB_REF_NAME', ''),
        help='Expected Odoo series, e.g. 19.0. Defaults to GITHUB_REF_NAME.',
    )
    args = parser.parse_args()

    modules = find_modules()
    if not modules:
        roots = ' nor '.join(str(root) for root in MODULE_ROOTS)
        print(f'No module found at {roots} '
              '(a module is a folder holding a __manifest__.py)', file=sys.stderr)
        return 1

    errors = []
    for module_dir in modules:
        errors.extend(check_module(module_dir, args.branch))
        errors.extend(check_store_description(module_dir))
    errors.extend(check_documentation_images(REPO_ROOT))

    for error in errors:
        print(f'FAIL  {error}', file=sys.stderr)

    print(f'Checked {len(modules)} module(s), {len(errors)} problem(s).')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
