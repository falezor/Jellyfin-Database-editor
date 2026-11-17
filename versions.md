# Version history — Jellyfin DB editor

English translation of [`wersje.md`](wersje.md) (Polish source of truth).

Scheme: **X.Y.Z** — `X` milestone, `Y` major feature, `Z` fix.
Every version has a `vX.Y.Z` tag; tags are immutable, commits are never deleted.

## 1.6.x

### 1.6.30 (2026-11-17)
- **Pagination without the 20,000 cap:** `/api/list` accepts `offset`; **Load more** fetches another 2000 rows until the end (max 5000 per page). Tested on a copy with 46,625 items — `offset=20000` and `30000` return further items.
- Problem sorting still analyses all matching rows (it may be slower on very large libraries), but nothing is truncated at 20k.
- Added public `README.md`, `README-extensive.md` and `versions.md` (English) and the MIT license.
- Documentation update: the changes above.

### 1.6.29 (2026-11-17)
- **[4] Backup from the live file** — `.db` + `-wal`/`-shm` copy during Upload and a repeated signature check before replacement.
- **[8] End of temporary tables** — libraries/filters use CTE/`IN`; removed the `_libfolders`/`_roots` race.
- **[12] `stat` cache** — 8 s TTL, cleared on disk refresh and privilege changes.
- **[14] Pagination** — `limit` 2000 (max 20,000) and the **Load more** button; problem sorting still fetches up to 20,000 rows.
- **[13] Parallel port scan** — `ThreadPoolExecutor` (32 threads) instead of sequential probing.
- **[2] Orphan cleanup** — Settings section + `/api/orphans` (GET/POST), skips `UserData`.
- **[15] Old `jfdb_*` directories** — removed at startup if older than 24 h.
- **[17] Docker-aware SQL script** — `docker stop/start` or `systemctl`, no sudo on Windows.
- **[18] Token outside the URL** — `.db`/`.sql` export through a POST form.
- **[20] Platform docstrings** — Linux/Windows/macOS limitations.
- Documentation update: the changes above.

### 1.6.28 (2026-11-17)
- **Mode badge next to the language:** `USER` / `SUDO` / `ADMIN` / `ROOT` with a tooltip and colours; updates after a mode or language change.
- **Per-platform detection:** Windows — `ADMIN` only when the process is elevated (UAC), otherwise `USER`; Linux — `SUDO` after enabling ADMIN mode, `ROOT` when running as root; macOS — `ADMIN` for the admin group / `SUDO` during a sudo session; unknown platform → badge hidden.
- `/api/priv` returns `label`; documentation update.

### 1.6.27 (2026-11-17)
- **Platform-aware paths at startup:** `--db` in another platform's format is ignored (console warning) and the platform default is used; `/api/info` returns `platform`.
- **Database-not-loaded messages:** the “Database not loaded” screen and the red status in Settings show a path in the current platform's format (`C:\...` on Windows, `/...` on Linux), without a Linux default path on Windows.
- Documentation update: the changes above.

### 1.6.26 (2026-11-17)
- **Database status in Settings:** when no database is loaded, a red “Database not loaded” message with the reason, instead of a green entry with the path.
- **Disks without a database:** the Disks section (Settings and Connection) shows “No database loaded — disk list unavailable.”, the refresh button is disabled, and no `/api/disks` requests or 409 errors are produced.
- **“Check again” in the Disks section:** wired up the button handler (it did not work before).
- Documentation update: the changes above.

### 1.6.25 (2026-11-17)
- **Platform default path:** the “another path” dialog suggests a path in the system's style (`C:\...` on Windows, `/...` on Linux) instead of the current value; `/api/setup` returns `platform` and `db_default`.
- **Path style validation:** a Linux path on Windows (and vice versa) gives a clear error instead of attempting to open a relative path.
- **⏭ icon on the no-database screen** — skips the screen while keeping the menu and Settings available; the screen does not return on status refresh.
- **File picker from the computer:** Chrome/Edge use `showOpenFilePicker` (no freeze after cancel); other browsers use an off-screen file input with cleanup and focus release.
- Documentation update: the changes above.

### 1.6.24 (2026-11-17)
- **Windows without sudo:** ADMIN mode disabled on the server (`400` with a message) and in the UI; `platform` in `/api/priv`; the ADMIN button is hidden on the no-database screen.
- **File selection without ADMIN:** the system database picker uses `/api/pickpath` and only then opens the file — no sudo password prompt.
- **Loading from another path:** a custom text dialog instead of `prompt()` (Enter = OK, Esc/Cancel = close).
- **File-picker cancellation:** clears the field and removes focus — no UI freeze or Windows error beep; cancelling does not show an alert.
- Hidden console window for the Tk process on Windows.
- Documentation update: the changes above, platform differences and per-platform packaging analysis.

### 1.6.23 (2026-11-17)
- **Language selection on the “Database not loaded” screen** — a fixed PL/EN/DE/FR/ES/RU/IT/NL list below the dialog; switches the interface and the error reason without mixing languages.
- Database error reasons (`DbError`) are translated per request (`X-Lang`) instead of being stored permanently in Polish.
- Documentation update: the change above.

### 1.6.22 (2026-11-17)
- No `/api/disks` requests when no database is loaded — no more 409 errors in the console after an “empty” start.
- Documentation update: the change above.

### 1.6.21 (2026-11-17)
- The 🛠 **Setup** icon becomes permanent (editing the data folder and `jellyfin.db` when the configuration is wrong); when opened from the icon it has a **close button** (cancel). The first run still cannot be closed.
- Documentation update: the change above.

### 1.6.20 (2026-11-17)
- **Temporary 🛠 Setup icon** after Languages — starts the initial setup (data folder and `jellyfin.db` selection, no close button). To be removed after testing.
- Documentation update: the change above.

### 1.6.19 (2026-11-17)
- **Detection of default Jellyfin databases** during setup (Windows: ProgramData/LocalAppData/Roaming; Linux: /var/lib, /config, /data, ~/jellyfin; program folder).
- **`jellyfin.db` selection in setup** (path or system dialog) and storing **`db_path`** in the config; when starting without `--db`, the database is loaded from the config. File validation (SQLite + `BaseItems`); missing/`.sql` → error.
- `--db` is automatic by default: CLI → config → detected → platform default.
- Tests: candidates, `valid_db_file`, setup with a selected database, restart without `--db`.
- Documentation update: the changes above.

### 1.6.18 (2026-11-16)
- **Quick fixes from the analysis:** `[5]` `install_file` requires only a writable directory (with fallback), `[6]` `None` when checking `.bak` uniqueness is treated as occupied, `[9]` `PRIV_LOCK` as an RLock (safe `priv_disable`), `[10]` `reset_work` is error-resistant and recreates the connection, `[11]` 30 s timeout in `/api/load` and SQL import, `[19]` GET does not expose exceptions (generic message + log), `[21]` `/api/problems` returns `{items,total,limit}` with the information shown in the UI.
- Tests: unit (`.bak` name, RLock, install, normal/error reset, API shape) + live (400 timeout, server stays alive, backup/delete, list).
- Documentation update: description of the changes above; no separate version.

### 1.6.17 (2026-11-16)
- **Database loading progress** at startup/after saving setup: a percentage next to “Loading database…” in the line below the search box (copying and working-copy preparation phases).
- Documentation update: description of the change above; no additional functional changes.

### 1.6.16 (2026-11-16)
- **History outside `tmp`:** automatic entries in `<data_dir>/history/` (with migration from the old `tmp/history`); `tmp/` is only for session copies, removed on exit.
- **Manual backup progress:** bar and `%` (`backup`/`done` phases) in the Manual backups section.
- **Jellyfin start message** shown on every start (also from the Connection window), in the bar between the title and “Select problems”.

### 1.6.15 (2026-11-16)
- Documentation: packaging requirement (AppImage/EXE) — identical portable mode; planned installer with setup import (to do later).

### 1.6.14 (2026-11-16)
- Documentation for 1.6.13 (no code changes).

### 1.6.13 (2026-11-16)
- **Portable config:** `jf_browser.settings.json` next to the program (fallback to `~/.config` when the directory is not writable).
- A new version in another folder → no config → setup again; backups/history are created in the new location (test: config and backup in the new folder, old `backups/` unchanged).

### 1.6.12 (2026-11-16)
- Documentation for 1.6.11 (no code changes).

### 1.6.11 (2026-11-16)
- **Disk detection via `lsblk` + mount point → device mapping** (stored in `disk_map`):
  - mounted → folder check,
  - **`unmounted` (🟠)** — device present in the system but not mounted,
  - **`detached` (🔴)** — device disappeared (disk disconnected),
  - without `lsblk`, fallback to fstab; Windows/macOS unchanged (`unknown`).
- Settings/Connection refresh disks when opened and every 15 s.

### 1.6.10 (2026-11-16)
- Documentation for 1.6.9 (no code changes).

### 1.6.9 (2026-11-16)
- “Clear history” removes **only automatic history**; manual backups remain (the confirmation says so explicitly).
- **Trash button for every manual backup** (confirmation, file and entry removal, message with the path).

### 1.6.8 (2026-11-16)
- Numbering correction: manual backups and their documentation moved from 1.7.x to 1.6.x (commits unchanged, new tags `v1.6.6`/`v1.6.7`).
- Rule: fixes and extensions of existing features stay in `1.6.x` (including 1.6.25); `1.7.0` is reserved for a large change (e.g. AppImage).

### 1.6.7 (2026-11-16)
- Documentation for manual backups (no code changes).

### 1.6.6 (2026-11-16)
- **Manual backups as a separate history section** (at the bottom, Backup button moved below the list):
  - entry with Jellyfin version, date and size,
  - expanding shows **differences against the current database**: `+` in the backup/missing in the database (green) and `−` in the database/missing in the backup (red),
  - metadata in `backups/index.json`; backups are outside the history limit and are not removed automatically.

### 1.6.5 (2026-11-16)
- Version number update in the documentation (no code changes).

### 1.6.4 (2026-11-16)
- Fixed a translation key collision `backup_note` → `backup_manual_note` (the Backup button tooltip in History showed the description of the Upload `.bak` file).

### 1.6.3 (2026-11-16)
- Documentation for 1.6.2 + new `wersje.md` file (changelog grouped by version).

### 1.6.2 (2026-11-16)
- **Backup in History**: a note and tooltip explaining that backups created with the Backup button are not removed automatically and do not count towards the history limit.
- **Schema validation**: comparing the new database tables with the **original** instead of a fixed list (no more false alarms for valid databases; still detects a trimmed copy).

### 1.6.1 (2026-11-16)
- Documentation update for 1.6.0 (no code changes).

### 1.6.0 (2026-11-16)
- Connection: Jellyfin status **green** when running; removed the duplicated version row below the disks.
- History: **Backup** button → full copy in `<data_dir>/backups/` (outside history and the limit).
- “Reload from original”: **percentage progress** (copying and working-copy preparation).
- List sorted by **title** (`Name`), tie-break year/Id; removed path sorting.
- **“💡 suggested deletion”** hint for duplicates without existing files (if the group has at least one existing file).
- SQL import: clearer errors (reject `.db` and binary data, clean messages).
- Popup explaining missing tables instead of a raw error.
- System dialogs (tkinter) hidden when unavailable (headless).
- Disk statuses calculated from mounts (`/proc/mounts`): no access → red/orange; refresh when windows open.
- Subtle “Jellyfin will start shortly…” message after starting from Upload/Revert.

## 1.5.x

### 1.5.3 (2026-11-16)
- Documentation for `Host` validation (no code changes).

### 1.5.2 (2026-11-16)
- **`Host` header validation** (DNS rebinding): `localhost`, IP addresses and exactly `--host` are allowed; domains are rejected (403).

### 1.5.1 (2026-11-16)
- Documentation for schema validation (no code changes).

### 1.5.0 (2026-11-16)
- **Schema validation** before Upload and Revert: missing tables → blocked with confirmation (`force_schema`).

## 1.4.x

### 1.4.1 (2026-11-16)
- Documentation for the refactor (no code changes).

### 1.4.0 (2026-11-16)
- **Structure refactor**: interface in `ui/index.html`, translations in `i18n.py`; `jf_browser.py` ~2400 lines.
- UI loaded from a file (also in a bundle via `sys._MEIPASS`); startup reports a missing file.

## 1.3.x

### 1.3.1 (2026-11-16)
- Documentation for SQL import/export (no code changes).

### 1.3.0 (2026-11-16)
- **SQL** menu: import `.sql`/`.sql.gz` (streamed, stage progress) and export `.sql`/`.sql.gz`.
- Import mounts the database as `kind=upload` (Upload disabled); `sqlite3` CLI when available, otherwise the Python parser.

## 1.2.x

### 1.2.4 (2026-11-16)
- Documentation for 1.2.3 (no code changes).

### 1.2.3 (2026-11-16)
- `/proc/mounts` parsing as a function + `/proc/self/mounts` fallback; Docker mount tests (bind/named volume).

### 1.2.2 (2026-11-16)
- Connection: disks without highlighting and cursor; `fstab` skips `noauto`.

### 1.2.1 (2026-11-16)
- Connection: disks grouped by mount point (`/mnt/SG1`), information only, no counters or filtering.

### 1.2.0 (2026-11-16)
- **Disk statuses**: colours (green/orange/red/grey/blue), item counters, per-disk filter.
- **Deletion protection** for an unavailable disk: blocked without `force`, “delete anyway” prompt for Delete and SQL generation.
- “Select problems” skips red disks; “all disks” checkbox.

## 1.1.x

### 1.1.4 (2026-11-16)
- **Installer**: data folder selection (default next to the program), `tmp/history` creation, root/home validation, preparation for AppImage/EXE.

### 1.1.3 (2026-11-15)
- SQL script button name without parentheses.

### 1.1.2 (2026-11-15)
- Selection counter inside the SQL script button.

### 1.1.1 (2026-11-15)
- Red SQL script button, selection counter, “or” between actions.

### 1.1.0 (2026-11-15) — first release
- Translations pl/en/de/fr/es/ru/it/nl (UI + API messages).
- Steam-style top menu: Settings, Connection, History, Languages.
- Upload history: entries with Jellyfin version, date, `−/+`, details; revert and cleanup.
- File/folder selection through a system dialog.
- Compact Upload button below the list.
- SQL script window with copy and `.sql` download.
- Loading bars (global, buttons), background database loading screen.
- Settings without collapsible sections; history in `tmp/history`.
- Earlier base features: working-copy workflow, Upload with rebase, library/disk/problem detection, LIMITED/ADMIN modes.
