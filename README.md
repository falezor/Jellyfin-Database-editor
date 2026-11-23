# Jellyfin DB editor

A local, browser-based viewer and cleaner for Jellyfin's `jellyfin.db`. It runs a small local server; the original database and media files stay untouched until you explicitly use **Upload** or **Revert**.

<img width="1649" height="898" alt="image" src="https://github.com/user-attachments/assets/d7cda185-fb97-42fd-a4cd-714484596766" />

<img width="1655" height="901" alt="image" src="https://github.com/user-attachments/assets/25d13f14-5055-4dce-888c-9682308917d3" />



## Features

- browse libraries, item types, series and movies, with search and per-disk filtering,
- edit basic and advanced metadata (Data JSON, path, hierarchy) from a double-click dialog in the list or series tree,
- 
  <img width="760" height="629" alt="image" src="https://github.com/user-attachments/assets/feee6aca-7439-40e4-ae2d-d0e7a25b5f05" />
  
  <img width="754" height="770" alt="image" src="https://github.com/user-attachments/assets/723020a4-35b2-4116-b1d0-b221bc8a72c6" />


- **orphan cleaning for related tables** — preview sample rows, skip `UserData`, and ignore empty/zero-GUID references,
  
<img width="400" height="83" alt="image" src="https://github.com/user-attachments/assets/46d880c8-e25a-4312-b18c-fdf36c181625" />

- **change the program data folder from Settings** — moves history and backups with progress,
- detect missing files, unmounted or detached disks, duplicates, orphaned items and orphaned rows in related tables,
- safely delete items from a working copy, with protection for unavailable disks,
- **Upload** and **Revert** with a backup, version history and schema validation,
  
  <img width="675" height="300" alt="image" src="https://github.com/user-attachments/assets/d6df1a98-b39e-4e10-b092-76fefc557477" />

- restore manual backups with the same safeguards as Upload,
- save a separate working-copy backup from the right panel,
- stop Jellyfin automatically before Upload/Restore/original backup, with an optional no-confirmation mode,
  
<img width="448" height="324" alt="image" src="https://github.com/user-attachments/assets/c204bfae-206d-4918-86e6-bdf0b6cd893c" />

- import/export SQL, export the full database as `.db`, and generate a manual SQL cleanup script,
  
  <img width="451" height="212" alt="image" src="https://github.com/user-attachments/assets/64285f7e-215a-4a37-b3ca-3ac9e5171742" />

- **8 interface languages**, portable configuration, Linux and Windows support (macOS untested).
  
<img width="860" height="666" alt="image" src="https://github.com/user-attachments/assets/4001eedb-210d-4c04-8456-f574d2bb2257" />

- **Compare** tab: compare databases and changes; the drop-down lists the original session backups (`*.bak`) from `/var/lib/jellyfin/data`
  
  <img width="948" height="733" alt="image" src="https://github.com/user-attachments/assets/06b40880-0f75-41b4-8dda-e1a42f63294b" />


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

or install the `.deb` for the native window

## Documentation

- **[README-extensive.md](README-extensive.md)** — full feature, configuration, API and limitations documentation.
- **[Versions.md](Versions.md)** - English version history.
- `README-extensivePL.md` — extensive documentation in Polish.

## License

MIT — see [LICENSE](LICENSE).
