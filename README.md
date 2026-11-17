# Jellyfin DB editor

Lokalna przeglądarka i czyszczarka bazy `jellyfin.db` Jellyfina. Działa w przeglądarce, ale wszystkie operacje wykonuje lokalny serwer — oryginalna baza i pliki mediów pozostają nietknięte aż do świadomego **Upload** lub **Revert**.

## Co potrafi

- przeglądanie bibliotek, typów, seriali i filmów, wyszukiwanie i filtrowanie po dyskach,
- wykrywanie brakujących plików, odmontowanych lub odłączonych dysków, duplikatów, osieroconych wpisów i sierot w tabelach powiązanych,
- bezpieczne usuwanie wpisów w kopii roboczej, z blokadą dla niedostępnych dysków,
- **Upload** i **Revert** z kopią zapasową, historią wersji i walidacją schematu,
- import/eksport SQL, eksport całej bazy `.db` i ręczny skrypt SQL,
- interfejs w **8 językach**, tryb portable i obsługa Linux/Windows (macOS nietestowany).

## Bezpieczeństwo

- oryginał jest zmieniany wyłącznie przez **Upload** lub **Revert**,
- usuwanie odbywa się na kopii roboczej w `<data_dir>/tmp`, kasowanej po zamknięciu,
- backup przed Uploadem jest robiony z żywego pliku, a nowa baza przechodzi `quick_check`,
- serwer słucha lokalnie, wymaga tokenu i waliduje nagłówek `Host`.

## Wymagania

- Python 3 (tylko biblioteka standardowa),
- przeglądarka graficzna,
- baza Jellyfina 10.10+ (schemat EF Core).

## Szybki start

```bash
python3 jf_browser.py
# http://127.0.0.1:8099
```

Opcjonalnie: `python3 jf_browser.py --db /ścieżka/do/jellyfin.db`. Przy pierwszym uruchomieniu kreator wybierze folder danych i bazę.

## Dokumentacja

- **[README-extensive.md](README-extensive.md)** — pełny opis funkcji, ustawień, API i ograniczeń.
- `jf_browser_dokumentacja.md` — dokumentacja techniczna projektu.

## Licencja

MIT — szczegóły w [LICENSE](LICENSE).
