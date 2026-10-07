#!/usr/bin/env python
# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).
"""Build the installable ZIP of the module(s) under addons/.

One ZIP per Odoo series: the branch *is* the series, and the manifest version
must start with it (``19.0`` branch -> ``19.0.x.y.z``). The archive carries the
module folder at its root -- ``easyocr/__manifest__.py``, no wrapping folder --
because that is what the Odoo Apps Store expects and, more to the point, what
Odoo can find: the addons scan in ``odoo/modules/module.py`` lists the direct
children of each addons path with ``os.listdir`` and never recurses, so a
module nested one level deeper is simply not discovered.

Text files are written with LF endings and no BOM. The module runs on Linux
and this machine has ``core.autocrlf=true``, and the working tree can hold CRLF
even when the repository does not (``git ls-files --eol`` shows it): a
``.gitattributes`` with ``eol=lf`` normalises on checkout, and only for the
files that are checked out again. The normalisation here does not depend on
that.

Usage
-----
    python tools/build_zip.py [--branch 19.0] [--output dist/]
                             [--module easyocr] [--include-tests]
                             [--require-clean] [--print-version]

Exit codes
----------
    0  every ZIP was built and verified
    1  environment problem: no git, no addons/, no module, bad flags
    2  the requested series does not match the branch or the manifest
    3  tools/check_module.py refused the module
    4  a ZIP was written but failed its own verification
    5  the working tree is dirty and --require-clean was given
"""

import argparse
import codecs
import fnmatch
import pathlib
import subprocess
import sys
import time
import zipfile

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
TOOLS_DIR = pathlib.Path(__file__).resolve().parent
ADDONS_DIR = REPO_ROOT / 'addons'
CHECK_MODULE = TOOLS_DIR / 'check_module.py'

# Extensions and bare names treated as text: these get LF endings and no BOM.
TEXT_SUFFIXES = {
    '.py', '.xml', '.csv', '.po', '.pot', '.js', '.scss', '.css', '.less',
    '.html', '.htm', '.rst', '.md', '.txt', '.json', '.yml', '.yaml', '.conf',
    '.cfg', '.ini', '.toml', '.sh', '.svg',
}
TEXT_NAMES = {'license', 'copying', 'readme', 'changelog', 'authors', 'notice', 'makefile'}

# Never inside the distributed ZIP: build leftovers, editors, tooling.
EXCLUDED_DIRS = {
    '__pycache__', '.git', '.github', '.idea', '.vscode', '.pytest_cache',
    '.mypy_cache', '.ruff_cache', '.tox', '.tx', '.specstory', 'node_modules',
    'htmlcov', 'dist',
}
TEST_DIRS = {'tests', 'test'}
EXCLUDED_PATTERNS = [
    '*.pyc', '*.pyo', '*.pyd', '*.orig', '*.rej', '*.bak', '*.swp', '*.swo',
    '*~', '*.log', '*.sqlite3', '*.sqlite', '.ds_store', 'thumbs.db',
    '.odoorc', '.env', '*.local.conf', '.editorconfig', '.gitignore',
    '.gitattributes', 'docker-compose.yml', 'docker-compose.yaml', 'roadmap.md',
]


def fail(*lines):
    """Write a failure to stderr, flushing stdout first so the log keeps its order."""
    sys.stdout.flush()
    for line in lines:
        print(line, file=sys.stderr)


def git(*args):
    """Run git in the repository root. Returns CompletedProcess, never raises."""
    return subprocess.run(
        ['git', *args], cwd=REPO_ROOT, capture_output=True, text=True,
    )


def current_branch():
    """The checked-out branch, or None on a detached HEAD (a tag build)."""
    result = git('rev-parse', '--abbrev-ref', 'HEAD')
    if result.returncode != 0:
        return None
    name = result.stdout.strip()
    return None if name in ('', 'HEAD') else name


def series_from_exact_tag():
    """Deduce the series from the tag pointing at HEAD: v19.0.1.0.0 -> 19.0."""
    result = git('describe', '--tags', '--exact-match')
    if result.returncode != 0:
        return None
    tag = result.stdout.strip().lstrip('v')
    parts = tag.split('.')
    if len(parts) >= 2 and all(part.isdigit() for part in parts[:2]):
        return f'{parts[0]}.{parts[1]}'
    return None


def resolve_series(requested):
    """Return (series, where it came from) or (None, None)."""
    if requested:
        return requested, '--branch'
    branch = current_branch()
    if branch:
        return branch, f'current branch ({branch})'
    from_tag = series_from_exact_tag()
    if from_tag:
        return from_tag, 'tag at HEAD'
    return None, None


def load_check_module():
    """Import tools/check_module.py to reuse its manifest parser."""
    sys.path.insert(0, str(TOOLS_DIR))
    try:
        import check_module  # noqa: PLC0415 - sibling tool, imported on purpose
    except ImportError as error:
        fail(f'FAIL  cannot import {CHECK_MODULE}: {error}',
             '      tools/check_module.py validates the manifest; it must be there.')
        return None
    return check_module


def find_modules():
    """The module folders under addons/, sorted. Empty list if there are none."""
    if not ADDONS_DIR.is_dir():
        return []
    return sorted(
        path for path in ADDONS_DIR.iterdir()
        if path.is_dir() and (path / '__manifest__.py').is_file()
    )


def is_excluded(rel, include_tests):
    """True when a module-relative path must not go into the ZIP."""
    folders = [part.lower() for part in rel.parts[:-1]]
    if any(folder in EXCLUDED_DIRS for folder in folders):
        return True
    if not include_tests and any(folder in TEST_DIRS for folder in folders):
        return True
    name = rel.name.lower()
    return any(fnmatch.fnmatch(name, pattern) for pattern in EXCLUDED_PATTERNS)


def is_text(rel):
    return rel.suffix.lower() in TEXT_SUFFIXES or rel.name.lower() in TEXT_NAMES


def to_lf(data):
    """Return (data, crlf_fixed, bom_stripped) with LF endings and no UTF-8 BOM."""
    bom_stripped = data.startswith(codecs.BOM_UTF8)
    if bom_stripped:
        data = data[len(codecs.BOM_UTF8):]
    crlf_fixed = b'\r' in data
    if crlf_fixed:
        data = data.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
    return data, crlf_fixed, bom_stripped


def collect(module_dir, include_tests):
    """Module-relative paths to distributable files, in a stable order."""
    files = []
    for path in sorted(module_dir.rglob('*')):
        if not path.is_file():
            continue
        rel = path.relative_to(module_dir)
        if not is_excluded(rel, include_tests):
            files.append(rel)
    return files


def zip_date_time(path):
    """Even, 1980-or-later (year, month, day, hour, minute, second) for ZipInfo."""
    stamp = time.localtime(path.stat().st_mtime)
    if stamp.tm_year < 1980:
        return (1980, 1, 1, 0, 0, 0)
    return (stamp.tm_year, stamp.tm_mon, stamp.tm_mday,
            stamp.tm_hour, stamp.tm_min, stamp.tm_sec - stamp.tm_sec % 2)


def build_zip(module_dir, files, out_path):
    """Write the ZIP. Returns the report of what normalisation had to fix."""
    report = {'crlf': [], 'bom': []}
    with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for rel in files:
            source = module_dir / rel
            data = source.read_bytes()
            if is_text(rel):
                data, crlf_fixed, bom_stripped = to_lf(data)
                if crlf_fixed:
                    report['crlf'].append(rel.as_posix())
                if bom_stripped:
                    report['bom'].append(rel.as_posix())
            info = zipfile.ZipInfo(
                f'{module_dir.name}/{rel.as_posix()}',
                date_time=zip_date_time(source),
            )
            info.compress_type = zipfile.ZIP_DEFLATED
            # Uniform, sane permissions instead of whatever Windows reports.
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)
    return report


def verify_zip(path, module_name, include_tests):
    """Re-open the ZIP and check what the store and Odoo will see. Returns problems."""
    problems = []
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if not names:
            return ['the ZIP is empty']
        for name in names:
            if not name.startswith(f'{module_name}/'):
                problems.append(f'entry outside the module folder: {name}')
            if '/__pycache__/' in f'/{name}/' or name.endswith(('.pyc', '.pyo', '.pyd')):
                problems.append(f'build leftovers in the ZIP: {name}')
            if not include_tests and name.startswith(f'{module_name}/tests/'):
                problems.append(f'tests in the ZIP without --include-tests: {name}')
        if f'{module_name}/__manifest__.py' not in names:
            problems.append(f'the ZIP has no {module_name}/__manifest__.py')
        if f'{module_name}/static/description/icon.png' not in names:
            problems.append(f'the ZIP has no {module_name}/static/description/icon.png')
        for name in names:
            if not is_text(pathlib.PurePosixPath(name)):
                continue
            data = archive.read(name)
            if b'\r' in data:
                problems.append(f'CRLF inside {name}')
            if data.startswith(codecs.BOM_UTF8):
                problems.append(f'UTF-8 BOM inside {name}')
    return problems


def human_size(size):
    for unit in ('B', 'KB', 'MB'):
        if size < 1024 or unit == 'MB':
            return f'{size:.1f} {unit}' if unit != 'B' else f'{size} B'
        size /= 1024
    return f'{size:.1f} MB'


def dirty_entries(module_dir):
    """Tracked-or-not changes under the module folder, one line each."""
    result = git('status', '--porcelain', '--untracked-files=all', '--', str(module_dir))
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def main():
    parser = argparse.ArgumentParser(
        description='Build the installable ZIP of the module(s) under addons/.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        '--branch',
        default='',
        help='Odoo series to package, e.g. 19.0. Defaults to the current branch, '
             'or to the series of the tag at HEAD.',
    )
    parser.add_argument(
        '--output', default='dist/',
        help='Directory for the resulting ZIP (default: dist/).',
    )
    parser.add_argument(
        '--module', default='',
        help='Package only this module (by folder name). Default: every module under addons/.',
    )
    parser.add_argument(
        '--include-tests', action='store_true',
        help='Ship tests/ too. By default it stays out: the ZIP is the installable artifact.',
    )
    parser.add_argument(
        '--require-clean', action='store_true',
        help='Refuse to build when the module folder has uncommitted changes (use in CI, '
             'so a released ZIP matches the tag).',
    )
    parser.add_argument(
        '--print-version', action='store_true',
        help='Print the manifest version of each module and exit. For CI to name the tag.',
    )
    args = parser.parse_args()

    modules = find_modules()
    if not modules:
        fail(f'FAIL  no module found under {ADDONS_DIR}',
             '      a module is a folder with __manifest__.py, and tools/check_module.py '
             'expects it under addons/.')
        return 1
    if args.module:
        modules = [path for path in modules if path.name == args.module]
        if not modules:
            fail(f'FAIL  there is no module named "{args.module}" under {ADDONS_DIR}')
            return 1

    check_module = load_check_module()
    if check_module is None:
        return 1

    if args.print_version:
        for module_dir in modules:
            try:
                manifest = check_module.read_manifest(module_dir / '__manifest__.py')
            except ValueError as error:
                fail(f'FAIL  {error}')
                return 3
            print(manifest.get('version', ''))
        return 0

    series, source = resolve_series(args.branch)
    if not series:
        fail('FAIL  no Odoo series: detached HEAD with no tag and no --branch.',
             '      Pass --branch <series>, e.g. --branch 19.0.')
        return 2

    branch = current_branch()
    print(f'Series {series} ({source})')
    if branch and branch != series:
        fail(f'FAIL  the checked-out branch is {branch}, and this build asks for {series}.',
             f'      Each branch carries one series: run git switch {series}, then build again.')
        return 2

    # The ZIP is built from what is on disk, not from git, so an uncommitted
    # change travels inside it. Say it out loud: a release asset that does not
    # match its tag is a bug nobody sees until a customer installs it.
    dirty = [line.strip() for module_dir in modules for line in dirty_entries(module_dir)]
    if dirty:
        for line in dirty:
            print(f'WARN  uncommitted change in the module folder: {line}')
        if args.require_clean:
            fail('FAIL  the module folder has uncommitted changes (--require-clean).',
                 '      Commit or stash them: a released ZIP must match the tag.')
            return 5
        print('WARN  the ZIP will carry those changes; the tree does not match any commit.')

    print(f'Validating with tools/check_module.py --branch {series}')
    validation = subprocess.run(
        [sys.executable, str(CHECK_MODULE), '--branch', series],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    for line in (validation.stdout + validation.stderr).splitlines():
        print(f'      {line}')
    if validation.returncode != 0:
        fail('FAIL  tools/check_module.py refused the module; nothing was packaged.')
        return 3

    out_dir = pathlib.Path(args.output)
    if not out_dir.is_absolute():
        out_dir = REPO_ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    if git('check-ignore', '-q', str(out_dir)).returncode != 0:
        print(f'WARN  {out_dir} is not in .gitignore: the ZIP would show up as an '
              'untracked file.')

    failures = 0
    for module_dir in modules:
        try:
            manifest = check_module.read_manifest(module_dir / '__manifest__.py')
        except ValueError as error:
            fail(f'FAIL  {error}')
            return 3
        version = str(manifest.get('version', ''))
        if not version.startswith(f'{series}.'):
            fail(f'FAIL  {module_dir.name}: version "{version}" does not start with '
                 f'"{series}." (series {series}).')
            return 2

        files = collect(module_dir, args.include_tests)
        out_path = out_dir / f'{module_dir.name}-{version}.zip'
        report = build_zip(module_dir, files, out_path)
        problems = verify_zip(out_path, module_dir.name, args.include_tests)

        print(f'Built {module_dir.name} {version}: {len(files)} files, '
              f'{human_size(out_path.stat().st_size)}')
        if report['crlf']:
            print(f'      CRLF -> LF in {len(report["crlf"])} file(s): '
                  f'{", ".join(report["crlf"])}')
        if report['bom']:
            print(f'      BOM removed from: {", ".join(report["bom"])}')
        if problems:
            fail(*[f'FAIL  {problem}' for problem in problems])
            failures += 1
            continue
        print(f'      {out_path}')
        print(f'      verified: {module_dir.name}/__manifest__.py at the root, '
              f'LF endings, no BOM, no build leftovers')

    if failures:
        return 4
    print('Ready. Attach the ZIP to the GitHub Release, never to an upload-artifact step.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
