# Historia wersji — Jellyfin DB editor

Schemat: **X.Y.Z** — `X` główna linia / duża zmiana, `Y` dodanie funkcji, `Z` poprawka lub bardzo mała zmiana.
Każda wersja ma tag `vX.Y.Z` oraz release GitHub z ZIP-em; tagi są niezmienne, commity nie są usuwane.
ZIP release zawiera program, UI, README/licencję i changelogi — bez `DB/`, `potencjalne poprawki` i danych runtime. `v1.6.31` pozostaje pełnym ZIP-em (legacy).
English translation: [`Versions.md`](Versions.md).

## 1.7.x

### 1.7.6 (2026-11-19)
- **Wersja w górnym pasku:** obok oznaczenia języka widnieje wersja programu, z tą samą czcionką, kolorem i wielkością.
- **Stały prawy róg:** język i wersja są nieruchome po prawej; plakietka `USER` / `SUDO` / `ADMIN` / `ROOT` pojawia się na lewo od nich, zamiast je przesuwać.
- Testy: 17/17; release `v1.7.6` z lekkim ZIP-em.
- Aktualizacja dokumentacji: powyższe zmiany.

### 1.7.5 (2026-11-19)
- **Bezpieczniejsze sieroty:** puste wartości i pusty GUID nie są już traktowane jako referencje do usunięcia, więc wiersze z wartością „brak powiązania” zostają.
- **Podgląd przed czyszczeniem:** „Wyczyść sieroty” pokazuje do trzech przykładowych wierszy na tabelę (wartości skrócone, BLOB-y zamaskowane) oraz listę `tabela.kolumna` przed zmianą kopii roboczej.
- Testy: 16/16; testy API czekają teraz na asynchroniczne wczytanie bazy. Release `v1.7.5` z lekkim ZIP-em.
- Aktualizacja dokumentacji: powyższe zmiany.

### 1.7.4 (2026-11-19)
- **Setup nie odrzuca poprawnej bazy przy odczycie WAL w trybie read-only:** jeśli SQLite nie może sprawdzić `BaseItems` z powodu dostępu do WAL/SHM, uprawnień, blokady lub błędu I/O, ścieżka jest przyjmowana i weryfikowana ponownie przy właściwym wczytaniu (ten sam mechanizm co „Odśwież z oryginału”).
- Prawdziwa baza inna niż Jellyfin (brak `BaseItems`, brak WAL) nadal jest odrzucana.
- Testy: 14/14; release `v1.7.4` z lekkim ZIP-em.
- Aktualizacja dokumentacji: powyższe zmiany.

### 1.7.3 (2026-11-19)
- **Sieroty w tabelach:** etykiety `tabela.kolumna` zamiast powielonych nazw tabel.
- **Bez podwójnego liczenia:** licznik per tabela liczy unikalne wiersze, gdy kilka kolumn wskazuje brakujące `BaseItems.Id` (np. `AncestorIds`).
- Testy: 11/11; release `v1.7.3` z lekkim ZIP-em.
- Aktualizacja dokumentacji: powyższe zmiany.

### 1.7.2 (2026-11-18)
- **Cache wersji Jellyfina aktualizowany przy każdym udanym wykryciu** — kolejne wykrycie nadpisuje poprzednią wersję; najnowsza trafia do anchor/Upload/Backup.
- Test: 11/11; release `v1.7.2` z lekkim ZIP-em.
- Aktualizacja dokumentacji: powyższe zmiany.

### 1.7.1 (2026-11-18)
- **Wersja Jellyfina w historii:** ostatnio wykryta wersja jest zapisywana w configu i używana dla anchor/Upload/Backup, gdy Jellyfin jest zatrzymany; fallback z poprzednich wpisów.
- Jeśli wersja nigdy nie została wykryta, wpis pozostaje „nieznany” — wersji Jellyfina nie da się odczytać z pliku bazy.
- Testy: 10/10; release `v1.7.1` z lekkim ZIP-em.
- Aktualizacja dokumentacji: powyższe zmiany.

### 1.7.0 (2026-11-18)
- **Wydanie funkcji 1.7.0** (1.6.33 było wydaniem pośrednim przed zmianą numeracji).
- Anchor sesji, opcjonalny limit rozmiaru historii, jeden `.bak` na sesję; domyślny limit `.bak` = **10** (0 = off, maks. 10).
- Testy: 10 testów; GitHub Actions Linux + Windows.
- Release `v1.7.0` z lekkim ZIP-em.
- Aktualizacja dokumentacji: powyższe zmiany.

## 1.6.x

### 1.6.33 (2026-11-18)
- **Anchor sesji:** pierwszy Upload tworzy główny backup sesji w historii; jest chroniony do końca procesu i pomijany przez limity oraz „Wyczyść historię”. Po restarcie staje się zwykłym wpisem.
- **Opcjonalny limit rozmiaru historii:** `history_max_size_mb` (0 = bez limitu), usuwanie od najstarszych; anchor sesji nie liczy się do limitu.
- **Jeden `.bak` na sesję:** pierwszy Upload z backupem tworzy `.bak`, kolejne już nie; opcjonalny `bak_keep` (0 = bez limitu) zostawia N najnowszych `.bak` programu, a bieżący `.bak` sesji jest chroniony.
- Testy: anchor, limity rozmiaru, `.bak`; łącznie 9 testów.
- Release `v1.6.33` z lekkim ZIP-em.
- Aktualizacja dokumentacji: powyższe zmiany.

### 1.6.32 (2026-11-18)
- **Testy automatyczne w repo:** `tests/` na `unittest` — auth/cookie, `Host`, paginacja, problemy, sieroty, delete/upload/backup/historia i filtr lekkiego ZIP-a.
- **GitHub Actions:** Linux + Windows, Python 3.12, `python -m unittest discover -s tests -v`.
- Release `v1.6.32` z lekkim ZIP-em.
- Aktualizacja dokumentacji: powyższe zmiany.

### 1.6.31 (2026-11-17)
- **GET-y wymagają sesji:** `/api/*` i `/img` przyjmują ciasteczko `jfb_token` (HttpOnly, SameSite=Strict) ustawiane przez `/`, nagłówek `X-Token` lub pole `t`; cross-site `<img>` nie ma dostępu.
- **Nagłówki bezpieczeństwa strony:** `X-Frame-Options: DENY`, `frame-ancestors 'none'`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store`.
- **Host:** dowolny literał IP dozwolony tylko przy `--host 0.0.0.0`/`::`; przy konkretnym adresie tylko on i localhost. Ostrzeżenie przy `--host` poza localhost.
- Release `v1.6.31` z ZIP-em.
- Aktualizacja dokumentacji: powyższe zmiany.

### 1.6.30 (2026-11-17)
- **Paginacja bez sufitu 20 000:** `/api/list` przyjmuje `offset`; „Pokaż więcej" doładowuje kolejne 2000 wierszy aż do końca (strona maks. 5000). Test na kopii z 46 625 wpisami — `offset=20000` i `30000` zwracają dalsze pozycje.
- Sortowanie problemów nadal analizuje wszystkie pasujące wiersze (może być wolniejsze na bardzo dużych bibliotekach), ale nic nie jest obcinane do 20k.
- Dodano publiczne `README.md`, `README-extensive.md`, `Versions.md` (English) oraz licencję MIT.
- Aktualizacja dokumentacji: powyższe zmiany.

### 1.6.29 (2026-11-17)
- **[4] Backup z żywego pliku** — kopia `.db` + `-wal`/`-shm` przy Uploadzie i ponowna kontrola sygnatury przed podmianą.
- **[8] Koniec tabel tymczasowych** — biblioteki/filtry przez CTE/`IN`; usunięty wyścig `_libfolders`/`_roots`.
- **[12] Cache `stat`** — TTL 8 s, czyszczony przy odświeżeniu dysków i zmianie uprawnień.
- **[14] Paginacja** — `limit` 2000 (maks. 20000) i przycisk **Pokaż więcej**; sortowanie problemów dalej pobiera do 20 000 wierszy.
- **[13] Równoległy skan portów** — `ThreadPoolExecutor` (32 wątki) zamiast sekwencyjnego.
- **[2] Czyszczenie sierot** — sekcja w Ustawieniach + `/api/orphans` (GET/POST), pomija `UserData`.
- **[15] Stare `jfdb_*`** — usuwane przy starcie, jeśli starsze niż 24 h.
- **[17] Skrypt SQL Docker-aware** — `docker stop/start` albo `systemctl`, Windows bez sudo.
- **[18] Token poza URL** — eksport `.db`/`.sql` przez formularz POST.
- **[20] Docstring platform** — ograniczenia Linux/Windows/macOS.
- Aktualizacja dokumentacji: powyższe zmiany.

### 1.6.28 (2026-11-17)
- **Plakietka trybu obok języka:** `USER` / `SUDO` / `ADMIN` / `ROOT` z tooltipem i kolorami; aktualizuje się po zmianie trybu i języka.
- **Rozpoznawanie per platforma:** Windows — `ADMIN` tylko przy procesie z podniesionymi uprawnieniami (UAC), inaczej `USER`; Linux — `SUDO` po aktywacji trybu ADMIN, `ROOT` jako root; macOS — `ADMIN` dla grupy admin / `SUDO` przy sesji sudo; nieznana platforma → plakietka ukryta.
- `/api/priv` zwraca `label`; aktualizacja dokumentacji.

### 1.6.27 (2026-11-17)
- **Ścieżki wg systemu także przy starcie:** `--db` w formacie innego systemu jest pomijany (ostrzeżenie w konsoli), a używana jest domyślna ścieżka platformy; `/api/info` zwraca `platform`.
- **Komunikaty o braku bazy:** ekran „Nie wczytano bazy" i czerwony status w Ustawieniach pokazują ścieżkę w formacie bieżącego systemu (`C:\...` na Windows, `/...` na Linuksie), bez domyślnej ścieżki linuksowej na Windows.
- Aktualizacja dokumentacji: powyższe zmiany.

### 1.6.26 (2026-11-17)
- **Status bazy w Ustawieniach:** przy braku bazy czerwony komunikat „Baza nie wczytana" z powodem, zamiast zielonego wpisu ze ścieżką.
- **Dyski bez bazy:** sekcja Dyski (Ustawienia i Połączenie) pokazuje „Brak wczytanej bazy — lista dysków niedostępna.", przycisk odświeżania jest wyłączony; brak żądań `/api/disks` i błędu 409.
- **„Sprawdź ponownie" w sekcji Dyski:** podłączona obsługa przycisku (wcześniej nie działał).
- Aktualizacja dokumentacji: powyższe zmiany.

### 1.6.25 (2026-11-17)
- **Platformowy domyślny path:** okno „innej ścieżki" proponuje ścieżkę w stylu systemu (`C:\...` na Windows, `/...` na Linuksie) zamiast bieżącego wpisu; `/api/setup` zwraca `platform` i `db_default`.
- **Walidacja stylu ścieżki:** ścieżka linuksowa na Windows (i odwrotnie) daje czytelny błąd zamiast próby otwarcia ścieżki względnej.
- **Ikona ⏭ na ekranie braku bazy** — pomija ekran, menu i ustawienia zostają dostępne; ekran nie wraca przy odświeżaniu statusu.
- **Wybór pliku z komputera:** Chrome/Edge przez `showOpenFilePicker` (bez zawieszania po anulowaniu), pozostałe przeglądarki przez pole pliku poza ekranem z czyszczeniem i zdjęciem fokusu.
- Aktualizacja dokumentacji: powyższe zmiany.

### 1.6.24 (2026-11-17)
- **Windows bez sudo:** tryb ADMIN wyłączony po stronie serwera (`400` z komunikatem) i UI; `platform` w `/api/priv`; ukryty przycisk ADMIN na ekranie braku bazy.
- **Wybór pliku bez ADMIN:** systemowe okno wyboru bazy korzysta z `/api/pickpath` i dopiero potem otwiera plik — bez pytania o hasło sudo.
- **Wczytywanie z innej ścieżki:** własne okno tekstowe zamiast `prompt()` (Enter = OK, Esc/Anuluj = zamknięcie).
- **Anulowanie wyboru pliku:** czyści pole i zdejmuje fokus — brak blokady interfejsu i dźwięku błędu Windows; anulowanie nie pokazuje alertu.
- Ukryta konsola procesu Tk na Windows.
- Aktualizacja dokumentacji: powyższe zmiany, różnice platform i analiza pakowania per platforma.

### 1.6.23 (2026-11-17)
- **Wybór języka na ekranie „Nie wczytano bazy"** — stała lista PL/EN/DE/FR/ES/RU/IT/NL pod oknem; przełącza interfejs i powód błędu bez miksu języków.
- Powód błędu bazy (`DbError`) tłumaczony przy żądaniu (`X-Lang`), a nie zapisywany na stałe po polsku.
- Aktualizacja dokumentacji: powyższa zmiana.

### 1.6.22 (2026-11-17)
- Bez odpytywania `/api/disks` przy braku bazy — koniec błędu 409 w konsoli po starcie „na pusto".
- Aktualizacja dokumentacji: powyższa zmiana.

### 1.6.21 (2026-11-17)
- Ikona 🛠 **Setup** zostaje na stałe (edycja folderu danych i `jellyfin.db` przy złej konfiguracji); przy otwarciu z ikony jest **przycisk zamknięcia** (anulowanie). Pierwszy start nadal bez zamykania.
- Aktualizacja dokumentacji: powyższa zmiana.

### 1.6.20 (2026-11-17)
- **Tymczasowa ikona 🛠 Setup** za Językami — uruchamia inicjalny setup (wybór folderu danych i `jellyfin.db`, bez przycisku zamknięcia). Do usunięcia po testach.
- Aktualizacja dokumentacji: powyższa zmiana.

### 1.6.19 (2026-11-17)
- **Wykrywanie domyślnych baz Jellyfina** przy setupie (Windows: ProgramData/LocalAppData/Roaming; Linux: /var/lib, /config, /data, ~/jellyfin; folder programu).
- **Wybór `jellyfin.db` w setupie** (ścieżka lub okno systemowe) i zapis **`db_path`** w configu; przy starcie bez `--db` baza wczytuje się z configu. Walidacja pliku (SQLite + `BaseItems`); brak/`.sql` → błąd.
- `--db` domyślnie automatyczny: CLI → config → wykryta → domyślna platformy.
- Testy: kandydaci, `valid_db_file`, setup z wybraną bazą, restart bez `--db`.
- Aktualizacja dokumentacji: powyższe zmiany.

### 1.6.18 (2026-11-16)
- **Szybkie poprawki z analizy:** `[5]` `install_file` wymaga tylko zapisywalnego katalogu (z fallbackiem), `[6]` `None` przy unikalności `.bak` traktowane jako zajęte, `[9]` `PRIV_LOCK` jako RLock (bezpieczne `priv_disable`), `[10]` `reset_work` odporny na błąd i odtwarza połączenie, `[11]` timeout 30 s w `/api/load` i imporcie SQL, `[19]` GET nie ujawnia wyjątków (ogólny komunikat + log), `[21]` `/api/problems` zwraca `{items,total,limit}` z informacją w UI.
- Testy: jednostkowe (nazwa `.bak`, RLock, install, reset normalny/błąd, kształt API) + live (timeout 400, serwer żyje, backup/delete, lista).
- Aktualizacja dokumentacji: opis powyższych zmian; bez osobnej wersji.

### 1.6.17 (2026-11-16)
- **Postęp wczytywania bazy** przy starcie/po zapisie setupu: procent obok „Loading database…" w linii pod wyszukiwarką (fazy kopiowania i przygotowania kopii roboczej).
- Aktualizacja dokumentacji: opis powyższej zmiany; bez dodatkowych zmian funkcjonalnych.

### 1.6.16 (2026-11-16)
- **Historia poza `tmp`:** automatyczne wpisy w `<data_dir>/history/` (z migracją ze starego `tmp/history`); `tmp/` tylko na kopie sesji, usuwane przy zamknięciu.
- **Postęp backupu ręcznego:** pasek i `%` (fazy `backup`/`done`) w sekcji Ręcznych kopii.
- **Komunikat startu Jellyfina** pokazywany przy każdym starcie (także z okna Połączenie), w pasku między tytułem a „Zaznacz problemy".

### 1.6.15 (2026-11-16)
- Dokumentacja: wymóg dla pakowania (AppImage/EXE) — identyczny tryb portable; planowany instalator z importem setupu (do zrobienia później).

### 1.6.14 (2026-11-16)
- Dokumentacja 1.6.13 (bez zmian w kodzie).

### 1.6.13 (2026-11-16)
- **Config portable:** `jf_browser.settings.json` obok programu (fallback do `~/.config`, gdy katalog niezapisywalny).
- Nowa wersja w innym folderze → brak configu → ponowna konfiguracja; backupy/historia tworzą się w nowej lokalizacji (test: config i backup w nowym folderze, stare `backups/` bez zmian).

### 1.6.12 (2026-11-16)
- Dokumentacja 1.6.11 (bez zmian w kodzie).

### 1.6.11 (2026-11-16)
- **Detekcja dysków przez `lsblk` + mapowanie punkt montowania → urządzenie** (zapisywane w `disk_map`):
  - zamontowany → sprawdzanie folderu,
  - **`unmounted` (🟠)** — urządzenie jest w systemie, ale niezamontowane,
  - **`detached` (🔴)** — urządzenie zniknęło (dysk odłączony),
  - bez `lsblk` fallback na fstab; Windows/macOS bez zmian (`unknown`).
- Ustawienia/Połączenie odświeżają dyski przy otwarciu i co 15 s.

### 1.6.10 (2026-11-16)
- Dokumentacja 1.6.9 (bez zmian w kodzie).

### 1.6.9 (2026-11-16)
- „Wyczyść historię" usuwa **tylko automatyczną historię**; ręczne kopie pozostają (potwierdzenie mówi o tym wprost).
- **Kosz przy każdej ręcznej kopii** (potwierdzenie, usunięcie pliku i wpisu, komunikat ze ścieżką).

### 1.6.8 (2026-11-16)
- Korekta numeracji: ręczne kopie i ich dokumentacja przeniesione z 1.7.x do 1.6.x (commity bez zmian, nowe tagi `v1.6.6`/`v1.6.7`).
- Zasada: poprawki i rozszerzenia istniejących funkcji zostają w `1.6.x` (także 1.6.25); `1.7.0` zarezerwowane na dużą zmianę (np. AppImage).

### 1.6.7 (2026-11-16)
- Dokumentacja ręcznych kopii (bez zmian w kodzie).

### 1.6.6 (2026-11-16)
- **Ręczne kopie jako osobna sekcja historii** (na dole, przycisk Backup przeniesiony pod listę):
  - wpis z wersją Jellyfina, datą i rozmiarem,
  - rozwinięcie pokazuje **różnice względem aktualnej bazy**: `+` w kopii/brak w bazie (zielone) i `−` w bazie/brak w kopii (czerwone),
  - metadane w `backups/index.json`; kopie poza limitem historii i bez automatycznego usuwania.

### 1.6.5 (2026-11-16)
- Aktualizacja numeru wersji w dokumentacji (bez zmian w kodzie).

### 1.6.4 (2026-11-16)
- Poprawka kolizji klucza tłumaczenia `backup_note` → `backup_manual_note` (podpowiedź przycisku Backup w Historii pokazywała opis pliku `.bak` z Uploadu).

### 1.6.3 (2026-11-16)
- Dokumentacja 1.6.2 + nowy plik `Wersje.md` (historia zmian pogrupowana po wersjach).

### 1.6.2 (2026-11-16)
- **Backup w Historii**: dopisek i podpowiedź, że kopie z przycisku Backup nie są usuwane automatycznie i nie liczą się do limitu historii.
- **Walidacja schematu**: porównanie tabel nowej bazy z **oryginałem** zamiast sztywnej listy (koniec fałszywych alarmów przy poprawnych bazach; nadal wykrywa okrojoną kopię).

### 1.6.1 (2026-11-16)
- Aktualizacja dokumentacji do 1.6.0 (bez zmian w kodzie).

### 1.6.0 (2026-11-16)
- Połączenie: status Jellyfina **zielony** przy działającym; usunięty zdublowany wiersz z wersją pod dyskami.
- Historia: przycisk **Backup** → pełna kopia w `<data_dir>/backups/` (poza historią i limitem).
- „Odśwież z oryginału": **procentowy postęp** (kopiowanie i przygotowanie kopii roboczej).
- Sortowanie listy po **tytule** (`Name`), tie-break rok/Id; usunięte sortowanie po ścieżce.
- Podpowiedź **„💡 sugerowane usunięcie"** dla duplikatów bez istniejących plików (o ile w grupie jest choć jeden istniejący).
- Import SQL: czytelne błędy (odrzucanie `.db` i danych binarnych, czyszczenie komunikatów).
- Popup wyjaśniający brakujących tabel zamiast surowego błędu.
- Okna systemowe (tkinter) ukrywane, gdy niedostępne (headless).
- Statusy dysków liczone z montowań (`/proc/mounts`): brak dostępu → czerwony/pomarańczowy; odświeżanie przy otwieraniu okien.
- Subtelny komunikat „Jellyfin za chwilę wystartuje…" po starcie z Upload/Revert.

## 1.5.x

### 1.5.3 (2026-11-16)
- Dokumentacja walidacji `Host` (bez zmian w kodzie).

### 1.5.2 (2026-11-16)
- **Walidacja nagłówka `Host`** (DNS rebinding): dozwolone `localhost`, adresy IP i dokładnie `--host`; domeny odrzucane (403).

### 1.5.1 (2026-11-16)
- Dokumentacja walidacji schematu (bez zmian w kodzie).

### 1.5.0 (2026-11-16)
- **Walidacja schematu** przed Uploadem i Revertem: brakujące tabele → blokada z potwierdzeniem (`force_schema`).

## 1.4.x

### 1.4.1 (2026-11-16)
- Dokumentacja refaktoru (bez zmian w kodzie).

### 1.4.0 (2026-11-16)
- **Refaktor struktury**: interfejs w `ui/index.html`, tłumaczenia w `i18n.py`; `jf_browser.py` ~2400 linii.
- Ładowanie UI z pliku (także w bundlu przez `sys._MEIPASS`), start zgłasza brak pliku.

## 1.3.x

### 1.3.1 (2026-11-16)
- Dokumentacja importu/eksportu SQL (bez zmian w kodzie).

### 1.3.0 (2026-11-16)
- Menu **SQL**: import `.sql`/`.sql.gz` (strumieniowo, postęp etapów) i eksport `.sql`/`.sql.gz`.
- Import osadza bazę jako `kind=upload` (Upload wyłączony); `sqlite3` CLI gdy dostępny, inaczej parser Python.

## 1.2.x

### 1.2.4 (2026-11-16)
- Dokumentacja do 1.2.3 (bez zmian w kodzie).

### 1.2.3 (2026-11-16)
- Parsowanie `/proc/mounts` jako funkcja + fallback `/proc/self/mounts`; testy montowań Dockera (bind/named volume).

### 1.2.2 (2026-11-16)
- Połączenie: dyski bez podświetlania i kursora; `fstab` pomija `noauto`.

### 1.2.1 (2026-11-16)
- Połączenie: dyski grupowane po punkcie montowania (`/mnt/SG1`), tylko informacja, bez liczników i filtrowania.

### 1.2.0 (2026-11-16)
- **Status dysków**: kolory (zielony/pomarańczowy/czerwony/szary/niebieski), liczniki wpisów, filtr po dysku.
- **Ochrona usuwania** z niedostępnego dysku: blokada bez `force`, prompt „usuń mimo to" przy Delete i generowaniu SQL.
- „Zaznacz problemy" pomija czerwone dyski; checkbox „wszystkie dyski".

## 1.1.x

### 1.1.4 (2026-11-16)
- **Instalator**: wybór folderu danych (domyślnie obok programu), tworzenie `tmp/history`, walidacja root/home, przygotowanie pod AppImage/EXE.

### 1.1.3 (2026-11-15)
- Nazwa przycisku skryptu SQL bez nawiasów.

### 1.1.2 (2026-11-15)
- Licznik zaznaczenia wewnątrz przycisku skryptu SQL.

### 1.1.1 (2026-11-15)
- Czerwony przycisk skryptu SQL, licznik zaznaczenia, „or" między akcjami.

### 1.1.0 (2026-11-15) — pierwsze wydanie
- Tłumaczenia pl/en/de/fr/es/ru/it/nl (UI + komunikaty API).
- Menu górne w stylu Steama: Ustawienia, Połączenie, Historia, Języki.
- Historia uploadów: wpisy z wersją Jellyfina, datą, `−/+`, szczegółami; revert i czyszczenie.
- Wybór pliku/folderu przez okno systemowe.
- Kompaktowy przycisk Upload pod listą.
- Skrypt SQL w oknie z kopiowaniem i pobieraniem `.sql`.
- Paski ładowania (globalny, przyciski), ekran wczytywania bazy w tle.
- Ustawienia bez zwijania sekcji; historia w `tmp/history`.
- Wcześniejsze elementy bazowe: praca na kopii, Upload z rebase, wykrywanie bibliotek/dysków/problemów, tryby LIMITED/ADMIN.
