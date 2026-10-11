#!/usr/bin/env python
# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).
"""Sanity checks for every module under addons/ before it reaches a release.

Runs without Odoo installed: reads the manifests, not the framework.
Usage: python tools/check_module.py [--branch 19.0]
"""

import argparse
import ast
import os
import pathlib
import re
import sys

ADDONS_DIR = pathlib.Path(__file__).resolve().parent.parent / 'addons'

# A screenshot as markdown shows it. Only the image form: a plain link is often
# a file that is meant to be absent (a release asset, a page of the wiki).
MARKDOWN_IMAGE = re.compile(r'!\[[^\]]*\]\(\s*<?([^)>\s]+)')

REQUIRED_KEYS = (
    'name',
    'version',
    'author',
    'license',
    'depends',
    'installable',
)


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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--branch',
        default=os.environ.get('GITHUB_REF_NAME', ''),
        help='Expected Odoo series, e.g. 19.0. Defaults to GITHUB_REF_NAME.',
    )
    args = parser.parse_args()

    if not ADDONS_DIR.is_dir():
        print(f'No addons directory at {ADDONS_DIR}', file=sys.stderr)
        return 1

    modules = sorted(path for path in ADDONS_DIR.iterdir() if path.is_dir())
    if not modules:
        print(f'No modules found under {ADDONS_DIR}', file=sys.stderr)
        return 1

    errors = []
    for module_dir in modules:
        errors.extend(check_module(module_dir, args.branch))
    errors.extend(check_documentation_images(ADDONS_DIR.parent))

    for error in errors:
        print(f'FAIL  {error}', file=sys.stderr)

    print(f'Checked {len(modules)} module(s), {len(errors)} problem(s).')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
