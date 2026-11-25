# Historia wersji — Jellyfin DB Editor

## 1.0.x

### 1.0.1 (2026-11-24)
- **Widoczność backupów:** okno Historii pokazuje folder ręcznych kopii i folder kopii roboczych oraz przyciski otwierające je w menedżerze plików.
- **Kopie robocze na liście:** kopie z przycisku **Backup kopii roboczej** dostają wpis w indeksie, są widoczne w **Ręcznych kopiach** i można je porównywać, przywracać oraz usuwać. Starsze nieindeksowane pliki są importowane automatycznie.
- **Unikalne ID backupów:** kopie utworzone w tej samej sekundzie dostają różne ID i nazwy w obu folderach.
- **Nazewnictwo i pakowanie:** UI, tytuł okna, metadane Windows, README i wpis `.desktop` w `.deb` używają spójnie **Jellyfin DB Editor**; techniczne nazwy pliku/pakietu pozostają `jellyfin-db-editor`.
- **Windows:** detekcja WebView2 używa oficjalnego GUID; w release są połączony instalator x86/x64 i paczka portable x64. Walidacja 32-bitowego Windows jest nadal w toku.
- Testy: **52/52** źródłowe; zaktualizowane testy statyczne/API/GUI `.deb` i wszystkie joby CI pakowania przechodzą.

### 1.0.0 (2026-11-23)
- **Kamień milowy 1.0 — funkcjonalnie kompletne:** brak nowych funkcji użytkownika względem 0.10.0; to wydanie jakościowo-wersjonowe dla stabilnej linii.
- **Porównywanie baz:** nowe okno **Porównaj** porównuje obecną bazę z `.bak` lub innym `.db`. Pokazuje `+` wpisy tylko w B, `−` tylko w A i `~` zmienione, z różnicami pól (stara/nowa wartość) i diffem JSON dla `Data`; baner ostrzega o innej instancji Jellyfina.
- **Zarządzanie `.bak`:** konfigurowalny limit, prompt przy starcie po przekroczeniu, usuwanie z ADMIN/sudo i raport usuniętych/nieusuniętych plików.
- **UI i pakowanie:** motyw Auto/Jasny/Ciemny, stały wskaźnik ładowania, dwukolumnowe Ustawienia, zawijanie w Połączeniu, ciemne tło startowe i natywne okno z minimum 800×600.
- **Audyt portów:** launcher desktopowy bierze losowy wolny port na `127.0.0.1`; bezpośredni `--no-browser` używa 8099 z fallbackiem 8100–8108. Nie zajmuje portów Jellyfina 8096/8920 i nie koliduje z typowymi portami Sonarr/Radarr/Prowlarr, SMB, Cockpit i NFS.
- **Ekstensywne testy `.deb`:** walidacja pakietu, instalacja/reinstall/upgrade/remove/purge, CLI/launcher, API, Compare/`.bak`, GUI/WebKit pod Xvfb, bezpieczeństwo/uprawnienia, współbieżność i wydajność.
- Testy: **50/50** źródłowe; suite `.deb` **136 testów** (134 pass, 2 skip), install/CLI **134 pass/0 fail**; release `v1.0.0` z ZIP-em i `.deb`.
- Aktualizacja dokumentacji: powyższe zmiany.

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
