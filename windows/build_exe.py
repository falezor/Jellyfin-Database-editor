#!/usr/bin/env python3
"""Build the Windows onedir package for Jellyfin DB Editor.

The application itself is the existing Python source; this script bundles it
with PyInstaller into a self-contained folder (python DLL, Tcl/Tk, UI files).
The default entry point is windows/launcher.py: a native WebView2 window with
a browser + control-window fallback.

Run with a Python that has PyInstaller, Pillow, pywebview and pythonnet
installed:

    python -m pip install pyinstaller pillow pywebview pythonnet
    python windows/build_exe.py

Use --console for a debug build that keeps a console window.
Use --no-webview for a browser-only build without pywebview/pythonnet.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WIN = ROOT / "windows"
BUILD = WIN / "build"
DIST = WIN / "dist"
APP = "jellyfin-db-editor"
DEFAULT_OUT = Path(os.environ.get("USERPROFILE") or Path.home()) / "Downloads"


def app_version() -> str:
    text = (ROOT / "jf_browser.py").read_text(encoding="utf-8")
    match = re.search(r"^APP_VERSION\s*=\s*['\"]([^'\"]+)['\"]", text, re.MULTILINE)
    if not match:
        raise SystemExit("APP_VERSION not found in jf_browser.py")
    return match.group(1)


def version_parts(version: str) -> tuple[int, int, int, int]:
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", version)
    if not match:
        raise SystemExit(f"cannot parse version: {version!r}")
    major, minor, patch = (int(x) for x in match.groups())
    return major, minor, patch, 0


def write_version_file(path: Path, version: str) -> None:
    major, minor, patch, build = version_parts(version)
    path.write_text(
        f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({major}, {minor}, {patch}, {build}),
    prodvers=({major}, {minor}, {patch}, {build}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          u'040904B0',
          [StringStruct(u'CompanyName', u'Jellyfin DB Editor contributors'),
           StringStruct(u'FileDescription', u'Jellyfin DB Editor'),
           StringStruct(u'FileVersion', u'{version}'),
           StringStruct(u'InternalName', u'{APP}'),
           StringStruct(u'LegalCopyright', u'Copyright (c) 2026 Jellyfin DB Editor contributors'),
           StringStruct(u'OriginalFilename', u'{APP}.exe'),
           StringStruct(u'ProductName', u'Jellyfin DB Editor'),
           StringStruct(u'ProductVersion', u'{version}')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
""",
        encoding="utf-8",
        newline="\n",
    )


def ensure_icon() -> Path | None:
    ico = WIN / f"{APP}.ico"
    png = WIN / f"{APP}.png"
    if ico.exists():
        return ico
    if not png.exists():
        return None
    try:
        from PIL import Image
    except ImportError:
        print("warning: Pillow is not installed; building without an icon")
        return None
    image = Image.open(png).convert("RGBA")
    image.save(ico, sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                           (64, 64), (128, 128), (256, 256)])
    return ico


def collect_datas() -> list[str]:
    docs = ("README.md", "README-extensive.md", "README-extensivePL.md",
            "LICENSE", "versions.md", "wersje.md")
    data = [f"{ROOT / 'ui' / 'index.html'};ui"]
    data += [f"{ROOT / name};." for name in docs]
    return data


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest(folder: Path) -> None:
    lines = []
    for path in sorted(p for p in folder.rglob("*") if p.is_file()):
        lines.append(f"{sha256(path)}  {path.relative_to(folder).as_posix()}")
    (folder / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n",
                                           encoding="utf-8", newline="\n")


def copy_docs(folder: Path) -> None:
    """Keep the program documents at the package root (installer + users)."""
    for name in ("LICENSE", "README.md", "README-extensive.md",
                 "README-extensivePL.md", "versions.md", "wersje.md"):
        source = ROOT / name
        if source.is_file():
            shutil.copy2(source, folder / name)


def copy_third_party_licenses(folder: Path) -> None:
    """Add the licenses of bundled components next to the app."""
    from importlib.metadata import PackageNotFoundError, distribution

    out = folder / "licenses"
    out.mkdir(exist_ok=True)
    copied = []
    for package, prefix in (("pywebview", "pywebview"),
                            ("pythonnet", "pythonnet"),
                            ("clr_loader", "clr_loader"),
                            ("pyinstaller", "pyinstaller")):
        try:
            dist = distribution(package)
        except PackageNotFoundError:
            continue
        for item in dist.files or ():
            parts = [part.lower() for part in item.parts]
            name = item.name.upper()
            if "licenses" not in parts or not name.startswith(("LICENSE", "COPYING")):
                continue
            source = Path(dist.locate_file(item))
            if not source.is_file():
                continue
            target = out / f"{prefix}-{item.name}"
            shutil.copy2(source, target)
            copied.append(target.name)

    candidates = [
        (Path(sys.base_prefix) / "LICENSE.txt", "python-LICENSE.txt"),
        (Path(sys.base_prefix) / "tcl" / "tk8.6" / "license.terms", "tcl-tk-license.terms"),
        (Path(sys.base_prefix) / "tcl" / "tcl8.6" / "license.terms", "tcl-license.terms"),
    ]
    for source, name in candidates:
        if source.is_file():
            shutil.copy2(source, out / name)
            copied.append(name)

    if copied:
        (out / "README.txt").write_text(
            "Third-party components bundled with this package:\n"
            "- Python (PSF license)\n"
            "- Tcl/Tk (BSD-style)\n"
            "- PyInstaller bootloader (GPLv2 with exception)\n"
            "- pywebview (BSD 3-Clause)\n"
            "- pythonnet (MIT)\n"
            "- clr_loader (MIT)\n"
            "- Microsoft Edge WebView2 Runtime (system component, not bundled)\n"
            "\nSee the LICENSE/COPYING files in this folder.\n",
            encoding="utf-8", newline="\r\n",
        )


def build_arch() -> str:
    machine = (platform.machine() or "").lower()
    bits = platform.architecture()[0]
    if machine in ("arm64", "aarch64"):
        return "arm64"
    if bits == "32bit":
        return "x86"
    if machine in ("amd64", "x86_64"):
        return "x64"
    return machine or "unknown"


def write_run_me(folder: Path, version: str, arch: str) -> None:
    (folder / "RUN-ME.txt").write_text(
        f"""Jellyfin DB Editor {version} (Windows {arch} portable)

Run: jellyfin-db-editor.exe

This is the Python/WebView2 build with the same HTML interface as the Linux
version. It is a portable onedir package: keep the whole folder together.

The interface opens in a native WebView2 window when available, otherwise in
the default browser with a small control window. The local server listens only
on 127.0.0.1. Settings and history are stored next to the exe when that folder
is writable, otherwise in the user profile.

Closing the window/control window stops the local server.

Log files: %LOCALAPPDATA%\\JellyfinDBEditor\\logs\\
  launcher.log, app.log

Architecture: {arch}. See BUILD-INFO.txt for build details.
""",
        encoding="utf-8",
        newline="\r\n",
    )


def write_build_info(folder: Path, version: str, arch: str) -> None:
    try:
        import PyInstaller
        pyinstaller = getattr(PyInstaller, "__version__", "unknown")
    except Exception:
        pyinstaller = "unknown"
    (folder / "BUILD-INFO.txt").write_text(
        f"""Jellyfin DB Editor {version} — Windows {arch} portable
================================================

Executable:   jellyfin-db-editor.exe
Architecture: {arch}
Build type:   onedir portable — keep the whole folder together
UI:           same HTML interface as the Linux version
Window:       native pywebview / WebView2, browser fallback
Python:       {platform.python_version()} ({arch})
PyInstaller:  {pyinstaller}
Source:       Jellyfin DB Editor {version}

Portable data:
  Settings, history, backups and temporary data stay next to the executable
  when this folder is writable. Otherwise the app uses the user profile.
  Do not copy only the .exe — _internal/ must stay next to it.

Source tests:
  python -m unittest discover -s tests -v
  See .github/workflows/tests.yml for the Windows/Linux CI matrix.

Label: {arch} portable
""",
        encoding="utf-8",
        newline="\r\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--console", action="store_true",
                        help="keep a console window (debug build)")
    parser.add_argument("--entry", choices=("launcher", "core"), default="launcher",
                        help="launcher: native window + browser fallback; core: browser only")
    parser.add_argument("--no-webview", action="store_true",
                        help="do not bundle pywebview/pythonnet (browser fallback only)")
    parser.add_argument("--out", default=str(DEFAULT_OUT),
                        help="folder for the final onedir package (default: Downloads)")
    parser.add_argument("--no-copy", action="store_true",
                        help="leave the result in windows/dist only")
    args = parser.parse_args()

    version = app_version()
    if BUILD.exists():
        shutil.rmtree(BUILD)
    if DIST.exists():
        shutil.rmtree(DIST)

    version_file = WIN / "version_info.txt"
    write_version_file(version_file, version)
    icon = ensure_icon()
    entry = WIN / "launcher.py" if args.entry == "launcher" else ROOT / "jf_browser.py"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onedir", "--noupx",
        "--name", APP,
        "--distpath", str(DIST),
        "--workpath", str(BUILD),
        "--specpath", str(WIN),
    ]
    for item in collect_datas():
        cmd += ["--add-data", item]
    if args.no_webview:
        for module in ("webview", "clr", "clr_loader", "pythonnet"):
            cmd += ["--exclude-module", module]
    if not args.console:
        cmd.append("--windowed")
    if icon:
        cmd += ["--icon", str(icon)]
    cmd += ["--version-file", str(version_file), str(entry)]

    print("Building:", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)

    source = DIST / APP
    exe = source / f"{APP}.exe"
    if not exe.is_file():
        raise SystemExit(f"PyInstaller did not produce {exe}")

    if not args.no_copy:
        arch = build_arch()
        target = Path(args.out) / f"{APP}_{version}_windows_{arch}_portable"
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)
        write_run_me(target, version, arch)
        write_build_info(target, version, arch)
        copy_docs(target)
        copy_third_party_licenses(target)
        write_manifest(target)
        print(f"Package: {target}")
        print(f"Exe:     {target / (APP + '.exe')} ({exe.stat().st_size} bytes)")
        print(f"SHA256:  {sha256(target / (APP + '.exe'))}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
