# Version history — Jellyfin DB editor

English version history.

Scheme: **X.Y.Z** — `X` main line / major change, `Y` new features, `Z` bugfix or very small change.
Every version has a `vX.Y.Z` tag and a GitHub release with a ZIP asset; tags are immutable, commits are never deleted.
Release ZIPs contain the program, UI, README/license and changelogs — no `DB/`, internal analysis or runtime data.

## 1.0.x

### 1.0.0 (2026-11-23)
- **Feature-complete 1.0 milestone:** no new user-facing functionality beyond 0.10.0; this release is the quality/version milestone for the stable line.
- **Compare databases:** the new **Compare** window diffs the current database with a `.bak` or another `.db`. It shows `+` items only in B, `−` items only in A and `~` changed items, with field-level old/new values and a JSON diff for `Data`; a banner warns when the files come from different Jellyfin instances.
- **`.bak` management:** configurable retention, startup prompt when the limit is exceeded, ADMIN/sudo-aware removal and clear removed/failed reporting.
- **UI and packaging:** Auto/Light/Dark theme, consistent startup loading indicator, two-column Settings, Connection text wrapping, dark startup background and a native window with a 800×600 minimum.
- **Port audit:** the desktop launcher binds a random free port on `127.0.0.1`; direct `--no-browser` uses 8099 with fallback 8100–8108. It does not bind Jellyfin's 8096/8920 and does not conflict with common Sonarr/Radarr/Prowlarr, SMB, Cockpit or NFS defaults.
- **Extensive `.deb` tests:** static package checks, install/reinstall/upgrade/remove/purge, CLI/launcher, API, Compare/`.bak`, GUI/WebKit under Xvfb, security/permissions, concurrency and performance.
- Tests: **50/50** source; `.deb` suite **136 tests** (134 pass, 2 skip), install/CLI **134 pass/0 fail**; `v1.0.0` GitHub release with ZIP and `.deb`.
- Documentation update: the changes above.

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
