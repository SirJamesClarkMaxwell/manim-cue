# manim-cue — plan rozwoju

Stan (2026-10-23): **fazy 0–3 i 7.0 zamknięte; F5d-f oraz F7a mają wdrożenie
i zaliczone kryteria automatyczne, F5g także. F4–F6a, F5d-f, F5g i F7a czekają na próbę
człowieka; faza 8 dopiero po próbie w oknie na komputerze prelegenta.**
**Decyzje prelegenta (2026-10-23):** D37 zatwierdzone; `greenlet` przyjęty (F6b idzie dalej jako
API); kolejne etapy: ruch warstw w podglądzie Info, F6b, F7b. Po pomiarze kryterium 8 fazy 5
(zawieszenie Qt przy 2–3 klipach) prelegent wybrał **fazę 10 — player ImGui (PC i przeglądarka)**;
ruch w podglądzie Info wchodzi do niej. Podział na dwie biblioteki
(osadzanie scen / prezentacje) i serwer prezentacji — task finalny po zamknięciu projektu:
komputer prelegenta przez Tailscale, live w przeglądarce w obu trybach (nagrany przebieg
domyślnie, interaktywny strumień, gdy serwer ma zasoby), hosting `.pptx` przez DeckCraft (web). Kierunek zmieniony 2026-10-21 decyzjami D13-D19 w `SPEC.md`: projekt staje się forkiem
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

## Faza 6b — PoC krokowania sceny podrzędnej (PoC wykonany, `greenlet` przyjęty 2026-10-23)

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
- **Decyzja prelegenta (2026-10-23): tak** — kontrakt API przed rundą recenzji.
- **Pytanie było:** zależność `greenlet` (C, szeroko używana: gevent, SQLAlchemy) jako
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
W samym etapie 5b bez cofania cue wejścia i replay live; aktualne checkpointy definiuje
F5g / D39–D41. Nadal bez pauzy live, zegara głównego i ruchu warstw.

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
| ←, V, R | zatwierdzona akcja albo granica; checkpointy live według F5g / D39–D41 |
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

Kontrakt domknięty rundą 18 (REVIEW-LOG.md), D35. Cel: grające klipy Info, przezroczyste
puste tło live, sterowalna obwódka. Bez łatania Manima, alfy klipów CE/GL, frame-lock i seek.

**Projekt 5d:** osobne, wyciszone QMediaPlayer warstw wideo podglądu, normalny `file`,
`playback_rate` warstwy, niezależne nieskończone pętle (również przy różnych długościach).
Baza ma własną pętlę i szybkość. Brak wspólnego restartu i bariery D31; dryf zaakceptowany.
Obrazy/GIF i live statyczne; wszystkie warstwy w `rect_at(0)` — ruch podglądu odroczony.
Reverse nie zmienia kierunku ani miniatury celu Info. Błąd pozostawia pierwszą miniaturę.
Zmiana celu/trybu, koniec i zamknięcie odcinają callbacki i zwalniają playery/sinki/źródła.
Ukryte Info nie dekoduje. Podgląd nie zmienia stanu głównego playera ani live.

**Projekt 5e:** `background_opacity: float = 1`, skończone [0,1], model → LiveSpec → worker
→ camera_config, także capture_first_frame. Transport i PNG: proste RGBA, bez globalnej
konwersji do premultiplikacji. Gwarancja dotyczy pustego tła kamery i pasów D34, które
odwzorowują camera.background_rgba (kolor pasów celowo ujednolicony z kamerą zamiast
stałej czerni, także przy kryciu 1); nie obejmuje półprzezroczystych obiektów i krawędzi
shaderów GL. Bramka GL sprawdza surowe tło i pasy 0/0.5/1, także kolorowe tło;
wyniki nad znaną bazą ±2/255. Miniatura ma krycie i wersję interpretacji w kluczu cache.
Ostatnia klatka zachowuje alfę i miesza się ponownie z nową bazą. Obie tożsamości sesji
uwzględniają krycie w sąsiednim ciągu D33; przerwa dopuszcza inne krycie. Hit-test bez zmian.

**Projekt 5f:** `BorderStyle(color=Color("#ffc800"), width=6, opacity=1)`; Color Pydantic
(nazwy CSS, hex, rgb/hsl), JSON według Color, alfa koloru × opacity. Liczby skończone,
width > 0, opacity [0,1]. `active_border` domyślnie żółta, `error_border` #dc2828;
null wyłącza rysowanie bez zmiany fokusu/błędu. Brak pól zachowuje stare decki v2/v3.
Jedna obwódka wybiera (indeks, rola): aktywna ma pierwszeństwo nawet przy None, po release
pierwszy błąd nawet przy None. Ruch odtwarza cały styl. Szerokość ograniczona do rozmiaru
kontenera, aby nie odwracać prostokąta. Style mogą się zmieniać bez restartu sesji.

**Demo:** slajd 9, kontrastowy obiekt bazy przechodzi pod pustym obszarem live i pasami;
krycie 0, własna obwódka, instrukcja klik/Esc. Indeksy 1–8 zachowane, mianowniki usunięte. Początek klipu 5 przeniesiony do kadru,
aby statyczna geometria Info pokazywała grający klip; animacja powiększania zachowana.

**Kryteria akceptacji:**
1. Podgląd dekoduje kontrolowane zmiany klipu nad nieruchomą bazą, niezależne długości i
   szybkości; obraz/live i rect_at(0) statyczne; reverse do przodu; pusty koniec; A→B→A,
   różne rozdzielczości i 20 zmian bez wzrostu liczby playerów; regresje D31/5c zielone.
2. Puste tło i pasy GL 0/0.5/1, surowa alfa i kompozycja ±2/255; miniatura po zmianie krycia
   bez flush; zachowana klatka nad nową bazą; zakres i ciągi D33; F2 bez obniżania progów.
3. Pełny styl, None, domyślne, ruch, role aktywna/błąd/release i mały kontener; round-trip
   JSON i walidacja bez importu Qt; fokus i Info bez regresji.
4. Dziewięć slajdów Demo renderuje się CE i GL; pełne testy F0–F5c i upstreamu zielone.
5. **Próba człowieka:** prawdziwe okno, Info przed 5/8, live na 9, klik/Esc, dwa monitory;
   porównanie czasu przejścia i płynności z Info widocznym/ukrytym, raport bez obietnicy
   niezmierzonego progu CPU/GPU. Osobno prezentacja z procesem live GL.

**Budżet:** ~10 h (bramka alfy 1 h, podgląd 2 h, tło/cache/sesje 2 h, obwódka 1 h,
demo i regresje 2 h, dokumentacja/setup 2 h); stop i raport przy 20 h.
Wykonawca: codex w głównym drzewie bez worktree; zmiany bez commitu.

**Wynik (2026-10-22/23):** kryteria 1–4 wykonane; końcowy pełny przebieg z diagnostyką
`faulthandler_timeout=60`: **434 passed, 2 skipped**, 334,39 s. Orbit/Demo wyrenderowane
w CE i GL (Demo: 9 slajdów); setup PowerShell wykonany dwukrotnie offline, Bash — składnia
poprawna. Kryterium 5, dwa monitory i pomiar wpływu Info pozostają do próby człowieka.

## Faza 5g — cofanie i replay cue live (kontrakt)

**Status:** kontrakt domknięty rundą 20; implementacja i dowody w śledzonym `reports/REPORT-5g.md`.
Zastępuje odroczenie checkpointów D33/D37 wyłącznie w zakresie F5g; próba człowieka osobno.

**Cel:** w sąsiednim ciągu `session_id` prelegent wraca do stanu live pozostawionego na
poprzednim slajdzie i może ponownie zagrać wejście bieżącego slajdu. GL i CE mają ten sam
protokół i semantykę; zachowują proces, obraz z alfą i mapowanie sesja → indeks (D33/D35).
Zgodność dotyczy stanów na granicach wejść, nie odwrócenia animacji ani zgodności każdej
klatki live z plikiem bazy. Ręczne zmiany na N są częścią stanu N, jeśli poprzedzają wejście
na N+1; ręczne zmiany wykonane na N+1 znikają po powrocie na N.

**Jednostka historii:** `entry_id` oznacza zatwierdzone wejście, nie numer slajdu ani nazwę cue.
Klucz checkpointu: instancja prezentacji w playerze, `session_id`, generacja procesu i
`entry_id`; ten sam plik otwarty dwukrotnie ma różne instancje. Przed wejściem na N zapisujemy
`before(N)`: stan po domknięciu poprzedniego cue, przed `enter_cue` N, kursor sekwencji i
całą dostępną historię `next/back` D37. Zapis także przy braku `enter_cue`, aby objąć ręczne
cue na takim slajdzie. Checkpoint jest niemutowalny, odtwarzalny wielokrotnie; nie dodaje wpisu
do historii D37 i nie jest implementowany przez wysłanie `back`. Odtworzenie odrzuca późniejszą
historię sekwencji. Wpis wejścia rozróżnia: przygotowany, cue niewysłane, wysłane, rozpoczęte,
zakończone, przerwane, pominięte, błąd; samo pole `enter_cue` nie dowodzi wykonania.

**Semantyka zatwierdzonych zdarzeń playera:**

| Przyczyna | Stan live i działanie |
|---|---|
| `initial`, także start od wskazanego indeksu | Świeży build, checkpoint lokalnego początku po READY; bez automatycznego cue jak dotąd. Brak rekonstrukcji pominiętych slajdów; pasek mówi „nowa sesja, bez historii wcześniejszych wejść”. |
| `next`, `auto_next` przy zmianie N → N+1 | Domknąć cue N, zapisać `before(N+1)`, po przygotowaniu uruchomić `enter_cue` celu raz. Bez cue pozostawić zapisany stan. |
| `skip_all` | Te same kroki dla każdego rzeczywiście zatwierdzonego wejścia wywołanego callbackiem, bez syntetycznych cue dla nieodwiedzonych indeksów. Nie scalać szeregu wejść w jedno. |
| `previous` (`←`) N+1 → N | Odtworzyć **before(N+1)**: stan pozostawiony na N, łącznie z ręcznymi zmianami na N. Nie wykonywać wejścia N. Baza gra normalny plik N od początku; klipy zgodnie z dotychczasowym normalnym wejściem. |
| `reverse` (`V`) N+1 → N | Ten sam checkpoint co dla `←`. Baza gra reverse **N**, klipy pozostają końcowymi klatkami N. Live pokazuje stan graniczny N, nie odwraca cue N ani N+1 w czasie pliku. |
| `reverse_to_normal` na N | Bez checkpointu, restore i cue; zachować live N. Także gdy źródłem był callback `auto_next`/`skip_all`; rozstrzyga zatwierdzona przyczyna, nie źródłowy klawisz. |
| replay (`R`) na N | Odtworzyć **before(N)** tego samego wejścia, odrzucając ręczne zmiany na N; ponownie uruchomić jego `enter_cue` raz po barierze. Bez cue tylko restore. Baza/klipy restartują według istniejącego replay. W reverse baza nadal gra reverse N, klipy zachowują dotychczasową semantykę; live powtarza cue do przodu, co pasek nazywa wprost. |
| Ponowne wejście do przodu po cofnięciu | Nowe `entry_id` i nowy checkpoint z aktualnego N, ponowne cue N+1. Porzucić przyszłą gałąź wejść, bez odtwarzania dawnego końca N+1. |
| Powtórzenie pętli slajdu / zamówienie jej końca | Bez zapisu, restore i ponownego cue. Dopiero rzeczywista zmiana slajdu podlega regułom powyżej. |
| Brak sąsiada, wznowienie `→`, pauza | Bez nowego wejścia i bez restore; akcja graniczna nie zmienia historii. |
| Przerwa w ciągu, inna prezentacja, ERROR/stopping | D33: stary proces i checkpointy kończą życie. Powrót z tym samym ID tworzy świeżą generację; żadnego restore między generacjami ani odtwarzania przez ponowne wykonanie wszystkich cue. |
| Zamknięcie | Anulowanie przygotowania, shutdown i zwolnienie historii; bez cue/restore. |

Oś A → B → A: po zakończeniu/przerwaniu cue A zapis `before(B)`; cue B i ewentualne ręczne
zmiany B; `←`/`V` domyka B i przywraca `before(B)`; dopiero potem startuje normalny/reverse
plik A. Przy kolejnym `→` powstaje nowe wejście B. `before(A)` zostaje do replay A i cofnięcia
A → poprzednik, dopóki mieści się w limicie. Kolejne cofnięcia korzystają z kolejnych wpisów,
nie z checkpointu slajdu docelowego. Brak wpisu (np. start od środka lub nowa generacja)
oznacza jawny fallback, nigdy próbę zgadywania stanu z indeksu slajdu.

**Protokół TCP:** rozszerzenie wspólnego `LiveTransport`, nadal linie
UTF-8 zakończone LF, bez przesyłania grafu sceny przez TCP/SHM. Identyfikatory to ograniczone
tokeny ASCII bez białych znaków; `request_id` jest unikalny w generacji. Istniejące ręczne
`next/back`, nazwy presetów, `view`, `shutdown` i `frame_seen` zachowują znaczenie.

| Komenda | Odpowiedź / zobowiązanie |
|---|---|
| `checkpoint <request_id> <checkpoint_id>` | `CHECKPOINT_READY <request_id> <checkpoint_id> <frame_id>` po zapisie i publikacji granicy. Ten sam ID nie nadpisuje istniejącego snapshotu. |
| `restore <request_id> <checkpoint_id>` | `RESTORE_START <request_id> <checkpoint_id>`, potem `RESTORE_DONE <request_id> <checkpoint_id> <frame_id>` dopiero po dokładnym odtworzeniu stanu, kursora i historii oraz publikacji granicy. |
| `enter <request_id> <checkpoint_id> <cue_name>` | Skorelowane `ENTRY_CUE_START <request_id> <checkpoint_id> <cue_name>` i `ENTRY_CUE_DONE <request_id> <checkpoint_id> <cue_name> <completed|interrupted> <frame_id>`. Walidacja presetu przed abort; nieznana nazwa daje błąd bez przerwania bieżącego cue. |
| `drop_checkpoint <request_id> <checkpoint_id>` | `CHECKPOINT_DROPPED <request_id> <checkpoint_id>`; zwolnić niepotrzebny wpis/gałąź. |
| `release <request_id> <checkpoint_id>` | `ENTRY_RELEASED <request_id> <checkpoint_id>` po przyjęciu końca rezerwacji bez cue; bieżący checkpoint jest chroniony. |
| Błąd operacji | `CHECKPOINT_ERROR <request_id> <checkpoint_id> <code>`; kody: `missing`, `stale_generation`, `unsupported`, `limit`, `invalid`, `restore_failed`. Brak statusu DONE/READY dla nieudanej operacji. |

Nowe prefiksy są zastrzeżone, parser odrzuca błędną liczbę pól/za długie ID i nie traktuje ich
jak nazw presetów. Szczegół błędu trafia do diagnostyki, kod do stanu 5c. CUE_DONE starego
protokołu nie potwierdza nowej operacji. Komendy skorelowane nie są retransmitowane: worker przyjmuje wyłącznie rosnące numery
żądań w generacji, powtórzenie lub cofnięcie numeru daje `invalid` bez mutacji. Bez automatycznej retransmisji cue po utracie połączenia; wynik pozostaje nieznany.

Każda granica ma dodatkowy status `BOUNDARY <request_id|0> <frame_id>`; `0` oznacza
READY/ręczne cue, nie operację stanu. Kontroler może dzięki temu odebrać klatkę przed DONE
i nadal rozpoznać granicę anulowanego wejścia. Nazwa cue w `enter` i ENTRY_CUE_* jest
kodowana procentowo UTF-8, aby zachować istniejące nazwy ze spacjami i polskimi znakami.

**Kolejność, bariery i przerwanie:**
- READY nadal oznacza build + pierwszą klatkę, nie bezczynność ani przygotowane wejście.
  Po READY i odbiorze jego granicy kontroler zamawia checkpoint/restore. Poprawna komenda
  stanowa przerywa zwykłe cue według D10: finish/cleanup **całego callable**, logiczny koniec
  play bez symulowania pominiętego dt updaterów. D9 dla live LOOPS: czekać do granicy
  powtórzenia. Blokujący kod autora nie staje się przerywalny dzięki checkpointom.
- Stara granica po D10 musi zostać odebrana i potwierdzona `frame_seen` przed publikacją
  kolejnej. Także CHECKPOINT_READY/RESTORE_DONE wskazują własny `frame_id`; kontroler czeka
  na pasującą klatkę, wstawia ją do właściwej warstwy i potwierdza odbiór. Status bez klatki
  nie zwalnia przygotowania. `frame_id` nigdy nie cofa się wraz z czasem sceny.
- D31 obejmuje teraz przygotowanie live również w ciepłej sesji, nad bazą statyczną,
  podczas replay i reverse (obecne pominięcie `clips.enter` dla reverse wymaga osobnej
  ścieżki bariery live). Baza/klipy stoją na właściwych klatkach początkowych/końcowych;
  po gotowości wszystkich w jednym ticku start grupy i `enter`, jeśli wymagane.
  Restore nie czeka na „play”: kończy się również przy `start_paused`; cue wejścia czeka
  na pierwszy rzeczywisty start. Pauza w przygotowaniu zmienia zamiar, nie kolejkuje kopii cue.
- Deadline przygotowania: 5 s od żądania przejścia, łącznie z READY, domknięciem i restore,
  bez restartowania licznika po każdym statusie. Zachować timeout odbioru granicy 2 s.
  Po deadline anulować niewysłane cue, odłączyć tę warstwę od bariery, baza/klipy kontynuują
  według zamiaru. Zatrzymać niepewną sesję, aby spóźnione restore/cue nie zmieniło obrazu;
  jej statusy/klatki nie wracają do kompozycji. Nowa generacja dopiero przy kolejnym wejściu.
- Szybkie A → B → A: operacje stanu jednej sesji wykonują się kolejno, bez przeplatania
  snapshotu i restore z ręcznym cue; podczas przygotowania ręczne cue są odrzucane z komunikatem.
  Zatwierdzone wejścia zachowują kolejność checkpointów, lecz start/cue anulowanego wejścia
  nie jest wysyłany. Kontroler odcina callbacki przez generację, `entry_id` i `request_id`;
  dopiero najnowsze wejście może zwolnić barierę i zmienić bieżący komunikat. Przerwane już
  wysłane cue ma wynik `interrupted`, nie „anulowane przed wysłaniem”.

**Odtworzenie i oba silniki:** użyć istniejących snapshotów D37: wspólny adapter grafu `PanelSnapshot` z mapą oryginałów, wspólnym memo i jawnym
odtworzeniem słowników oraz krawędzi; GL nie używa `get_state/undo` dla checkpointów.
Osobna otoczka checkpointu przechowuje kursor i historię D37 (do 50 pozycji); snapshot sceny
sam nie obejmuje historii transportu. Nie kopiować procesu, socketu, renderera ani Qt.
Zakres CE pozostaje standardowym panelem Cairo 2D D38, bez nowych obietnic dla kamery/3D;
GL tylko stan wspierany przez jego mechanizm D37. Zasoby zewnętrzne, mutowalne zamknięcia,
RNG i dowolne pola autora nie są automatycznie cofane. Sceny zależne od nich nie mają gwarancji
identycznego replay; nieobsługiwany typ danych kończy operację błędem, ale zależności updaterów od pól sceny,
I/O i zamknięć nie są wykrywane. Gwarancja obejmuje standardowe węzły panelu,
numeryczne tablice, style, add/remove, współdzielone dzieci i referencje updaterów;
identyczny replay wymaga deterministycznego cue i tego samego sposobu przerwania. Bez forkowania/łatania Manima i bez serializacji na dysk.

**Wybór animacji:** restore animowany przez 0,6 s na zgodnych węzłach, następnie dokładny stan,
jak ręczny back D3/D37; dotyczy także przygotowania replay. Widoczny ruch wyjaśnia prelegentowi
cofnięcie i zachowuje decyzję D3 przeciw ostremu skokowi. Zmiana topologii domyka się na końcu.
Baza pozostaje wtedy zatrzymana, pasek mówi „przywracanie”; nie obiecujemy reverse oryginalnego
cue ani wspólnej trajektorii z reverse bazy. D17 gwarantuje wspólny start po przygotowaniu,
nie frame-lock. Ręczne back nadal animuje według D3; spacja nadal nie pauzuje działającego live.

**Pamięć i fallback:** maksymalnie 50 checkpointów wejść i 256 MiB rozliczonej pamięci
snapshotów na proces live, łącznie z grafami historii D37 utrzymywanymi przez checkpointy;
w rachunku są też bieżące dane oryginałów utrzymywanych przez snapshoty, nawet po usunięciu
ze sceny. Rezerwa restore obejmuje największy z grafu sceny, zapisanej kopii i bieżących oryginałów;
wspólne dane liczyć raz, nie tylko rozmiar listy. Limit nie jest obietnicą RSS całego Manima.
Pomiar/konserwatywny rachunek grafu bez pickle; jeśli backend nie potrafi bezpiecznie rozliczyć
snapshotu, `unsupported`. Bramką implementacji jest wykazanie rachunku na korpusie obu silników.
Przy przekroczeniu usuwać najstarsze niebieżące checkpointy, raportować ich ID przez
`CHECKPOINT_EVICTED <checkpoint_id> limit`. Nie usuwać checkpointu bieżącego wejścia ani
używanego restore. Jeśli nadal brak miejsca (także pojedynczy zbyt duży zapis), `limit`,
bez niepotwierdzonego checkpointu i bez automatycznego cue tego wejścia. Zapis tymczasowy
też wymaga rezerwy w limicie; brak rezerwy oznacza odmowę przed alokacją kopii.

Brak/eksmisja checkpointu: pozostawić ostatni poprawny obraz i stan, cue replay pominąć,
wyraźnie pokazać „stan live nieprzywrócony”; nawigacja bazy/klipów działa. Błąd restore po
częściowej mutacji: nie publikować częściowego wyniku jako sukcesu, zachować ostatni obraz
GUI, oznaczyć panel jako nieaktualny i zatrzymać proces (ERROR bez przejęcia). Przywracanie
nie jest transakcją efektów ubocznych autora. Przerwa ciągu/nowa prezentacja daje nowy build,
a nie fałszywe „przywrócono”. Bez globalnego cache sesji i bez restartu udającego restore.

**Stan 5c:** Info i nakładka korzystają z tego samego `presenter_snapshot`; stan operacji
osobno od `session.state == ready` i transportu bazy. Krótki wynik ~2 s, ale degradacja
„nieaktualny / bez checkpointu” zostaje do następnego poprawnego przygotowania.

| Zdarzenie | Tekst (z numerem warstwy i slajdu/prezentacji) |
|---|---|
| Zapis / potwierdzony zapis | „live: zapis stanu wejścia” / „checkpoint gotowy” |
| Restore / odebrana granica DONE | „live: przywracanie stanu N” / „przywrócono stan N” |
| Replay | „replay: przywracanie początku N” → „wysłano cue X” → „start cue X” → „koniec cue X” |
| Replay podczas reverse | „baza reverse; live powtarza cue do przodu” |
| D10 / D9 | „cue przerwane i domknięte” / „oczekiwanie na koniec powtórzenia live” |
| Pauza / anulowanie wejścia | „stan gotowy, cue czeka na start” / „wejście anulowane, cue niewysłane” |
| Brak historii / limit / błąd / timeout | Konkretna przyczyna + „stan live nieprzywrócony; cue pominięte”, nigdy „gotowe” jako wynik restore |
| Eksmisja / nowa generacja | „starszy checkpoint usunięty: limit” / „nowa sesja, wcześniejszy stan niedostępny” |
| Ręczne cue podczas przygotowania | „live przygotowuje stan — klawisz pominięty” |

**Kryteria akceptacji (offscreen, po przyjęciu i implementacji):**
1. Dla GL i CE przez rzeczywiste callbacki playera: A → B → A (`←` oraz `V`), replay A/B,
   replay w reverse, reverse_to_normal, auto_next/skip_all także w reverse, wznowienie,
   pętla i granice. Liczniki wejść/START/DONE potwierdzają jedno cue dla udanego next/replay z nazwą i zamiarem startu,
   zero dla initial, braku nazwy, anulowania, fallbacku, pętli i powrotu. Replay podczas przygotowania pozostaje ignorowane jak dotąd.
2. Przed B ręczne next/nazwane cue na A, po B dalsze next/back/nazwane cue; powrót daje dokładny
   graf, referencje, kursor i historię A. Replay B dwukrotnie daje ten sam początek i koniec
   na deterministycznym panelu; brak enter_cue także odtwarza ręczne zmiany. Korpus D37:
   grupy, współdzielone dzieci, add/remove, style, updatery i czas; piksele wnętrza ±2/255,
   krawędzie 2 px, geometria i tożsamości sprawdzone niezależnie od pikseli.
3. TCP: podzielone/sklejone linie, błędne ID/nazwa, odrzucenie powtórzeń, nieaktualna generacja,
   disconnect i opóźnione statusy. DONE nie wystarcza bez odebranej wskazanej granicy;
   frame_seen nie pozwala nadpisać granicy, timeout 2 s zachowany. Nieznane cue nie przerywa.
4. Baza+live bez klipów, baza statyczna, ciepły/zimny start, start_paused, pauza w przygotowaniu,
   replay i reverse: kolejność READY → checkpoint/restore+odbiór → start grupy/enter;
   deadline 5 s i brak spóźnionego cue. Dwa play/wait przerwane według D10 oraz LOOPS według D9.
5. ≥20 szybkich A → B → A, zmiana indeksu warstwy, dwie sesje na slajdzie, mieszane CE/GL,
   dwie prezentacje z tym samym ID, przerwa ciągu, ERROR/stopping i zamknięcie podczas restore:
   brak obcych klatek/statusów, brak przejęcia starej generacji i wycieków procesów/SHM.
6. Wstrzyknięte unsupported/restore_failed/missing, eksmisja 51. wpisu i przekroczenie limitu
   bajtów, także jeden zbyt duży snapshot: zgodny fallback i tekst obu widoków 5c. Po 100 wejściach
   limity liczby/bajtów utrzymane, drop/shutdown zwalnia snapshoty i ich historie.
7. ≥30 prób na silnik: restore z klatką pośrednią dla widocznych zgodnych węzłów, nominalnie 0,6 s; raport p50/p95/max komenda
   → odebrana granica, osobno zapis/przygotowanie/odtworzenie i pamięć. Cel dla prostego panelu
   restore 0,6 ±0,1 s; przekroczenie raportować, nie ukrywać pod czasem wysłania. Raport wspólnego
   startu trzech warstw osobno, bez wymogu ±1 klatka. GUI poll/try_read_frame <50 ms.
8. Regresje F0–F5d-f/7a i upstreamu zielone, progi GL F2 i CE D38 nieobniżone. Zaktualizować
   obecne testy „brak cue dla replay” i tekst D33 dopiero przy wdrożeniu przyjętego kontraktu.
   Osobna próba człowieka po implementacji: czytelność cofania/replay/statusu w prawdziwym oknie
   i na dwóch monitorach; offscreen nie zalicza tej próby.

**Poza zakresem:** retransmisje i rozbudowany cache duplikatów; seek/frame-lock/zegar główny, reverse cue klatka
po klatce, pauza live, cofanie efektów I/O/RNG/zamknięć, odtwarzanie dowolnego grafu Pythona,
CE OpenGL/3D/animowana kamera, historia między procesami/prezentacjami/przerwanymi ciągami,
rekonstrukcja pominiętych slajdów, dyskowy cache i nowe ustawienia użytkownika.

**Uściślenia rundy 20 (normatywne, pierwszeństwo nad skrótem powyżej):**
- Rezerwacja obejmuje przygotowanie, gotowość w pauzie i czas do przyjęcia `enter` lub
  `release` dla wejścia bez cue. Polecenia ręczne już odebrane przed rezerwacją są domykane
  FIFO; nowe `next/back`, presety i `view` są odrzucane. Nawigacja playera pozostaje możliwa.
- Jedna generacja to jeden socket/proces. Token checkpointu `g<hex>_e<decimal>` (≤64 ASCII),
  żądanie dodatnia liczba dziesiętna (≤20 cyfr), linia ≤512 bajtów, kolejka ≤128 operacji.
  Monotoniczne numery żądań odrzucają duplikaty; bez retransmisji. `release <request> <id>`
  zamyka rezerwację bez cue. Zmiana bieżącego ID unieważnia stare `enter`; drop jest
  idempotentny, ponowny checkpoint istniejącego ID jest `invalid`. Generację sprawdza worker.
- ACK należy do kontrolera: aktualny obraz wstawia przed ACK; starą granicę nadal odbiera
  i potwierdza, bez wstawienia. Status i wskazana klatka mogą dotrzeć w dowolnej kolejności.
- Zimne next/auto_next/skip_all (także po ERROR i między prezentacjami) zapisują build i
  wykonują cue celu; initial oraz zimne previous/V zapisują build bez cue. Replay lokalnego
  początku wykonuje cue celu. Warstwy bez session_id pozostają w D27, bez checkpointów F5g.
- Cofnięcie usuwa bieżący wpis ze stosu po zamówieniu restore jego before; kolejne cofnięcie
  korzysta z kolejnego poprzednika. Przyszłość jest odłączona natychmiast, jej checkpointy
  zwalniane po wykonaniu restore. Replay nie przesuwa stosu. Brak wpisu i nieudany restore
  przesuwają pozycję nawigacji, ale trwale oznaczają panel jako nieaktualny; nie zgadujemy
  checkpointu. Zapis wykonany po rozbieżności nie usuwa degradacji i nie odblokowuje cue;
  odzyskanie zgodności wymaga restore wcześniejszego poprawnego wpisu albo nowej generacji.
- GL home aktualizuje się na opublikowanej granicy; view podczas rezerwacji jest blokowane.
  CE view pozostaje no-op. Test: kamera→checkpoint→view→restore→reset.
- Limit 256 MiB dotyczy rozliczonego grafu snapshotów i aktywnego undo/redo oraz konserwatywnej
  rezerwy 4× graf bieżącego panelu na zapis/restore/interpolację. Nie jest limitem RSS.
  Dane typów spoza korpusu dają unsupported przed kopią; brak miejsca daje limit przed kopią.
  Współdzielone snapshoty historii liczymy raz, także po drop i eksmisji.
- Replay ładuje bazę/klipy od początku przez tę samą barierę, resetuje pętle i odcina stare
  callbacki; reverse przygotowuje tylko bazę/live, zachowując końcowe klatki klipów.
- Stan mówi „przywrócono stan pozostawiony na N” lub „przywrócono początek N”; odróżnia
  cue niewysłane, przerwane i wynik nieznany. Trwałe „stan live nieprzywrócony: powód” ma
  pierwszeństwo nad READY. Info i nakładka czytają ten sam stan.

**Budżet implementacji:** 24 h po bramce: snapshot/rachunek GL+CE 6 h, transport/rezerwacja/ACK
5 h, player/bariera/status 6 h, korpus/pomiary/regresje/dokumentacja 7 h. Stop i raport przy
48 h, bez rozszerzania zakresu. Próba człowieka osobno. Bramki nie zaliczają kryteriów bez dowodu.


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

### 7a — adapter live Cairo (kontrakt)

**Cel:** autorska scena CE 0.22 Cairo 2D pracuje bez okna w istniejącej warstwie live,
obok GL i klipów; zachowuje D1–D3, D9–D10, D17, D20–D35 w opisanym niżej zakresie.
Kontrakt domknięty rundą 19; poniższy projekt uwzględnia ograniczenia D36–D38.

**Ustalenia z kodu zainstalowanego CE 0.22.0** (ścieżki względem
`.venv/Lib/site-packages/manim/`; punkty zaczepienia przez podklasy, bez zmian upstreamu):
- `scene/scene.py:1188` przekazuje `play()` do managera; `manager.py:234` →
  `renderer.play(scene, ...)` (`:260`). `Scene.render()` (`scene/scene.py:304`) też idzie
  przez managera, a nie starą samodzielną pętlę `construct`. Bootstrap musi respektować
  setup/construct/tear_down i sprzątanie na wyjątku, nie zakładać API sprzed 0.22.
- `renderer/cairo_renderer.py:77` kompiluje animacje, wywołuje begin, przygotowuje
  obraz statyczny i woła `scene.play_internal()`. `scene/scene.py:1384` iteruje po czasie
  offline i wykonuje finish/cleanup; `:1714` (`update_to_time`) liczy dt z `last_t`,
  aktualizuje animacje, mobjecty i updatery sceny. Adapter zastępuje tę pętlę zegarem
  monotonicznym: t od początku play, dt od ostatniej aktualizacji, t ograniczone do duration;
  spóźnione terminy pomija zamiast wydłużać cue. Między cue nie aktualizuje updaterów.
- `renderer/cairo_renderer.py:139` (`update_frame`) rysuje do kamery, `:183` (`render`)
  robi dodatkowo `get_frame().copy()` i `add_frame`; `:197` (`add_frame`) zwiększa czas
  o liczbę klatek/fps i woła writer. Projekt: własna podklasa renderera dla live używa
  `update_frame` i publikuje `camera.pixel_array`, bez ścieżki add_frame. `renderer.time`
  (odczytywane przez `Scene.time`, `scene/scene.py:286`) dostaje aktywny czas sceny z zegara,
  także przed updaterami; nie może naliczać drugi raz czasu publikacją klatki.
- D10: po przerwaniu pętli trzeba wykonać `animation.finish()` i
  `clean_up_from_scene` jak `scene/scene.py:1409`, wyzerować static_image i opublikować
  stan **po cleanup całego cue**. Flaga abort zostaje do końca callable: dalsze play
  przechodzą begin/finish/cleanup bez czekania, dalsze wait nie czekają. Nie rzucać wyjątku
  przerywającego callable przed kolejnymi play. Dowolny blokujący kod Pythona autora
  nie jest kooperacyjnie przerywalny. D9 ma pierwszeństwo dla LOOPS: zwykła komenda
  kończy bieżące powtórzenie; shutdown działa od razu. Nieznana komenda/view/frame_seen
  nie ustawia abort. Czas logiczny domkniętego play dochodzi do jego końca, czas ścienny
  po D10 nie musi; następne play ma nowy punkt odniesienia zegara.
- `wait()` (`scene/scene.py:1242`) buduje Wait; `:1312` rozpoznaje statyczne czekanie,
  renderer (`cairo_renderer.py:147`, `:239`) wtedy omija play_internal i powiela klatkę.
  W live potrzebna osobna kooperacyjna obsługa obu ścieżek: statyczne wait czeka i czyta
  komendy bez renderowania wnętrza, dynamiczne aktualizuje updatery i publikuje klatki;
  stop_condition jest dynamiczne według CE i sprawdzane co tick; frozen_frame zachowane,
  ale jego połączenie ze stop_condition odrzuca CE.
- Konfiguracja **przed** konstrukcją: renderer=cairo, format=none, disable_caching=True,
  preview/live_preview/enable_gui=False, bez zakresu `-n` i skip_animations. Samo wyłączenie
  cache nie wyłącza filmu. `_config/render_session.py:64` rozwiązuje format,
  `_config/output_plan.py:266` daje dla NONE brak artefaktu i segment_cache_dir;
  `scene/scene.py:229` utrwala plan/ustawienia writera. `scene_file_writer.py:469`, `:504`
  chronią zapis warunkiem is_video; `cairo_renderer.py:97` omija hashowanie przy
  disable_caching. `write_to_movie` nie jest już opcją CE. Brak filmu/segmentów/PNG
  końcowego sprawdzamy po procesie; cache zasobów TeX/tekstu nie jest cache filmu.
- `camera/camera.py:91` ustala wymiary, kanały RGBA uint8 i krycie; `:250` dopasowuje
  frame_shape do pikseli. Renderujemy izotropowy kadr 16:9 dopasowany do panelu D34
  (zaokrąglenie do pikseli), nie rozciągnięty do pionowego bufora. `:275` inicjalizuje
  tło z koloru i background_opacity; `:591` daje macierz y w dół, `:769` odwraca RGB
  na wejściu Cairo — nie zamieniać ponownie kanałów gotowego pixel_array.
  D35: puste tło i pasy mają kolor kamery i alfę z LiveLayer; transport straight RGBA.
  Cairo ARGB32 używa premultiplikacji, lecz inicjalizacja tła CE zapisuje RGBA wprost:
  nie zakładać jednolitej reprezentacji wszystkich pikseli przy częściowej alfie.
  **Pierwsza bramka implementacji:** tło/pasy 0/0.5/1 nad znaną bazą ±2/255, także
  kolorowe; jeżeli wymagają normalizacji, robi ją adapter poza Manimem i mierzy jej koszt.
  Nie rozszerza to D35 na dowolną półprzezroczystą treść/krawędzie; nie łatać kamery CE.
- `interactive_embed` (`scene/scene.py:1419`, `:1439`) wymaga OpenGLRenderer i okna,
  `interact` (`:1523`) obsługuje interaktywny shell/wątek. Nie stanowi pętli Cairo live
  i nie wchodzi do adaptera. Jeden wątek aplikacji na proces; animacje używają terminów
  monotonicznych, `sleep` i `live_poll(0)`, a `select` z timeoutem tylko idle i bariery.

Źródło CE 0.22.0: SHA256 `renderer/cairo_renderer.py` = `040a1dbbbff6fc02cf1ffe65d6ab5ea7b37948b3eb01f127f4101f4bfd70663b`.

**Pomiar przed kontraktem (2026-10-23, Windows, CE 0.22.0):**
`experiments/f7a_cairo/measure.py`, metodologia w README, surowe próbki i środowisko
w `results.json`. 30 klatek rozgrzewki + 240 próbek/przypadek, pełne przerysowanie
bez static_image, osobno kopia RGBA z odwróceniem wierszy do bufora D21.
Panel demo: round(0.28×1920) × round(0.6×1080) = **538×648**, treść **538×303** + pasy.
Poniżej rotate Panel 2D; pozostałe geometrie D22 i pulse/sweep są w JSON.

| bufor | render mediana/p95 [ms] | kopia mediana/p95 [ms] | p95 razem [ms] | przepustowość razem [kl./s] |
|---|---|---|---|---|
| 960×540 | 0,407 / 0,486 | 0,095 / 0,109 | 0,589 | 1875,5 |
| 480×270 | 0,225 / 0,255 | 0,013 / 0,015 | 0,269 | 4117,3 |
| 538×648 | 2,257 / 3,478 | 0,144 / 0,261 | 3,801 | 452,2 |

To przepustowość render+copy bez limitu zegara, **nie odebrane różne klatki F2**.
Brak kosztów aktualizacji geometrii, TCP, blokady, publikacji SHM, odbioru i Qt; znaczna
zmienność CPU w małym/pionowym panelu, bez ekstrapolacji na złożone sceny/1080p.
TeX pominięty jawnie: MiKTeX wymaga konfiguracji. SlowBuild/wyjątki/idle mają reprezentanta
geometrii, nie mierzą semantyki; 3D wyłączone. Pomiar nie zalicza żadnego testu adaptera.

**Projekt:**
- API autora: `from manimcue.live_scene_ce import LiveSceneCE`; podklasa sceny CE 2D,
  `build_objects()`, `PRESETS: dict[str, callable(self)]`, `SEQUENCE`, `LOOPS`, zwykłe
  `self.play`/`self.wait` z CE. Bez automatycznego tłumaczenia mobjectów manimgl.
  `→`/next przesuwa kursor, nazwa presetu z TCP nie przesuwa (D2); koniec sekwencji
  SEQUENCE_END, `←`/back na początku bez zmiany. Osobny moduł nie importuje GL.
- D3 wymaga własnego snapshotu CE, nie `Scene.save_state` z manimgl: przed cue z next zachować
  tożsamości i kopie rodzin mobjectów oraz listy sceny/foreground.
  back interpoluje każdy zgodny węzeł dokładnie raz przez własną Animation przez 0,6 s,
  następnie dokładnie przywraca listy (w tym dodane/usunięte obiekty) i relacje grup. Referencje
  autora do oryginalnych obiektów pozostają ważne. Nie serializujemy socketów/rendererów,
  plików ani dowolnych pól użytkownika. Wymagane przypadki: grupy, współdzielony członek,
  add/remove i ponowne next; back dotyczy sekwencji, nie nazwanych enter_cue (D33).
- `LiveLayer.engine: Literal["manimgl", "ce-cairo"] = "manimgl"` i analogiczne pole
  **na końcu** LiveSpec (zachowanie istniejących argumentów pozycyjnych). Brak pola
  w decku v2/v3 oznacza GL. Nowy zapis z wyborem silnika: format v4, migracja v2/v3
  do GL; starszy player odrzuca v4 zamiast uruchomić scenę CE jako GL. kind="live"
  pozostaje bez zmian. Nie wybierać silnika przez import i zgadywanie klasy.
- Worker wybiera backend przed pierwszym importem Manima i pliku autora, czyści argv,
  waliduje klasę odpowiedniej bazy, uruchamia spawn bez Qt. Engine trafia do obu
  tożsamości D33 (`config.py:546`, `live_layers.py:101`), LiveSpec i klucza miniatury.
  Nie zmieniać silnika istniejącego procesu. Nadal wymagane: ścieżka, klasa, fps,
  rozmiar i krycie; pozycja/style/miniatura nie restartują sesji.
- Wspólny protokół bez zmian: lokalny TCP, bajty do pełnej linii UTF-8, next/back,
  nazwy cue, shutdown, frame_seen, view; statusy READY/CUE_START/CUE_DONE/SEQUENCE_END/ERROR.
  SharedMemory v1 + przekazany Lock D21, RGBA8 **bottom-up** (Cairo jest top-down,
  więc adapter odwraca wiersze); OwnedFrame zostaje top-down. Render poza blokadą,
  kopiowanie payloadu i nagłówka pod tą samą blokadą, odczyt GUI acquire(False).
  READY dopiero po build i pierwszej publikacji boundary. Bariera frame_seen na starcie,
  końcu/przerwaniu i back, timeout 2 s; zwykłe klatki view bez bariery. Nieznana komenda
  nie przerywa, klient EOF nie zabija sceny; zachować kolejność klient-przed-listenerem.
  Shutdown kooperacyjnie do 2 s, potem kill; restart ma świeże IPC; ERROR z klasą i cue.
- D33/enter_cue, D31 i D17 bez zmian: ciąg sąsiednich slajdów przejmuje żywy proces
  i ostatni obraz, przerwa tworzy nową generację; bez ID działa D27. Cue wejścia tylko
  przy zatwierdzonym wejściu do przodu, po READY przy wspólnym starcie, bez fokusu;
  brak READY przez 5 s usuwa live z bariery. Ciepła sesja nie blokuje startu; pauza
  bazy/klipów nie pauzuje live. Brak zegara głównego/seek/frame-lock.
- Klawiatura/fokus D20 zostają w playerze: przygotowanie na wejściu, aktywacja kliknięciem,
  strzałki do aktywnej gotowej warstwy, Esc/klik poza/zmiana slajdu/dezaktywacja aplikacji
  zwalnia; autorepeat odrzucony, przed READY klawisze nie są kolejkowane. Info i główne
  okno to jeden obszar aktywności, podgląd następnego slajdu używa miniatury.
- D28 w CE odroczone: view jest jawnym no-op, nie przerywa cue ani bariery; pan/zoom/reset,
  animowana kamera oraz CE 3D nie należą do panelu 2D fazy 8.
- Miniatura: istniejący `capture_first_frame` przez ten sam worker i engine
  (`slides/slide/base.py:710`), pierwsza klatka po READY, PNG straight RGBA z alfą/pasami
  identycznymi jak live. Klucz: dotychczasowe dane + engine, fps, CE 0.22 i wersja
  generatora/interpretacji alfy; zmiana importowanej zależności nadal wymaga flush.

**Progi CE — cele akceptacyjne do sprawdzenia pełnym pomiarem:**
pomiar nie uzasadnia obniżenia do 30 fps w prostych scenach. Osobne minimum
CE: 60 różnych odebranych kl./s przy 960×540, 480×270 i 538×648 dla ciągłego ruchu D22
oraz Panel 2D; okno 30 s po rozgrzewce, liczba ≥ 60·T − 2 według D26. Statycznego wait
i idle nie obejmuje licznik różnych klatek. CPU idle < 5% jednego rdzenia,
p95 komenda → odebrana zmieniona klatka < 100 ms w ciepłej sesji, zimny start osobno.
To cele sprawdzane pełnym pomiarem po implementacji, nie wnioski z samego renderu.
Osobno raportować update/render/kopię/normalizację alfy/publish/odbiór, liczniki surowe
zamrożone na końcu okna. **Progi manimgl F2 zostają:** 960×540 60, 1920×1080 30,
CPU i latencja bez zmian; CE 1080p bez deklarowanego progu w 7a.

**Kryteria akceptacji (offscreen, po implementacji):**
1. Round-trip v4 CE/GL i migracja v2/v3 do GL, błędny engine/klasa → diagnoza; oba silniki
   w jednym decku bez importu Manima/Qt przez moduły transportu na poziomie modułu.
2. Porty 2D korpusu D22: first frame, narożniki, ruch 5 s w 4,9–5,2 s z klatkami pośrednimi;
   dwa play przerwane w połowie → CUE_DONE < 1 s i końcowy x=4; nieznana komenda nie przerywa;
   LOOPS kończy powtórzenie na granicy. D1–D3: kursor, nazwane cue, animowany back 0,6 s
   (tolerancja 0,1 s) z klatką pośrednią i dokładną maską końcową, add/remove/grupy/referencje.
3. Wait 1,5 s w 1,4–1,7 s bez klatek wnętrza; updater wait 2 s → przesunięcie 2 ±0,1 jednostki;
   idle 2 s bez ruchu/publikacji. Stop_condition bez ruchu i z updaterem, frozen_frame,
   przerwanie wait i kolejne play/wait w cue; sztuczny zegar ze spóźnieniem bez dryfu dt.
   Zmiana obrazu przed frozen wait jest publikowana na początku, identyczna klatka nie jest powielana.
4. TCP split/multi/UTF-8/reconnect, READY po SlowBuild ≥3 s; ERROR w build bez READY
   i w cue z treścią. Granice nie nadpisane przed frame_seen, timeout 2 s, shutdown podczas
   wait/pętli/build/importu, restart ze świeżym IPC i brak procesu/SHM po 20 cyklach.
   Metody GUI poll/try_read_frame <50 ms także podczas build.
5. Engine w obu tożsamościach sesji i cache miniatur; mieszany deck CE+GL z klipami:
   przejęcie PID/obrazu na sąsiednim slajdzie, rozłączenie ciągu, błąd niespójności,
   enter_cue raz tylko do przodu, pauza w przygotowaniu/timeout 5 s, routing fokusu D20.
6. 16:9 i okrąg bez deformacji w trzech rozmiarach; jawny no-op view,
   view podczas cue i po SEQUENCE_END bez zerwania bariery. Tło/pasy 0/0.5/1, kolorowe
   tło, miniatura i ostatnia klatka nad nową bazą ±2/255. Bramka alfy przed dalszą integracją.
7. Zero artefaktów filmu/segmentów po wielu play i shutdown (przy podłożonej pułapce
   na otwarcie encodera), disable_caching nie wywołuje hash/cache lookup; także drugi start.
   TeX: kompilacja CE lub jawny skip środowiskowy, żadnego cichego zaliczenia.
8. Pełny zestaw F0–F5d-f/7.0/upstream zielony oraz 30 s odbiornika Qt offscreen z przyjętymi
   osobno progami CE. Panel 2D rotate/pulse/sweep i ThreePanel mają porty CE w demo testowym.
   Offscreen nie zalicza projektora, dwóch monitorów ani odczucia fokusu — osobna próba
   prelegenta po implementacji; nie jest warunkiem wdrożenia adaptera.

**Poza zakresem 7a:** OpenGL CE = 7b (osobny adapter/kontrakt), CE 3D; checkpointy przy
nawigacji/replay są osobno w F5g / D39–D41. Nadal poza zakresem serializacja dowolnego stanu Pythona,
fork/patch Manima, zegar główny i seek, dowolna przezroczysta treść poza D35.

**Domknięcie rundy 19 (D36–D38, wiążące):**
- Renderer kontroluje cały play: compile/begin, frozen wait, finish/cleanup; nie uruchamia
  encodera ani hashowania; next_section(skip_animations=True) jest błędem.
- D10 kończy animacje i czas logiczny, nie symuluje brakującego dt updaterów; zwykły
  wait bez ruchu nie publikuje wnętrza, warunek zawsze jest dynamiczny, frozen+warunek
  odrzuca CE; wcześniejszy warunek kończy czas w chwili spełnienia.
- Snapshot obejmuje standardowe Mobject/VMobject paneli 2D: geometrię, style, updatery
  (referencje callable), listy scene/foreground i krawędzie submobjects; wspólne memo
  zachowuje tożsamości, nie kopiuje stanu zamknięć ani dowolnych zasobów Pythona.
  Przy back interpolujemy każdy zgodny węzeł raz bez podwójnej transformacji dziecka,
  potem odtwarzamy dokładny graf; zmiana liczby dzieci jest w korpusie.
- Oba silniki zapisują historię tylko przed next, powiązaną z kursorem, 50 pozycji
  bez deduplikacji; back po next → nazwane cue wraca przed next (D33).
- Worker narzuca config po imporcie autora na cały lifecycle; setup/build/cue/tear_down
  mają jeden finalizer, pierwotny wyjątek ma pierwszeństwo; construct nie wolno nadpisywać.
  Shutdown podczas play przerywa callable, blokujący import/build kończy nadzorca po 2 s.
- Testy integracyjne obejmują nieznany enter_cue bez abort, zamknięcie podczas play,
  ERROR/stopping bez przejęcia, dwie animujące CE i GL obok, krycie między generacjami.
- Piksele liczymy przez porównanie kolejnych obrazów treści, nie frame_id; 30 s ciągłego
  nieokresowego ruchu, trzy przebiegi ze zmienną kolejnością wymiarów, rozrzut/max/opóźnienia.
  Maski: tolerancja krawędzi 2 px, wnętrze ±2/255; asymetryczne narożniki.
  Dla 538×648 treść 538×303 zaczyna się w (0,172), dolny pas ma 173 wiersze.
  Bufor wynika z rect i rozdzielczości decku, nie rozmiaru okna; alfa sprawdzana w Qt.
- Back mierzymy od komendy do odbioru granicy (cel 0,6 ±0,1 s dla panelu), osobno
  snapshot/przygotowanie/odtworzenie i pamięć po wielu cue; wyniki GL nie zastępują CE.

**Budżet implementacji:** ~16 h, stop i raport przy 32 h; bramki lifecycle/zegar/alfa
4 h → snapshot i panel/transport 4 h → D33/miniatura/demo 3 h → korpus/pomiary/regresje
5 h. Po każdej bramce sprawdzenie pozostałego budżetu; brak zwiększania limitu w trakcie.
Próba człowieka osobno. Odroczone: D28 CE, animowana kamera, dowolne grafy spoza korpusu.


**Wynik (2026-10-23, Windows 11, CE 0.22.0):**
- Kryteria 1–8 w części automatycznej zaliczone; pełny `uv run --frozen pytest -q -p no:cacheprovider`:
  **506 passed, 3 skipped, 57 warnings in 470.60s (0:07:50)**. Dowody test po teście w `reports/REPORT-7a.md`.
- 18 okien 30 s (dwie geometrie × trzy rozmiary × trzy przebiegi): 1799–1800 różnych
  odebranych klatek, 59,967–60 fps. Dodatkowa próba końcowej ścieżki 960×540:
  1798 klatek, 59,933 fps; wszystkie 19 okien spełniają ≥60T−2. CPU idle ≤0,8% rdzenia,
  najgorsze p95 komendy 25,64 ms; progi GL F2 bez zmian.
- `Orbit` (1 slajd) i `Demo` (11 slajdów, dwa panele CE na 10–11) wyrenderowane w CE,
  oba polecenia z kodem 0. README/API po angielsku; `.venv` bez zmian źródeł.
- Próba człowieka: **otwarta** (projektor, dwa monitory, fizyczny fokus i płynność);
  D28 CE, animowana kamera i dowolny graf spoza korpusu odroczone jawnie D38.
  Czas i odstępstwa w `reports/REPORT-7a.md`; budżet 16 h / stop 32 h nieprzekroczony.

## Faza 8 — integracja z seminarium

Seminarium przechodzi z vendorowanej manim-slides 5.7.0 na fork — wymaga zgodności z CE 0.22.
Panel NV⁻ w scenie czterowidokowej (D9 tamtego planu) jako warstwa live obok trzech
prerenderowanych. Punkt wejścia: `SeminarScene`/`SeminarScene3D` w tamtym `deck/base.py`
(D10 tamtego planu). **Warunek wejścia:** próba na komputerze prelegenta — dwa monitory, fokus.
Do tego czasu nic w seminarium od tego projektu nie zależy (R8 tamtego planu).

## Faza 9 — manimgx (warunkowa)

Wchodzi, gdy manimgx dostanie udokumentowany tryb interaktywny (warunek z D12).

## Faza 10 — player ImGui: jeden kod na PC i w przeglądarce (kontrakt)

**Stan 2026-10-23:** bramki i zadania 3–10 etapu 10a wykonane, player eksperymentalny;
zadanie 11 (pomiar z vsync przy odblokowanym ekranie i odbiór człowieka) pozostaje otwarte.
Pierwsza próba prelegenta na Demo dała decyzje D45–D47 i etap 10d poniżej.
Dowody wcześniejszego przeglądu: ostatnia sekcja `reports/REPORT-10a.md`.

**Powód i cel.** Qt QGraphicsVideoItem zawiesza UI przy bazie i 2–3 klipach 1080p60
z Info (`reports/REPORT-f5-crit8.md`). ImGui ma dać parytet PC z uzgodnionym wyjątkiem
audio (D44), wspólny kod UI/logiki z webem i brak zawieszeń. PoC `experiments/f5i_imgui/`
jest punktem wyjścia, nie dowodem parytetu ani zaliczeniem kryteriów w oknie.
Qt pozostaje domyślny, nie usuwamy go. JSON v4, render, SceneView, EntryHistory,
LiveSession, protokół transportu i workery Manima pozostają źródłem istniejącej semantyki.
Nie forkujemy ani nie łatamy Manima; jeden wątek aplikacji na proces.

**Decyzje:** D42–D48 w SPEC; D45–D48 mają pierwszeństwo nad starszym opisem 10a
w zakresie granic cue, Info i gestów. Kolejność: 10a → 10d → 10b → 10c.
Wykonawca całej F10: **codex**, zadaniami po kolei,
także kontroler live i odbiór techniczny przypisane w recenzji Claude'owi.
Claude przegląda po każdym etapie, wykonuje próby człowieka i pomiar przy odblokowanym ekranie.
Bez commita/stash/reset/checkout i bez zmian .venv w tej sesji.
Rozstrzygnięcia wszystkich 23 punktów rundy 21 zapisano w REVIEW-LOG.

### Architektura i protokół źródła

Wspólne moduły `player/manifest.py`, `clock.py`, `controller.py`, `geometry.py`,
`state.py`, `stage.py`, `input.py`, `info.py`, `keys.py` nie importują Qt, PyAV,
multiprocessing, modelu Pydantic/rtoml ani platformowych adapterów, także tranzytywnie.
Import imgui_bundle jest dozwolony dla UI; czysta logika nie wymaga kontekstu.
Adapter PC waliduje model v4 i przekazuje manifest JSON: version=1, resolution,
presentations/slides (file/rev_file, kind, duration, rate/reverse_rate, loop/auto_next,
notes, layers, rect/motion, alpha/border, thumbnail, live descriptor).
Ścieżki PC mapowane na dozwolone URL przy eksporcie web; żadnych klas modelu w danych.
Walidacja manifestu odrzuca nieznaną wersję, niepoprawne rozmiary i nieskończone czasy/rate.
API wspólne przyjmuje zwykłe dict/list/liczby/teksty; nie importuje CLI.

`Source.prepare(entry_id: int, media: dict) -> None` rozpoczyna nieblokujące przygotowanie;
`poll(now: float, target: float | None, budget_ms: float) -> SourceUpdate` zwraca
status preparing/ready/eof/error, generation/entry_id, frame_id, PTS, duration,
owned RGBA8 top-left/stride=4*width lub uchwyt trwałej tekstury, boundary/request_id i błąd.
`play(anchor: float) -> None`, `pause() -> None`, `reset(entry_id: int) -> None`,
`request_close() -> None`, `poll_closed(now: float) -> bool` są nieblokujące dla UI.
SourceUpdate nie zawiera obiektów av/Qt. Gotowość wymaga dostępnej pierwszej klatki,
nie tylko otwartego pliku. EOF pozostawia ostatni dobry obraz; błąd pokazuje placeholder
lub zachowaną klatkę z błędem i usuwa źródło z bariery. Reset unieważnia stare wyniki.
Podgląd ma własne źródła; bieżący obraz w Info współdzieli zasoby kompozycji głównej.

**Zegary i przeciążenie.** PC używa wewnętrznego monotonicznego czasu mediów grupy
z kotwicą startu, pauzą i iloczynem rate CLI/slajdu; CFR cel=floor(t*fps*rate).
Jest to jawny wyjątek D43 od zakazu zegara D17, bez publicznego seek/frame-lock i bez
synchronizacji czasu live. Ruch D30 ma osobny aktywny czas, zatrzymany po końcu bazy
i w pauzie; Info ma czas rzeczywisty i elapsed od startu aplikacji, niezależny od pauzy.
Reverse czyta rev_file do przodu, klipy pozostają na końcowym obrazie/rect_at(duration).
Renderowane CFR są gwarantowane; inne wideo według znormalizowanego PTS (pierwszy PTS=0),
brak wiarygodnego PTS/czasu albo niemonotoniczne PTS daje czytelny błąd przed startem.
GIF: czasy poszczególnych klatek, disposal przez Pillow, minimum 10 ms dla zerowego czasu,
limit 256 MiB rozkodowanych RGBA na źródło; przekroczenie to błąd, nie nieograniczony preload.

UI najpierw poll live, przyjęcie granic i ACK, potem wejście/deadline, następnie media round-robin.
Budżet mediów UI łącznie 4 ms/tick, max 1 ms/źródło; preview ma niższy priorytet.
Nie wykonujemy blokujących decode/seek w UI: PC izoluje PyAV w nadzorowanych procesach
(jeden wątek aplikacji w każdym, wewnętrzne wątki FFmpeg dozwolone), z ograniczonym mailboxem
2 klatek/źródło i bez narastającej kolejki. Adapter czyta najnowszą gotową klatkę, odrzuca starsze.
Proces dekoduje max 4 klatki/tick; przy zaległości >250 ms przeskakuje do klatki kluczowej
i publikuje najbliższą dostępną PTS, bez nadrabiania w UI. Do tego czasu zostaje ostatni obraz.
Brak postępu przez 2 s oznacza error i asynchroniczne zakończenie procesu, bez blokującego join;
przygotowanie ma wspólny deadline 5 s. Pomiar oddziela decode, konwersję, upload i seek pętli.
Zegar nie czeka na spóźnione wideo, a licznik odrzuconych klatek ujawnia degradację.
Twardego czasu reakcji nie dowodzi sam budżet Pythona; odbiór wymaga testu zawieszonego procesu.

### Bariera 5g, ACK i zamykanie

Każde initial/next/previous/V/R/auto_next/skip_all dostaje nowe ID wejścia; reverse_to_normal
zachowuje wejście live. Zachowujemy D39–D41, rezerwację, historię i izolację generacji/socketu.
Kolejność: pierwsze obrazy plików → checkpoint/restore → status operacji i wskazana skorelowana
klatka graniczna (generacja, wejście, request_id, frame_id) → trwały zasób kompozycji → ACK →
gotowa grupa → rzeczywisty wspólny start mediów i enter/release. Sam READY nie zwalnia bariery.
Pauza pozwala przygotować checkpoint i obraz, ale nie wystartować mediów/cue.
Deadline całej bariery 5 s, ACK 2 s; nowa nawigacja anuluje stare wejście, nie przedłuża jego terminu.
Timeout odcina niepewny worker, pokazuje trwałą degradację, baza/klipy mogą kontynuować.

**Dokładny ACK:** `try_read_frame(acknowledge=False)` kopiuje obraz; aktualna granica jest
potwierdzana `frame_seen <frame_id>` dopiero po udanym uploadzie do trwałej tekstury i przypisaniu
jej do snapshotu kompozycji bieżącego wejścia. Zasób jest przypięty do końca wykonania draw data
obu viewportów tej iteracji i nie może być nadpisany przez następny update przed tym użyciem.
Nie trzeba czekać na swap ani fizyczne wyświetlenie. Granice anulowane odbieramy i ACK bez
uploadu/kompozycji. Błąd uploadu aktualnej granicy nie daje gotowości; odcinamy źródło i raportujemy.
Test sprawdza kolejność copy/upload/assign/ACK/start/enter oraz brak ACK przed trwałym zasobem.
Shutdown: najpierw request_stop/begin_shutdown i poll procesu, potem zwolnienie tekstur w bieżącym
kontekście GL, na końcu zniszczenie viewportów i kontekstu; brak blokujących join w callbacku.

### Tabela przejść nawigacji (test każdej pozycji)

Stan zawiera preparing, requested_playing, paused, running/ended, reverse, loop_exit_requested,
termination_achieved, entry_id i indeks prezentacji/slajdu. Każdy efekt nosi entry_id.

| Stan × akcja | Wynik i efekty |
|---|---|
| preparing, next, start niezamówiony | requested_playing=True, nadal czekaj na całą barierę |
| preparing, next, start zamówiony | anuluj wejście i przygotuj następny cel |
| preparing, replay | ignoruj, zachowaj przygotowanie |
| preparing, pause | przełącz requested_playing, checkpoint może się przygotować |
| paused bez termination_achieved, next | wznów grupę, bez zmiany indeksu |
| static running, next | następny slajd; static paused, next: wznów grupę |
| running loop + next_terminates_loop, next | zamów koniec bieżącej iteracji, bez skoku teraz |
| zamówiona pętla, granica iteracji | zatrzymaj na ostatniej klatce, zatrzymaj klipy/ruch; auto_next przechodzi dalej |
| running/ended bez powyższych, next | kolejny slajd; reverse: normalny plik tego samego indeksu, bez nowego wejścia live |
| dowolny, previous | normalny kierunek, poprzedni slajd/deck i bariera D39; na początku komunikat i brak zmiany |
| dowolny, reverse | poprzedni slajd/deck w reverse i bariera D39; na początku brak zmiany |
| gotowy, replay | reset czasu/flag pętli, bariera restore początku + cue celu zgodnie D39, zachowaj kierunek |
| running/paused, pause | wspólna pauza/wznowienie plików i ruchu; live działa dalej; ended nie wznawia zakończonej bazy |
| EOF bazy | zatrzymaj klipy/ruch, zachowaj obrazy, live nie zatrzymuj; auto_next ładuje następny cel |
| skip_all, dowolna pętla | jedno odtworzenie, EOF → next; wymuś exit_after_last_slide |
| next na końcu | zamknij oba okna gdy exit_after_last_slide, inaczej komunikat bez zmiany |
| start_at / zmiana decku | normalizuj ujemne indeksy, zero różne od None; nowa rozdzielczość, wyczyść stary preview |
| quit / zamknięcie okna | wspólny dwufazowy shutdown obu okien i wszystkich źródeł |

### Obraz, wejście, Info i macierz CLI

Geometria rozróżnia kadr decku, kontener warstwy w ułamkach kadru, obraz w kontenerze
i logiczne współrzędne viewportu (DPI dopiero przy renderze). Warstwy przycinamy do kadru;
hit-test wybiera najwyższy kontener, także przezroczyste marginesy blokujące klik.
Bufor live zawiera już pasy D34: bez ponownego dopasowania proporcji sceny.
Zewnętrzne tło playera jest osobne od background_rgba kamery. Alfa prosta, opacity mnoży alfę
koloru, również dla zachowanej klatki i miniatur. BorderStyle.width skaluje się z kadrem,
jest ograniczone wymiarem kontenera i rysowane do wewnątrz; None ukrywa tylko styl, nie fokus.
Rola aktywna wygrywa z błędem, po release pierwszy błąd. Brak dobrej klatki: placeholder.

Router: zamknięcie/utrata aktywności aplikacji → edycja tekstu/Markdown → rezerwacja live →
aktywne cue next/back (repeat konsumowany bez wysłania) → pozostałe akcje Config.keys → gesty.
Nie przejmujemy strzałek do domyślnej nawigacji widgetów. Esc/klik poza live zwalnia fokus;
przejście do Info nie zwalnia go (agregacja aktywności wszystkich okien). Klik marginesu
najwyższej warstwy blokuje niższe; Shift-drag/wheel/double-click to D28, ruch normalizowany
przez kontener, nie okno ani wewnętrzną scenę. Rezerwacja blokuje cue/view; CE view pozostaje no-op.
TOML nadal zapisuje kody Qt; keys.py jest jedyną tabelą mapowania, rozszerzoną o Plus/Asterisk
z modyfikatorami i numpadem. Błąd: akcja, kod dziesiętny, hex i nazwa tylko jeśli znana.

Info i S czytają jeden snapshot: scena/slajd, kierunek, pętla/wyjście, przygotowanie/zamówiony
start/koniec, fokus, klipy, operacja historii, początek/pozostawiony stan, niewysłane/przerwane/
nieznany wynik i trwała degradacja ponad READY. Komunikat 2 s ma rewizję, stary timer nie kasuje nowego.
Info: Markdown, czas lokalny/elapsed, identyczna bieżąca kompozycja; podgląd normalny, wyciszony,
niezależne pętle/rate, miniatury live, bez bariery i pauzy głównej, bez dekoderów gdy ukryte.
Ruch podglądu pozostaje w 10a: osobny aktywny czas każdego plikowego źródła preview, reset przy
jego pętli/zmianie celu, rect_at(czas źródła); miniatura live rect_at(0). **Do potwierdzenia**,
zachowawczo izolowany od zegara/barier głównego slajdu; D35 zmienione tylko w zakresie ruchu preview.

| Opcje/akcje objęte parytetem | Test odbioru (planowany, nie dowód wykonania) |
|---|---|
| scenes, brak scen/wybór, powtórzona scena, folder/config/verbosity, -h/--help | test_imgui_cli.py::test_selection_and_common_options |
| --player imgui/qt, domyślnie qt | test_imgui_cli.py::test_backend_default |
| --start-paused, -s/--skip-all, --exit-after-last-slide | test_imgui_cli.py::test_playback_flags |
| -F/--full-screen/--fullscreen, -H/--hide-mouse | test_imgui_cli.py::test_aliases |
| --aspect-ratio keep/ignore, --playback-rate | test_imgui_cli.py::test_geometry_and_rate |
| --sa/--start-at, --sacn/--start-at-scene-number, --sasn/--start-at-slide-number | test_imgui_cli.py::test_start_indices (zero/ujemne/priorytet/błędy) |
| -S/--screen, --info-window-screen, --hide-info-window/--show-info-window | test_imgui_cli.py::test_screens (1/2 monitory, błędny indeks, ostrzeżenia) |
| --next-terminates-loop | test_imgui_navigation.py::test_loop_exit |
| QUIT, PLAY_PAUSE, NEXT, PREVIOUS, REVERSE, REPLAY, FULL_SCREEN, HIDE_MOUSE, PRESENTER_STATE | test_player_keys.py oraz test_imgui_input.py::test_actions parametrized po 9 akcjach |

Windows: jawne GLFW + OpenGL3; Info osobny natywny viewport od startu, uchwyt identyfikowany
przez ImGui platform IO/viewport (platform_handle), nigdy zgadywany po kolejności okien.
GLFW per-window ustawia pozycję, rozmiar i dekoracje; fullscreen bez ramek na geometrii monitora,
nie wyłączny (**do potwierdzenia**). F przełącza oba okna i odtwarza osobne geometrie;
H jak Qt tylko okno główne. Upload po post_init w aktywnym współdzielonym kontekście, usuwanie
przed jego zniszczeniem. Vsync włączony, realne swapy mierzone osobno, utrata fokusu nie minimalizuje Info.

### Etapy 10a — zamknięte pliki, porty i odbiór

Wszystkie poniższe nazwy nowych testów są wymaganiami, nie istniejącymi zielonymi wynikami.
`p/` oznacza `src/manimcue/player/`, `t/` oznacza `tests/`, `e/` oznacza `experiments/f10a_gate/`.
Plik raz utworzony można zmieniać tylko w zadaniu wymieniającym go; zmiana semantyki wymaga
powrotu do kontraktu i przeglądu Claude. Zadanie 1 musi być zielone przed 2, oba przed portem.
Po każdym zadaniu uruchomić jego testy, zapisać wyniki i przekazać do przeglądu Claude.

| Zadanie / budżet (stop 2×) | Zamknięta lista plików | Sygnatury wejścia → wyjścia | Testy odbioru |
|---|---|---|---|
| 0. Kontrakt / 3 h | PLAN.md, SPEC.md, REVIEW-LOG.md, reports/REPORT-10a.md, REPORT-10a.md, CLAUDE.md (tylko punkt 2), README.md, docs/api.md | recenzja + player Qt → kontrakt i 23 decyzje | komplet punktów recenzji, D42–44, macierze i bramki |
| 1. Bramka Windows / 4 h | e/windows.py, t/test_imgui_windows_gate.py, pyproject.toml, uv.lock, reports/REPORT-10a.md | run_gate(main_monitor:int, info_monitor:int, output:Path)->int; JSON monitors/windows/backend/swaps | test_two_native_windows, test_fullscreen_roundtrip, test_cursor_and_backend (gpu), programowa lista monitorów/pozycje/rozmiary/tryb; Claude: DPI/fokus/wygląd |
| 2. Bramka wspólnego kodu / 3 h | p/__init__.py, p/manifest.py, p/clock.py, p/controller.py, p/geometry.py, p/state.py, e/imports.py, e/pyodide.html, t/test_imgui_shared_imports.py, t/test_imgui_shared_logic.py, reports/REPORT-10a.md | validate_manifest(data:dict)->dict; run_shared_cases()->dict; run_import_gate(channel='msedge')->dict | subprocess PC i Pyodide headless Edge przez uv run --with playwright, bez Qt/PyAV/multiprocessing; te same named cases |
| 3. Klawisze/config / 3 h | p/keys.py, p/input.py, src/manimcue/slides/config.py, t/test_player_keys.py, t/test_imgui_input.py | bindings(config:dict)->dict; route(event:dict,state:dict)->list[dict] | domyślne/własne/nieznane, Plus/Asterisk, modyfikatory/repeat, Config() bez Qt; regresja liczbowego TOML |
| 4. Nawigacja / 6 h | p/controller.py, p/clock.py, p/state.py, t/test_imgui_navigation.py, t/test_imgui_shared_logic.py | reduce(state:dict,event:dict,now:float)->tuple[dict,list[dict]]; snapshot(state:dict)->dict | każda pozycja tabeli, sztuczny zegar, stare entry_id, 5c i rewizje komunikatów |
| 5. Źródła PC / 7 h | p/sources_av.py, p/decoder_worker.py, t/test_imgui_sources.py | protokół Source powyżej; run_decoder(spec:dict,connection)->None | identyfikowalne CFR/GIF/obraz/PTS, reset/pętla/EOF/błędy, zawieszony dekoder, bounded mailbox i UI poll |
| 6. Kompozycja / 5 h | p/stage.py, p/geometry.py, p/textures.py, t/test_imgui_composition.py | compose(manifest:dict,frames:dict,now:float)->list[dict]; draw(commands:list,draw_list)->None; upload(frame)->TextureLease | draw list: kontekst/display/delta/ini off, renderer_has_textures + set_tex_id/set_status; UV/indices/vertices/clip rect, nie liczba scalanych komend; render pikselowy gpu |
| 7. Live / 9 h | p/live.py, t/test_imgui_live.py, t/test_imgui_live_checkpoint.py | LiveController.poll(now:float)->list[dict]; enter(entry:dict)->None; accept_frame(frame,lease)->None; begin_shutdown()->None | port scenariuszy test_live_layers/persistent_live/live_ce_player/live_checkpoint, D39–41, stale granice, timeout, pauza/rezerwacja, ACK i dwufazowy shutdown |
| 8. Wejście live / 3 h | p/input.py, p/live.py, t/test_imgui_input.py | route(event,state)->list[dict]; view(event:dict,container:tuple)->dict | D20/D28, oba okna, klik marginesu, Shift-drag/wheel/double-click, repeat i rezerwacja, CE no-op |
| 9. Info / 5 h | p/info.py, p/state.py, p/stage.py, p/app.py, t/test_imgui_info.py | render_info(snapshot:dict,preview:dict)->None; preview_target(manifest:dict,index:tuple)->Optional[dict] | port test_presenter_state, test_preview_alpha_border i 5d; brak preview decoder gdy ukryte, zmiana rozdzielczości decku, niezależny ruch |
| 10. CLI / 4 h | p/desktop.py, p/app.py, p/manifest.py, src/manimcue/slides/present/__init__.py, t/test_imgui_cli.py, README.md, docs/api.md | run_desktop(manifest:dict,options:dict)->int; model_to_manifest(configs:list)->dict | cała macierz CLI, Qt domyślny bez regresji, ostrzeżenie audio raz/materiał |
| 11. Odbiór / 8 h | e/measure.py, t/test_imgui_acceptance.py, reports/REPORT-10a.md, REPORT-10a.md, PLAN.md, CLAUDE.md (tylko punkt 2), README.md, docs/api.md | measure(options:dict)->dict; watchdog(command:list,timeout:float)->dict | pełny pytest, okna gpu, dwa monitory, GL/CE, pomiar/stabilność i próba Claude |

Budżet bazowy 10a **60 h** (suma tabeli), stop przy **120 h** całości lub 2× zadania;
estymacja ryzyka implementacji/przeglądów/prób 50–80 h, reestymacja po bramkach, bez automatycznego
podnoszenia limitu. Raport oddziela czas pracy codex, przeglądu Claude i czekania na człowieka.
Niepowodzenie/brak dowodu bramki oznacza STOP, nie skip zaliczający i nie obejście.

### Kryteria odbioru 10a

1. Obie bramki zaliczone dowodem z PC i Pyodide, testy zadania przed kolejnym zadaniem zielone.
2. Pełna tabela nawigacji i macierz CLI/9 akcji, bez regresji Qt; D31/D39–41 z gotowym obrazem,
   ACK i timeoutami również dla ciepłego live, replay/reverse i anulowania.
3. Kompozycja D30/D34/D35: geometria/UV/clip rect ±0,5 logicznego px; kontrolowane zrzuty demo
   1–11 względem Qt, maska krawędzi 1 fizycznego px, poza nią ≥99% pikseli z błędem kanału ≤3/255;
   obwódki/geometria ±1 px fizyczny. Zrzuty po ustalonym PTS, osobno alfa i pasy.
4. Pełne scenariusze live GL/CE i 5g, brak zagłodzenia poll/ACK podczas zastoju dekodera;
   degradacja trwała i widoczna, brak czarnej klatki, shutdown zwalnia procesy/tekstury.
5. Info/Markdown/czas/bieżący obraz/podgląd z niezależnym ruchem i poprawnym ukryciem oraz fokus D20/D28.
6. Pomiar przy odblokowanym ekranie, dwa monitory, vsync, sprzęt i Hz zapisane; N=1..3,
   Info widoczne, live GL i CE osobno, 5 s rozgrzewki + 60 s próby, 3 powtórzenia.
   Dla każdego strumienia osobno mediana liczby nowych obrazów w 1 s ≥55 fps (materiały 60 fps),
   p95 odstępu ≤34 ms, max ciszy ≤250 ms, p95 wejście→zmiana ≤100 ms (min. 30 akcji).
   Liczniki drop/decode/upload z tych samych okien; CPU raportowane, hwaccel poza zakresem.
   Zewnętrzny watchdog: brak heartbeat UI >2 s przerywa próbę i oznacza porażkę;
   dodatkowo 30 min stabilności i ≥100 przejść slajd/pętla, przełączanie aplikacji, live GL/CE.
7. Pełne `uv run --frozen pytest -q -p no:cacheprovider` zielone; testy prawdziwych okien oznaczone gpu.
8. Próba człowieka: DPI, wygląd, fokus/Info, dwa monitory, F/H, klik/Esc, gesty i ←/V/R z live.
   Automatyczna geometria okien nie zastępuje tej próby; PoC nie zalicza wydajności finalnego playera.

### 10d — poprawki po próbie prelegenta

**Kontrakt, bez implementacji w tej sesji.** Decyzje prelegenta z 2026-10-23 są wiążące.
Rozszerzenie D48 zmienia wyłącznie PLAN.md, SPEC.md i dziennik REVIEW-LOG.md.
Tabela wyznacza pliki przyszłego wykonania;
nie upoważnia do ingerencji w równoległe poprawki Claude. Wykonawca **codex**,
przegląd **Claude** po każdym zadaniu, następnie próba **człowieka**; bez commita.
Skróty `p/`, `t/`, `e/` jak w 10a; `m/` oznacza `src/manimcue/`.

**Stan poprawek Claude (poza projektowaniem 10d):** wyłączenie okna cienia workera
`pyglet.options["shadow_window"]=False`; zachowanie ostatniej kompozycji poprzedniego
slajdu do gotowości nowego wejścia; pula 4 **bezczynnych** ciepłych procesów (start
~350 → ~70 ms), uzupełniana po pobraniu; każdy obsługuje jedno źródło do końca życia.
Dekoder publikuje `show_at` z wyprzedzeniem pół klatki (slot 32 B, HEADER 96); UI wybiera
najnowszą klatkę po show_at zgodnie z D43 `floor(t·fps·rate)`, pomijając zapis w toku.
Tekstura plików aktualizowana przez ponowne `glTexImage2D` tego samego obiektu
(`SubImage` dawało p95 14 ms stall); snapshot bez kopii manifestu;
`PyOpenGL.ERROR_CHECKING` wyłączone, jawne `glGetError` po uploadzie; merge Inconsolata
ze strzałkami w Markdown. To stan prac przekazany przez prelegenta, nie zaliczenie odbioru.
**Otwarte osobno:** parytet prefetcha Qt (pula LiveSession wspólna już w D48),
prefetch reverse/skoków i między deckami oraz dobór parametrów poza sprzętem odbioru.
Start live i prefetch normalnego N+1 w ImGui wchodzą teraz do 10d jako D48.

**D45 — źródło prawdy i routing.** Dziś `advance()` wysyła nieskorelowane `SEQUENCE_END`,
a odmowa `step_back()` tylko loguje „Jestes na poczatku sekwencji; nie ma czego cofac”.
`EntryHistory.cue_state` śledzi enter cue (`prepared/sent/started/completed/...`),
nie cursor SEQUENCE ani undo_stack. Nie parsować logu i nie wnioskować z tej historii.
Rozszerzyć wspólny transport GL/CE o opt-in komendę `step <request_id> next|back`
i odpowiedź `STEP_RESULT <request_id> <done|start|end|error> <frame_id>` oraz
`STEP_STATUS <request_id> <waiting|running|looping>` z tą samą korelacją co wynik.
Waiting przy przyjęciu do FIFO, running przy rozpoczęciu wykonania i po domknięciu
pętli, looping podczas powtarzania. Worker wysyła running/looping co ≤1 s tylko przy
potwierdzonym postępie wykonania cue/pętli (także wait), oraz waiting dla kroku
czekającego na tego poprzednika; sam żywy transport nie potwierdza postępu.
Nieskorelowany CUE_DONE nie steruje deadline’ami.
ID monotoniczne w obrębie socketu; player wiąże oczekiwanie z session/generation/entry_id
i aktywną warstwą. Stare `next/back` i statusy pozostają kompatybilne dla Qt.
Worker sprawdza granicę przy wykonaniu w FIFO: end gdy cursor >= len(SEQUENCE),
start gdy cursor == 0 **lub** undo_stack pusty (również po presetach/restore).
Pusta sekwencja ma obie granice. `done` dopiero po wykonaniu kroku i publikacji granicy;
`start/end` bez mutacji publikuje także granicę, z jej frame_id. BOUNDARY/ACK według D41;
nie mylić granicy sekwencji z klatką graniczną. Błąd nie uruchamia nawigacji.

Jedno fizyczne NEXT/PREVIOUS: blokada repeat aż do key-up, także po oddaniu fokusu.
Przy rezerwacji wejścia albo przygotowaniu: konsumuj bez kolejki. Przy cue w locie zachowaj
D9/D10: pojedynczy nowy krok FIFO może przerwać/domknąć cue, lecz nigdy nie przeskakuje
na podstawie kursora wyprzedzającego animację. Osobno krok wykonywany i najwyżej jeden
oczekujący `step` FIFO: drugi fizyczny press po key-up musi dotrzeć do workera,
aby domknąć/przerwać pierwszy krok z LOOPS według D9/D10. Pełne FIFO konsumuje
kolejny press bez wysyłki; oczekujący krok zaczyna wykonanie po poprzednim.
Po aktualnym `start/end`, skomponowaniu i ACK wskazanej klatki zwolnij fokus i wywołaj
**raz** zwykły reducer previous/next. Obowiązują jego pauza, pętla, koniec decku i exit;
„następny slajd” to zwykła semantyka next, bez obejścia tych reguł. Przyjęcie/status
w 5 s od wysłania; waiting ma 5 s od statusu, odnawiane tylko przy potwierdzonym postępie
poprzednika. Running i looping mają watchdog 5 s braku postępu, bez limitu długości cue
ani powtarzania. Od żądania przerwania/domknięcia obowiązuje nieodnawialny deadline
5 s na wynik, także przy dalszych heartbeat; ACK 2 s. Timeout zatrzymuje niepewną sesję według D41
i utrwala degradację, bez skoku.
Zmiana wejścia/fokusu unieważnia oczekiwanie; późny wynik nie nawiguje.
Klik nadal aktywuje, hover nie. Granica dotyczy całej sekwencji workera, nie slajdu ani
checkpointu. Przy trwałym live zachować sesję i before(N), barierę, enter_cue i gałęzie
D39–D41; oddanie fokusu nie czyści historii. V/reverse i R pozostają akcjami playera,
nie testują granic cue; V odtwarza checkpoint, nie odwraca live. W reverse zwykły next
może najpierw wrócić do normalnego pliku tego samego indeksu (tabela 10a).
**Qt: jawny wyjątek D45**, zachowuje przechwycenie strzałek także na granicy.
Rekomendacja: wyjątek teraz; późniejszy parytet szacowany 3 h, stop 6 h, osobny kontrakt
routera Qt i testów. D47 ma parytet obu playerów już w 10d.

**D46 — Info i zasoby.** Dwie kolumny, orientacyjnie 60/40 szerokości dostępnej ponad
paskiem miniatur: lewa duża bieżąca kompozycja z tego samego snapshotu/tekstur co scena,
nad nią zegar lokalny, elapsed, pauza/wznowienie i restart **czasu prelegenta**.
Timer monotoniczny startuje z aplikacją; restart zeruje i zachowuje stan pauzy;
pauza timera nie pauzuje mediów ani live. Prawa: normalny następny slajd, pod nim
przewijane notatki. Dotychczasowy niezależny ruch preview zostaje. Notatki domyślnie
24 logiczne px, A+/A− krok 2 px, zakres 16–48; tylko notatki i ich matematyka,
bez zmiany reszty UI. Ustawienie sesji, wspólne dla slajdów, uwzględnia DPI.
Stan/degradacja nadal widoczne i zgodne z S. Brak następnego celu ma czytelny pusty podgląd.

Na dole przewijany poziomo pasek **wszystkich slajdów bieżącego decku**, indeks i zaznaczenie
bieżącego. Klik wysyła `start_at` z jawnym indeksem decku/slajdu, nie symuluje serii next.
Nowe entry_id anuluje stare przygotowanie; ta sama bariera/ACK/deadline co nawigacja.
Klik bieżącego slajdu jest no-op w `p/controller.py` po normalizacji indeksu, przed
`_enter()`: bez zmiany entry_id, pauzy, reverse, przygotowania i bez efektów.
Skok niesąsiedni nie rekonstruuje historii live:
zimna sesja, bez enter_cue jak initial; sąsiedni start_at zachowuje zgodną sesję,
ale ustanawia nowy lokalny początek bez odgrywania cue i bez deklaracji ciągłości historii.
`p/live.py` i `m/live_entry.py` odcinają stos EntryHistory, stare oczekiwania
i checkpointy (także restore w locie); nowy checkpoint ma has_predecessor=False.
Zachowany socket nie resetuje generacji ani monotonicznych liczników; nowe entry_id
odrzuca późne statusy/wyniki/ACK. Previous/V/R korzystają wyłącznie z nowej historii.
Nie rozszerzać D39 o odtwarzanie całej drogi do celu. Kontrolki Info konsumują klik
i nie nadają fokusu live; klawiatura w obu oknach nadal przechodzi przez router.

Miniatura to statyczna kompozycja w t=0: dostępne `thumbnail`, inaczej pierwsza klatka
normalnego pliku; live wyłącznie zapisany thumbnail, nigdy nowy worker. Bez obrazu:
placeholder z numerem, nawigacja dostępna. Zachować rect_at(0), alfa, border i proporcje.
Ładować widoczne pozycje plus po jednej obok, najwyżej jedno zadanie ekstrakcji naraz,
niższy priorytet niż scena/live/preview. Limit miniatur: jeden proces ekstrakcji,
niezależnie od dekoderów sceny i obowiązkowego ruchomego preview; bez globalnego limitu 4.
Pula 4 to zapas bezczynnych ciepłych procesów, uzupełniany po pobraniu; każdy obsługuje
jedno źródło do końca życia. Liczyć osobno aktywne scena/preview/miniatura, bezczynne
(≤4) i kończące się (od stop do potwierdzonego exit) oraz sumę żywych. Nowa ekstrakcja
dopiero po exit poprzedniej, także anulowanej; kończące się nadal wliczać do limitu
miniatur i sumy żywych. Maks. 256×144 RGBA/miniaturę; LRU 64 obrazy i 16 MiB łącznie CPU+GPU
(wliczyć kopie robocze, zwalniać tekstury w kontekście). Przy 20 obrazach to ok. 5,6 MiB
CPU+GPU; metadane O(N), dekodowanie tylko potrzebnych, nie N procesów. Ukryte Info
nie uruchamia ekstrakcji ani dekoderów preview; zmiana decku anuluje stare wyniki.

Markdown zachowany; matematyka `$...$` i `$$...$$`, bez wykonywania TeX, plików i makr
systemowych. PC: najpierw natywny MicroTeX (`AddOnsParams.with_latex` oraz
`MarkdownOptions.with_latex`), fonty lokalne. Offline w .venv: imgui-bundle 1.93.0,
`has_latex()` False przed inicjalizacją, True po init MicroTeX i Markdown; raster
`\\frac{1}{2}+x^2` uzyskany bez okna. Upload i skład inline pozostają do odbioru GPU.
Wheel ma latinmodern-math.clm1/.otf (889927 B razem), matplotlib **3.11.2**.
Fallback PC przy niedostępnym MicroTeX: mathtext/Agg w adapterze PC, inline z baseline
i display jako blok; import matplotlib wyłącznie tam, raster do tekstury, bez subprocessu
TeX. Obsługiwany podzbiór mathtext; błąd wzoru pokazuje źródło i komunikat, nie crash.
Cache kluczowany wzorem/stylem/rozmiarem/DPI/kolorem, LRU maks. 128 wzorów i 16 MiB
CPU+GPU, maks. 4096 znaków i 2048×2048 px/wzór; bez rasteryzacji co klatkę.
Roboto pozostaje bazą Markdown; `MarkdownOptions.font_options.merge_fonts` z Inconsolata
uzupełnia ←→, również po A+/A− i zmianie DPI; bez globalnej zamiany fontu.

D42: układ, timer, A+/A−, pasek i routing wspólne; adaptery dają obrazy/tekstury.
Lokalny `_pyodide_latex_fonts.py` i `pyodide_patch_runners.py` potwierdzają ścieżkę MicroTeX
w Pyodide: slim wheel pomija fonty i pobiera je przy with_latex. **Nie jest to test
przypiętego wheelu wasm**: brak lokalnego runtime/wheelu do uruchomienia offline.
Bramka 10b musi potwierdzić has_latex po init i inline/display; fonty z licencją
muszą być w eksporcie offline, bez wymaganego CDN. Wspólny kod nie importuje matplotlib;
fallback web: przygotowane na PC rastry wzorów wraz z metrykami, nieznany wzór jako źródło
z komunikatem. Miniatury web eksportowane na PC, lazy img/tekstury bez N video/dekoderów.

**D47 — wejście kamery.** MMB orbit, Shift+MMB pan, wheel zoom; równolegle skróty touchpada
Alt+LMB orbit, Alt+Shift+LMB pan, Alt+RMB zoom; bez przełącznika trybu w tej fazie.
Zwykły LMB-drag nie porusza kamerą; dwuklik LMB reset. Gest wymaga istniejącego fokusu
z kliknięcia i początku nad aktywnym kontenerem; samo wheel/hover go nie nadaje.
Pierwszy klik może nadać fokus, lecz nie generuje delty. Capture do release, anulowanie
przy utracie aktywności/fokusu, zmianie wejścia albo rezerwacji; po anulowaniu nowy press.
Pan ma pierwszeństwo nad orbit; niejednoznaczne wieloprzyciskowe kombinacje ignorować.
Δx/width, Δy/height kontenera w jednostkach logicznych, y w dół, bez mnożenia przez dt
(referencja Defect-Studio mnoży przez dt×60; nie kopiujemy zależności od fps).
Czułość orbit/pan ×1 jak D28, backend zachowuje FRAME_WIDTH/HEIGHT i pan_sensitivity;
wheel kroki ciągłe (Qt angleDelta.y/120, pixelDelta.y/40 gdy brak angleDelta), dodatnie
przybliża; touchpad zoom = −20×Δy/height kroków. Zoom workera nadal 0.9**steps.
Progi/znaki identyczne Qt/ImGui, DPI nie mnoży delty drugi raz; zerowy kontener daje no-op.
`view orbit|pan|zoom|reset` pozostaje poza cue; reset ostatniej granicy, kamera w historii,
rezerwacja blokuje view, CE Cairo nadal no-op (D38). Referencja ViewportInput.cpp tylko odczyt.

**D48 — najpierw pula, potem prefetch (decyzja 2026-10-23).** Pomiar Claude na Windows,
i7-13700KF: live GL 1,6–1,8 s, import manimlib ~1,4 s po wyłączeniu shadow_window,
spawn ~0,15 s, scena i pierwsza klatka ~0,2–0,3 s; import CE ~0,9 s.
Pliki z istniejącej puli: 83–130 ms. To dane wejściowe, nie odbiór implementacji D48.

Pula osobna dla `manimgl` i `ce-cairo`, docelowo **2 bezczynne workery na użyty silnik**.
Silniki zbiera adapter PC z manifestu bieżącego decku (Qt z tych samych pól modelu;
brak engine oznacza manimgl); bez importów backendów w procesie UI. Po zmianie decku
zamykać zapas nieużywanych silników. Rozgrzewanie asynchroniczne po załadowaniu decku,
uzupełnianie po pobraniu, maks. jeden start uzupełnienia naraz; priorytet wejścia nad zapasem.
Import zakończony potwierdza osobny `POOL_READY`, nie sceniczne READY.
`run_worker` dziś zeruje argv, wyłącza shadow_window i importuje GL przed importem pliku sceny;
`live_scene_ce` importuje manim już na poziomie modułu, a run_ce_worker ustawia tempconfig
dopiero dla spec. Ten porządek zachować w bootstrapie: argv/shadow_window przed importem,
bez importu pliku autora, sceny ani kontekstu GPU w bezczynnym workerze.

`LiveSession.start` dziś tworzy SharedMemory, ctx.Lock i Pipe i przekazuje je przy spawn.
W puli **Lock (SemLock) oraz oba kanały control/bootstrap tworzyć przed spawn**; nie wysyłać
Lock zwykłym Pipe po starcie. Rodzic zachowuje lock danego slotu; po take tworzy bufor
o rozmiarze spec i wysyła `(spec, shm_name)` po istniejącym control. SharedMemory otwierane
po nazwie, LiveSpec jako dane są przekazywalne później; bootstrap_sender pozostaje w dziecku.
Nie przesyłać sceny, FrameBuffer ani nowych prymitywów synchronizacji. Po przydziale worker
wywołuje dotychczasowy run_worker/run_ce_worker raz i nigdy nie wraca do puli: jedna scena
przez całe życie, bez podmiany globalnego stanu GL/config/cache shaderów. Dwie równoczesne
sesje trwałego live 5g nadal dozwolone; pula nie jest limitem aktywnych sesji.
Wspólny LiveSession daje pulę obu playerom; adaptery posiadają pulę i jawnie przekazują ją
do start. capture_first_frame bez puli zachowuje zimny start i dotychczasowy lifecycle.
Brak gotowego slotu: dotychczasowy zimny start w limicie zasobów, bez blokowania GUI;
brak wolnego slotu oznacza oczekiwanie do deadline D41, nigdy nadmiarowy spawn.
`take` zwraca worker albo None natychmiast. LiveSession.start oraz Source.prepare/start
tylko zgłaszają żądanie; stan waiting_slot ponawia admisję przez poll, który nadal odbiera
exit i zwalnia sloty. Bez blokującego sleep/join w GUI. Żądanie wiąże entry_id (prefetch
token); nowe wejście anuluje stare oczekiwanie przed startem. Deadline D41 od przyjętej
nawigacji obejmuje oczekiwanie, nie zaczyna się ponownie po zwolnieniu slotu.
Qt: właściciel decku w m/slides/present/player.py przekazuje konfigurację całego decku
do LiveLayerController, pompuje pulę także bez aktywnego live i obejmuje ją końcowym
shutdown; zmiana decku zamyka nieużywany zapas. Dotyczy także decku zaczynającego się plikiem.

Worker czekający sprawdza co ≤0,25 s EOF control i parent_process().is_alive(); wszystkie
zbędne końce Pipe zamknięte po spawn. Śmierć rodzica kończy czekanie w ≤1 s, bez spec/sceny.
Import ma deadline 5 s; awaria nie uruchamia nieskończonej pętli restartów (maks. jedna
ponowna próba na slot, potem komunikat i zimna ścieżka). Shutdown obu UI zamyka przydział
i uzupełnianie, wysyła stop/zamyka control; poll odbiera exit/join, po 2 s kill, potem reap.
Zasoby sesji sprząta dotychczasowy właściciel LiveSession dopiero po exit; brak SHM dla
bezczynnych. Nie polegać na daemon/atexit jako jedynym sprzątaniu.

**Prefetch wyłącznie ImGui PC**, bez zmian web/Qt poza wspólną pulą. Po gotowości N
przygotuj jeden normalny cel N+1 w tym samym decku, niezależnie od widoczności Info.
Token = rewizja manifestu/deck + źródłowe entry_id + indeks celu + pełne spec plików/live
(w tym rozmiar, silnik, fps, alfa/session_id). Żadnego przewidywania ←/V/R/start_at ani
przekroczenia decku. Zwykły next w reverse nie przejmuje prefetcha. Sąsiednie przejęcie D39
sprawdzać **przed** prefetchem każdej warstwy; zgodnego trwałego live nie budować drugi raz.
Zmiana spec unieważnia token. Przy częściowym trafieniu przejmować zgodne warstwy,
resztę przygotować zwyczajnie; nie utrzymywać dwóch właścicieli procesu/SHM/tekstury.

Pliki: osobne Source, pierwsza normalna klatka w t=0, potwierdzone hold w dekoderze,
bez postępu, EOF, pętli i watchdogów odtwarzania podczas hold. Po przejęciu przestawić
entry_id/generation i kotwicę show_at/zegara dopiero na wspólny start D31, zachować pauzę;
nie dekodować od początku drugi raz. Preview Info **nie przejmujemy**: ma osobne źródła,
pętle i ruch, może być w dowolnym t; live w nim nadal tylko thumbnail. Miniatury D46
też nie są prefetchem i nie uruchamiają live.

Live z puli buduje obiekty i pierwszą klatkę READY; potem brak cue/view i odtwarzania
updaterów do przyjęcia (odrzucać późniejsze klatki jałowe, nie przesuwać stanu sceny).
`LiveSpec.prefetch:bool=False` wybiera ten tryb. Po READY pętla transportu GL/CE nie
wywołuje update_mobjects/update_frame nawet z dt=0; nadal obsługuje stop, ACK i FIFO.
Techniczna granica READY prefetcha dostaje ACK w 2 s bez postępu sceny i zwolnienia
bariery D31. Późniejsza granica wejścia D41 ma nowy frame_id i osobny ACK po kompozycji.
Pierwsza właściwa rezerwacja/enter/release D41 kończy hold przed operacjami wejścia.
Dla live bez session_id, także bez cue, przyjęty next wysyła jawne adopt_prefetch
skorelowane session/generation/entry_id/request_id: granica wejścia → kompozycja/ACK
→ release na wspólnym starcie D31. Release kończy hold, zachowując pauzę do resume;
stare komendy/ACK ignorować. Bez enter_cue ani syntetycznej historii do obudzenia sceny.
Samo build_objects jest kodem autora i może mieć efekty I/O — prefetch tego nie izoluje.
Nie tworzy EntryHistory, before(N+1), entry_id wejścia ani rezerwacji, nie wysyła enter_cue.
Dopiero zatwierdzony normalny next (także efekt granicy D45) nadaje nowe entry_id,
przekazuje własność i uruchamia dotychczasowe przygotowanie D39–D41: rezerwacja,
before/cue właściwe dla zimnego next, granica, kompozycja, ACK i release. READY prefetcha
nie zwalnia bariery; nie ACK-ować granicy wejścia z wyprzedzeniem. Deadline D41 5 s
liczyć od rzeczywistego wejścia, ACK 2 s; prefetch ma własne 5 s do przygotowania
wraz z technicznym ACK. Potem deadline spekulacji wygasa: gotowy cel może czekać
dowolnie długo do przyjęcia/anulowania, bez timeoutu pierwszej granicy transportowej.

←/V/R, start_at (poza no-op bieżącego celu), inny cel, zmiana decku, błąd i timeout
anulują prefetch, unieważniają token i zamykają procesy; wyniki starego tokenu ignorować
i sprzątać, bez historii/degradacji aktywnej sesji. Nie ponawiać błędnego celu do zmiany
źródłowego wejścia. Nietrafienie nie zmienia semantyki wejścia ani checkpointów.
Pętla slajdu nie konsumuje prefetcha i nie resetuje go przy każdym obrocie; auto_next
i skip_all przejmują tylko gdy reducer faktycznie wybierze normalny N+1. Końcowy slajd,
wrap do początku/decku i exit_after_last_slide nie mają prefetcha; exit zamyka także pule.

**Budżet procesów D48 (doprecyzowuje D46, nie globalny limit 4).** Na deck wyliczyć
S = maks. liczba źródeł procesowych jednego slajdu (pliki + live), P = maks. liczba
plikowych źródeł preview, F = maks. liczba źródeł N+1 (F≤S), E = liczba użytych silników ≤2.
Twardy pułap żywych dzieci playera: **B = 2S + P + F + 1 + 4 + 2E**;
2S obejmuje bieżący i poprzedni/kończący slajd, 1 ekstrakcję miniatur, 4 zapas dekoderów,
2E zapas live. W każdej kategorii kończący proces zajmuje slot aż do exit; bez podwojenia
budżetu przy wielokrotnym anulowaniu. Przykład S=4, P=4, F=4, E=2: maks. 25 dzieci.
Importujące/uruchamiane procesy też zajmują slot zapasu. Przy zmianie decku obowiązuje
max(B starego, B nowego) do odebrania starych procesów, potem B nowego; bez sumowania pul.
Współdzielone liczniki/admisja PC obejmują również zimne starty; po anulowaniu czekać na
zwolnienie slotu, bez spawnu poza B. Priorytety: scena/restore 5g → ruchome preview Info
→ prefetch → miniatury → bezczynny zapas. Przy braku zwalniać od końca tej listy,
prefetch może być częściowy albo pominięty; wymagane wejście czeka najwyżej D41.
To rozszerzenie ponad brak globalnej admisji w rundzie 22, bez zmiany znaczenia puli 4.
Właściciel licznika w m/live_pool.py: `ProcessBudget.try_acquire(role:str)->bool` oraz
`release_after_exit(pid:int)->None`; adapter PC podaje go pulom/źródłom, wspólny kod UI
nie importuje multiprocessing. Zwolnienie slotu nigdy nie wynika z samego request_stop.

Zapas live ma koszt RSS importów, lecz zero SHM klatek i brak własnego kontekstu GPU;
prefetch live ma pełną scenę/kontekst i nieograniczony kod autora. Limit dodatkowych
buforów klatek/tekstur prefetcha **128 MiB CPU+GPU** (rozliczać także kopie robocze;
przekroczenie pomija warstwę), pamięć checkpointów nadal D40. RSS/VRAM backendu/sceny
nie są objęte tym limitem: mierzyć osobno aktywne, zapas, prefetch i kończące; przy błędzie
alokacji zwolnić spekulację, nie degradować bieżącej sceny. Nie obiecywać limitu całego RAM/GPU.

Odbiór D48: Windows/i7-13700KF, docelowe rozdzielczości Demo, GL i CE osobno,
10 wejść rozgrzewki + 100 nowych scen/silnik, 3 serie, raport p50/p95/max i trafień puli.
**≤0,5 s p95** od zaakceptowanego next do skomponowanej pierwszej klatki/ACK nowego live
bez enter_cue (długiego cue nie wliczać do tego benchmarku); pula rozgrzana, prefetch
wyłączony, zimny fallback raportowany osobno. Powtórzyć z prefetchem i pełnym obciążeniem
D46, nie zastępować pomiaru wejścia samym READY. Testy historii/ACK i osierocenia przez
subprocess również offline; rzeczywisty obraz, fokus, VRAM i p95 wymagają okna człowieka.
Kolejność zadań **6 → 7 → 8**, stop 2× obejmuje też nieosiągnięcie progu: raport/przegląd,
bez automatycznego zwiększenia puli lub osłabienia progu. Cache wyrenderowanych animacji
live odrzucony: zależy od czasu cue i kamery; deterministyczne treści jako pliki.

| Zadanie / budżet (stop 2×) | Zamknięta lista plików | Sygnatury wejścia → wyjścia | Testy odbioru (planowane) |
|---|---|---|---|
| 0. Kontrakt / 4 h | PLAN.md, SPEC.md, REVIEW-LOG.md | próba + odczyt protokołu/API → D45–D48 | spójność ze stanem 10a i D39–D44, przegląd Claude; rozszerzenie D48 PLAN/SPEC + REVIEW-LOG |
| 1. Granice cue / 6 h | m/live_transport.py, p/live.py, p/input.py, p/app.py, t/test_live_scene.py, t/test_live_ce.py, t/test_imgui_input.py, t/test_imgui_live.py, t/test_imgui_live_checkpoint.py | LiveController.step(direction:str, entry_id:int)->None; poll(now:float)->list[dict]; step_result(request_id:int,result:str,frame_id:int)->dict | test_sequence_start_end_empty; test_no_log_parsing; test_stale_step_result; test_step_repeat_until_keyup; test_busy_reserved_step; test_step_loop_keyup_step; test_loop_over_5s_then_stall; test_cue_over_5s_then_stall; test_interrupt_deadline_despite_heartbeat; test_persistent_boundary_restore; test_reverse_boundary; GL i CE, ACK przed jednym reducer effect, błąd/timeout bez skoku |
| 2. Info / 5 h | p/info.py, p/state.py, p/controller.py, p/live.py, m/live_entry.py, p/app.py, p/desktop.py, t/test_imgui_info.py, t/test_imgui_navigation.py, t/test_imgui_live_checkpoint.py, t/test_live_entry.py | render_info(snapshot:dict,preview:dict)->list[dict]; update_timer(state:dict,action:str,now:float)->dict | test_presenter_columns; test_timer_pause_restart; test_notes_scale_limits; test_thumbnail_start_at_barrier; test_jump_live_history; test_thumbnail_during_restore_stale_status_previous_v_r; test_current_thumbnail_noop_entry_pause_reverse_preparing_no_effects; test_info_widgets_consume_click; screenshot dwóch kolumn i pustego preview |
| 3. Miniatury / 6 h | p/info.py, p/app.py, p/sources_av.py, p/decoder_worker.py, p/textures.py, p/manifest.py, t/test_imgui_info.py, t/test_imgui_sources.py | request_thumbnail(index:tuple,size:tuple)->None; poll_thumbnails(now:float)->list[dict] | test_thumbnails_24_slides_bounded; test_thumbnail_composition; test_hidden_info_no_extract; test_stale_thumbnail; 24 slajdy, baza+3 klipy+ruchome preview+miniatury; jeden proces ekstrakcji wraz z kończącym się, ≤4 bezczynne; osobne liczniki aktywnych/bezczynnych/kończących się i suma żywych, LRU/limity CPU+GPU, responsywność podczas przewijania |
| 4. Matematyka / 4 h | p/info.py, p/desktop.py, p/notes_math.py (nowy adapter PC), p/textures.py, t/test_imgui_info.py, t/test_imgui_shared_imports.py | render_formula(text:str,size:float,dpi:float,style:str)->dict; formula dict: rgba,width,height,baseline,error | test_latex_after_init; test_inline_display_baseline; test_mathtext_fallback; test_formula_cache_limits; test_markdown_arrow_merge; PC offline raster, gpu upload, oba font size/DPI; brak importu matplotlib w shared modules |
| 5. Gesty obu playerów / 5 h | p/input.py, p/live.py, p/desktop.py, m/composition.py, m/live_layers.py, t/test_imgui_input.py, t/test_live_layers.py | route(event:dict,state:dict)->list[dict]; view(event:dict,container:tuple)->dict; LiveLayerController.drag(point:QPointF,shift:bool,button:str='middle',alt:bool=False)->None; sygnał pointer_dragged(point,shift,button,alt) | test_gesture_matrix parametrized Qt/ImGui; test_lmb_drag_no_orbit; test_gesture_focus_capture_cancel; test_dpi_fps_invariant; test_zoom_steps; test_reserved_ce_noop; test_reset_last_boundary |
| 6. Pula live / 10 h | m/live_pool.py (nowy), m/live_session.py, m/live_worker.py, m/live_scene_ce.py, m/live_layers.py, m/slides/present/player.py, p/live.py, p/desktop.py, p/app.py, p/sources_av.py, t/test_imgui_sources.py, t/test_live_pool.py (nowy), t/test_live_session.py, t/test_live_ce_player.py, t/test_imgui_live.py | LivePool.configure(engines:set[str])->None; take(engine:str)->WarmWorker\|None; poll(now:float)->None; begin_shutdown()->None; run_pooled_live(engine:str,frame_lock,control,bootstrap_sender)->None; LiveSession.start(spec:LiveSpec,*,pool:LivePool\|None=None)->None | test_spawn_lock_late_spec_shm; test_pool_import_ready_gl_ce; test_engine_selection_refill; test_one_scene_per_process; test_pool_parent_death; test_pool_shutdown_reap_unlink; test_pool_budget_including_retiring; test_budget_wait_poll_delayed_exit_new_entry; test_qt_file_first_deck_pool_poll_shutdown (offscreen); regresje Qt/ImGui i dwóch sesji 5g; nowy live ≤0,5 s p95 po rozgrzaniu, bez prefetcha |
| 7. Prefetch N+1 / 11 h | m/live_pool.py, m/live_session.py, m/live_worker.py, m/live_scene.py, m/live_scene_ce.py, m/live_transport.py, t/test_live_scene.py, t/test_live_ce.py, p/prefetch.py (nowy), p/app.py, p/desktop.py, p/controller.py, p/live.py, p/sources_av.py, p/decoder_worker.py, p/textures.py, t/test_imgui_prefetch.py (nowy), t/test_imgui_sources.py, t/test_imgui_live_checkpoint.py, t/test_imgui_navigation.py | Prefetch.prepare(token:tuple,slide:dict)->None; poll(now:float)->None; take(token:tuple,entry_id:int)->dict\|None; cancel(reason:str)->None; Source.prepare(entry_id:int,media:dict,*,hold_first:bool=False)->None; Source.poll(now:float)->None; Source.adopt(entry_id:int,now:float,paused:bool)->None; LiveController.enter(entry:dict,*,prefetched:dict\|None=None)->None | test_file_first_frame_held_rebase; test_preview_independent; test_prefetch_no_cue_history_reservation; test_hold_no_zero_dt_updaters_gl_ce; test_next_adopt_checkpoint_ack; test_adopt_no_session_no_cue_next_paused_gl_ce; test_ready_hold_over_5s_then_checkpoint_composition_ack_gl_ce; test_adjacent_wins; test_previous_v_jump_cancel_history_unchanged; test_stale_deck_error_timeout; test_loop_auto_skip_exit; test_budget_cancel_waits_exit; test_source_wait_poll_delayed_exit_new_entry; brak prefetcha Qt |
| 8. Odbiór / 3 h | PLAN.md, SPEC.md, t/test_imgui_acceptance.py, e/measure.py | measure(options:dict)->dict | pełny pytest, regresje Qt i GL/CE/5g; 24 slajdy pod pełnym obciążeniem scena+preview+prefetch+miniatury+pule, także anulowanie i exit procesów; metryki 10a bez obniżania progów, pomiar D48 z/bez prefetcha, RSS/VRAM i liczniki procesów; Claude przegląd i próba człowieka |

Budżet 10d **54 h** (33 + 10 + 11), stop **108 h** całości lub 2× zadania; nie podnosić automatycznie.
Po rundzie 24 zadanie 6: 8 → 10 h (Qt i nieblokująca admisja), zadanie 7: 9 → 11 h
(hold/ACK i oczekiwanie Source). Zadanie 8 obejmuje regresje tych scenariuszy bez zmiany 3 h.
Zadanie 3 przeszacowane 4 → 6 h po rundzie 22: osobny limit ekstrakcji, lifecycle
i pomiar pełnego obciążenia, bez globalnego schedulera.
Czas przeglądu Claude i oczekiwania na człowieka raportować osobno. Brak okna nie zalicza gpu.
Środowisko testów: `uv run --frozen`, UV_OFFLINE=1, UV_CACHE_DIR w `.cache/uv`, TMP/TEMP
w `.tmp`, QT_QPA_PLATFORM=offscreen; .venv bez zmian. Wyniki obecnej sesji są dowodami
kontraktu, nie zielonymi wynikami przyszłych testów. Odbiór człowieka: Demo i deck 24 slajdów,
oba okna/monitory, ←→ przy granicy i trzymaniu klawisza, cue w locie, trwały live, V/R,
skok miniaturą podczas przygotowania, czytelność wzorów/strzałek/A+/A− oraz gesty myszy
i touchpada w Qt i ImGui. 10a zadanie 11 pozostaje odrębną obowiązującą bramką.

**Recenzja kontraktu:** rundy 22–23 `codex exec -s read-only`, 2026-10-23: pięć ustaleń
rundy 22 i poprawka watchdogu długiego cue z rundy 23 przyjęte do kontraktu;
rozstrzygnięcia w REVIEW-LOG.md. Recenzja statyczna diffu
i kodu, bez testów GPU; przed implementacją przegląd Claude poprawionego kontraktu.

**Do potwierdzenia w próbie (bez renegocjacji decyzji):** wygoda proporcji 60/40 i fontu
24 px, czułość touchpad zoom/pixelDelta, czytelność na DPI obu monitorów; bramka wasm
i fonty offline przed 10b. Ryzyka: opóźnione wyniki po restore, skład baseline matematyki,
podzbiór mathtext, zimna ekstrakcja miniatur przy zajętej puli, start live ~1,6 s.

### 10b i 10c — granice wspólnego kodu

10b: `--player web`, wspólne moduły i manifest z 10a; źródła HTML video/img i WebGL,
bez lokalnych workerów/live, miniatury z oznaczeniem. Nazwany wspólny zestaw
`test_imgui_shared_logic`: clock_pause, navigation_table, geometry_clip, stale_entry,
manifest_validation z atrapami źródeł uruchamiany identycznie na PC/Pyodide.
Integracje live i Qt są wyłącznie desktopowe. Drugie okno jest repliką: authority w głównym,
snapshot/handshake, deck_id/entry_generation/revision, id komendy i lokalna kotwica czasu;
odrzuć stare rewizje i podwójne komendy. Po throttlingu wznów ze snapshotu, zamknięcie authority
zatrzymuje replikę. Domyślna tolerancja dryfu 100 ms, większy dryf wymusza resync (**do potwierdzenia**).
Tylko baza główna emituje audio, preview/klipy/Info muted; gest odblokowuje play,
odrzucone Promise blokuje start grupy i daje komunikat. Obsłużyć odmowę popup/fullscreen i Esc.
Serwer async w jednym wątku: porcjowanie plików, GET/HEAD, 206/416, zakres ograniczany do EOF,
allowlista manifestu. Offline: przypięty runtime/WASM/stdlib/lock/zależności/fonty i koła Emscripten,
manifest SHA256 i lokalne URL bez PyPI fallback; test świeżego profilu, pustego cache i sieci tylko loopback.
Odbiór 10b: named suite w Edge msedge headless, demo i dwa prawdziwe okna; próg web ≥50 fps
każdy strumień, drop ≤10% każdy, ta sama metodologia okien co PC. Budżet wstępny 20 h,
stop 40 h, do ponownej estymacji po 10a; brak implementacji 10b w tej sesji.
10c: live WebSocket i serwer prezentacji wymagają osobnego kontraktu po 10b, poza 10a/10b.
Poza zakresem: usunięcie Qt, wizard bez Qt, publiczny seek/frame-lock/live sync,
hwaccel, adaptacyjne skalowanie, audio PC inne niż D44, eksport warstw i hosting/logowanie.

---

## Poza zakresem całego projektu

- Fork albo łatanie Manima (CE, GL, GX). Forkujemy manim-slides, nie Manima.
- Publiczny zegar główny, seek warstw i synchronizacja live co do klatki (D17); wewnętrzny zegar mediów PC dopuszcza D43.
- Przechwytywanie ekranu / OBS jako architektura.
- Uwierzytelnianie i transport między hostami. Zakres to lokalne `127.0.0.1`.
- Back-pressure i kolejka aplikacyjna.
- `%%manim_slides` w IPythonie i dyrektywa Sphinx — usunięte z forka (D13).
- Dane grupowe i cokolwiek z teorii grup — to jest `groupy`, nie tutaj.
