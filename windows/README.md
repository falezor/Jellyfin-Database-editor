# Windows x64 portable EXE build

The Windows package is a **self-contained onedir folder**: the exe, Python
runtime, Tcl/Tk, UI, WebView2 bridge and documentation. Keep the whole folder
together. The generated package is labelled **x64 portable** and contains
`BUILD-INFO.txt` with its architecture and build details.

The launcher opens the UI in a **native WebView2 window**. If the WebView2
Runtime or pywebview is unavailable, it opens the default browser and shows a
small control window instead. Closing either window stops the local server.

## Build

Requirements:

- Windows 10/11 x64,
- Python 3.13 (standard CPython installation),
- PyInstaller, Pillow, pywebview and pythonnet:

```powershell
python -m pip install pyinstaller pillow pywebview pythonnet
python windows\build_exe.py
```

The result is copied to:

```text
%USERPROFILE%\Downloads\jellyfin-db-editor_<version>_windows_x64_portable\
```

The suffix is built from the active Python architecture, so an x64 build gets
`_windows_x64_portable`, and an experimental x86 build would get
`_windows_x86_portable`.

Useful options:

```powershell
# browser fallback only, without pywebview/pythonnet
python windows\build_exe.py --no-webview

# debug build with a console window, result left in windows\dist
python windows\build_exe.py --console --no-copy

# different output directory
python windows\build_exe.py --out D:\builds
```

## Run

```text
jellyfin-db-editor.exe
```

The local server starts on an ephemeral `127.0.0.1` port. The original Jellyfin
database is only changed by **Upload** or **Revert**. The first run asks for the
data folder (or opens the setup screen).

If the folder is writable, settings and history stay next to the exe
(portable mode). Otherwise they go to the user profile. Logs are written to:

```text
%LOCALAPPDATA%\JellyfinDBEditor\logs\launcher.log
%LOCALAPPDATA%\JellyfinDBEditor\logs\app.log
```

The WebView2 profile (localStorage for language/theme) is stored in:

```text
%LOCALAPPDATA%\JellyfinDBEditor\webview\
```

## Installer (x86/x64, Windows 10+)

One NSIS-based machine-wide installer contains both the x64 and x86 portable
packages and selects the matching payload at install time:

- x64 Windows gets the x64 package,
- 32-bit Windows gets the x86 package,
- Windows 10 or newer is required.

Build both payloads first. Build the x64 payload with the normal 64-bit Python;
build the x86 payload with a 32-bit Python 3.13 environment:

```powershell
# x64
python windows\build_exe.py --out "$env:USERPROFILE\Downloads"

# x86 (run with a 32-bit Python 3.13 + PyInstaller/pywebview/pythonnet)
python windows\build_exe.py --out "$env:USERPROFILE\Downloads"
```

Then build the combined installer:

```powershell
powershell -File windows\build_installer.ps1 `
  -PayloadX64 "$env:USERPROFILE\Downloads\jellyfin-db-editor_1.0.1_windows_x64_portable" `
  -PayloadX86 "$env:USERPROFILE\Downloads\jellyfin-db-editor_1.0.1_windows_x86_portable" `
  -Makensis "C:\Program Files (x86)\NSIS\makensis.exe"
```

The result is:

```text
%USERPROFILE%\Downloads\jellyfin-db-editor_1.0.1_windows_x86_x64_setup.exe
```

The installer:

- installs for all users in `%ProgramFiles%\Jellyfin DB Editor`
  (`Program Files (x86)` only for an x86 Windows build); UAC/admin is required,
- creates an all-users Start Menu shortcut named **Jellyfin DB Editor** and an
  optional desktop shortcut with the same display name,
- registers an uninstaller in Apps & Features,
- selects x64 or x86 automatically; it does not ask the user,
- detects WebView2 using Microsoft's official registry GUID and shows a link
  only when it is genuinely missing; the app then uses the browser fallback,
- preserves `backups/`, `history/`, `tmp/` and `jf_browser.settings.json` on uninstall.

The installer deliberately does **not** embed the WebView2 Evergreen Bootstrapper.
Windows Defender's ML engine flagged the unsigned NSIS installer containing and
executing that nested bootstrapper as `Trojan:Win32/Bearfoos.B!ml` (a false
positive; the bootstrapper itself is Microsoft-signed and scans clean). Removing
the nested bootstrapper keeps the installer clean. Microsoft's
[WebView2 distribution documentation](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution)
does allow including the bootstrapper or standalone installer, but that should be
combined with code signing and/or a Microsoft false-positive submission.

The executable keeps the technical filename `jellyfin-db-editor.exe`; the
user-facing product name, Start Menu shortcut, uninstall entry and installer
text use **Jellyfin DB Editor**. The installer also registers the App Paths
aliases `jellyfin-db-editor.exe` and `Jellyfin DB Editor.exe`.

### Windows Search

For an unpackaged Win32 app, no MSIX/AUMID registration is required. Windows
Search indexes the all-users Start Menu shortcut automatically, so typing
`Jellyfin` in Start should show **Jellyfin DB Editor**, with the shortcut
description as the search hint. The shortcut is created under:

```text
%ProgramData%\Microsoft\Windows\Start Menu\Programs\Jellyfin DB Editor\
```

If it does not appear immediately, give the search index a moment or rebuild
the Windows Search index. File Explorer searches inside `Program Files` only
when that location is included in the index; Start Menu search does not depend
on that.

The installer is unsigned; Windows SmartScreen may warn on first launch.

## Tests

The shared Python core/API suite is run with:

```powershell
python -m unittest discover -s tests -v
```

The Windows and Linux CI matrix is defined in `.github/workflows/tests.yml`.
The frozen package is additionally smoke-tested manually: native WebView2
window opens, the local server serves the UI, and the database operations use
the bundled Python runtime. The launcher itself has no separate automated test
suite.

## Runtime requirements

- WebView2 Evergreen Runtime (Edge). It is present on most Windows 10/11
  systems. The launcher checks it explicitly; without it the app falls back to
  the browser rather than silently using IE11.
- .NET Framework 4.6.2+ for pythonnet. Windows 10/11 normally has 4.8.
- If either is missing, use the `.exe` with `--browser`, or build with
  `--no-webview`.

## Options

```text
--browser           force the default browser + control window
--no-window         server only: no window and no browser
--db PATH           database path
--port PORT         fixed port (default: ephemeral)
--help              show help
--version           show version
```

## Notes

- Do not distribute the exe alone; it needs `_internal`, including the Python
  DLL, `ui/index.html`, pywebview and Python.Runtime.dll.
- The exe is unsigned. Windows SmartScreen may show a warning on first launch.
- The build script never includes `DB/`, `tmp/`, `history/`, test databases or
  local settings.
- The local server binds only to `127.0.0.1` by default.
