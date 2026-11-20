# Historia wersji — Jellyfin DB editor

Schemat: **X.Y.Z** — `X` główna linia / duża zmiana, `Y` dodanie funkcji, `Z` poprawka lub bardzo mała zmiana.
Każda wersja ma tag `vX.Y.Z` oraz release GitHub z ZIP-em; tagi są niezmienne, commity nie są usuwane.
ZIP release zawiera program, UI, README/licencję i changelogi — bez `DB/`, `potencjalne poprawki` i danych runtime.
English version: [`Versions.md`](Versions.md).

## 0.9.x

### 0.9.0 (2026-11-20)
- **Podstawowa i zaawansowana edycja wpisów:** dwuklik na wierszu listy lub dowolnym rekordzie w widoku serialu/drzewa. Tryb podstawowy edytuje `Name`, `SortName`, `ProductionYear`, `IndexNumber`, `ParentIndexNumber` i `SeriesName`; **Zaawansowane** dodaje `Path`, `Data` JSON, referencje hierarchii oraz `ForcedSortName`/`OriginalTitle`, jeśli istnieją. `Data` musi być obiektem JSON, referencje muszą istnieć, cykle `ParentId` dowolnej długości są odrzucane, a `Id`/`Type` pozostają tylko do odczytu.
- **Ręczne kopie:** przycisk **Backup** w Historii kopiuje żywy oryginał bazy (z `-wal`/`-shm`); w trybie upload kopiuje kopię roboczą. Osobny przycisk **Backup kopii roboczej** zapisuje kopię roboczą w `backups/working-copy/` i jest wyszarzony, gdy nie ma zmian.
- **Przywracanie ręcznych kopii:** każda kopia ma **Przywróć**, z tymi samymi zabezpieczeniami co Upload (Jellyfin zatrzymany, uprawnienia, walidacja schematu, `quick_check`, opcjonalny `.bak`, atomowa podmiana).
- **Wymuszony stop przy backupie oryginału:** serwer odmawia backupu oryginału, gdy Jellyfin działa; UI zatrzymuje go najpierw i proponuje ponowne uruchomienie.
- **Automatyczny stop/start:** nowa opcja w Połączeniu pomija potwierdzenia stop/start (także ręcznego przycisku **Stop**) i uruchamia Jellyfina po Uploadzie, Przywracaniu lub backupie oryginału. Sam stop nadal jest wykonywany.
- **Zmiana folderu danych z Ustawień:** przenosi `history/` i `backups/` z postępem, waliduje cel i przeładowuje bazę z oryginału. Bazy w trybie upload trzeba najpierw wyeksportować albo wczytać ze ścieżki.
- Testy: 35/35; release `v0.9.0` z lekkim ZIP-em.
- Aktualizacja dokumentacji: powyższe zmiany.

## 0.7.x

### 0.7.6 (2026-11-20)
- Reset publicznej numeracji: linia main używa teraz 0.x.x.
- Release `v0.7.6` z lekkim ZIP-em.
