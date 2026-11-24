# Jellyfin DB Editor

A local viewer and cleaner for Jellyfin's `jellyfin.db`. It runs a small HTTP
server on `127.0.0.1` and opens a native desktop window (WebView2 on Windows,
GTK/WebKit in the `.deb`) or the default browser. The original database and
media files stay untouched until you explicitly use **Upload** or **Revert**.

<img width="1649" height="898" alt="Jellyfin DB Editor main window" src="https://github.com/user-attachments/assets/d7cda185-fb97-42fd-a4cd-714484596766" />

<img width="1655" height="901" alt="Jellyfin DB Editor item editor" src="https://github.com/user-attachments/assets/25d13f14-5055-4dce-888c-9682308917d3" />

## Downloads

Version **1.0.1**:

| Package | Download |
|---|---|
| Windows installer (x86/x64) | [`jellyfin-db-editor_1.0.1_windows_x86_x64_setup.exe`](https://github.com/falezor/Jellyfin-Database-editor/releases/download/v1.0.1/jellyfin-db-editor_1.0.1_windows_x86_x64_setup.exe) |
| Windows x64 portable | [`jellyfin-db-editor_1.0.1_windows_x64_portable.zip`](https://github.com/falezor/Jellyfin-Database-editor/releases/download/v1.0.1/jellyfin-db-editor_1.0.1_windows_x64_portable.zip) |
| Linux `.deb` (standard Python) | [`jellyfin-db-editor_1.0.1.deb`](https://github.com/falezor/Jellyfin-Database-editor/releases/download/v1.0.1/jellyfin-db-editor_1.0.1.deb) |
| Source archive | [`jellyfin-db-editor_1.0.1.zip`](https://github.com/falezor/Jellyfin-Database-editor/releases/download/v1.0.1/jellyfin-db-editor_1.0.1.zip) |

The Windows installer selects the x64 or x86 payload automatically. It installs
for all users in `Program Files` and creates a Start Menu shortcut. The
installer is unsigned, so Windows SmartScreen may warn on first launch.

## Platform support

| Platform | Status |
|---|---|
| **Windows 10/11 x64** | **Supported** — native WebView2 window or browser fallback |
| **Linux** | **Supported** — standard-Python `.deb` with GTK/WebKit, or run the source with a browser |
| **Windows 32-bit** | **Pending** — the combined installer contains an x86 payload, but full 32-bit Windows validation is still pending |
| **macOS** | **Pending** |
| **Headless server / remote UI** | **Pending** — the current interface is local-desktop oriented; remote/headless access is planned separately |

## Features

- browse libraries, item types, series and movies, with search and per-disk filtering,
- edit basic and advanced metadata (Data JSON, path, hierarchy) from a double-click dialog in the list or series tree,
- **orphan cleaning for related tables** — preview sample rows, skip `UserData`, and ignore empty/zero-GUID references,
- **change the program data folder from Settings** — moves history and backups with progress,
- detect missing files, unmounted or detached disks, duplicates, orphaned items and orphaned rows in related tables,
- safely delete items from a working copy, with protection for unavailable disks,
- **Upload** and **Revert** with a backup, version history and schema validation,
- restore manual backups with the same safeguards as Upload,
- **backup visibility:** the History window shows the manual-backup and working-copy folders with **Open folder** buttons; working-copy backups are listed alongside original backups and can be restored or deleted,
- stop Jellyfin automatically before Upload/Restore/original backup, with an optional no-confirmation mode,
- import/export SQL, export the full database as `.db`, and generate a manual SQL cleanup script,
- **Compare** tab: compare databases and changes; field-level differences, JSON diff and instance warnings,
- **8 interface languages**, portable configuration, native window on Windows/Linux and browser fallback.

Screenshots:

<img width="760" height="629" alt="Jellyfin DB Editor editor dialog" src="https://github.com/user-attachments/assets/feee6aca-7439-40e4-ae2d-d0e7a25b5f05" />

<img width="754" height="770" alt="Jellyfin DB Editor metadata fields" src="https://github.com/user-attachments/assets/723020a4-35b2-4116-b1d0-b221bc8a72c6" />

<img width="400" height="83" alt="Jellyfin DB Editor orphan cleaning" src="https://github.com/user-attachments/assets/46d880c8-e25a-4312-b18c-fdf36c181625" />

<img width="675" height="300" alt="Jellyfin DB Editor upload and history" src="https://github.com/user-attachments/assets/d6df1a98-b39e-4e10-b092-76fefc557477" />

<img width="448" height="324" alt="Jellyfin DB Editor connection settings" src="https://github.com/user-attachments/assets/c204bfae-206d-4918-86e6-bdf0b6cd893c" />

<img width="451" height="212" alt="Jellyfin DB Editor SQL tools" src="https://github.com/user-attachments/assets/64285f7e-215a-4a37-b3ca-3ac9e5171742" />

<img width="860" height="666" alt="Jellyfin DB Editor language and theme settings" src="https://github.com/user-attachments/assets/4001eedb-210d-4c04-8456-f574d2bb2257" />

<img width="948" height="733" alt="Jellyfin DB Editor compare view" src="https://github.com/user-attachments/assets/06b40880-0f75-41b4-8dda-e1a42f63294b" />

## Safety

- the original database is only changed by **Upload** or **Revert**,
- deletions happen on a working copy in `<data_dir>/tmp`, removed when the program exits,
- the pre-Upload backup is taken from the live file, and the new database passes `quick_check`,
- manual backups are stored in `<data_dir>/backups`; working-copy backups in `<data_dir>/backups/working-copy`,
- the server listens only on `127.0.0.1`, validates the `Host` header and protects API/image reads with a session cookie or token.

## Requirements

### Windows

- Windows 10 or newer, x64 for the supported build,
- Microsoft Edge WebView2 Runtime for the native window (the installer falls back to the browser if it is missing).

### Linux

- Python 3.10+ and the packages declared by the `.deb`,
- a graphical desktop for the native GTK/WebKit window; browser mode also works.

## Quick start

### Windows

Run the installer, or unpack the x64 portable ZIP and start `jellyfin-db-editor.exe`.
The application stores user data outside `Program Files`.

### Linux `.deb`

```bash
sudo apt install ./jellyfin-db-editor_1.0.1.deb
jellyfin-db-editor
```

### From source

```bash
python3 jf_browser.py
# http://127.0.0.1:8099
```

Optional: `python3 jf_browser.py --db /path/to/jellyfin.db`. On first run, the
setup wizard asks for a data folder and a database.

## Documentation

- **[README-extensive.md](README-extensive.md)** — full features, configuration, API and limitations.
- **[Versions.md](Versions.md)** — English version history.
- **[Wersje.md](Wersje.md)** — Polish version history.
- **[README-extensivePL.md](README-extensivePL.md)** — extensive documentation in Polish.

## License

MIT — see [LICENSE](LICENSE).
