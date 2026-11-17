# jf_browser — dokumentacja projektu

Stan na 17 listopada 2026, **wersja 1.6.30** (tag `v1.6.30`, lokalne repo git).

Program składa się z trzech plików, które muszą leżeć razem:

```
jf_browser.py   # logika i serwer (wejście)
i18n.py         # tłumaczenia (pl, en, de, fr, es, ru, it, nl)
ui/index.html   # interfejs (HTML + CSS + JS)
```

Przy pakowaniu (PyInstaller) katalog `ui/` trzeba dołączyć przez `--add-data "ui;ui"` (Windows) lub `--add-data "ui:ui"` (Linux); program szuka go obok siebie albo w `sys._MEIPASS`.

## 1. Cel

Przeglądarka i czyszczarka bazy `jellyfin.db` (SQLite) działająca w przeglądarce. Program służy do:

- przeglądania bibliotek (filmy, seriale i inne typy) wprost z bazy, także przy wyłączonym Jellyfinie,
- wykrywania wpisów-sierot: brakujących plików, odmontowanych dysków, duplikatów i folderów odpiętych od bibliotek,
- bezpiecznego usuwania takich wpisów (tylko z `BaseItems`), bez ruszania plików mediów,
- zatrzymywania/uruchamiania Jellyfina i podmiany bazy z kopią zapasową,
- prowadzenia **historii uploadów** z możliwością przywrócenia dowolnej zapisanej wersji.

Powód powstania: Jellyfin 10.10+ potrafi nie usunąć martwego wpisu (błąd `FOREIGN KEY constraint failed`), a taki wpis blokuje ponowne dodanie plików. Wcześniej robiono to ręcznie poleceniami `sqlite3`.

Program **nie modyfikuje plików mediów** i nie dotyka oryginalnej bazy poza przyciskami Upload/Revert.

## 2. Wymagania i uruchomienie

- Python 3 (tylko biblioteka standardowa), Linux (wykrywanie dysków korzysta z `/proc` i `/etc/fstab`).
- Przeglądarka graficzna.

```bash
sudo systemctl stop jellyfin      # zalecane przed edycją (program i tak o to zapyta)
sudo python3 jf_browser.py
# adres: http://127.0.0.1:8099
```

Bez uprawnień do bazy program startuje mimo to (ekran konfiguracji/„Nie wczytano bazy"), a uprawnienia można włączyć w UI hasłem sudo.

**Platformy:** tryb ADMIN (sudo) dotyczy Linuksa i jest tam opcjonalny. **Windows** nie używa sudo — program działa od razu jako LIMITED, przycisk ADMIN jest wyłączony z podpowiedzią, a serwer odrzuca włączenie trybu (`400`). Uprawnienia wynikają z konta użytkownika; pliki w `ProgramData` mogą wymagać odpowiednich praw. **macOS** nie był testowany.

**Windows — różnice:** systemowe okno wyboru pliku nie wymaga sudo (osobny proces Tk z ukrytą konsolą), „Wczytaj bazę z innej ścieżki" otwiera okno w aplikacji (Enter = OK, Esc = anuluj), a anulowanie wyboru pliku nie blokuje interfejsu. Domyślna propozycja ścieżki jest dobierana wg systemu (`C:\...` na Windows, `/...` na Linuksie), a nie z bieżącego wpisu. Ścieżka w formacie innego systemu (np. `/var/...` na Windows) jest odrzucana czytelnym komunikatem zamiast próby otwarcia ścieżki względnej; dotyczy to także `--db` — taka ścieżka jest pomijana i używana jest domyślna platformy. Komunikaty o braku bazy pokazują więc ścieżkę w formacie bieżącego systemu. Domyślne bazy: `%ProgramData%\Jellyfin\Server\data\jellyfin.db` i `%LOCALAPPDATA%\jellyfin\data\jellyfin.db`. Sterowanie usługą Jellyfina (`systemctl`) jest niedostępne — przyciski start/stop pozostają wyłączone.

### Flagi

| Flaga | Domyślnie | Znaczenie |
|---|---|---|
| `--db` | automatycznie | ścieżka bazy: podana → `db_path` z configu → wykryta domyślna → domyślna platformy; ścieżka w formacie innego systemu jest pomijana (z ostrzeżeniem w konsoli) i używana jest domyślna platformy |
| `--host` | `127.0.0.1` | adres serwera lokalnego |
| `--port` | `8099` | port; zajęty → kolejne (do +9) |
| `--no-browser` | wyłączone | nie otwieraj przeglądarki |
| `--jf-service` | wykrywane | `systemd:nazwa` albo `docker:nazwa_kontenera` |
| `--jf-port` | z `network.xml` / 8096 | port HTTP Jellyfina, tylko ta sesja |
| `--no-service-check` | wyłączone | nie blokuj Upload, gdy Jellyfin działa |

### Zmienne środowiskowe

| Zmienna | Znaczenie |
|---|---|
| `JF_BROWSER_CONFIG` | ścieżka pliku ustawień |
| `JF_SUDO_CMD` | zamiennik `sudo` (testy) |
| `JF_FORCE_LIMITED` | udaje brak roota (testy) |
| `APPIMAGE` | używana do ustalenia katalogu programu w AppImage |

Otwieranie przeglądarki: tylko graficzna, przez `xdg-open`, gdy jest `DISPLAY`/`WAYLAND_DISPLAY`; pod `sudo` jako `SUDO_USER`. W razie niepowodzenia wypisywany jest adres.

## 3. Folder danych (instalator) i układ plików

Przy pierwszym uruchomieniu (brak `data_dir` w ustawieniach) pokazuje się **okno konfiguracji** — nie da się go pominąć:

- domyślna propozycja: **katalog programu** (`APPIMAGE` → folder pliku AppImage, PyInstaller/EXE → folder `sys.executable`, skrypt → folder `jf_browser.py`), a gdy niezapisywalny → `~/JellyfinDBeditor`,
- wybór przez systemowe okno folderu (`/api/pickdir`),
- walidacja: odrzuca katalog główny dysku (`D:\`, `/`) i katalog domowy; pozwala utworzyć nowy folder; sprawdza prawo zapisu,
- po zapisie tworzy strukturę i zapisuje `data_dir` w ustawieniach,
- **wykrywa domyślne bazy Jellyfina** (Windows: `%ProgramData%\Jellyfin\Server\data`, `%LOCALAPPDATA%\jellyfin\data`, `%APPDATA%\Jellyfin\Server\data`; Linux: `/var/lib/jellyfin/data`, `/config/data`, `/data`, `~/jellyfin/data`, folder programu) i pokazuje, czy którąś znaleziono,
- pozwala **wskazać plik `jellyfin.db`** (ścieżka lub okno systemowe); wybór zapisywany jest jako `db_path` w configu i używany do automatycznego wczytania przy kolejnych startach (także gdy baza leży poza standardowym folderem, np. na Windows z własnym folderem danych).

```
<data_dir>/
  tmp/
    jfdb_XXXX/            # kopia robocza bieżącej sesji (usuwana przy wyjściu)
      orig/jellyfin.db    # nietknięty snapshot oryginału
      work.db             # kopia robocza — tu działają usunięcia
  history/
    index.json            # metadane wpisów automatycznych
    20261115-213132/
      jellyfin.db         # kopia wgranej bazy (nazwa jak oryginału)
  backups/                # ręczne kopie (poza historią i limitem)
```

Ustawienia (`jf_port`, `jf_service`, `history_max`, `data_dir`, `db_path`, `disk_map`) trafiają domyślnie do **`jf_browser.settings.json` obok programu** (tryb portable) — nowa wersja w innym folderze nie ma configu, więc przechodzi **ponowną konfigurację** i tworzy dane u siebie. Gdy katalog programu jest niezapisywalny, fallback: `~/.config/jf_browser/settings.json` (albo `$XDG_CONFIG_HOME`; pod sudo katalog `SUDO_USER`). Katalog danych jest widoczny w Ustawieniach.

**Wymóg dla pakowania (AppImage/EXE/inne):** zachowanie musi być identyczne — config obok programu, pierwsze uruchomienie nowej wersji = setup, dane tworzone w wybranej lokalizacji. Docelowo (do zrobienia później) **instalator**: wykrywa ścieżkę instalacji, nadpisuje pliki programu, **importuje setup** z poprzedniej wersji (`data_dir`, `db_path`, `jf_port`, `jf_service`, `history_max`, `disk_map`) i uwzględnia zmiany.

## 4. Model pracy i bezpieczeństwa

1. Przeglądanie i usuwanie dotyczy wyłącznie `work.db`.
2. **Odśwież z oryginału** odrzuca zmiany i pobiera świeżą bazę.
3. **Upload** podmienia oryginał kopią roboczą i zapisuje wpis historii.
4. **Revert** przywraca bazę z wybranego wpisu historii (te same zabezpieczenia co Upload).
5. Sygnatura oryginału (rozmiar + czas pliku i `-wal`) wykrywa zmianę po skopiowaniu → rebase usunięć po GUID.

Zabezpieczenia:

- serwer słucha tylko na `127.0.0.1`,
- **walidacja nagłówka `Host`**: dozwolone są `localhost`, adresy IP (także LAN) i dokładnie wartość `--host`; domeny są odrzucane (ochrona przed DNS rebinding),
- losowy token (16 bajtów hex) wstawiany do strony; POST wymaga `X-Token`, a eksport idzie przez formularz POST z polem `t` (GET `?t=` zostaje dla zgodności),
- **blokada usuwania z niedostępnego dysku** (patrz sekcja 8),
- przed Upload sprawdzenie, czy Jellyfin nie działa,
- `PRAGMA quick_check` nowej bazy przed podmianą,
- eksport i kopie historii zawierają całą bazę (konta, hashe haseł) — ostrzeżenie w UI.

## 5. Architektura

- `jf_browser.py` — logika bazy, dysków, historii, SQL i serwer HTTP; interfejs wczytywany z `ui/index.html`.
- `i18n.py` — słownik `TEXT` (8 języków), `tr()`, `set_lang()`, tłumaczenie powodów/statusów.
- `ui/index.html` — cały HTML/CSS/JS; `page_html()` wstrzykuje token i słownik tłumaczeń.

Stan: `con` (połączenie z `work.db`), `src`, `orig`, `work`, `tmp`, `dirty`, `deleted`, `sig`, cache `problems/pmap/libs/roots`, `kind` (`path`/`upload`), `unreadable`, `loading`, `setup`, `sqljob`.
Dostęp do bazy chroni `LOCK`; połączenie w `isolation_level=None`.
Baza ładuje się **w tle po starcie serwera**; `/api/info` zwraca `loading: true/false`, UI pokazuje „Wczytywanie bazy…" i sam przechodzi dalej.
Biblioteki i filtry korzystają z CTE/`IN` — nie ma tabel tymczasowych `_libfolders`/`_roots`.
Brak wczytanej bazy → `409 {nodb:true}` (poza trasami `/`, `/api/info`, `/api/priv`, `/api/jellyfin`, `/api/service`, `/api/open`, `/api/load`, `/api/reload`, `/api/pick`, `/api/history`, `/api/settings`, `/api/setup`, `/api/pickdir`, `/api/import-sql`, `/api/sqljob`, `/api/job`, `/api/backups`, `/api/pickpath`).

## 6. Wykrywanie bibliotek, dysków i problemów

Biblioteka = wiersz `BaseItems` o typie kończącym się na `.CollectionFolder`. Powiązanie z folderami fizycznymi pochodzi z pola `Data` (`PhysicalFolderIds`, `PhysicalLocationsList`, `CollectionType`). Foldery fizyczne: `TopParentId = Id` i rzeczywista ścieżka. Wynik w tabelach `_libfolders` i `_roots` (`Kind` = `lib`/`orph`).

### Statusy i kolory

| Status | Kolor | Znaczenie |
|---|---|---|
| `ok` | 🟢 | folder istnieje i nie jest pusty |
| `unmounted_fstab` | 🟠 | w fstab, brak w `/proc/mounts` (najpewniejszy sygnał odmontowania) |
| `empty` | 🟠 | pusty folder bez własnego montowania |
| `missing_mounted` | 🟠 | dysk zamontowany, folderu nie ma |
| `empty_mounted` | 🟠 | dysk zamontowany, folder pusty |
| `missing` | 🔴 | folderu nie ma i brak wpisu fstab |
| `unmounted` | 🟠 | urządzenie jest w systemie (lsblk), ale nie jest zamontowane |
| `detached` | 🔴 | urządzenie zniknęło z systemu (dysk odłączony) |
| `unknown` | ⚪ | nie sprawdzono (baza z innej maszyny / brak uprawnień) |
| — (0 wpisów) | 🔵 | dysk bez powiązań z bazą („poza bazą") |

`/etc/fstab`: wpisy `noauto` są pomijane; obsługiwane `\040` itd. Montowania: `/proc/mounts`, fallback `/proc/self/mounts`.

### Grupowanie po dyskach

- W **Ustawieniach** widoczne są foldery bibliotek (np. `/mnt/SG1/Films`, `/mnt/SG1/Series`) z licznikami wpisów i klikalnym filtrem.
- W **Połączeniu** dyski są grupowane po **punkcie montowania** (`/proc/mounts`, najdłuższe dopasowanie): np. `/mnt/SG1` zamiast podfolderów. Bez mountów fallback: pierwsze dwa segmenty ścieżki, litera dysku (`D:\`), `/Volumes/Nazwa`.
- Kolor dysku w Połączeniu = najgorszy status wśród folderów; kliknięcie/filtrowanie tylko w Ustawieniach (Połączenie to czysta informacja).
- **Mapowanie ścieżka → urządzenie (`lsblk`):** przy pierwszym zamontowaniu program zapamiętuje w ustawieniach (`disk_map`), które urządzenie (`sdb1`, `sdc1`…) odpowiada danemu punktowi montowania. Dzięki temu po odmontowaniu rozpoznaje:
  - `unmounted` (🟠) — urządzenie jest w systemie, ale nie jest zamontowane,
  - `detached` (🔴) — urządzenie zniknęło z systemu (dysk fizycznie odłączony).
  Bez `lsblk` używany jest fstab (`unmounted_fstab`).
- Ustawienia i Połączenie odświeżają statusy przy otwarciu oraz co 15 s, dopóki są otwarte.

### Docker

W kontenerze (właściwe miejsce uruchomienia) bind mounty i wolumeny widać w `/proc/mounts` pod ścieżkami docelowymi (`/data`, `/mnt/SSD`) — grupowanie działa; nazwa wolumenu (`ssd-data`) nie ma znaczenia. Na hoście wolumen nazwany nie jest montowaniem (to katalog w `/var/lib/docker/volumes/...`), a bind mount widać pod ścieżką źródłową. Gdy baza pochodzi z kontenera, a program działa na hoście, ścieżki kontenera zwykle nie istnieją → statusy `unknown` (szare). Uruchamiać program w kontenerze (`docker exec`) dla pełnej zgodności.

### Problemy

| Powód | Reguła |
|---|---|
| brak pliku/folderu na dysku | ścieżka istnieje w bazie, nie ma jej na dysku, a root jest `ok`/`unknown` |
| dysk/folder główny niedostępny: *status* | jak wyżej, ale root ma status inny niż `ok`/`unknown` |
| poza bibliotekami (osierocony wpis) | wiersz pod folderem odpiętym od biblioteki |
| duplikat ścieżki | ta sama para (`Path`, `Type`) więcej niż raz |
| zdublowana pozycja w bibliotece | ta sama (typ, nazwa bez wielkości liter, rok) na najwyższym poziomie biblioteki |
| zdublowany odcinek | ta sama trójka (`SeriesId`, `ParentIndexNumber`, `IndexNumber`) |

Trzystanowe istnienie pliku: `True` / `False` / `None` (brak uprawnień). `None` nie jest traktowane jako brak pliku — wiersz ma `?` i ostrzeżenie o niepełnych wynikach.

## 7. Interfejs

**Menu górne:** `Jellyfin DB editor` · Ustawienia · Połączenie · Historia · SQL · Języki ▾ (przełączanie na żywo, zapamiętywane w `localStorage`; przy pierwszym uruchomieniu język z przeglądarki) · 🛠 **Setup** — ponowne otwarcie konfiguracji (folder danych + baza `jellyfin.db`), z możliwością anulowania; przydatne, gdy ścieżki zostały źle ustawione. Obok oznaczenia języka mała plakietka **USER / SUDO / ADMIN / ROOT** pokazuje aktywny tryb uprawnień; na Windows `ADMIN` tylko przy procesie uruchomionym z podniesionymi uprawnieniami (UAC), na Linuksie `SUDO` po aktywacji trybu ADMIN, na macOS `ADMIN` dla członka grupy admin lub `SUDO` przy aktywnej sesji; przy nieznanej platformie plakietka jest ukryta.

**Lewy panel:** kategoria (biblioteki lub typy + kategorie ostrzegawcze), sortowanie, „Wszystkie problemy", wyszukiwanie, chip filtra dysku (`Disk: … ✕`), lista pozycji (miniatura, nazwa, ścieżka, powody), przycisk **Pokaż więcej** (gdy wyników jest więcej niż pobrane 2000; kolejne porcje po 2000, bez górnego limitu — do końca wyników), na dole przycisk **Upload** (ikona ⬆ + pogrubione „Upload" + mniejszy opis).

**Prawy panel:** tytuł, „Zaznacz problemy" + checkbox **„wszystkie dyski"**, „Zaznacz wszystko", „Wyczyść", **Delete selected (N)**, „lub", **SQL script manual (N)** (oba czerwone), tabela drzewa.

**Ustawienia:** status bazy (przy braku bazy **czerwony** komunikat „Baza nie wczytana" z powodem), folder danych, odświeżenie, kopia zapasowa, wczytywanie ścieżki/pliku (także systemowe okno wyboru; bez sudo, anulowanie nie blokuje UI), eksport, sekcja **Sieroty w tabelach powiązanych** (sprawdzenie + czyszczenie z pominięciem `UserData`), sekcja **Dyski** (liczniki + filtr + „Sprawdź ponownie"; bez bazy pokazuje komunikat i wyłącza odświeżanie), sekcja historii (limit + ostrzeżenie o miejscu + czyszczenie).

**Połączenie:** status Jellyfina (zielony przy działającym), „Sprawdź ponownie", port, lista dysków (bez klikania/liczników), start/stop usługi, tryb ADMIN. Przy każdym starcie Jellyfina — także z okna Połączenie — w pasku pojawia się na chwilę subtelny komunikat „Jellyfin za chwilę wystartuje…" (między tytułem a „Zaznacz problemy"), znikający po wykryciu działania.

**Historia:** dwie sekcje:
- **automatyczne** — wpisy z Uploadów (wersja, data, `−N +M`, `⚠ brak pliku`), rozwijane szczegóły, **Restore**;
- **Ręczne kopie** (na dole, przycisk **Backup**) — pełne kopie w `<data_dir>/backups/`, poza limitem historii; wpis pokazuje wersję, datę i rozmiar, a po rozwinięciu **różnice względem aktualnie wczytanej bazy**: `+N` (w kopii, brak w bazie) na zielono i `−N` (w bazie, brak w kopii) na czerwono — z listą pozycji. Backup pokazuje **postęp procentowy**. Każdy wpis ma **kosz** (usunięcie pojedynczej kopii z potwierdzeniem). „Wyczyść historię" w Ustawieniach usuwa **tylko automatyczną historię** — ręczne kopie zostają.

**SQL:** osobne okno z importem dumpu (`.sql` / `.sql.gz`, strumieniowo, z paskiem postępu: przesyłanie → rozpakowanie → wykonywanie poleceń) oraz eksportem `.sql` i `.sql.gz`. Po imporcie baza jest traktowana jak plik z komputera (`kind=upload`) — Upload wyłączony, dostępny eksport SQL/.db.

**SQL (skrypt ręczny):** osobne okno z gotowym skryptem `sqlite3`, przyciskami Copy i **Download .sql**.

**Ładowanie:** cienki pasek u góry przy każdym zapytaniu, spinner w długich przyciskach, ekran „Wczytywanie bazy…" z **procentem** (pod wyszukiwarką) przy starcie i po zapisie setupu, oraz procentowy postęp przy „Odśwież z oryginału" (fazy: kopiowanie, przygotowanie kopii roboczej).

**Ekran „Nie wczytano bazy":** przyciski ADMIN / ścieżka / plik z komputera / okno systemowe oraz **stała lista języków pod oknem** (PL/EN/DE/FR/ES/RU/IT/NL); przełącza cały interfejs i powód błędu (tłumaczony po stronie serwera wg `X-Lang`). Ikona **⏭** pomija ekran (menu i ustawienia zostają dostępne); przy ponownym odświeżeniu bez bazy ekran nie wraca do przeładowania strony.

**Wybór pliku z komputera:** w Chrome/Edge używane jest `showOpenFilePicker` (bez fokusu na ukrytym inpucie), w pozostałych przeglądarkach klasyczne pole pliku poza ekranem z czyszczeniem i zdjęciem fokusu po anulowaniu.

**Sortowanie** listy jest alfabetyczne po tytule (`Name`), z tie-breakiem po roku i Id — nie po ścieżce. Dla grup duplikatów wpisy bez istniejących plików dostają podpowiedź **„💡 sugerowane usunięcie"** (o ile w grupie jest choć jeden istniejący plik).

Limity: lista jest stronicowana po 2 000 (`Pokaż więcej` do końca wyników, API `limit` maks. 5 000); problemy do 5 000 — gdy jest ich więcej, tytuł pokazuje „Problemy: 5000 z N wpisów (limit)".

## 8. Usuwanie

- `DELETE FROM BaseItems WHERE Id IN (…)` w jednej transakcji na kopii roboczej (paczki po 500, max 50 000).
- **Ochrona dysków:** dla wybranych wpisów ustalany jest root (`TopParentId`):
  - root `missing` (🔴) → serwer **odmawia** (`e_disk_blocked`), chyba że przyjdzie `force: true`,
  - root pomarańczowy → przechodzi, ale UI ostrzega.
- **Prompt „usuń mimo to"** pojawia się tylko w dwóch miejscach: przy **Delete selected** i przed wygenerowaniem **SQL script manual** (anulowanie = brak operacji).
- **„Zaznacz problemy"** domyślnie pomija wpisy z czerwonych dysków; checkbox „wszystkie dyski" zaznacza bez wyjątku.
- Usuwane są tylko wiersze `BaseItems` (bez kaskady; tak jak ręczne `sqlite3`). Usunięcie serii nie usuwa sezonów/odcinków — użyć „Zaznacz wszystko" w jej drzewie. Sieroty w tabelach powiązanych można wyczyścić osobno w Ustawieniach (sekcja **Sieroty w tabelach powiązanych**, `UserData` jest pomijane).
- „SQL script manual" generuje `systemctl stop/start` albo `docker stop/start` (zależnie od wykrytej usługi), `sqlite3 … DELETE … IN (…)`, `SELECT changes(); COMMIT;`; na Windows są komentarze zamiast `sudo`/usługi systemd.

## 9. Upload

Front: sprawdzenie Jellyfina (propozycja zatrzymania), monit o sudo, potwierdzenie, potem pytanie o start Jellyfina.

Serwer: odmowa dla bazy „z komputera" i bez zmian; blokada przy działającym Jellyfinie (systemd lub port; `--no-service-check` pomija); wymóg zapisu; **rebase** przy zmienionej sygnaturze; opcjonalna kopia zapasowa `<baza>-RRRR-MM-DD_GG-MM-SS.bak` tworzona z **żywego pliku** (kopia + `-wal`/`-shm`, ponowna kontrola sygnatury przed podmianą); `quick_check`; **walidacja schematu** (porównanie tabel nowej bazy z oryginałem — brakujące tabele = blokada z `force_schema`); atomowa podmiana z zachowaniem właściciela/uprawnień; usunięcie starych `-wal`/`-shm`; **wpis do historii** (diff `orig` vs working copy) i ponowne wczytanie kopii roboczej.

## 10. Historia

- Każdy Upload zapisuje pełną kopię wgranej bazy w `<data_dir>/history/<id>/<nazwa bazy>` oraz wpis w `index.json` (id, data, wersja Jellyfina z UI, liczniki i listy `−`/`+`, rozmiar). `tmp/` służy wyłącznie do plików sesji i jest czyszczone przy zamknięciu.
- Limit: `history_max` 1–50 (domyślnie 5). Zmiana limitu przycina najstarsze wpisy razem z plikami. Każdy wpis to pełna kopia bazy — większy limit zajmuje więcej miejsca.
- **Revert** przywraca wybrany wpis jak Upload: te same testy (Jellyfin zatrzymany, uprawnienia, opcjonalny backup), walidacja schematu, `quick_check`, atomowa podmiana, przeładowanie kopii roboczej. Revert nie tworzy nowego wpisu historii.
- Brak pliku kopii: oznaczany przy dacie (`⚠ brak pliku`), Restore zablokowany; przy starcie lista braków trafia do konsoli.
- Czyszczenie całej historii z potwierdzeniem (nieodwracalne). Historia przeżywa restart programu; sesyjne `tmp/jfdb_*` są usuwane przy wyjściu, a pozostałe po awarii i starsze niż 24 h — automatycznie przy starcie.

## 11. Wczytywanie i eksport

- **Z innej ścieżki** — `POST /api/open` (Upload możliwy).
- **Z komputera** — `POST /api/load` (surowe bajty, nagłówek `X-Filename`), sprawdzany nagłówek SQLite i tabela `BaseItems`; rodzaj `upload` (tylko eksport).
- **Import SQL** — `POST /api/import-sql` (surowe bajty, `X-Filename`): dump `.sql`/`.sql.gz` jest przesyłany strumieniowo, rozpakowywany, wykonywany przez `sqlite3` CLI (jeśli jest w systemie) albo przez wbudowany parser strumieniowy, a gotowa baza trafia jako kopia robocza (`kind=upload`). Postęp: `/api/sqljob`.
- **Eksport SQL** — formularz POST `/api/export-sql` z polem `t=<token>` (i `gz=1` dla `.sql.gz`): pełny dump `iterdump()` z kopii roboczej; token nie trafia do URL/historii przeglądarki.
- **Eksport** — formularz POST `/api/export` z polem `t=<token>` → `jellyfin-kopia-robocza_<data>.db`. Stare GET `?t=` nadal działa dla zgodności.

## 12. Tryby LIMITED / ADMIN

| Tryb | Opis |
|---|---|
| LIMITED | domyślny; brak odczytu chronionych folderów i start/stop |
| ADMIN (sudo) | hasło sudo; sesja wygasa po 15 min bezczynności |
| ADMIN (root) | program uruchomiony jako root |

Hasło idzie tylko na stdin `sudo`, nie jest zapisywane. Dalej działa proces pomocniczy ze stałym zestawem operacji: `ping`, `stat`, `read`, `install`, `remove`, `svc` (systemd/Docker, nazwa walidowana). Wymaga systemowego `python3` (do zmiany przy pakowaniu AppImage).

Na **Windows** tryb ADMIN nie istnieje: `GET /api/priv` zwraca `platform:"windows"` i `mode:"limited"`, a `POST /api/priv {action:"enable"}` → `400` z komunikatem o braku sudo. Przycisk w UI jest wyłączony, a na ekranie „Nie wczytano bazy" ukryty. Plakietka w pasku pokazuje `USER` albo `ADMIN` na podstawie `IsUserAnAdmin()` (proces z podniesionymi uprawnieniami), a nie na podstawie sesji sudo.

## 13. API HTTP (lokalne)

| Trasa | Metoda | Token | Opis |
|---|---|---|---|
| `/` | GET | – | interfejs (token wstawiany do strony) |
| `/api/info` | GET | – | ścieżka, dirty, kind, label, nodb, nodb_reason, platform, loading, setup |
| `/api/setup` | GET / POST | POST | stan konfiguracji (`platform`, `db_default`, `db_options`); zapis `path` (folder danych) |
| `/api/pickdir` | POST | tak | systemowe okno wyboru folderu |
| `/api/types` | GET | – | kategorie: biblioteki albo typy |
| `/api/list` | GET | – | `type`, `sort`, `q`, `disk` (filtr dysku), `limit` (strona, domyślnie 2000, maks. 5000), `offset` (paginacja bez górnego limitu) |
| `/api/tree` | GET | – | drzewo pozycji (`id`) |
| `/api/problems` | GET | – | problemy `{items, total, limit}` |
| `/api/disks` | GET | – | dyski (`refresh=1` przelicza statusy): `disks` (foldery) i `mounts` (punkty montowania) |
| `/img` | GET | – | obraz po `id` |
| `/api/export` | GET / POST | `?t=` / pole `t` | kopia robocza; POST z formularza nie ujawnia tokenu w URL/historii |
| `/api/jellyfin` | GET / POST | POST | stan; akcje `test`, `save`, `scan` |
| `/api/priv` | GET / POST | POST | tryb + `platform` + `label` (`user`/`sudo`/`admin`/`root`); `enable` (hasło), `disable`; Windows: `enable` → 400 |
| `/api/service` | GET / POST | POST | usługa; `start`, `stop` |
| `/api/history` | GET / POST | POST | lista (`id` = szczegóły); POST `{action:"clear"}` |
| `/api/backup` | POST | tak | kopia bazy w `<data_dir>/backups/` + wpis metadanych (`ver`) |
| `/api/backups` | GET / POST | POST | lista ręcznych kopii; `id` = różnice względem bieżącej bazy; POST `{action:"delete", id}` |
| `/api/job` | GET | – | postęp operacji (np. reload: fazy i bajty) |
| `/api/sqljob` | GET | – | postęp importu SQL (faza, bajty) |
| `/api/import-sql` | POST | tak | surowy dump SQL / `.sql.gz` (`X-Filename`) |
| `/api/export-sql` | GET / POST | `?t=` / pole `t` | dump SQL (`gz=1` → `.sql.gz`); POST jak wyżej |
| `/api/orphans` | GET / POST | POST | sieroty w tabelach powiązanych; POST `{clean:true}` usuwa i zwraca `removed`/`total` |
| `/api/settings` | POST | tak | `history_max`, `data_dir` |
| `/api/delete` | POST | tak | `ids`, `force` |
| `/api/upload` | POST | tak | `backup`, `ver` → wpis historii |
| `/api/revert` | POST | tak | `id`, `backup` |
| `/api/reload` | POST | tak | odrzuć zmiany |
| `/api/open` | POST | tak | `path` |
| `/api/load` | POST | tak | surowy plik bazy |
| `/api/pick` | POST | tak | systemowe okno wyboru bazy i od razu otwarcie (starsza ścieżka) |
| `/api/pickpath` | POST | tak | systemowe okno wyboru bazy — zwraca `path` bez otwierania (bez sudo) |

Błędy: JSON `{error}`; `403 need_admin`, `409 {nodb, loading}`.

## 14. Zakres danych Jellyfina

`BaseItems`: `Id`, `Name`, `SortName`, `Type`, `Path`, `ParentId`, `TopParentId`, `SeriesId`, `SeasonId`, `SeriesName`, `IndexNumber`, `ParentIndexNumber`, `ProductionYear`, `Size`, `PrimaryVersionId`, `Data`.
`BaseItemImageInfos`: `Id`, `ItemId`, `ImageType` (0–12), `Path`.
Typy: `…CollectionFolder`, `…Series`, `…Season`, `…Episode`, `…Movie` i inne.

Schemat z epoki EF Core (Jellyfin 10.10+). Wersji Jellyfina nie da się ustalić z pliku bazy — pokazuje ją tylko `/System/Info/Public` działającego serwera.

## 15. Tłumaczenia

Języki: **pl, en, de, fr, es, ru, it, nl** (ok. 230 kluczy). Jedno źródło prawdy w Pythonie (`TEXT`): UI wstawia słownik do strony, serwer tłumaczy komunikaty błędów i powody problemów na podstawie nagłówka `X-Lang`. Powody i statusy dysków są przechowywane jako klucze, tłumaczone przy wysyłce.

## 16. Testy

Wykonane na kopii bazy użytkownika (2 tabele) oraz w przeglądarce (Chromium w aplikacji):

- import, biblioteki, duplikaty, drzewo, wyszukiwanie, eksport,
- usuwanie → reload (oryginał nietknięty), upload z backupem i historią, revert (16625 → 16615 wpisów),
- historia: wpisy, rozwijanie, przycinanie po limicie, czyszczenie, brak pliku → blokada Restore,
- instalator: odrzucenie root/home, utworzenie nowego folderu, trwałość po restarcie,
- dyski: punkty montowania (Linux/Windows/macOS/Docker), fstab z `noauto`, `\040`, NFS, statusy i kolory; `lsblk` z mapą ścieżka→urządzenie: zamontowany, obecny-niezamontowany (`unmounted`), odłączony (`detached`), fallback fstab, brak `lsblk` → `unknown` na Windows,
- **config portable 1.6.13:** nowy folder wersji → brak configu → setup; po zapisie `jf_browser.settings.json` obok programu i backup w nowym folderze (stary `backups/` bez zmian).
- **wykrywanie bazy 1.6.19:** lista domyślnych ścieżek (Windows/Linux/Docker/folder programu), wybór `jellyfin.db` w setupie i zapis `db_path`; test: setup z wybraną bazą → wczytana, restart **bez `--db`** wczytuje ją z configu; `valid_db_file` odrzuca `.sql` i brak pliku.
- **szybkie poprawki 1.6.18:** `None` w nazwie `.bak` = zajęte; `PRIV_LOCK` jako RLock (priv_disable pod lockiem, bez blokady); `install_file` tylko z zapisywalnym katalogiem (+ fallback); `reset_work` odporny na błąd i odtwarza połączenie; timeout 30 s przy `/api/load` i imporcie SQL (400 zamiast wiszenia); GET bez ujawniania wyjątków (ogólny komunikat + log); `/api/problems` zwraca `{items,total,limit}` i UI pokazuje „z N wpisów (limit)".
- blokada usunięcia z `missing` bez `force`, z `force` przechodzi; pomarańczowy bez blokady,
- UI: menu, okna, filtry, paski ładowania, przełączanie języków,
- **refaktor 1.4.0:** interfejs w `ui/index.html`, tłumaczenia w `i18n.py`; sprawdzone: strona z tokenem i słownikiem, brak placeholderów, tłumaczenia API (de), eksport SQL, historia, dyski, brak błędów w konsoli.
- **walidacja schematu:** porównanie tabel nowej bazy z oryginałem — ta sama struktura przechodzi bez ostrzeżeń, brakujące tabele (np. przy okrojonej kopii) dają `409 {schema:true}` i `force_schema` przechodzi.
- **Host 1.5.2:** brak nagłówka → 403, domena (rebinding) → 403, `127.0.0.1`/`localhost`/IP LAN/`[::1]` → 200; POST z domeną → 403.
- **1.6.0:** backup z historii (plik w `backups/`), postęp `%` przy reload, sortowanie po tytule, podpowiedź „sugerowane usunięcie", czytelne błędy importu SQL (`.db`/binarne), ukrywanie okien systemowych bez tkinter/DISPLAY, popup wyjaśniający brak kluczowych tabel, status dysków oparty na montowaniach (Linux) także przy braku dostępu do żadnego folderu.
- **1.6.6:** ręczne kopie jako osobna sekcja historii z metadanymi i różnicami względem bieżącej bazy (`+` w kopii / `−` w bazie); test: po usunięciu wpisu różnica `+1`, po reloadzie `—`.
- **1.6.9:** „Wyczyść historię" usuwa tylko automatyczną (test: 5 wpisów usuniętych, 2 ręczne kopie zostały); kosz przy każdej ręcznej kopii usuwa plik i wpis (test: potwierdzenie → ubyła 1 kopia, plik zniknął).
- **Windows 1.6.24:** `/api/priv` → `platform:windows`, `mode:limited`, `sudo:false`; `POST enable` → 400 z komunikatem o braku sudo; przycisk ADMIN wyłączony, ukryty na ekranie braku bazy; okno ścieżki: otwarcie, Enter, Esc i Anuluj; `cancel` pola pliku czyści wartość i zdejmuje fokus; brak błędów konsoli (poza celowym 400 z testu złej ścieżki).
- **1.6.25:** `/api/setup` → `platform:windows`, `db_default:C:\ProgramData\...`; okno „innej ścieżki" domyślnie pokazuje ścieżkę Windows (mimo bieżącego `src` w stylu linuksowym); ścieżka linuksowa na Windows → `400 e_path_style` (test API: EN/DE, komunikat PL sprawdzony w `tr`); wybór pliku w Chromium idzie przez `showOpenFilePicker` (test: wywołanie 1, anulowanie Esc, UI odpowiada natychmiast, fokus wraca na przycisk); ikona ⏭ ukrywa ekran braku bazy i nie wraca po `refreshStatus`; menu Ustawienia działa po pominięciu; brak błędów konsoli.
- **1.6.26:** bez bazy `#status` ma klasę `bad` (czerwony) i tekst „Baza nie wczytana. Nie znaleziono pliku: …”; sekcja Dyski w Ustawieniach i Połączeniu pokazuje komunikat o braku bazy, przycisk odświeżania jest wyłączony; brak żądań `/api/disks` (konsola bez 409). Po wczytaniu bazy: status zielony, dyski wypełnione, „Sprawdź ponownie" wysyła `/api/disks?refresh=1`.
- **1.6.27:** start z `--db /var/lib/...` na Windows → ścieżka pominięta, `/api/info` zwraca `platform:windows` i `src`/`nodb_reason` z `C:\ProgramData\...`; napis na ekranie braku bazy i czerwony status w Ustawieniach pokazują ścieżkę Windows; brak śladu ścieżki linuksowej w UI; brak błędów konsoli.
- **1.6.28:** `/api/priv` → `label:"user"` na Windows bez podniesionych uprawnień; plakietka `USER` obok języka (szara), tooltip tłumaczony; symulacja `ADMIN`/`ROOT`/`SUDO` daje odpowiednie kolory i podpisy; zmiana języka aktualizuje tooltip; brak błędów konsoli.
- **1.6.29:** backup przy Uploadzie z żywego pliku (kopia + `quick_check` na tymczasowym serwerze, 16 625 wpisów); brak tabel tymczasowych — biblioteki/filtry działają przez CTE/`IN`, testy typów/listy/problemów; cache `stat` (drugie sprawdzenie z pamięci, czyszczenie przy odświeżeniu); `limit` listy (5/50 wierszy) i „Pokaż więcej"; równoległy skan portów (20 portów × 0,2 s → 0,2 s); czyszczenie 35 sierot obrazów i powrót przez reload; usuwanie starych `jfdb_*` (24 h); skrypt SQL Docker/systemd; POST eksportu `.db`/`.sql.gz` (200, poprawne nazwy plików); docstring platform.
- **1.6.30:** prawdziwa paginacja `limit`/`offset` bez sufitu 20 000; test na kopii z **46 625** wpisami — `offset=20000` i `offset=30000` zwracają dalsze pozycje „Over20k"; UI dokłada 5 → 10 wierszy; sortowanie problemów nadal skanuje wszystkie pasujące pozycje (może być wolniejsze na ogromnych bibliotekach).

**Niesprawdzone:** prawdziwe `sudo`/`systemctl`/Docker w tej sesji, systemd automount, macOS, AppImage/EXE, wydajność na bardzo dużych bazach (>1 GB), miniatury z prawdziwych folderów w trybie ADMIN, realny skan portów na Linuksie (logika równoległa sprawdzona na makiecie).

## 17. Znane ograniczenia

- Sieroty w tabelach powiązanych nie są usuwane automatycznie razem z `BaseItems` — trzeba użyć osobnej sekcji w Ustawieniach (pomija `UserData`).
- Kontrola dysków działa tam, gdzie te same ścieżki istnieją (serwer/kontener); przy bazie z innej maszyny bez `/proc` statusy są „nie sprawdzono". Na Linuksie (są montowania) brak dostępu do folderów daje czerwony/pomarańczowy, a nie szary.
- Program i Jellyfin w różnych przestrzeniach montowania (host vs kontener) → ścieżki kontenera mogą wyjść jako „brak" (chroni blokada usuwania).
- macOS: brak `/proc` — nie wykryje odłączonego wolumenu, tylko brak folderu.
- Montowania systemd `automount` (bez fstab) nie są rozpoznawane jako oczekiwane.
- `.sql`/`.sql.gz` są importowane; jeśli system nie ma `sqlite3` CLI, używany jest wbudowany parser (wolniejszy przy bardzo dużych dumpach).
- W trybie LIMITED miniatury z chronionych folderów się nie wyświetlą.
- Zwykła lista jest stronicowana (`limit`/`offset`), ale sortowanie „najpierw problemy" i „tylko problemy" pobiera wszystkie pasujące wiersze do analizy — przy bardzo dużych bibliotekach (setki tysięcy) może to być wolne.

## 18. Plan dalszy

1. **AppImage / EXE:** PyInstaller + `appimagetool` (katalog `ui/` przez `--add-data`), tryb portable (`settings.json` obok programu), tkinter w paczce, **funkcje per platforma**:
   - **Windows:** bez sudo/ADMIN (zrobione w 1.6.24), `os.startfile`/`webbrowser` zamiast `xdg-open`, usługa Jellyfina przez `sc.exe`/`net stop`, wybór pliku w tkinterze **w procesie lub wątku** (w zamrożonym EXE `sys.executable -c` nie uruchomi Pythona), ścieżki `%ProgramData%`/`%LOCALAPPDATA%`, ukryta konsola i ikona;
   - **macOS (niezbadany):** `open` zamiast `xdg-open`, usługa przez `launchctl`, uprawnienia bez sudo (UI bez ADMIN);
   - **Linux/AppImage:** helper ADMIN bez systemowego `python3` (re-exec binarki), `libfuse2`, `systemctl`/Docker, `xdg-open`.
2. **Weryfikacja `sqlite3` CLI przy pakowaniu (AppImage / inne systemy):** sprawdzić, czy `sqlite3` jest zainstalowany; jeśli nie, przy pierwszym starcie pokazać okno kontrolne (folder `tmp/history`, `sqlite3`) z:
   - ikoną/przyciskiem **„Zainstaluj sqlite3"** (instrukcja dla dystrybucji),
   - wskazaniem **folderu, w którym leży `sqlite3`**, gdy nie zostanie wykryty automatycznie (zapis w ustawieniach),
   - **postępem akcji** (instalacja/weryfikacja/import).
   Import SQL działa też bez CLI (parser wbudowany), ale CLI jest szybszy dla dużych dumpów.
3. **Instalator AppImage/EXE (później):** zachować tryb portable; instalator wykrywa ścieżkę, nadpisuje pliki programu, importuje setup ze starej wersji (`data_dir`, `jf_port`, `jf_service`, `history_max`, `disk_map`) i uwzględnia zmiany.
4. Testy automatyczne w repo (`tests/`).
5. Usuwanie pojedynczych wpisów historii, zmiana folderu danych z Ustawień.

## 19. Wersjonowanie

Schemat **X.Y.Z**: `X` — przełom, `Y` — duża zmiana funkcjonalna, `Z` — poprawka/rozszerzenie (także powyżej 10: 1.6.25). Każda zmiana = nowy commit i **nowy tag** `vX.Y.Z` (tagi są niezmienne; commity nigdy nie są usuwane; dokumentacja bez osobnego tagu). Historia: `v1.1.0` → `v1.6.30`; pełna lista w `wersje.md`. Wersję `1.7.0` rezerwujemy na duże zmiany (np. pakowanie AppImage).
