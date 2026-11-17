# Historia wersji — Jellyfin DB editor

Schemat: **X.Y.Z** — `X` przełom, `Y` duża zmiana funkcjonalna, `Z` poprawka.
Każda wersja ma tag `vX.Y.Z` oraz release GitHub z ZIP-em; tagi są niezmienne, commity nie są usuwane.
ZIP release zawiera program, UI, README/licencję i changelogi — bez `DB/`, `potencjalne poprawki` i danych runtime. `v1.6.31` pozostaje pełnym ZIP-em (legacy).
English translation: [`Versions.md`](Versions.md).

## 1.6.x

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
