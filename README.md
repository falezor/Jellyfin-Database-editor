# Jellyfin DB editor

A local, browser-based viewer and cleaner for Jellyfin's `jellyfin.db`. It runs a small local server; the original database and media files stay untouched until you explicitly use **Upload** or **Revert**.

## Features

- browse libraries, item types, series and movies, with search and per-disk filtering,
- **orphan cleaning for related tables** — preview sample rows, skip `UserData`, and ignore empty/zero-GUID references,
- detect missing files, unmounted or detached disks, duplicates, orphaned items and orphaned rows in related tables,
- safely delete items from a working copy, with protection for unavailable disks,
- **Upload** and **Revert** with a backup, version history and schema validation,
- import/export SQL, export the full database as `.db`, and generate a manual SQL cleanup script,
- **8 interface languages**, portable configuration, Linux and Windows support (macOS untested).

## Safety

- the original database is only changed by **Upload** or **Revert**,
- deletions happen on a working copy in `<data_dir>/tmp`, removed when the program exits,
- the pre-Upload backup is taken from the live file, and the new database passes `quick_check`,
- the server listens locally, validates the `Host` header and protects API/image reads with a session cookie or token.

## Requirements

- Python 3 (standard library only),
- a graphical browser,
- Jellyfin 10.10+ database schema (EF Core era).

## Quick start

```bash
python3 jf_browser.py
# http://127.0.0.1:8099
```

Optional: `python3 jf_browser.py --db /path/to/jellyfin.db`. On first run, the setup wizard asks for a data folder and a database.

## Documentation

- **[README-extensive.md](README-extensive.md)** — full feature, configuration, API and limitations documentation.
- **[Versions.md](Versions.md)** — English version history.

## License

MIT — see [LICENSE](LICENSE).
