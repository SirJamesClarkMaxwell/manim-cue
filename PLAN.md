# manim-cue — plan rozwoju

Stan (2026-10-22): **fazy 0-3 i 7.0 (CE 0.22) zamknięte; 4, 5, 6a po pierwszej próbie
prelegenta (uwagi niżej), 6b czeka na decyzję o `greenlet`. Aktywna: 5c (druga próba), potem
5d-5f.** Kierunek zmieniony 2026-10-21 decyzjami D13-D19 w `SPEC.md`: projekt staje się forkiem
manim-slides 5.7.0, rozszerzonym o warstwy i wstrzykiwany live.
Rundy 6-7 recenzji (codex) przebudowały fazy 2-9; decyzje D20-D22.

## Wizja (prelegent, 2026-10-21)

1. Fork manim-slides z rozszerzoną funkcjonalnością.
2. Scena jako obiekt w innej scenie: wyzwalanie jej animacji, przesuwanie finalnego renderu.
3. Notatki prelegenta i podgląd następnego slajdu.
4. Domyślnie prerender, z możliwością wstrzyknięcia sceny interaktywnej.
5. Silniki w kolejności: Manim CE, manimgl, manimgx.

**Co z tego już istnieje:**
- (3) okno Info manim-slides 5.7.0 — notatki w markdown, podgląd następnego slajdu, zegar,
  obsługa dwóch ekranów (`present/player.py:24-160`). Zero pracy dla slajdów prerenderowanych.
- (4, strona live) `LiveScene` z fazy 0 — TCP, `select`, klawisze, animowane cofanie, pętla,
  przerywanie animacji.
- (5, prerender) manim-slides renderuje CE (`slide/manim.py`) i GL (`slide/manimlib.py`).

**Zasada budżetu:** każda faza ma szacunek. Przy przekroczeniu dwukrotnym — zatrzymać się
i zgłosić, zamiast dociągać.

---

## Faza 0 — PoC żywej sceny (zamknięta)

`LiveScene` w manimgl: okno żyje, komendy po TCP z `127.0.0.1`, jeden wątek, `select` z timeoutem
jednej klatki. Dziewięć kryteriów z `SPEC.md`, wszystkie spełnione; trzecia pułapka (kolejność
klient-przed-listenerem) wyszła dopiero w teście w oknie.

Zrobione zaliczkowo w starej fazie 1 i zostaje: strzałki z sekwencją (D1, D2), animowane cofanie
(D3), zapętlenie cue (D9), przerywanie animacji w dowolnej klatce (D10), komendy `next`/`back`.

**Rola w nowym planie:** backend live. Faza 2 dokłada mu tryb headless ze strumieniem klatek.

---

## Faza 1 — fork manim-slides (czeka na próbę w oknie)

**Cel:** manim-slides 5.7.0 wchłonięty do `src/manimcue/slides/`, działający pod CLI `manim-cue`
tak samo jak oryginał. Nic nowego funkcjonalnie — fundament pod fazy 3-5.

**Źródło:** tag `v5.7.0`, commit `305bd8a`, licencja MIT (D13).

**Zakres:** przeniesienie kodu i testów upstreamu, przemianowanie importów `manim_slides` →
`manimcue.slides`, usunięcie `ipython/` i `docs/`, zależności w `pyproject.toml`, demo deck.

**Kryteria akceptacji:**
1. Kod upstreamu w `src/manimcue/slides/`, bez `ipython/` i `docs/`. Zero importów `manim_slides`
   w `src/` i `tests/`.
2. Licencja upstreamu leży obok kodu; `README.md` mówi, skąd kod pochodzi.
3. CLI `manim-cue` z komendami `render`, `present`, `convert`, `wizard`, `init`, `list-scenes`,
   `checkhealth`.
4. Testy upstreamu przeniesione i zielone; pominięte tylko z podanym powodem środowiskowym.
   30 testów fazy 0 nadal zielonych.
5. Demo deck `examples/demo.py` renderuje się w CE i w GL; `manim-cue present` pokazuje go
   z notatkami i podglądem — weryfikacja w oknie przez prelegenta.
6. Sprawdzanie nowej wersji na PyPI wyłączone: porównywałoby fork z manim-slides.

**Budżet:** ~2 h, stop przy 4 h.

**Wynik (2026-10-22, Windows 11):**
- 1-4, 6 — spełnione. `uv run pytest`: **269 passed, 1 skipped** (pominięcie jest upstreamowe:
  `test_present.py:142`, „Fails when running the whole test suite”). Demo deck renderuje się
  w CE i GL (3 slajdy, notatki, pętla w JSON); `manim-cue present` startuje bez tracebacku
  w trybie offscreen.
- 5 — spełnione 2026-10-22 po poprawce: próba prelegenta w oknie wykazała krzaki w notatkach.
  Błąd upstreamu: `PresentationConfig.from_file` czytał JSON kodowaniem systemowym (cp1252),
  a `to_file` zapisuje UTF-8 (`config.py:335`, test `test_notes_round_trip_utf8`). Po poprawce
  prelegent potwierdził notatki i podgląd.
- **Odstępstwo (zamknięte w fazie 7.0, 2026-10-22):** Manim CE był przypięty do `<0.22` — manim-slides 5.7.0 pada na CE 0.22
  (`SPEC.md`, ustalenia rundy 6). Wsparcie CE 0.22 to osobna praca: przed adapterami CE
  (faza 7), bezwzględnie przed integracją seminarium (faza 8), bo seminarium stoi na CE 0.22.
- Przy okazji naprawione: testy fazy 0 padały na każdej opcji pytesta poza `-q`, bo manimgl
  parsuje `sys.argv` przy imporcie (`tests/conftest.py`).
- Czas pracy nie był mierzony zegarem — ta sama luka co w kryterium 9 fazy 0.

---

## Decyzje przed fazą 2 — rozstrzygnięte (2026-10-22)

Runda 6 wskazała sześć decyzji; prelegent przyjął 2-6 jak w propozycji, na 1 odpowiedział
kliknięciem w okno. Po rundzie 7: D20 (przygotowanie przy wejściu, aktywacja kliknięciem),
D21 (spawn + `Lock` + SharedMemory), D22 (korpus scen) w `SPEC.md`.

**Progi wydajności (decyzja 2):** panel 960×540 ≥ 60 różnych odebranych klatek/s, 1920×1080 ≥ 30,
CPU procesu live w statycznej bezczynności < 5% rdzenia, p95 komenda → odebrana zmieniona klatka
< 100 ms (ciepła sesja). Zimny start raportowany osobno.

**Semantyka warstw (decyzja 4):** źródła ładowane przed wspólnym startem; równe efektywne
długości (po `playback_rate`); slajd kończy wskazana warstwa plikowa albo prelegent; live nie
steruje końcem slajdu; reverse kompozycji ograniczony jawnie.

---

## Faza 2 — strumień klatek z procesu live (zamknięta)

**Cel:** osobny proces GL bez okna → SharedMemory → minimalny odbiornik Qt, z poprawnym czasem
animacji, klatkami granicznymi i zamykaniem. **Bez playera**, bez modelu slajdów, bez CE.

**Pliki:** `src/manimcue/live_worker.py` (target spawn, bootstrap, nadzór; bez importów Manima
i Qt na poziomie modułu), `src/manimcue/frame_buffer.py` (format bloku i kopia pod blokadą; bez
Manima i Qt), `src/manimcue/live_session.py` (właściciel procesu, pamięci i połączenia; API
nieblokujące GUI), `src/manimcue/live_scene.py` (tryb headless obok trybu okna),
`examples/live_receiver.py` (minimalny `QLabel`), sceny `tests/scenes/live_gl.py`, testy.

**Kontrakt:** pełna specyfikacja z rundy 7 — `REVIEW-LOG.md`, „Specyfikacja F2 do przekazania
wykonawcy”: API (`LiveSpec`, `run_worker`, `LiveSession`), bootstrap (spawn, czyste argv,
`Scene(window=None)`, wyłączony zapis filmu, READY po pierwszej klatce), protokół pamięci (D21),
transport (`shutdown`, `frame_seen <id>`, statusy READY/ERROR; parser odróżnia komendę od
przerwania — nieznana komenda nie przerywa cue), zegar (`time.monotonic()`, oczekiwanie przez
`select`, updatery zamrożone między cue, statyczna bezczynność bez renderu), zamykanie (2 s
kooperacyjnie, potem wymuszenie; świeże zasoby po restarcie).

**API (zamknięte 2026-10-22, wspólne dla scen, testów i implementacji):**

```python
# src/manimcue/live_session.py
@dataclass(frozen=True)
class LiveSpec:
    scene_file: str          # ścieżka absolutna do pliku sceny
    scene_name: str          # klasa, podklasa LiveScene
    width: int = 960
    height: int = 540
    fps: int = 60

@dataclass(frozen=True)
class OwnedFrame:
    frame_id: int
    width: int
    height: int
    timestamp: float         # time.monotonic() procesu live w chwili publikacji
    boundary: bool           # klatka graniczna: start, koniec/przerwanie cue, cofnięcie
    pixels: bytes            # RGBA8, wiersze od góry, stride = 4 * width
    def pixel(self, x: int, y: int) -> tuple[int, int, int, int]: ...  # (0, 0) = lewy górny róg

class LiveSession:
    state: str               # "idle" | "starting" | "ready" | "error" | "stopped"
    error: str | None
    def start(self, spec: LiveSpec) -> None: ...
    def poll(self) -> list[str]: ...   # nowe zdarzenia: "READY", "CUE_START <nazwa>",
                                       # "CUE_DONE <nazwa>", "SEQUENCE_END", "ERROR <opis>", "STOPPED"
    def send(self, command: str) -> None: ...
    def try_read_frame(self) -> OwnedFrame | None: ...  # najnowsza nowa klatka albo None
    def request_stop(self) -> None: ...
```

Żadna metoda `LiveSession` nie blokuje (GUI). Potwierdzenie `frame_seen` wysyła sama sesja przy
kopii klatki granicznej. `time.monotonic()` na Windows jest wspólne dla procesów jednej maszyny,
więc znaczniki czasu da się porównywać z czasem odbiornika.

**Kryteria jako testy:** 13 testów z kontraktu (`test_spawn_from_console_entrypoint` …
`test_no_movie_output`) plus pomiar akceptacyjny: progi wydajności z decyzji 2, 30 s prostej
animacji po rozgrzewce, osobne czasy renderu, odczytu GPU, publikacji i kopii odbiornika.
Testy z prawdziwym GL oznaczone `gpu`. Offscreen Qt nie zalicza płynności na projektorze ani
fokusu — to próba prelegenta.

**Wykonawca:** codex (workspace-write) jako jedyny właściciel integracji F2 — części są zależne
(definicje „gotowy”, „przerwany”, „ostatnia klatka”). Sceny korpusu F1/F2: Claude Haiku.
Przegląd, uruchomienie testów i pomiar: Claude.

**Budżet:** ~3 h, raport stanu przy 6 h.

**Wynik (2026-10-22, Windows 11, RTX 4060):**
- `uv run pytest`: testy projektu 80 passed + 1 skip środowiskowy (TeX, niżej); upstream
  slides 240 (1 skip upstreamu). 13 testów kontraktu zielone; korpus: 13 scen zielonych,
  `LiveGLTex` pominięta — scena TeX nie była wykonana na żadnej maszynie. Xfaile zdjęte.
- Pomiar (`live-measurement.json`, Qt offscreen, 30 s po rozgrzewce):

  | | 960×540 | 1920×1080 |
  |---|---|---|
  | klatki opublikowane / odebrane / różne (30 s) | 1800 / 1800 / 1799 | 1796 / 1796 / 1795 |
  | różne odebrane klatki/s | 59,97 (próg ≥ 60·T − 2) | 59,83 (próg ≥ 30·T − 2) |
  | CPU w bezczynności (próg < 5%) | 0% rdzenia | 2,2% |
  | p95 komenda → zmieniona klatka (próg < 100 ms) | 18 ms | 28 ms |
  | render / odczyt GPU / publikacja / kopia odbiornika | 0,6 / 4,7 / 0,2 / 1,6 ms | 0,5 / 7,4 / 0,5 / 3,9 ms |
  | zimny start | 1,8 s (31,7 s w pierwszym pomiarze dnia) | 1,8 s |

- **Próg fps (D26 po rundzie 8):** pierwotne 59,96 przy progu „≥ 60” to granica okna, nie strata —
  każda opublikowana klatka została odebrana. Próg to teraz „≥ fps·T − 2 klatki”; pomiar zamraża
  liczniki z końcem okna i zapisuje surowe liczby. Pierwszy pomiar (29 fps) wyprzedzał poprawkę
  tempa: `select` na Windows zaokrągla timeout w górę do
  ~15,6 ms, tempo trzyma teraz `time.sleep` (`live_scene.py:505`).
- Test `test_clock_skips_missed_deadlines` po poprawce tempa wisiał w nieskończonej pętli
  (fałszywy zegar szedł tylko przez `live_poll`); teraz podmienia też `time.sleep`.
- **TeX nie działa na tej maszynie z manimgl:** manimgl woła `latex -no-pdf`, a pdfTeX z MiKTeX
  24.4 odrzuca tę opcję (`optionError="unknown option"`). Błąd środowiska/upstreamu, nie F2;
  `test_tex_renders` sonduje teraz właściwą kompilację i robi jawny skip (D22).
- Próba w oknie (`examples/live_receiver.py`): sekwencja, cofanie do początku, koniec sekwencji
  i zamknięcie bez tracebacku — z logu. Scena musi być podklasą `LiveScene` z własnego pliku:
  `live_scene.py` ładowany po ścieżce to drugi moduł, a `issubclass` z oryginałem zawodzi.

---

## Faza 3 — model danych slajdu + minimalna kompozycja (zamknięta)

**Cel:** slajd deklaruje warstwę live; JSON jest wersjonowany; player rysuje slajd w
`QGraphicsView`, a okno Info pokazuje tę samą kompozycję. Warstwa live pokazuje w F3 miniaturę
(pierwszą klatkę sceny z renderu) — proces live wchodzi w F4. **Bez** procesu live w playerze,
bez fokusu i routingu klawiszy, bez warstw wideo/obrazu i transformacji (F5).

**Deklaracja autorska** — nowe pole `layers` w `BaseSlideConfig`, więc wrapper
(`config.py:202`) od razu robi z niego argument `next_slide`, a zapis i odczyt JSON idą
dotychczasową drogą:

```python
from manimcue.slides import LiveLayer, Slide

self.next_slide(
    notes="...",
    layers=[LiveLayer(scene_file="panels.py", scene_name="NVPanel", rect=(0.55, 0.1, 0.4, 0.4))],
)
self.play(...)  # slajd nadal potrzebuje klipu bazowego (walidator upstreamu, config.py:291)
```

**Model (D24):**
- `LiveLayer`: `scene_file: FilePath`, `scene_name: str`, `rect: (x, y, w, h)` jako ułamki kadru
  slajdu z (0, 0) w lewym górnym rogu (walidacja: w kadrze, w, h > 0), `fps: int = 60`,
  `thumbnail: FilePath | None`. Rozdzielczość procesu live = `rect` × `resolution` prezentacji.
- `PresentationConfig.version: int = 2`; plik bez pola (upstream 5.7.0) czyta się jako zgodny,
  bo `layers` ma wartość domyślną; wersja > 2 → czytelny błąd „nowszy format”.
- Ścieżki warstw rozwiązywane jak `file`/`rev_file` w `from_file` (względem `path.parent.parent`).

**Miniatura (render):** `_save_slides` dla każdej warstwy live uruchamia scenę headless przez
`LiveSession` (osobny proces spawn, więc render CE nie importuje manimgl), bierze pierwszą klatkę
po READY i zapisuje PNG w `slides/files/<Scena>/`. Nazwa z hasha (bajty pliku sceny, nazwa klasy,
rozmiar) — cache jak przy klipach. Błąd sceny live przerywa render z treścią `ERROR`.

**Kompozycja (D25):** `src/manimcue/composition.py` — `SlideComposition(QGraphicsScene)` (rect
sceny = `resolution`, tło `background_color`; element wideo `QGraphicsVideoItem`, element obrazu,
elementy warstw z miniaturą w `rect`) i `SlideView(QGraphicsView)` (dopasowanie `fitInView` przy
resize, tryb proporcji z `--aspect-ratio`). Okno główne i bieżący widok Info to **dwa widoki tej
samej sceny** — zgodność obrazu z konstrukcji. Ochrona przed czarną klatką z `frame_changed`
(`player.py:664`) przechodzi na sink elementu wideo. Podgląd następnego slajdu to osobna
`SlideComposition` z `next_media_player`. Prototyp (Qt 6.12, Windows, real display): dwa widoki,
klip 60 fps — 361 klatek / 6 s, rysowanie elementu mediana 0,38 ms, p95 9 ms.

**`convert` (D23):** prezentacja z warstwą live → jawny błąd z indeksem slajdu i nazwą sceny.
Obraz zastępczy odrzucony: wymagałby kompozycji w każdym konwerterze (HTML, PDF, PPTX).

**Kryteria akceptacji:**
1. JSON upstreamu 5.7.0 (`tests/slides/data/slides/BasicSlide.json`) czyta się bez zmian
   i zapisuje z `version: 2`; plik z `version: 3` → `ValidationError` z komunikatem o nowszym
   formacie.
2. `LiveLayer` odrzuca `rect` poza kadrem, zerowe wymiary i NaN; rozmiar renderu ≥ 1 px.
   Ścieżki warstwy z JSON rozwiązują się względem `path.parent.parent` także z innego CWD.
3. Render CE **i GL** decku z warstwą live daje JSON z warstwą i PNG miniatury; piksele
   miniatury odpowiadają pierwszej klatce sceny (narożniki `LiveGLCorners`). Drugi render bez
   zmian nie nadpisuje miniatury (cache). Błąd sceny warstwy przerywa render z treścią błędu
   i bez JSON. Zawieszone budowanie → `TimeoutError`, bez pozostawionego workera. Znacznik `gpu`.
4. Player offscreen: element warstwy stoi w `rect` (współrzędne sceny) z miniaturą; widok Info
   pokazuje tę samą `QGraphicsScene`; podgląd następnego slajdu zawiera miniaturę jego warstwy;
   piksele dwóch widoków w prostokącie warstwy to miniatura, poza nim — obraz bazowy (`src=`).
   Przejście do prezentacji o innej rozdzielczości zmienia kadr bieżący i podglądu;
   `hide_mouse` działa nad viewportem.
5. Nieprawidłowa klatka wideo w sinku zastąpiona poprzednią, ale tylko poprawną (bez
   rekurencji sygnału przy pustej poprzedniej).
6. `convert`, konwertery użyte z kodu i `copy_to` odrzucają warstwę live z numerem prezentacji,
   slajdu i nazwą sceny.
7. Wszystkie testy upstreamu i F0-F2 nadal zielone.
8. **Próba prelegenta w oknie:** `examples/demo.py` z warstwą live — miniatura w prostokącie
   w obu oknach, resize zachowuje proporcje, przejścia między slajdami bez czarnego mignięcia,
   podgląd następnego slajdu z miniaturą.

**Budżet (po rundzie 8):** ~6 h (model i miniatura ~2 h, player i akceptacja ~4 h), stop
i raport przy 12 h. Start pracy: 2026-10-22 ~14:00.

**Wynik (2026-10-22):** kryteria 1-7 — testy `tests/test_layers.py` (19, w tym 4 `gpu`), pełny
zestaw 340 passed + 2 skip. Kryterium 8: prelegent widział miniaturę w prostokącie warstwy;
nieruchomość warstwy była zgodna z zakresem F3 („jeśli miało się coś zmienić, to nie wyszło”) —
ożywienie to F4. Czas pracy ~1 h zegarowo (14:00-15:00), w budżecie.

## Faza 4 — warstwa live w playerze (zaimplementowana, czeka na próbę prelegenta)

**Cel:** D20 w jednym oknie. Wejście na slajd z warstwą uruchamia proces, pierwsza klatka
zastępuje miniaturę, kliknięcie warstwy daje jej strzałki, Esc oddaje je playerowi, wyjście ze
slajdu zatrzymuje proces. **Bez** transformacji, wspólnego startu z wideo i wielu warstw
naraz w aktywnym sterowaniu (F5).

**Projekt:**
- `src/manimcue/live_layers.py` — `LiveLayerController`, właściciel sesji warstw bieżącego
  slajdu (runda 8, p. 12: kompozycja nie zna `LiveSession`). Jeden `QTimer` pompuje `poll()`
  i `try_read_frame()` wszystkich sesji, także zatrzymywanych, aż do `STOPPED`; nowa klatka →
  `QImage` (RGBA8888, kopia przez `QPixmap.fromImage`) → `SlideComposition.set_layer_image`.
  Timer stoi, gdy nie ma żadnej sesji.
- **Cykl życia:** `show(slide_config)` z `Player.load_current_slide` i z konstruktora — jedna
  zatwierdzona zmiana slajdu, nie setter indeksu. Ten sam obiekt slajdu (replay, pętla) →
  sesje zostają. Inny slajd → `request_stop()` starych, nowe sesje dla warstw nowego. Ponowne
  wejście = nowa sesja (świeże zasoby, F2). Zamknięcie playera zatrzymuje i odbiera wszystkie.
- **Fokus (D20):** klik w okno główne trafia przez `SlideView.mousePressEvent` + `itemAt` do
  warstwy (albo poza nią → zwolnienie). Widok Info nie aktywuje (podgląd). Aktywna warstwa ma
  obwódkę (`QGraphicsRectItem` w scenie, więc widać ją też w Info). Zwolnienie: Esc, klik poza
  warstwą, zmiana slajdu, `applicationStateChanged` ≠ aktywna, błąd sesji.
- **Router klawiszy** przed `dispatch` w `Player.keyPressEvent` (tam trafiają też klawisze z
  Info): przy aktywnej warstwie Esc zwalnia; klawisze `NEXT`/`PREVIOUS` z konfiguracji →
  `send("next")`/`send("back")`; reszta skrótów playera bez zmian. Komenda idzie tylko do sesji
  w stanie `ready` — klik w trakcie startu nie kolejkuje cue (D20, tabela rundy 7).
- **Błąd sesji:** warstwa zostaje z ostatnim obrazem, obwódka czerwona, treść `ERROR` w logu
  i w tytule okna Info; player działa dalej, sterowanie wraca do playera.

**Kryteria akceptacji:**
1. Wejście na slajd z warstwą: proces startuje, do READY widać miniaturę, potem piksele
   warstwy to pierwsza klatka sceny (korpus `LiveGLCorners` z innym kolorem miniatury).
2. Wyjście ze slajdu: proces odebrany (`mp.active_children()` puste po pompowaniu), ponowne
   wejście tworzy nową `SharedMemory`.
3. Klik w warstwę + `→` wykonuje cue w scenie (zmiana pikseli), indeks slajdu bez zmian;
   Esc, potem `→` zmienia slajd. To samo dla klawiszy przekazanych z Info. Klik poza warstwą
   zwalnia. (`LiveLayerFocus` z korpusu rundy 7.)
4. Klik i `→` przed READY nie wykonują cue po READY.
5. Wyjątek w cue (`LiveGLCueRaises`) i w `build_objects` (`LiveGLBuildRaises`): czerwona
   obwódka, błąd w logu i w tytule Info, player przechodzi dalej strzałkami; zamknięcie bez
   pozostawionego procesu.
6. Utrata aktywności aplikacji zwalnia warstwę (D27); autorepeat strzałek nie wysyła cue.
7. Szybkie wyjście i powrót (A → B → A przed odbiorem): stara sesja nie dotyka nowej warstwy.
8. Nawigacja (D28): przeciąganie po aktywnej warstwie 3D zmienia obraz, dwuklik przywraca kadr
   z ostatniej klatki granicznej.
9. Ścieżka GUI: aktualizacje obrazu warstwy ≥ 80% z 60 fps w 5-sekundowym cue.
10. Testy F0-F3 i upstreamu zielone.
11. **Próba prelegenta:** demo deck, slajd 3 — klik w panel, strzałki sterują rotate → pulse →
   sweep i cofaniem, Esc wraca do slajdów, wyjście i powrót na slajd restartuje panel, płynność
   na ekranie i w Info; slajd 4 — nawigacja myszą po scenie 3D.

**Budżet:** ~4 h, stop i raport przy 8 h.

## Faza 5 — warstwy pełne (zaimplementowana, czeka na próbę prelegenta)

**Cel:** „scena jako obiekt w innej scenie” po stronie prezentacji (wizja, p. 2). Slajd ma
oprócz live także warstwy z gotowych plików — klip albo obraz, np. render innej sceny — w swoim
prostokącie, z ruchem i skalą w czasie, wspólnym startem i pauzą (D17). **Bez** zegara
głównego dekoderów, seeka i synchronizacji co do klatki.

**PoC wspólnego startu (2026-10-22, Windows, RTX 4060, klipy 1080p60 z demo, Qt offscreen):**
`play()` N playerów zaraz po `LoadedMedia` — pierwsza klatka ~200 ms później, rozjazd 14 ms
(N=2) i 67 ms (N=4). **Przygotowanie pierwszych klatek** (`play()`, pauza na pierwszej
poprawnej klatce, wspólne `play()`, gdy wszystkie mają klatkę) — rozjazd 0 ms (N=2) i 18 ms
(N=4), przygotowanie 0,23-0,31 s; wszystkie playery 59,3-60 fps.

**Projekt:**
- **Model (D29):** `ClipLayer(kind="clip", file, rect, loop=False, playback_rate=1.0,
  keyframes=[], thumbnail, end_thumbnail)`; `LiveLayer` dostaje `kind="live"` i `keyframes`.
  `layers` to unia dyskryminowana po `kind`; `from_file` dopisuje `kind="live"` warstwom
  z plików v2 przed walidacją i rozwiązuje ścieżki `file`/`end_thumbnail`. `to_file` zapisuje
  zawsze bieżącą wersję, `FORMAT_VERSION = 3`. Prostokąt klipu i klatek kluczowych: skończony,
  dodatnie wymiary, pozycja dowolna (wjazd spoza kadru); `LiveLayer.rect` nadal w kadrze, bo
  wyznacza rozdzielczość renderu. Pomocnik `slide_file(json, index)` — plik bazowy slajdu
  `index` (od 0) innego, wcześniej wyrenderowanego decku, przez `from_file` (bez jego warstw).
- **Ruch (D30):** `keyframes: list[(t, rect)]`, `t` skończone, ≥ 0, ściśle rosnące; liniowo,
  poza zakresem — stała. Czas ruchu to **aktywny czas slajdu**: `QElapsedTimer` od wspólnego
  startu, zatrzymywany pauzą i końcem bazy, zerowany przez replay; nie zależy od
  `playback_rate` ani pętli bazy. Animacja geometrii co klatkę timera, nie z `position()`
  (FFmpeg Qt 6.12 zgłasza pozycję co 50 ms).
- **Wspólny start (D31):** grupa = baza wideo + warstwy-klipy wideo slajdu. Wejście na slajd:
  sygnały podłączone przed `setSource()`, każdy player `play()` → pauza na pierwszej poprawnej
  klatce → gdy wszystkie gotowe, jedno wspólne `play()` (albo pauza przy `start_paused`).
  Błąd albo brak klatki po 5 s: warstwa wypada (miniatura zostaje), baza bez klatki — jak dziś,
  bez grupy. Bariera należy do jednego wejścia na slajd; sygnały poprzedniego są ignorowane.
- **Transport grupowy:** warstwy-klipy idą za stanem bazy (`playbackStateChanged`: gra → grają,
  pauza/koniec → pauza na bieżącej klatce), więc `next`, koniec pętli, `skip_all`, `auto_next`
  i `start_paused` działają bez zmian w ich kodzie. Replay — `setPosition(0)` warstw i zerowanie
  zegara ruchu. W trakcie przygotowania `play_pause`/`next`/replay zmieniają tylko żądany stan
  po starcie. Slajd-obraz (baza statyczna): grupa ma własny stan, `PLAY_PAUSE` przełącza ruch
  i klipy, koniec slajdu ręczny.
- **Reverse:** baza odtwarza `rev_file`; warstwy-klipy pokazują `end_thumbnail` (ostatnia klatka
  z renderu) w prostokącie końcowym, bez playerów; live jak w D27.
- **Walidacja długości:** wspólny walidator po renderze i raz przed prezentacją (nie w
  `from_file`). Klip wideo bez `loop` nad bazą wideo: `długość/playback_rate` równe bazie
  z tolerancją = większy z czasów klatki obu materiałów po szybkości. Zwolnione: `loop`, obrazy,
  GIF (animacja zapętlona), baza statyczna. Nieznana długość albo fps → czytelny błąd;
  `playback_rate` ≤ 0 lub nieskończony → błąd.
- **Indeksy:** sesje live i playery klipów pod indeksem warstwy kompozycji (słownik), nie
  pozycją na liście swojego rodzaju — także klik, klatki, błędy i ruch.
- **Ochrona przed czarną klatką** jak w `frame_changed`, osobno dla sinka każdego klipu.
- `convert`/`copy_to`: błąd dla każdej warstwy (klip też nie ma odpowiednika w eksporcie).

**Kryteria akceptacji** (testy deterministyczne offscreen; wideo — integracyjne z timeoutem):
1. Model: v2 bez `kind` czyta się jako live; v3 z klipem, obrazem i live zapisuje i czyta
   `kind`; niejednoznaczne/niepoprawne dane odrzucone; `keyframes` walidowane; ścieżka
   `next_slide → PreSlideConfig → SlideConfig → JSON → from_file` dla mieszanych warstw;
   `slide_file` z innego CWD.
2. Kompozycja offscreen: przemieszane `[clip, live, image, live]` — piksele zgodne z z-order
   i prostokątami, klik i klatki live trafiają we właściwe warstwy; Info to samo.
3. Ruch: dla zadanych czasów prostokąty zgodne z interpolacją; pauza zatrzymuje, replay zeruje.
4. Wspólny start (integracyjny, wideo): baza + 2 klipy — żaden nie gra przed gotowością
   wszystkich; rozjazd pierwszych klatek po starcie ≤ 50 ms; pauza i wznowienie razem; klip
   z błędnym plikiem nie blokuje reszty; pauza w trakcie przygotowania jest zachowana.
5. Walidacja: nierówne długości → błąd z nazwami plików i obiema długościami; `loop`, obraz
   i baza statyczna zwolnione.
6. Reverse: baza cofa się, klipy pokazują ostatnią klatkę w prostokącie końcowym — także gdy
   slajd docelowy nie był wcześniej odtwarzany.
7. Testy F0-F4 i upstreamu zielone.
8. **Próba prelegenta:** demo deck — render innej sceny wjeżdża i rośnie obok live; spacja
   pauzuje wszystko; pomiar na komputerze prelegenta: baza + 1/2/3 klipy z Info i live.
**Budżet:** ~6 h jako cel prototypu, raport przy 12 h (runda 11, p. 12).

**Wynik (2026-10-22):** kryteria 1-7 — `tests/test_clip_layers.py` (19), pełny zestaw 373 passed
+ 2 skip. Runda 12 (przegląd kodu) znalazła bramkę bazy zwalnianą klatką poprzedniego slajdu,
replay i `next` poza grupą, pustą warstwę po awarii klipu i obwódkę bez ruchu — poprawione,
regresje sprawdzone w obie strony. Kryterium 8 — czeka na próbę. Czas: ~1,5 h zegarowo.

## Faza 6a — `SceneView` z gotowych klatek (zaimplementowana, czeka na próbę prelegenta)

**Cel:** „scena jako obiekt w innej scenie” po stronie renderu (D16): mobject w scenie-gospodarzu
(CE Cairo i manimgl), który pokazuje klatki gotowego renderu innej sceny, np. `slide_file`.
Czas widoku to czas sceny-gospodarza, więc render jest deterministyczny; transformacje
i animacje gospodarza działają jak na każdym obrazie. Wynik to jeden klip gospodarza.
**Bez** wykonywania sceny podrzędnej (to F6b) i bez live.

**API (D32, propozycja):**

```python
from manimcue.scene_view import SceneView

view = SceneView(slide_file("slides/Orbit.json", 0), height=3, loop=True, rate=1.0)
self.add(view)                       # gra od dodania: updater liczy czas gospodarza
self.play(view.animate.scale(0.5).to_corner(UL), run_time=2)   # wideo gra w trakcie
view.pause(); self.wait(1); view.resume(); view.seek(0.5)
```

**Projekt:**
- Czas: updater z `dt` gospodarza; indeks klatki = `floor(t·fps·rate)`, na końcu stop na
  ostatniej klatce albo pętla. Dekodowanie `av` sekwencyjnie, cofnięcie czasu → ponowne otwarcie;
  w pamięci tylko bieżąca klatka.
- CE: podklasa `manim.ImageMobject`, podmiana `pixel_array` (RGBA uint8). Atrybut z kluczem
  źródła (ścieżka, rozmiar, mtime), żeby hash cache CE zmieniał się z nowym renderem źródła.
- manimgl: podklasa `manimlib.ImageMobject` na własnym pliku pierwszej klatki (unikalna ścieżka,
  bo `image_path_to_texture` ma `lru_cache` po ścieżce), klatki zapisywane do tekstury
  `shader_wrapper.textures[0].write(...)`. PoC (headless, 320×180): zapis i render działają,
  `shift` po zapisie zachowany, kopia z `.animate` dzieli teksturę.
- Wybór silnika jak w `Slide` (`manimcue.slides.slide.MANIM`).

**Kryteria akceptacji:**
1. CE: render gospodarza z `SceneView` syntetycznego klipu (kolor zmienia się co 0,5 s) —
   piksel środka widoku w klatkach wyjścia ma kolor klipu z właściwej chwili.
2. To samo w manimgl (`gpu`).
3. Animacja gospodarza w trakcie odtwarzania: widok w nowym miejscu, stare miejsce — tło.
4. `pause`/`resume`/`seek`/`loop`/`rate`: mapowanie czasu → klatka (test jednostkowy) i jeden
   render z pauzą.
5. `SceneView` w `Slide` przez `manim-cue render` (CE) — slajd z widokiem w klipie.
6. CE: zmiana źródła zmienia hash cache — drugi render z nowym klipem nie bierze starego.
7. Testy F0-F5 i upstreamu zielone.
8. **Próba prelegenta:** demo — slajd z renderem `Orbit` jako `SceneView`, przesuwanym
   i skalowanym animacją gospodarza.

**Budżet:** ~3 h, raport przy 6 h.

**Wynik (2026-10-22):** runda 13 zmieniła projekt na zegar absolutny gospodarza i wspólny stan
kopii (D32). Kryteria 1-7 — `tests/test_scene_view.py` (8 testów: czas→klatka 24/60 fps, zegar
z pauzą i seek, oś czasu CE i GL z FadeIn, `.animate` w trakcie odtwarzania, pauzą i ciągłością
slajd 1 → 2, dwa widoki jednego klipu w CE i GL, cache CE po nowym renderze źródła — sprawdzony
w obie strony). Kryterium 8: demo deck, slajd 6 — czeka na próbę. Po drodze: przypięcie
`pillow<13` (CE 0.21 nie renderował żadnego `ImageMobject`). Czas: ~1 h zegarowo.

## Faza 6b — PoC krokowania sceny podrzędnej (PoC wykonany, czeka na decyzję prelegenta)

Gospodarz i dziecko postępują równolegle bez rekurencyjnego `play()` (synchroniczny w obu
silnikach). Wynik może zamknąć ten kierunek.

**Ocena dróg (przed PoC):**
- *Dziecko jako generator* (`yield from self.play(...)`) — zmienia API autora; sprzeczne
  z zasadą „`Scene` jak każda inna”. Odrzucone.
- *Wątek albo greenlet dla dziecka* — wątek łamie „jeden wątek kodu aplikacji na proces”,
  greenlet to nowa zależność i współbieżność tylnymi drzwiami. Odrzucone.
- **Nagranie stanów (PoC):** `construct()` dziecka wykonuje się raz, przy budowaniu gospodarza,
  w trybie nagrywania: jego `play()`/`wait()` krokują animacje w czasie wirtualnym (fps
  gospodarza), **bez renderu**, i zapisują kopie mobjectów dziecka co klatkę. Kod dziecka po
  `play()` widzi stan końcowy jak zwykle. W gospodarzu `SceneRecording` odtwarza zapisane stany
  wektorowo w ramce (prostokąt w jednostkach gospodarza), którą gospodarz animuje jak każdy
  mobject; czas z zegara gospodarza jak w D32. Wynik tożsamy z „równoległym postępem” dla dzieci
  niezależnych od gospodarza; dziecko reagujące na stan gospodarza — poza zakresem (wymagałoby
  współbieżności z odrzuconych dróg).
- Zysk względem F6a: treść wektorowa (ostra przy powiększeniu), bez tła klipu (nakłada się na
  gospodarza), animowalna geometria pojedynczych mobjectów dziecka po stronie gospodarza — nie
  w PoC.

**PoC — kryteria (CE, Cairo; GL dopiero po pozytywnym wyniku):**
1. Dziecko z dwoma `play()` i `wait()` nagrane bez plików filmu i bez renderu; liczba stanów
   = fps × czas dziecka (± 1).
2. Gospodarz: w trakcie własnej animacji innego obiektu stany dziecka postępują — piksele
   w klatkach wyjścia zgodne z pozycją obiektu dziecka w danej chwili.
3. Ramka animowana przez gospodarza (przesunięcie, skala) przenosi treść dziecka; tło
   gospodarza pod ramką widoczne (brak nieprzezroczystego prostokąta).
4. Pomiar: czas nagrania i pamięć stanów dla dziecka z ~20 mobjectami przez 5 s przy 60 fps.
5. Raport: kontynuować (API, GL, testy) albo zamknąć kierunek z powodem.

**Budżet:** ~2 h na PoC.

**Wynik PoC (2026-10-22, po rundzie 14) — kierunek wykonalny:**
- Runda 14 wykazała, że „nagranie stanów” odpowiada tylko na pytanie o wektorowe F6a, a greenlet
  daje jednowątkową drogę do prawdziwego krokowania **bez zmiany API autora**. PoC zrobiony na
  greenlecie (`experiments/f6b_stepping/`, `uv run --with greenlet`, bez zależności projektu).
- Dziecko to zwykła `Scene` CE. Jej `play()` krokuje animacje bez renderu i po każdej próbce
  oddaje sterowanie gospodarzowi (`greenlet.switch`); gospodarz wznawia je raz na swoją klatkę.
  Dziecko **reaguje na gospodarza**: `wait_until(lambda: self.host.dot.get_x() > 0)` kończy się
  w klatce przejścia kropki gospodarza (4,067 s przy 15 fps).
- Treść dziecka rysuje jego kamera Cairo w rozdzielczości ramki, z przezroczystym tłem, do jednego
  `ImageMobject`; gospodarz animuje ramkę (przesunięcie i skala w trakcie kroków dziecka), pod
  pustą częścią ramki widać tło gospodarza. Piksele w klatkach wyjścia zgodne z osią czasu.
- Koszt (720p30, 5 s, dziecko z 20 mobjectami): render samego dziecka 2,0 s, gospodarz z
  krokowanym dzieckiem 4,4 s (~21 ms na klatkę razem z renderem dziecka). RNG gospodarza zachowany.
- Ograniczenia: kod dziecka między `play()` blokuje gospodarza (współbieżność kooperacyjna);
  bez kamery ruchomej dziecka, dźwięku i sekcji; tylko CE (GL — po decyzji).
- **Do decyzji prelegenta:** zależność `greenlet` (C, szeroko używana: gevent, SQLAlchemy) jako
  mechanizm współbieżności kooperacyjnej w jednym wątku. Tak → F6b jako API (`ChildView`), testy,
  potem GL. Nie → kierunek zamknięty, „scena w scenie” to F6a (render) i warstwy F5.

## Uwagi z próby prelegenta F4-F6a (2026-10-22)

Diagnoza: codex (read-only, pomiary offscreen). Kolejność wybrał prelegent.

1. **Podgląd następnego slajdu w Info nie animuje warstw.** Baza gra (171 klatek/3 s, pętla),
   ale `preview.set_layers` bez wideo — klipy i live to miniatury (`composition.py:74-79`).
   Bez następnego slajdu zostaje stary podgląd (`player.py:563-585`). → **5d**: klipy w podglądzie
   grają; live w podglądzie nie (osobny proces).
2. **Styl obwódki** (kolor, grubość, krycie) zaszyty w `live_layers.py:27-30`. → **5f**:
   `LiveLayer.active_border`/`error_border: BorderStyle`.
3. **Przezroczyste tło warstw.** Live: transport RGBA gotowy, blokuje `background_opacity: 1.0`
   na sztywno (`live_worker.py:35`) → **5e**. Klipy CE/GL z alfą: Qt przenosi alfę, ale
   półprzezroczystość miesza się źle (alfa 128 nad niebieskim: `(255,0,127)` zamiast
   `(128,0,127)`), reverse wymusza `libx264` (`slides/utils.py:154`); `SceneView` — wykonalne
   z kodu. → później, osobny kontrakt.
4. **Ospałość.** Ranking zmierzony: restart procesu live przy każdym slajdzie (~1,8 s ciepło,
   31,7 s zimno), readback GPU→CPU 1080p 7,4 ms + kopie, bariera F5 56-186 ms; konwersja klatki
   w GUI 0,6 ms — nie ona. Brak pomiaru w prawdziwym oknie. → **5b** (pomiar + trwałe live);
   rozdzielczość renderu live niezależna od prostokąta — kandydat po pomiarze.
5. **Jedno kliknięcie, trzy sceny** — nie ma ani testu, ani mechanizmu; zmiana slajdu restartuje
   live, spacja nie pauzuje live (notatka slajdu 5 demo jest błędna), Orbit na slajdzie 5 jeździ.
   → **5b**.

Stan kryteriów prób F4-F6a: prelegent nie potwierdził ani nie odrzucił pozostałych punktów.

## Faza 5b — trwałe live i jedno kliknięcie w trzech scenach

**Cel:** D33. Jedno `→` uruchamia naraz animację bazy CE, cue w scenie live i klip innej sceny
CE; sceny stoją, ruszają się tylko animacje. Proces live przechodzi przez sąsiednie slajdy.
**Bez** cofania cue wejścia i replay live (osobny etap, protokół checkpointów — runda 16), pauzy
live, zegara głównego, ruchu warstw.

**Projekt:**
- Model: `LiveLayer.session_id`, `LiveLayer.enter_cue`; walidacja ciągów (D33) po renderze
  i przy `from_file`, z indeksami slajdów.
- Player: jawna przyczyna zatwierdzonego przejścia (tabela z D33) do `LiveLayerController.show()`;
  `previous()`/`reverse()` bez zgadywania z `playing_reversed_slide`.
- Kontroler: sesje po tożsamości (prezentacja, `session_id`, generacja), nie po indeksie warstwy;
  ostatni obraz, metadane i błąd przy sesji; mapowanie sesja → indeks odtwarzane na wejściu.
- Koordynacja startu: warunek „live z `enter_cue` nie-READY” obok klipów/klatek kluczowych, także
  nad bazą statyczną; timeout live nie idzie ścieżką usuwania playera klipu.
- Pomiar (`examples/measure_player.py`): wspólna oś `perf_counter` — żądanie przejścia, zwolnienie
  bariery, wysłanie cue, publikacja live, pierwsza **zmieniona** klatka odebrana w GUI dla każdej
  z trzech warstw; zimny start procesu osobno; reakcja na ręczne cue osobno. Wynik JSON.
- Demo: slajdy 7-8 — trzy nieruchome prostokąty i kamery (baza, live z `session_id`
  i `enter_cue`, klip innej sceny CE bez klatek kluczowych), animacje ze zmianą widoczną od
  pierwszej klatki. Poprawka notatki slajdu 5 (spacja nie pauzuje live).

**Kryteria akceptacji:**
1. Pomiar przed zmianą i po niej w prawdziwym oknie (Claude; sandbox codex nie uruchamia okna):
   przejście slajd → slajd z live — restart vs sesja trwała; wyniki w `PLAN.md`.
2. Model: round-trip JSON obu pól; niespójny ciąg, duplikat ID na slajdzie → błąd z indeksami;
   zmiana pozycji przy tym samym rozmiarze — dozwolona; v3 bez pól czytany jak dotąd.
3. Trwałość: A → B w ciągu — ten sam PID, obraz po cue na A widoczny na B od razu (bez nowej
   publikacji), także gdy live zmienia indeks w liście warstw (`[live, clip]` → `[clip, live]`);
   bez `session_id` — nowy PID (D27).
4. Zdarzenia: `enter_cue` przy `next`, `auto_next`, `skip_all`; brak przy powtórzeniu pętli,
   reverse → normalny plik, `←`, `V`, `R`, zamknięciu (testy przez rzeczywiste callbacki playera).
5. Jeden klik (integracyjny, offscreen): `→` na decku trzech scen — wszystkie trzy zmieniają
   piksele; raport opóźnień i rozrzutu z ≥ 10 prób; cel ≤ 50 ms rozrzutu przy ciepłej sesji na
   tym sprzęcie (cel, nie gwarancja); zimny start osobno.
6. Odporność: sesja zatrzymywana ani w ERROR nie jest przejmowana; szybkie A → B → A nie myli
   sesji; live bez READY w 5 s nie blokuje startu bazy; cue wejścia nie przejmuje fokusu, klik
   w live na B daje strzałki (D20).
7. Testy F0-F7.0 i upstreamu zielone.
8. **Próba prelegenta:** demo, slajdy 7-8 — jedno `→`, trzy animacje naraz, bez restartu panelu.

**Budżet:** ~6 h, stop i raport przy 12 h. Wykonawca: codex w osobnym worktree; przegląd diffu
i pomiar w oknie — Claude.

**Wynik (2026-10-22):** kryteria 2-7 — `tests/test_persistent_live.py` (23 testy: model, nawigacja
przez rzeczywiste callbacki playera, PID/obraz/zmiana indeksu/fokus, generacje, bariera live nad
bazą statyczną, timeout, przypięcie pierwszych klatek, 10 przejść trzech scen); pełny zestaw
410 passed + 2 skip. Przy okazji: spóźniona klatka Qt po `pause()` w przygotowaniu (przypięcie
pierwszych klatek). Przegląd diffu usunął kopię 5 MB klatki live na każdą klatkę w wątku GUI.
Kryterium 1 — pomiar w oknie (`examples/measure_player.py`, Windows 11, RTX 4060, 10 prób,
mediany od żądania przejścia do pierwszej zmienionej klatki odebranej w GUI):

| Tryb | baza / klip / live [ms] | rozrzut mediana / maks. [ms] | zimny READY [s] |
|---|---|---|---|
| restart (D27) | 1927 / 1937 / 1932 | 11 / 16 | 2,0 |
| `session_id` | 61 / 103 / 58 | 48 / 51 | 1,9 |

Ręczne cue: ~10 ms od żądania do zmienionej klatki w GUI. Restart procesu był głównym kosztem
zmiany slajdu. Rozrzut przy sesji trwałej wyznacza klip (pierwsza zmieniona klatka zależy od
treści klipu); cel ≤ 50 ms — mediana tak, maksimum o 1 ms ponad. Kryterium 8 czeka na próbę.
Wykonawca: codex (~25 min), przegląd i pomiar w oknie — Claude.

## Faza 5c — druga próba: proporcje, demo, stan dla prelegenta

**Uwagi z drugiej próby (2026-10-22, slajdy 7-8; potwierdzone przeklikaniem skryptem ze zrzutami
obu okien):** animacje różnej długości; oba nowe panele „wyglądają dziwnie”; „nie wiem, kiedy co się
wykona przy ← / →, czy operacja się udała i w którym momencie prezentacji jestem”. Przyczyny:
1. **Live zniekształcone:** `live_worker.py:33` ustawia rozdzielczość kamery, nie kształt kadru —
   kadr zostaje 16:9 w prostokącie o innych proporcjach (obrót kwadratu daje równoległobok).
2. **Klip rozciągnięty:** `composition.py:103` — `IgnoreAspectRatio` (koło Orbit jako elipsa).
3. **Klip znika na ~100 ms** przy wejściu na slajd z klipem (przygotowanie bariery).
4. **Demo:** baza 2 s, cue `flip` 0,4 s, Orbit 2 s; `flip` przełącza kolor, więc stan slajdu 8
   zależy od liczby wejść, a `←` go nie przywraca (D33: bez cofania cue).
5. **Brak informacji o stanie:** numer slajdu tylko w Info (przy jednym monitorze Info ukryte,
   `present/__init__.py`); nie widać, czy slajd gra, czeka na przygotowanie, jest w pauzie lub
   skończony, czy live jest gotowe, co zrobił ostatni klawisz; `V` + `→` zostaje na tym samym
   slajdzie (upstream) bez wyjaśnienia; spacja na skończonym slajdzie nic nie mówi.
6. Cienka biała pozioma linia przez cały kadr okna głównego w oknie o proporcjach innych niż 16:9
   (zrzut prelegenta) — nie odtworzona w oknie 16:9; do zdiagnozowania.

**Projekt (domknięty po rundzie 17):**
- Live: render 16:9 dopasowany do panelu, czarne pasy, bez obcinania całej dotychczasowej
  treści. Worker przekazuje domyślny `frame_config.frame_shape` przed konstrukcją sceny;
  publikacja uzupełnia klatkę do wymiaru bufora. Miniatura używa tej samej ścieżki.
  Dowód wykonawczy: samo rozszerzenie frame_shape nie działa — `Camera.refresh_uniforms`
  używa stałych FRAME_WIDTH/HEIGHT. Bez łatania Manima i bez zmian czułości D28.
- Klipy: wszystkie reprezentacje (wideo, obraz, miniatura, end_thumbnail, fallback i ruch)
  zachowują proporcje: skala `min(rw/sw,rh/sh)`, wyśrodkowanie, przezroczyste marginesy.
  Pełny kontener D30 blokuje klik do niższych warstw. Obwódka aktywności dotyczy tylko live.
- Placeholder miniatury (bez niej szary zastępnik) od utworzenia kompozycji do pierwszej
  poprawnej klatki nowego wejścia. Tylko nowa klatka zalicza READY. Błąd/timeout pozostawia
  fallback; numer wejścia odcina stare callbacki także przy A→B→A; replay zachowuje obraz.
- Demo: czarne live, deterministyczny początek i koniec każdego cue, rzeczywista animacja
  przez nominalne 2 s liniowo. Identyczny koniec po zatwierdzonym wejściu do przodu;
  cofanie/reverse/replay według D33. Rozrzut czasów raportowany, bez frame-lock.
- Stan: wspólny snapshot pól kontrolerów w Info i nakładce głównego viewportu (bez fokusu,
  przezroczysta dla myszy, domyślnie ukryta). Przełącznik `Config.keys`: S.
  Identyfikator prezentacji/lokalny slajd, transport i reverse osobno, live i fokus.
  Krótki wynik akcji na ~2 s; małe powiadomienia dozwolone, bez zmiany nawigacji upstreamu.

| Zdarzenie | Informacja dla prelegenta |
|---|---|
| → | wznowienie / zamówiony start / wyjście z pętli / nowy slajd / reverse→normal |
| ←, V, R | zatwierdzona akcja albo granica; live bez cofania/replay (D33) |
| Spacja | transport grupy, zamiar podczas przygotowania albo koniec |
| Pętla, auto_next, skip_all | aktualny transport, lokalny indeks po automatycznym przejściu |
| Koniec decku | brak następnego slajdu albo zamknięcie według istniejącej opcji |
| D31 | przygotowanie z zamiarem gra/pauza, transport po barierze; błąd/timeout |
| Live | start / gotowe / błąd; pominięte cue po timeout nie jest wykonaniem |
| Fokus | slajdy albo numer live; klik/Esc, zmiana slajdu, dezaktywacja i błąd |
| Klawisz live | wysłano (nie wykonano), przed READY zignorowano, autorepeat pominięty |

Historia każdej iteracji pętli i potwierdzenia wykonania cue poza zakresem: wymagałyby
rozszerzenia protokołu, nie są potrzebne do odczytu bieżącego stanu.

**Kryteria akceptacji:**
1. Live w panelu 0,28×0,6: izotropowy obraz z pasami i cały stary kadr; kontrolowana figura
   2D, miniatura i reset zachowują proporcje. Regresje 16:9, D22/D28 i F2 bez obniżania progów.
2. Klip: proporcje wszystkich reprezentacji i ruchu, przezroczyste marginesy, hit-test kontenera.
   Geometria i raster po kompozycji 320×180, viewport 640×360, DPR=1; koło/kwadrat 2D,
   maska jednolitego koloru, tolerancja rasteryzacji 2 px.
3. Ciągłość deterministycznie: opóźniona pierwsza, pusta i spóźniona klatka, anulowanie,
   błąd/timeout; placeholder nie zwalnia bariery, znika po poprawnej klatce.
4. Demo: nominalnie 2 s liniowo, deterministyczny początek/koniec ponownych cue;
   zmierzony rozrzut, bez wymagania końca ±1 klatka.
5. Wspólny tekst Info/nakładki według tabeli; nakładka tylko głównego viewportu,
   domyślnie ukryta; konfiguracja i konflikty skrótów sprawdzone także przy merge.
6. Linia: diagnoza z limitem 45 min: viewport/DPR, scena vs viewport, baza/warstwy/fokus/
   błąd/nakładka, różne rozdzielczości prezentacji. Jeśli nieodtworzona, raport z dowodami
   i ograniczeniem; bez nieudowodnionej deklaracji „nie nasz kod”. Prawdziwe okno w próbie człowieka.
7. Pełne testy F0–F5b i upstreamu zielone.
8. **Próba prelegenta:** rzeczywiste okno 1614×956, slajdy 7–8; wygląd, ciągłość i czytelność stanu.

**Budżet:** ~8 h implementacja i regresje + 45 min diagnoza linii; stop i raport przy 17,5 h.
Próba człowieka poza budżetem wykonawcy. Wykonawca: codex w worktree; bez commita.

**Wynik wykonawcy (2026-10-22):** implementacja i testy F5c w drzewie roboczym, bez commita.
Pełny zestaw: **418 passed, 2 skipped**, 312,86 s. F2: 1799 różnych klatek / ~30 s w obu
rozdzielczościach, wszystkie dotychczasowe progi spełnione. Kryteria 1–5 i 7 sprawdzone;
kryterium 6 częściowo otwarte (linia nieodtworzona offscreen, przyczyna nieustalona),
kryterium 8 czeka na człowieka. Szczegóły i komendy: `REPORT-5c.md`.

**Próba prelegenta (2026-10-22):** kryterium 8 przyjęte — „działa”. Kryterium 6 (linia) bez
ponownego zgłoszenia; wraca, jeśli prelegent przyśle zrzut z rozmiarem okna.

## Faza 5d-f — uwagi 1-3 z pierwszej próby: podgląd, tło live, obwódka

Źródło: „Uwagi z próby prelegenta F4-F6a”, punkty 1-3. Kolejność po 5b/5c wybrana przez
prelegenta („najpierw live”). Alfa klipów CE/GL i `SceneView` — poza tą fazą (osobny kontrakt:
mieszanie Qt i reverse `libx264`).

**5d — klipy grają w podglądzie Info.**
- Podgląd następnego slajdu odtwarza warstwy wideo `ClipLayer` w pętli, wyciszone, z
  `playback_rate` warstwy, zawsze do przodu; obrazy i GIF statyczne; live — miniatura (drugiej
  sesji live dla podglądu nie startujemy). Ruch (`keyframes`) według pozycji wideo bazy podglądu,
  tym samym `rect_at` co w oknie głównym; ponytail: bez synchronizacji klatek klipów z bazą
  podglądu poza wspólnym startem pętli (D17).
- Podgląd nie uczestniczy w barierze D31 okna głównego, nie zmienia jego stanu ani stanu
  prelegenta; błąd dekodera podglądu zostawia miniaturę i nie jest błędem slajdu.
- Bez następnego slajdu podgląd jest czyszczony (dziś zostaje stary, `player.py:563-585`).
- Odtwarzacze podglądu sprzątane przy każdej zmianie slajdu: ich liczba nie rośnie.

**5e — `LiveLayer.background_opacity: float = 1.0`.**
- Zakres [0, 1], skończona; walidacja przy ładowaniu. Worker przekazuje wartość do
  `camera_config.background_opacity` zamiast stałej (`live_worker.py:40`); transport RGBA już jest.
- Kompozycja rysuje live z alfą we właściwym formacie (prosta vs premultiplikowana) — wybór
  udowodniony pomiarem, nie założeniem: półprzezroczysty piksel nad znanym tłem daje oczekiwany
  kolor ±2/255. Pasy D34 to tło, więc przy `background_opacity < 1` też przepuszczają.
  Miniatura i ostatnia klatka sesji (5b) zachowują alfę.
- Warstwy jednej sesji (`session_id`, D33) muszą mieć tę samą wartość — jedna sesja to jedna
  kamera; błąd w `validate_live_runs`.
- Hit-test i fokus bez zmian: klik w przezroczysty obszar live trafia w live (kontener D30).

**5f — `BorderStyle` obwódki live.**
- `BorderStyle`: `color` (nazwa albo hex, walidowany przy ładowaniu), `width` (> 0, piksele
  kompozycji, jak dziś `BORDER_WIDTH`), `opacity` [0, 1]. `LiveLayer.active_border:
  BorderStyle | None` i `error_border: BorderStyle | None`; domyślne równe dzisiejszym stałym
  (`live_layers.py:26-28`), `None` — bez obwódki, fokus i błąd nadal w stanie prelegenta (5c).
- Obwódka jest jedna (`live_layers.py`): rysuje styl warstwy, na której stoi; ruch z warstwą
  i powrót na warstwę z błędem po `release` zachowane. Serializacja JSON slajdu w obie strony.

**Demo:** nowy slajd 9 — live z `background_opacity=0` nad animowaną bazą i własną
`active_border`; slajdy 1-8 bez zmian. Podgląd Info przed slajdami 5 i 8 pokazuje grający klip.

**Kryteria akceptacji:**
1. 5d: w podglądzie dwie klatki w odstępie > 200 ms różnią się w prostokącie klipu wideo;
   obraz i live statyczne; ruch według bazy podglądu; brak następnego slajdu — podgląd pusty;
   liczba odtwarzaczy podglądu stała po 20 zmianach slajdu; testy bariery D31 i stanu 5c zielone.
2. 5e: `background_opacity=0` — piksele tła live pokazują warstwę niżej; `0.5` — mieszanie
   ±2/255 względem wzoru; `1.0` — obraz identyczny z 5c; walidacja zakresu i spójności sesji;
   F2 bez obniżania progów.
3. 5f: własny styl daje pióro o tym kolorze, grubości i kryciu; `None` — brak obwódki, fokus
   działa; domyślne identyczne z 5c; ruch obwódki z warstwą; round-trip JSON.
4. Demo slajd 9 renderuje się w CE i GL; pełne testy F0–F5c i upstreamu zielone.
5. **Próba prelegenta:** podgląd Info przed slajdem 5/8, slajd 9 (przezroczystość, obwódka).

**Budżet:** ~6,5 h (5d 3 h, 5e 2 h, 5f 1 h, demo 0,5 h); stop i raport przy 13 h.
Wykonawca: codex w głównym drzewie (bez worktree, decyzja prelegenta); commit robi Claude.

## Faza 7 — live w CE

Najpierw adapter Cairo (zegar, publikacja w trakcie `play()`, przerwanie, `wait()`, wyłączony
cache, brak plików filmu), potem OpenGL jako osobny adapter z własnymi testami. Zgodność z CE 0.22
sprawdzić przed adapterami.

### 7.0 — zgodność forka z CE 0.22 (kontrakt)

**Cel:** fork renderuje na CE 0.22, na której stoi seminarium; adaptery live 7a/7b powstają od
razu na 0.22. Nic nowego funkcjonalnie.

**Ustalenia (wheel CE 0.22.0 i upstream, 2026-10-22):**
- Upstream manim-slides nie ma poprawki: brak wydania po 5.7.0, `main` wyprzedza `v5.7.0`
  o jeden commit (CI). Poprawka jest nasza.
- CE 0.22 przeniósł wyjście na plan wyjścia (`_config/output_plan.py`, `resolve_output_plan`
  w `Scene.__init__`). Klucz `write_to_movie` zniknął — `slide/manim.py:48` rzuca.
- `max_files_cached` przyjmuje tylko liczbę całkowitą ≥ 0 albo `-1` (bez limitu);
  `float("inf")` z `slide/manim.py:160` odrzucony.
- `flush_cache` zniknął z konfiguracji i z CLI (`--flush_cache`); czyszczenie segmentów to
  komenda `manim cache` i `manim.utils.caching.clear_segment_cache(dir)`. Odwołania:
  `slide/manim.py:162-179`, testy `tests/slides/test_slide.py:146`, `:168`.
- `file_writer.partial_movie_files` i `Scene.next_section(skip_animations=...)` zostały.
- CE 0.22 nadal woła `Image.fromarray(..., mode="RGBA")` (`camera/camera.py:1044`), więc
  pin `pillow<13` zostaje; zmienia się tylko wersja w komentarzu.
- Warstwa live (F0-F4) to manimgl — `live_worker.py:38` ustawia `write_to_movie` w konfiguracji
  manimgl, nie CE; poza zakresem.

- (runda 15) CE 0.22 kopiuje `config.max_files_cached` do ustawień writera w `Scene.__init__`
  (`scene/scene.py:252-257`) i czyści cache według kopii (`scene_file_writer.py:554-556`);
  CE 0.21 czytało konfigurację w chwili czyszczenia.
- (runda 15) `format=auto` daje wideo, ale przy podglądzie na żywo/GUI — `NONE`
  (`_config/render_session.py:72-79`); wtedy writer nie dodaje segmentów.

**Decyzja (świadome ograniczenie wsparcia):** wyłącznie CE 0.22, `manim>=0.22,<0.23`.
Seminarium stoi na 0.22, CE 0.21 nie ma konsumenta; obsługa obu jest wykonalna (rozgałęzienie
inicjalizacji), ale to podwójna walidacja bez zysku. Górna granica, bo fork zależy od
wewnętrznych API CE, które wydanie minor łamie.

**Projekt:**
- `Slide.__init__`: `max_files_cached = -1` **przed** `super().__init__` (writer bierze kopię),
  przywrócenie konfiguracji w `finally`; zamiast `write_to_movie` — po inicjalizacji czytelny
  błąd, gdy plan wyjścia nie jest wideo (`segment_cache_dir is None`).
- `render()`: bez manipulacji `max_files_cached` i `flush_cache` konfiguracji CE.
- **Flush:** CE 0.22 usunął `--flush_cache`; segmenty czyści jego komenda `manim cache clear`.
  Fork niczego nie dokłada: atrybut `Slide.flush_cache` zachowuje semantykę upstreamu (czyści
  tylko katalog slajdów, `base.py:615`). Zmiana zachowania względem upstreamu: `manim-cue render
  ... --flush_cache` znika razem z flagą CE. Fragmenty testu upstreamu z `--flush_cache`
  usunięte z komentarzem o powodzie.
- `scene_view.py`: komentarz o hashu cache zaktualizowany do 0.22 (hash obejmuje `pixel_array`).
- `pyproject.toml`, `README.md`: pin i komentarze.
- Praca w osobnym worktree z własnym `.venv` — główny `.venv` obsługuje próbę prelegenta.

**Poza zakresem 7.0 (ograniczenia forka sprzed 0.22, runda 15 p. 5, 7):** segmenty WebM
i przezroczysty MOV przy reverse (`utils.py:154` wymusza `libx264`), własny `partial_movie_dir`,
GIF, `-n a,b` przecinające granice slajdów. CE 0.21 też wstawiał `None` dla pominiętych
animacji — mapowanie indeksów się nie zmienia.

**Kryteria akceptacji:**
1. `uv sync` instaluje CE 0.22; `manim-cue checkhealth` bez błędu.
2. Pełny `uv run pytest` zielony (upstream render CE Cairo i `--renderer=opengl`, GL,
   `test_scene_view`); pominięcia te same co przed zmianą.
3. Render z `max_files_cached = 0` i kilkoma animacjami: wszystkie slajdy powstają, konfiguracja
   przywrócona także po wyjątku w konstruktorze.
4. Wyjście niewideo (`format=none`/png): czytelny błąd w konstruktorze, nie pusty deck.
5. Cache CE: drugi identyczny render `SceneView` trafia w cache (segmenty nie powstają od
   nowa); zmiana źródła nadal unieważnia (istniejący test).
6. Regresja end-to-end: demo deck i `Orbit` na 0.22 vs 0.21 — ta sama liczba slajdów, rodzaje
   warstw, długości klipów i klipów odwróconych per slajd (± 1 klatka).
7. `manim-cue present Demo` na renderze 0.22 startuje bez tracebacku (offscreen).
8. Odstępstwo z fazy 1 (pin `<0.22`) zamknięte w `PLAN.md` i `SPEC.md`.

**Budżet:** ~3 h (runda 15 podniosła z 2 h), stop i raport przy 6 h.

**Wynik (2026-10-22, Windows 11):**
- Fork korzysta z planu wyjścia CE 0.22; limit segmentów `-1` jest ustawiany przed
  inicjalizacją writera, a globalna konfiguracja przywracana w `finally`. Wyjścia niewideo
  są odrzucane czytelnym błędem konstruktora, także w podglądzie OpenGL.
- Usunięte odwołania do `write_to_movie` i konfiguracji `flush_cache` CE. Atrybut
  `Slide.flush_cache` nadal czyści wyłącznie wynikowe slajdy; segmenty CE czyści
  `manim cache clear`. Wsparcie ograniczone świadomie do `>=0.22,<0.23`.
- Testy regresji obejmują limit cache równy 0, przywracanie po wyjątku, wyjścia niewideo
  i trafienie w cache `SceneView` przed unieważnieniem po zmianie źródła.
- `checkhealth`: kod 0, CE 0.22.0. `Orbit` i `Demo` wyrenderowane; względem CE 0.21
  identyczne liczby klatek obu kierunków (Demo: 60/120/120/60/90/300; Orbit: 120),
  liczby slajdów, rodzaje warstw i pętle. Player Demo offscreen: 8 s bez tracebacku.
- Pełny `uv run --frozen pytest -q -p no:cacheprovider`: **387 passed, 2 skipped**
  (te same pominięcia: upstreamowy test ekranu i kompilacja TeX), 253,85 s.
  Wykonawca: codex (`workspace-write`, osobny worktree), ~18 min; przegląd diffu — Claude.
- Odstępstwo fazy 1 dotyczące pinu `<0.22` zamknięte. Nie rozszerzono zakresu fazy.

### 7a — adapter live Cairo (zarys; kontrakt po 7.0)

Zegar, publikacja klatek w trakcie `play()` do strumienia F2, przerwanie (D10), `wait()`,
wyłączony cache, brak plików filmu, korpus scen D22. Ryzyko: progi F2 (960×540 ≥ 60 fps)
liczone pod GPU; Cairo rysuje na CPU — najpierw pomiar, potem osobne progi do decyzji.

## Faza 8 — integracja z seminarium

Seminarium przechodzi z vendorowanej manim-slides 5.7.0 na fork — wymaga zgodności z CE 0.22.
Panel NV⁻ w scenie czterowidokowej (D9 tamtego planu) jako warstwa live obok trzech
prerenderowanych. Punkt wejścia: `SeminarScene`/`SeminarScene3D` w tamtym `deck/base.py`
(D10 tamtego planu). **Warunek wejścia:** próba na komputerze prelegenta — dwa monitory, fokus.
Do tego czasu nic w seminarium od tego projektu nie zależy (R8 tamtego planu).

## Faza 9 — manimgx (warunkowa)

Wchodzi, gdy manimgx dostanie udokumentowany tryb interaktywny (warunek z D12).

---

## Poza zakresem całego projektu

- Fork albo łatanie Manima (CE, GL, GX). Forkujemy manim-slides, nie Manima.
- Zegar główny i seek warstw, synchronizacja co do klatki (D17).
- Przechwytywanie ekranu / OBS jako architektura.
- Uwierzytelnianie i transport między hostami. Zakres to lokalne `127.0.0.1`.
- Back-pressure i kolejka aplikacyjna.
- `%%manim_slides` w IPythonie i dyrektywa Sphinx — usunięte z forka (D13).
- Dane grupowe i cokolwiek z teorii grup — to jest `groupy`, nie tutaj.
