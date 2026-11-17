# Jellyfin DB editor

A local, browser-based viewer and cleaner for Jellyfin's `jellyfin.db`. It runs a small local server; the original database and media files stay untouched until you explicitly use **Upload** or **Revert**.

## Features

- browse libraries, item types, series and movies, with search and per-disk filtering,
- detect missing files, unmounted or detached disks, duplicates, orphaned items and orphaned rows in related tables,
- safely delete items from a working copy, with protection for unavailable disks,
- **Upload** and **Revert** with a backup, version history and schema validation,
- import/export SQL, export the full database as `.db`, and generate a manual SQL cleanup script,
- **8 interface languages**, portable configuration, Linux and Windows support (macOS untested).

## Safety

- the original database is only changed by **Upload** or **Revert**,
- deletions happen on a working copy in `<data_dir>/tmp`, removed when the program exits,
- the pre-Upload backup is taken from the live file, and the new database passes `quick_check`,
- the server listens locally, requires a token and validates the `Host` header.

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
- `jf_browser_dokumentacja.md` — internal technical documentation (Polish).

## License

MIT — see [LICENSE](LICENSE).
