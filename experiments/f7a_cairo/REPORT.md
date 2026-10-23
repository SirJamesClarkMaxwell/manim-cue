# Raport szkicu 7a — 2026-10-23

Wykonano pomiar przed zmianą sekcji 7a w PLAN.md. Adapter nie został zaimplementowany.
Gałąź `develop`, główne drzewo; zmiany tylko w PLAN.md i tym katalogu, bez commitu.

## Wynik pomiaru

CE 0.22.0, Windows, bez okna i wyjścia multimedialnego. 30 klatek rozgrzewki i 240
próbek na scenę/rozmiar. Pełny render Cairo, następnie kopia do przydzielonego bufora
RGBA bottom-up; bez aktualizacji geometrii i transportu. Szczegóły: README.md,
środowisko, wszystkie mediany/p95 i surowe próbki: results.json.

Panel 2D, obrót kwadratu (najwolniejszy wariant Panel w każdym rozmiarze):

| bufor | treść | render mediana / p95 ms | kopia mediana / p95 ms | p95 razem ms | kl./s render + kopia |
|---|---|---|---|---|---|
| 960×540 | 960×540 | 0,407 / 0,486 | 0,095 / 0,109 | 0,589 | 1875,5 |
| 480×270 | 480×270 | 0,225 / 0,255 | 0,013 / 0,015 | 0,269 | 4117,3 |
| 538×648 | 538×303 + pasy | 2,257 / 3,478 | 0,144 / 0,261 | 3,801 | 452,2 |

33 zmierzone kombinacje, 3 jawne pominięcia TeX: lokalny MiKTeX wymaga konfiguracji.
Wynik końcowego przebiegu zastąpił pierwszy przebieg po uściśleniu wzoru korpusu TeX
i przeniesieniu jego plików pomocniczych do `.tmp`. Nie wybierano szybszego wyniku.
Zmienność CPU widać zwłaszcza w ostatnich przypadkach; to krótki mikrobenchmark,
bez gwarancji dla dowolnej złożoności i bez zaliczenia pełnych progów F2.

## Najważniejsze ustalenia kontraktu

- `play` w CE 0.22 przechodzi przez managera. Własna pętla `play_internal` musi
  zachować begin/finish/cleanup i ustawiać czas aktywny przed updaterami. Samo
  przechwycenie add_frame daje błędny zegar przy opuszczaniu klatek.
- Statyczny wait omija zwykłą pętlę play: potrzebuje osobnej kooperacyjnej ścieżki.
  D10 domyka wszystkie kolejne play w callable, D9 kończy powtórzenie pętli.
- `format=none` wyłącza artefakty i segmenty; `disable_caching=True` omija cache/hash.
  Nie stosować usuniętego `write_to_movie` ani okna interactive_embed OpenGL.
- Wybór `engine` jest jawny i przekazywany przez model, LiveSpec, workera,
  obie tożsamości D33 oraz cache miniatur. Stare decki zachowują manimgl;
  proponowany zapis v4 zapobiega błędnej interpretacji CE przez starszy player.
- Cairo jest top-down; istniejący bufor transportu v1 bottom-up, OwnedFrame top-down.
  Nie trzeba nowego protokołu TCP ani pamięci. READY dopiero po pierwszej klatce,
  bariery, cue wejścia i fokus zachowują istniejące reguły.
- Alfa pustego tła i pasów D35 to pierwsza bramka implementacji. Kod CE nie uzasadnia
  bezwarunkowego traktowania wszystkich pikseli jako straight/premultiplied RGBA.
- Cofanie CE potrzebuje snapshotu zachowującego referencje i strukturę grup.
  Nawigacja 2D obejmuje pan/zoom/reset; orbit i CE 3D są poza 7a.
- 60 fps jest celem produktowym do sprawdzenia pełnym pomiarem trzech rozmiarów;
  mikrobenchmark nie dowodzi stabilności ani kosztu transportu. Progi manimgl F2 bez zmian.

## Weryfikacja i ograniczenia

Skrypt uruchomiono przez `uv run --frozen` offline, z ustawieniami TMP/TEMP/Qt
z zadania. Samokontrole kształtu RGBA, koloru, kopii i wyłączonego wyjścia CE przeszły.
`git diff --check` bez błędów. Nie zmieniano `.venv`; nie uruchamiano okna ani pełnej
regresji aplikacji, ponieważ zmiana nie implementuje adaptera. Pliki pomocnicze
pierwszego pomiaru usunięto wyłącznie z katalogu eksperymentu.

Próba wymaganej przez CLAUDE.md recenzji: `codex exec -s read-only` przez shim `.ps1`
zablokowała polityka uruchamiania PowerShell. `codex.cmd exec -s read-only` uruchomił
klienta, lecz połączenia WebSocket i HTTPS do API były blokowane (`os error 10013`);
próbę przerwano. Niezależna recenzja nie została wykonana; runda 19 pozostaje otwarta.
REVIEW-LOG.md nie zmieniono, zgodnie z ograniczeniem zakresu plików użytkownika.

**Aktualizacja po rundzie 19 (2026-10-23):** powyżej zachowano raport historycznego PoC;
domknięty kontrakt i implementacja są w PLAN.md, D36–D38 oraz REPORT-7a.md. Pan/zoom/reset
CE odroczono; historia zachowuje graf standardowych paneli 2D, bez dowolnego stanu Pythona.
Pełna dostarczona recenzja rundy 19 jest zapisana w REVIEW-LOG.md.

## Czas pracy

Około 8–10 minut łącznie z lekturą, dwoma krótkimi przebiegami i próbą recenzji
(szacunek czasu całej pracy; brak znacznika startu sprzed pierwszej lektury).
Dokładny czas samego końcowego pomiaru jest w `results.json: elapsed_seconds`;
skrypt utworzono o 00:52:11, końcową kontrolę wykonano około 00:57 CEST.
Budżet implementacji zaproponowany w PLAN.md: 12 h, stop przy 24 h;
szkic i pomiar mieszczą się w budżecie 1 h.
