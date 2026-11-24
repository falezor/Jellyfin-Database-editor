#!/usr/bin/env python3
"""Build a lightweight release ZIP from a git tag.

Includes the program, UI, README/license and changelogs.
Excludes test databases, internal analysis and runtime data.
"""
import argparse
import os
import subprocess
import sys
import time
import zipfile

GIT = 'git'
TOP_FILES = ('.gitattributes', '.gitignore', 'LICENSE', 'jf_browser.py', 'i18n.py')


def included(path):
    if path in TOP_FILES:
        return True
    if '/' not in path and path.endswith('.md'):
        return True
    return (path.startswith('ui/') or path.startswith('windows/')) and not path.endswith('/')


def zip_date(tag):
    """Test builds stay reproducible (1980); releases use the tag commit date (UTC)."""
    if '-test' in tag:
        return (1980, 1, 1, 0, 0, 0)
    try:
        ts = int(subprocess.check_output(
            [GIT, 'log', '-1', '--format=%ct', tag], text=True).strip())
        t = time.gmtime(ts)
        return (t.tm_year, t.tm_mon, t.tm_mday, t.tm_hour, t.tm_min, t.tm_sec)
    except (OSError, ValueError, subprocess.CalledProcessError):
        return (1980, 1, 1, 0, 0, 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('tag', help='tag to package, e.g. v0.9.0')
    ap.add_argument('-o', '--out', help='output ZIP path')
    args = ap.parse_args()
    tag = args.tag
    version = tag[1:] if tag.startswith('v') else tag
    try:
        subprocess.run([GIT, 'rev-parse', '--verify', f'refs/tags/{tag}'],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        names = subprocess.check_output([GIT, 'ls-tree', '-r', '-z', '--name-only', '--full-tree', tag])
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise SystemExit(f'Cannot read tag {tag}: {e}')
    paths = [p.decode('utf-8', 'replace') for p in names.split(b'\0') if p]
    paths = [p for p in paths if included(p)]
    out = args.out or f'jf_browser_{tag}.zip'
    prefix = f'jf_browser_{version}/'
    date_time = zip_date(tag)
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for path in paths:
            try:
                data = subprocess.check_output([GIT, 'show', f'{tag}:{path}'])
            except subprocess.CalledProcessError as e:
                raise SystemExit(f'Cannot read {path} from {tag}: {e}')
            info = zipfile.ZipInfo(prefix + path, date_time=date_time)
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)
    print(f'{out}: {len(paths)} files, {os.path.getsize(out)} bytes')


if __name__ == '__main__':
    main()
