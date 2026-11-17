# Jellyfin DB editor — functional documentation

**Version:** 1.6.30 (2026-11-17)  
This document describes the program from the user's point of view. It is updated with every release. Changelog: [`versions.md`](versions.md). # change to eng

---

## 1. What the program does

Jellyfin DB editor is a local viewer and cleaner for the `jellyfin.db` SQLite database. It runs on your computer or server, and the interface opens in a browser at `http://127.0.0.1:8099`.

It is intended for:

- browsing libraries, movies, series, seasons and episodes directly from the database — even while Jellyfin is stopped,
- finding items that point to missing files or unavailable disks,
- detecting duplicates and items detached from libraries,
- safely deleting such items from a working copy,
- replacing the Jellyfin database with a backup and version history,
- importing and exporting SQL or the full database as `.db`.

The program **never modifies media files**. The original database is only changed by **Upload** or **Revert**.

Why it exists: Jellyfin 10.10+ may fail to remove a dead item (for example, `FOREIGN KEY constraint failed`), and such an item blocks re-adding the files. This previously had to be done manually with `sqlite3`.

---

## 2. Data safety

Workflow:

1. When a database is loaded, the program creates a **working copy** in `<data_dir>/tmp/jfdb_*`.
2. Browsing, searching and deleting only affect the working copy.
3. **Reload from original** discards changes and fetches a fresh copy.
4. **Upload** replaces the original Jellyfin database with the working copy.
5. **Revert** restores a selected version from history.

Additional safeguards:

- the original is copied together with `-wal`/`-shm` files,
- if the file signature changes during work, the program performs a **rebase** — deletions are replayed by GUID on a fresh copy,
- before Upload, the program checks that Jellyfin is not running,
- the new database must pass `PRAGMA quick_check`,
- tables in the new database are compared with the original; missing tables require confirmation,
- the optional `.bak` backup is created from the **live file**, not from an old snapshot,
- the server listens locally, requires a token and validates the `Host` header (DNS rebinding protection).

Exports and history copies contain the **entire database**, including accounts and password hashes. Do not share them publicly.

---

## 3. Requirements and platforms

- **Python 3** — standard library only; no PyPI packages are required.
- **Graphical browser** — Chromium/Chrome, Edge, Firefox or another modern browser.
- **Jellyfin 10.10+** — EF Core era database schema.
- Read access to the database file; Upload requires write access (or ADMIN mode on Linux).

Platform support:

| Platform | Status | Notes |
|---|---|---|
| Linux | full | sudo, systemd/Docker, `/proc`, `/etc/fstab`, `lsblk` |
| Windows | supported | no sudo/ADMIN; disks checked by path existence; file picker via tkinter |
| macOS | untested | no `/proc`; sudo works like on Linux; systemd service control unavailable |

On Windows the program does not require administrator rights. If the process/EXE is started elevated (UAC), the badge shows `ADMIN`; during a normal launch it shows `USER`.

---

## 4. Quick start

### Linux

```bash
# recommended: stop Jellyfin before editing
sudo systemctl stop jellyfin

sudo python3 jf_browser.py
# open http://127.0.0.1:8099
```

The program still asks for confirmation before Upload if Jellyfin is running.

### Windows

```powershell
python jf_browser.py
```

or launch the script/EXE. The interface opens in the browser; if it does not open automatically, use the address printed in the console.

### Selecting a database

```bash
python3 jf_browser.py --db /var/lib/jellyfin/data/jellyfin.db
```

Without `--db`, the program uses:

1. the path saved in the config (`db_path`),
2. an automatically detected default database,
3. the platform default path.

A path in another platform's format (for example `/var/...` on Windows) is ignored with a warning; the platform default is used instead.

---

## 5. First run and data folder

On first run (no `data_dir` in settings) a **setup wizard** appears:

- it suggests the program directory; if that is not writable — `~/JellyfinDBeditor`,
- it allows choosing a folder through a system dialog,
- it detects typical Jellyfin databases (Windows: `%ProgramData%\Jellyfin\Server\data`, `%LOCALAPPDATA%\jellyfin\data`, `%APPDATA%\Jellyfin\Server\data`; Linux: `/var/lib/jellyfin/data`, `/config/data`, `/data`, `~/jellyfin/data`, program folder),
- it allows selecting a `jellyfin.db` file — the path is saved as `db_path` and used on subsequent starts.

Data layout:

```text
<data_dir>/
  tmp/
    jfdb_XXXX/            # session working copy, removed on exit
      orig/jellyfin.db    # original snapshot
      work.db             # working copy — deletions happen here
  history/
    index.json            # automatic history metadata
    20261117-193000/
      jellyfin.db         # uploaded database copy
  backups/                # manual backups, outside the history limit
```

Settings (`data_dir`, `db_path`, `jf_port`, `jf_service`, `history_max`, `disk_map`) are stored by default in **`jf_browser.settings.json` next to the program** (portable mode). If the program directory is not writable, `~/.config/jf_browser/settings.json` is used.

A new program version in a different folder has no config, so it goes through setup again and creates its own data. This allows several versions to coexist.

Other leftover temporary files (`jfdb_*`, `jfup_*`, `jfexp_*`, `import_*`) are removed at startup if they are older than 24 hours.

---

## 6. Interface

### Top bar

`Jellyfin DB editor` · **Settings** · **Connection** · **History** · **SQL** · **Languages ▾** · 🛠 **Setup**

- **Languages** — switches the interface language immediately; the choice is stored in `localStorage`.
- **🛠 Setup** — reopens the data-folder and database configuration; it can be cancelled.
- Next to the language code there is a mode badge: **USER / SUDO / ADMIN / ROOT** (see section 11).

### Left panel

- library or type selection,
- sorting: name, problems first, only problems,
- search by name, path and series name,
- disk filter (`Disk: … ✕`),
- item list with thumbnail, name, path and problem reasons,
- **Load more** — loads the next 2000 results; there is no hard 20,000 cap,
- **Upload** — replaces the original database with the working copy.

### Right panel

- title and details of the selected item,
- **Select problems**, optionally including items on red disks,
- **Select all**, **Clear**,
- **Delete selected** — deletes items from the working copy only,
- **SQL script manual** — generates a script for manual execution,
- item tree (series → seasons → episodes).

### Settings

Settings include:

- database status and the number of pending changes,
- data folder,
- reload from original,
- backup-before-Upload toggle,
- loading a database from another path or file,
- exporting the working copy,
- **Orphans in related tables** section,
- **Disks** section,
- history limits and cleanup.

### Connection

Shows Jellyfin status, port, disk list, service start/stop buttons and ADMIN mode. On Windows, systemd service control is unavailable.

### History

Two sections:

- **automatic** — entries created by each Upload (date, version, `−N +M`, missing file, Restore),
- **manual backups** — created with the **Backup** button, outside the history limit; they show differences against the current database.

Each manual backup can be removed with a trash button. “Clear history” removes only automatic entries — manual backups are kept.

### SQL

- import `.sql` and `.sql.gz` (streamed, with progress),
- export `.sql` and `.sql.gz`,
- manual SQL script window with Copy and Download buttons.

### “Database not loaded” screen

Shown when no database has been loaded. It contains:

- buttons to load a path, a file from the computer, or a file through a system dialog,
- language list (PL/EN/DE/FR/ES/RU/IT/NL),
- **⏭** icon — skips the screen and leaves the menu and Settings available.

---

## 7. Search and pagination

The list is sorted alphabetically by title (`Name`), with ties broken by year and Id.

- First fetch: up to **2000** items.
- **Load more** fetches another 2000 and appends them to the list.
- There is no 20,000 cap — you can page to the end of the results.
- The API accepts `limit` (max 5000 per page) and `offset` (no upper limit).
- **Problems first** and **Only problems** must analyse all matching rows, so they may be slower on very large libraries.
- The problem list has a separate limit of 5000; the UI then shows “Problems: 5000 of N items (limit)”.

Search covers name, path and series name. The disk filter can be cleared with ✕.

---

## 8. Problem detection

The program detects:

| Problem | Rule |
|---|---|
| missing file/folder | path exists in the database but not on disk, and the root is `ok`/`unknown` |
| unavailable disk/folder | as above, but the root has a status other than `ok`/`unknown` |
| item outside libraries | row under a folder detached from a library |
| duplicate path | the same (`Path`, `Type`) pair more than once |
| duplicated item | the same (type, case-insensitive name, year) at the top level of a library |
| duplicated episode | the same (`SeriesId`, `ParentIndexNumber`, `IndexNumber`) triple |

File existence is three-state: `True` / `False` / `None`. `None` means no permission and is **not** treated as a missing file — the item gets a warning about incomplete results.

### Disk statuses

| Status | Colour | Meaning |
|---|---|---|
| `ok` | 🟢 | folder exists and is not empty |
| `unmounted_fstab` | 🟠 | listed in fstab, absent from `/proc/mounts` |
| `empty` | 🟠 | empty folder without its own mount |
| `missing_mounted` | 🟠 | disk mounted, folder missing |
| `empty_mounted` | 🟠 | disk mounted, folder empty |
| `missing` | 🔴 | folder missing and no fstab entry |
| `unmounted` | 🟠 | device present in the system but not mounted |
| `detached` | 🔴 | device disappeared from the system |
| `unknown` | ⚪ | not checked (database from another machine / no permission) |
| no items | 🔵 | disk with no database references |

The path → device mapping (`lsblk`) is stored in `disk_map`, so the program can distinguish “unmounted” from “detached”.

### Docker

Run the program in the same container as Jellyfin if you want to see its paths and mounts. On the host, container paths may not exist — statuses then become `unknown`. Grouping by bind mounts and volumes follows destination paths.

---

## 9. Deleting items

- `BaseItems` rows are deleted from the working copy in a transaction, in batches of 500 (max 50,000 per operation).
- **Disk protection:** if the selected item's root has status `missing` (🔴), the server refuses to delete it; the UI offers “delete anyway”.
- An orange root is allowed, but the UI warns.
- “Select problems” skips items on red disks by default; the “all disks” checkbox includes them.
- Deleting a series does not automatically remove its seasons and episodes — use “Select all” in the tree.
- **Orphans in related tables** (for example images) are not removed together with `BaseItems`. Use the separate Settings section — it skips `UserData` and reports the number of removed rows.

### SQL script manual

Instead of clicking Delete, you can generate a script:

- `systemctl stop/start` or `docker stop/start` — depending on the detected service,
- `sqlite3 … DELETE … IN (…)`,
- `SELECT changes(); COMMIT;`.

On Windows the script contains comments instead of `sudo`/systemd. The script can be copied or downloaded as `.sql`.

---

## 10. Upload, backup and history

### Upload

1. The program checks whether Jellyfin is running and offers to stop it.
2. Optionally it creates a backup `<database>-YYYY-MM-DD_HH-MM-SS.bak` from the live file.
3. It creates the new database from the working copy and runs `quick_check`.
4. It compares the schema with the original; missing tables require confirmation.
5. It atomically replaces the file, preserving owner and permissions.
6. It removes old `-wal`/`-shm` files, writes a history entry and reloads the database.

Upload is disabled for a database loaded “from the computer” (export-only mode) and when there are no changes.

### History and Revert

- Every Upload stores a full copy in `history/<id>/` and metadata in `index.json`.
- History limit: **1–50**, default **5**; changing the limit trims the oldest entries.
- **Revert** restores a selected entry with the same safeguards as Upload (Jellyfin stopped, backup, schema, `quick_check`). It does not create a new history entry.
- A missing copy file is marked next to the date and Restore is disabled.

### Manual backups

The **Backup** button in the History window creates a full copy in `<data_dir>/backups/`. Backups are outside the history limit and show differences against the current database (`+` in the backup / `−` in the database). They can be removed individually with the trash button.

---

## 11. Privilege modes

| Mode | Meaning |
|---|---|
| **USER** / LIMITED | normal user; no access to protected folders or service start/stop |
| **SUDO** | active sudo session on Linux (macOS untested); expires after 15 minutes of inactivity |
| **ADMIN** | elevated privileges (Windows UAC, macOS admin group) |
| **ROOT** | program running as root |

- On Linux, the sudo password is passed only on stdin and is never stored.
- The helper process exposes only `ping`, `stat`, `read`, `install`, `remove` and `svc`.
- On Windows there is no sudo mode; the badge shows `USER` or `ADMIN` based on `IsUserAnAdmin()`.
- macOS is untested; root/admin-group/sudo detection is prepared.

---

## 12. SQL, import and export

- **SQL import** — `.sql` or `.sql.gz` is streamed, decompressed and executed by the `sqlite3` CLI (if available) or the built-in parser. The result becomes the working copy as a “from computer” database (export only).
- **SQL export** — full `iterdump()` dump to `.sql` or `.sql.gz`.
- **Database export** — the working copy as `.db`.
- Exports are downloaded through a POST form, so the token does not appear in the URL or browser history. Old GET `?t=` links still work.

The SQL window also provides the manual cleanup script (section 9) with Copy and Download buttons.

---

## 13. Configuration and flags

| Flag | Default | Meaning |
|---|---|---|
| `--db` | automatic | database path; order: CLI → config → detected → platform default |
| `--host` | `127.0.0.1` | local server address |
| `--port` | `8099` | port; if busy → next one (up to +9) |
| `--no-browser` | off | do not open the browser |
| `--jf-service` | detected | `systemd:name` or `docker:container_name` |
| `--jf-port` | from `network.xml` / 8096 | Jellyfin HTTP port, this session only |
| `--no-service-check` | off | do not block Upload while Jellyfin is running |

Environment variables:

| Variable | Meaning |
|---|---|
| `JF_BROWSER_CONFIG` | settings file path |
| `JF_SUDO_CMD` | sudo replacement (testing) |
| `JF_FORCE_LIMITED` | pretend there is no root (testing) |
| `APPIMAGE` | program directory inside an AppImage |

Settings can be changed in the UI (Settings, Setup, Connection, History). The config is portable and lives next to the program when that folder is writable.

---

## 14. Local API

The program exposes a local HTTP API used by the interface. Most POST operations require the `X-Token` header (the token is injected into the page).

| Route | Method | Description |
|---|---|---|
| `/api/info` | GET | database state, `nodb`, `platform`, `loading`, `setup` |
| `/api/setup` | GET/POST | configuration, `db_default`, `db_options` |
| `/api/types` | GET | libraries or types |
| `/api/list` | GET | list: `type`, `sort`, `q`, `disk`, `limit`, `offset` |
| `/api/tree` | GET | item tree |
| `/api/problems` | GET | problems `{items,total,limit}` |
| `/api/disks` | GET | disks and mount points |
| `/api/export` | GET/POST | working copy `.db` |
| `/api/export-sql` | GET/POST | SQL dump / `.sql.gz` |
| `/api/import-sql` | POST | SQL dump import |
| `/api/orphans` | GET/POST | orphans in related tables |
| `/api/open` | POST | open a database from a path |
| `/api/load` | POST | load a database file from the computer |
| `/api/delete` | POST | delete items |
| `/api/upload` | POST | Upload with backup |
| `/api/revert` | POST | restore a history entry |
| `/api/reload` | POST | discard changes |
| `/api/history` | GET/POST | history and cleanup |
| `/api/backup` / `/api/backups` | POST/GET | manual backups |
| `/api/settings` | POST | limits and data folder |
| `/api/priv` | GET/POST | privilege mode |
| `/api/service` | GET/POST | Jellyfin service |
| `/api/jellyfin` | GET/POST | Jellyfin detection/port |
| `/api/pickpath` / `/api/pickdir` | POST | system file/folder dialogs |

Errors are returned as JSON `{error}`; a missing database gives `409 {nodb:true}`, and missing privileges give `403 need_admin`.

---

## 15. Languages

The interface and API messages are available in:

**Polish, English, German, French, Spanish, Russian, Italian, Dutch**.

The language can be changed in the top menu or on the “Database not loaded” screen. The choice is remembered by the browser. Server error messages are translated based on the `X-Lang` header.

---

## 16. Limitations and notes

- The program does not automatically delete related rows; use the separate orphans section (it skips `UserData`).
- Disk checks work best when the program sees the same paths and mounts as Jellyfin. For a database from another machine, statuses may be `unknown`.
- On macOS there is no `/proc` — the program detects a missing folder but not a detached volume.
- systemd `automount` mounts without an fstab entry may not be recognized as expected.
- SQL import without the `sqlite3` CLI uses the slower built-in parser.
- In LIMITED mode, thumbnails from protected folders may not be displayed.
- Problem sorting on very large libraries may be slower — it analyses all matching rows.
- AppImage/EXE packaging is not ready yet; it is planned for `1.7.0`.
- macOS and some service-control features have not been tested on a live system.

---

## 17. Development and versioning

- Current version: **1.6.30**.
- Version scheme: `X.Y.Z`; `X` — milestone, `Y` — major feature, `Z` — fix.
- Every version has a `vX.Y.Z` tag; changes are listed in [`wersje.md`](wersje.md).
- This document is updated with every release.
- Next steps: AppImage/EXE packaging, installer, automated tests in the repo, changing the data folder from Settings.

---

## 18. License

This project is released under the **MIT** license. See [`LICENSE`](LICENSE).
