# Version history — Jellyfin DB editor

English version history.

Scheme: **X.Y.Z** — `X` main line / major change, `Y` new features, `Z` bugfix or very small change.
Every version has a `vX.Y.Z` tag and a GitHub release with a ZIP asset; tags are immutable, commits are never deleted.
Release ZIPs contain the program, UI, README/license and changelogs — no `DB/`, internal analysis or runtime data.

## 0.9.x

### 0.9.0 (2026-11-20)
- **Basic and advanced item editing:** double-click a list row or any record in the series/tree view. Basic mode edits `Name`, `SortName`, `ProductionYear`, `IndexNumber`, `ParentIndexNumber` and `SeriesName`; **Advanced** adds `Path`, `Data` JSON, hierarchy references and `ForcedSortName`/`OriginalTitle` when present. `Data` must be a JSON object, references must exist, `ParentId` cycles are rejected of any length, and `Id`/`Type` stay read-only.
- **Manual backups:** the History **Backup** button snapshots the live original database (with `-wal`/`-shm`); upload mode snapshots the working copy. A separate **Back up working copy** button saves the working copy to `backups/working-copy/` and is disabled when there are no changes.
- **Restore manual backups:** each backup has **Restore**, using the same safeguards as Upload (Jellyfin stopped, permissions, schema check, `quick_check`, optional `.bak`, atomic replace).
- **Mandatory stop for original backup:** the server refuses an original backup while Jellyfin is running; the UI stops it first and offers to start it again afterwards.
- **Automatic stop/start:** the new Connection option skips stop/start confirmations (including the manual **Stop** button) and restarts Jellyfin after Upload, Restore or original Backup. The stop itself is still performed.
- **Change data folder from Settings:** moves `history/` and `backups/` with progress, validates the target and reloads the original database. Upload-mode databases must be exported or loaded from a path first.
- Tests: 35/35; `v0.9.0` GitHub release with a lightweight ZIP asset.
- Documentation update: the changes above.

## 0.7.x

### 0.7.6 (2026-11-20)
- Public versioning reset: the main line now uses 0.x.x.
- `v0.7.6` GitHub release with a lightweight ZIP asset.
