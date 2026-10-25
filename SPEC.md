# manim-cue — specyfikacja

_Wyjęte z planu seminarium (`STUDIA/scientific-student-seminaries/group-theory/PLAN.md`, decyzja D18)
po pięciu rundach adwersaryjnej recenzji z codex, 2026-10-19._
Ten plik istnieje po to, żeby nie wygrzebywać od nowa ustaleń, które już zostały
zweryfikowane w kodzie manimgl i przepuszczone przez pięć rund adwersaryjnej recenzji.
Pełna historia argumentów: `PLAN-REVIEW-LOG.md` w `scientific-student-seminaries/group-theory/`.

> **Zmiana kierunku (2026-10-21).** Projekt staje się forkiem manim-slides 5.7.0 z warstwami
> i wstrzykiwanym live — decyzje D13-D19 na końcu pliku. Faza 0 i jej ustalenia zostają w mocy:
> `LiveScene` jest backendem live. Część decyzji D4-D12 jest przez D13-D19 zmieniona; przy każdej
> jest odsyłacz.

---

## Problem

Manim ma jeden model wykonania: `construct()` leci raz, liniowo, do pliku. Brakuje **żywej sceny,
którą wyzwala się z zewnątrz** — jednego miejsca, które steruje animacją i ją wyzwala, żeby dało się
potem synchronizować więcej źródeł.

Wymaganie prelegenta, dosłownie: *„dobrze by było aby to był obiekt w manimie jak każdy inny:
ManimScene aby działały na nim metody typowe dla manima"*. Czyli **nie** osobna warstwa sterująca
z własnym słownictwem, a `Scene`, na której działa `self.play()`, `self.add()`, `self.wait()`
i metody mobjectów.

---

## Ustalenia zweryfikowane w kodzie (nie powtarzać tej pracy)

Wersje: manim CE 0.22, **manimgl 1.7.2**, manimgx 0.1.1, manim-slides 5.7.0 (vendorowany, załatany).

> **Korekta z fazy 1 (2026-10-19).** `manimgx` nie jest „trzecią równoległą wersją Manima", jak
> zakładał ten dokument. To osobny silnik: rdzeń w Ruscie na `wgpu`, celujący w API **Manim CE**
> (nie manimgl), z buildem przeglądarkowym jako pakiet npm — Python w Web Workerze przez Pyodide,
> render przez WebGPU, nic po stronie serwera. Wersja 0.1.1 ma około tygodnia. To ma znaczenie dla
> decyzji o przeglądarce: przejście na manimgx to **przepisanie sceny z manimgl na CE** na silnik
> sprzed tygodnia, nie zmiana backendu renderu.

1. **`Scene.embed()` jest cienką otoczką.** Cała treść:
   ```python
   def embed(self, close_scene_on_exit=True, show_animation_progress=False):
       if not self.window: return
       self.show_animation_progress = show_animation_progress
       self.stop_skipping()
       self.update_frame(force_draw=True)
       InteractiveSceneEmbed(self).launch()
       if close_scene_on_exit: raise EndScene()
   ```
   Wniosek: **wymaga okna**, a `launch()` to po prostu `self.shell()`.

2. **Mechanizm „okno żyje, gdy scena czeka na wejście" ma pięć linii.**
   `InteractiveSceneEmbed.enable_gui` w `manimlib/scene/scene_embed.py`:
   ```python
   def inputhook(context):
       while not context.input_is_ready():
           if not self.scene.is_window_closing():
               self.scene.update_frame(dt=0)
       if self.scene.is_window_closing():
           self.shell.ask_exit()
   ```
   Wniosek: **`self.update_frame(dt=0)` w pętli JEST pompowaniem okna.** To cała sztuczka.

3. **Cykl życia sceny pozwala na własną pętlę w `construct()`.** `Scene.run()` woła `construct()`,
   potem `interact()`; `EndScene` jest przechwytywany i prowadzi do `tear_down()`. Potwierdzone
   przez codex w rundzie 4 jako wykonalne.

4. **`manimgl` otwiera okno domyślnie.** `-p` to tryb presentera, **nie** warunek otwarcia okna
   (potwierdzone w rundzie 5).

5. **`select.select` na gniazdach jest poprawne na Windowsie**; na plikach i potokach nie jest.
   To determinuje wybór transportu.

---

## Architektura

```python
# src/manimcue/live_scene.py  —  uv run manimgl src/manimcue/live_scene.py LiveScene --port 47821
class LiveScene(Scene):                      # manimgl; normalna Scene
    PRESETS = {...}                          # nazwa komendy -> callable(self)

    def construct(self):
        if not self.window:                  # tryb okna wymagany, PRZED wiązaniem gniazda
            raise RuntimeError("LiveScene dziala tylko w trybie okna")
        self.listener = self.open_listener() # nieblokujące gniazdo nasłuchujące
        try:
            self.build_objects()
            while True:
                self.PRESETS[self.next_command()](self)
        finally:
            self.close_sockets()             # listener i klient, na każdej ścieżce wyjścia

    def next_command(self) -> str:
        while not self.buffer_has_line():    # buffer trzyma BAJTY, nie str
            if self.is_window_closing():
                raise EndScene()
            watch = [self.listener] if self.client is None else [self.client]
            ready, _, _ = select.select(watch, [], [], 1 / 60)   # max jedna klatka
            if ready and self.client is None:
                self.accept_one_client()     # kolejnych odrzucamy i zamykamy
            elif ready:
                chunk = self.client.recv(4096)
                if not chunk:                # EOF = rozłączenie; scena żyje dalej
                    self.drop_client()
                else:
                    self.buffer += chunk
            self.update_frame(dt=0)
        return self.pop_line()               # dzieli po b"\n", potem dekoduje LINIĘ
```

**Transport: gniazdo TCP na `127.0.0.1`**, biblioteka standardowa.
Odrzucone i dlaczego: nazwany potok Windows (inny kod per system), `stdin` (zajęty przez launcher
manimgl), plik wartowniczy (`select` nie działa na plikach w Windows), `QLocalServer` w `Player`
manim-slides (steruje odtwarzaniem nagranych klipów, więc metody Manima nie stosują się wcale;
dodatkowo wątek GUI Qt i patch vendora).

> **Korekta (2026-10-21).** Player manim-slides 5.7.0 nie ma `QLocalServer` ani żadnych gniazd —
> sprawdzone grepem po całym pakiecie. Uzasadnienie odrzucenia jako transportu pozostaje słuszne
> (steruje klipami, nie scenami), ale samo `QLocalServer` pochodzi najpewniej z załatanej kopii
> w seminarium, nie z upstreamu.

**`select` z timeoutem jednej klatki (`1/60`) rozwiązuje naraz dwa problemy**: nie ma busy-loopa
zjadającego rdzeń, i nie ma blokującego `readline()`, które zamroziłoby okno. Jeden wątek, bez
współbieżności.

**Protokół**: komendy UTF-8, jedna na linię, `\n` jako framing. Nieznana komenda → log i ignorowanie,
bez wywrotki.

**Endpoint**: zmienna środowiskowa `MANIMCUE_PORT` z domyślną wartością `47821`; scena wypisuje
faktycznie zbindowane `host:port` na stdout przy starcie, z `flush=True`. Klient nie zgaduje
i nie potrzebuje pliku pomocniczego.

> **Korekta z fazy 0 (2026-10-19).** Pierwotnie miał to być argument `--port` w linii komend
> `manimgl`. Zweryfikowane w `manimlib/config.py`: `parse_cli()` kończy na `parser.parse_args()`,
> bez `parse_known_args` i bez passthrough, więc `manimgl ... --port 47821` pada na
> `unrecognized arguments` **przed** zaimportowaniem pliku sceny — scena nie ma gdzie tego
> argumentu przejąć. Zmienna środowiskowa jest jedynym wejściem, które nie wymaga łatania
> launchera, a łatanie Manima jest poza zakresem projektu.

**Model bezpieczeństwa jawnie niezabezpieczony**: nasłuch tylko na `127.0.0.1`, ale każdy lokalny
proces znający port może wyzwalać animacje. Dopuszczalne dla narzędzia prezentacyjnego na jednym
laptopie. Token/uwierzytelnianie poza zakresem PoC.

---

## Trzy pułapki, na których szkic już padł

Pierwsze dwie wyłapane w rundzie 5 recenzji, trzecia w teście wizualnym fazy 0 — nie powtarzać:

1. **Brak `accept()`.** Pierwsza wersja robiła `select.select([self.sock], ...)`, co zakłada **już
   połączone** gniazdo. Bez listenera i `accept()` pętla nie przyjmie pierwszego klienta i kod
   nie da się uruchomić. `select` musi patrzeć na **listener, dopóki klienta nie ma, i na klienta,
   gdy jest**.

2. **Dekodowanie UTF-8 per `recv()`.** `recv(...).decode("utf-8")` rzuci wyjątkiem, gdy pakiet TCP
   rozdzieli znak wielobajtowy — i framing po `\n` tego **nie** ratuje, bo kolejność operacji jest
   odwrotna. Poprawnie: buforować **bajty**, dzielić po `b"\n"`, dopiero kompletną linię dekodować.

3. **Kolejność w `select`: klient przed listenerem.** Znalezione w teście wizualnym fazy 0,
   nie w recenzji. Pierwsza wersja iterowała po `ready` w kolejności, w jakiej `select` zwraca
   gniazda, czyli z listenerem pierwszym. Gdy klient rozłączył się w czasie animacji, jego EOF
   czekał nieodczytany, a nowe połączenie trafiało na `self.client`, które jeszcze nie zostało
   wyzerowane — i **zostawało odrzucone jako „dodatkowy klient", a jego komendy ginęły bez śladu.**
   W pierwszym przebiegu testu wizualnego zgubiły się w ten sposób dwie komendy, w tym cała próba
   kryterium 5. Poprawnie: odczytać klienta **przed** `accept()`, żeby martwe połączenie zdążyło
   zniknąć. Test regresyjny:
   `test_new_client_accepted_while_previous_eof_pending`.

---

## Semantyka, której nie wolno przeobiecać

**Kolejkowanie podczas animacji**: w czasie `self.play()` pętla odbioru nie działa, ale bufor gniazda
w jądrze przechowuje bajty i po animacji odczytujemy je w kolejności. **FIFO — ale tylko dla ruchu
o rozsądnej objętości.** Bufor jądra jest skończony; dostatecznie szybki nadawca może się zablokować
albo rozłączyć, zanim scena go opróżni. „Nic nie jest gubione" jest za mocne. Dla sterowania
prezentacją (kilka komend na sekundę) próg jest daleko. Back-pressure poza zakresem PoC.

**Rozłączenie klienta ≠ koniec sceny**: `recv()` zwracające `b""` to EOF → zamknąć gniazdo klienta,
wyzerować bufor, wrócić do bezczynnego pollingu. Tylko zamknięcie **okna** rzuca `EndScene`.

---

## Kryteria akceptacji PoC

1. Scena startuje **przez prawdziwy launcher** (`uv run manimgl src/manimcue/live_scene.py LiveScene`), nie tylko
   jako test jednostkowy klasy; okno żyje i odpowiada, gdy nic nie przychodzi.
2. Trzy komendy z presetów wyzwalają właściwą animację w otwartym oknie.
3. Komenda nieznana → log, scena żyje dalej.
4. Komenda podzielona na dwa pakiety i dwie komendy w jednym pakiecie → obie wykonane poprawnie.
5. **Dwie komendy wysłane w czasie trwania jednej animacji** wykonane po niej, w kolejności.
6. Zamknięcie klienta nie zabija sceny; zamknięcie okna kończy scenariusz czysto przez `EndScene`.
7. Uruchomienie bez okna daje jasny `RuntimeError`, nie ciche nic.
8. **Zużycie CPU w bezczynności niskie** — dowód, że `select` z timeoutem zdjął busy-loop.
9. Zmierzony czas pracy. Pierwotny szacunek: **~1 h na jednym systemie (Windows)**. Potwierdzenie na
   Linuksie i macOS poza tym zakresem.

**Wynik (2026-10-19, Windows 11).** Dziewięć na dziewięć. Kryteria 3, 4, 6 (EOF), 7 i 8 oraz obie
pierwotne pułapki mają testy automatyczne (`tests/test_live_scene.py`); kryteria 1, 2, 4, 5 i 6
(zamknięcie okna) przeszły w oknie, sterowane skryptem, z logiem sceny jako dowodem — kryterium 5
potwierdzone linią `Cue:` pokazującą, że dwie komendy wysłane w trakcie 6-sekundowej animacji
wykonały się po niej i w kolejności. Trzecia pułapka wyszła właśnie w tym przebiegu.

_Luka w dowodzie: kryterium 9 wymaga zmierzonego czasu pracy, a liczba nie została nigdzie
zapisana._

---

## Decyzje fazy 1 (cue sheet i feeling prezentacji)

> **Uwaga o numeracji.** `D1`-`D12` poniżej to decyzje **tego** projektu. Plan seminarium
> (`group-theory/PLAN.md`) ma własną numerację `D...` — jego `D9` i `D10` to scena czterowidokowa
> i klasy bazowe, nie nasze zapętlenie i przerywalność. Odwołania do tamtych pisane są jawnie
> jako „D9 tamtego planu".

Powód powstania: po przejściu fazy 0 prelegent ocenił, że brakuje nie żywego renderu, a **sposobu
prowadzenia** — niezależnego sterowania strzałkami, podglądu, co będzie dalej, i notatek do cue'ów,
czyli tego, co daje `manim-slides`. Poniższe decyzje odpowiadają na to bez rezygnacji z żywej sceny.

**D1. Transport klawiaturowy obok gniazda.** `→` wyzwala kolejne cue z sekwencji, `←` cofa.
Zdarzenia klawiatury docierają przez `update_frame(dt=0)`, czyli z tej samej pętli, która pompuje
okno — **zasada „jeden wątek" zostaje nietknięta**, nie ma nowego źródła współbieżności. Klawisz
wciśnięty w czasie `play()` trafia do kolejki i wykonuje się po animacji, tak samo jak bajty
z gniazda. Przy kolizji **klawisz ma priorytet**: prelegent przy maszynie bije komendę zdalną.
Zweryfikowane w kodzie manimgl: `Scene.on_key_press` już wiąże `→` i spację (zwalniają `hold_loop()`
w trybie presentera), a `hold_loop()` to dokładnie ta sama sztuczka co nasza pętla odbioru.

**D2. Gniazdo nie przesuwa kursora sekwencji.** Komenda z gniazda wyzwala preset po nazwie
i **nie** zmienia pozycji prelegenta. Inaczej zdalny klient przestawiałby mu prezentację pod rękami.

**D3. `←` cofa z animacją, interpolacją między stanami.** Zweryfikowane w kodzie: `SceneState`
manimgl trzyma `mobjects_to_copies`, czyli mapę mobject → kopia sprzed cue. Dzięki temu cofanie
da się **animować** mimo żywego renderu: `Transform` prowadzi mobjecty do zapisanych kopii, a po
animacji `undo()` domyka stan dokładnie — także dla mobjectów, które cue dodało albo usunęło.

**Czego to nie jest:** ścieżka cofania jest interpolacją między stanem końcowym i początkowym,
**nie odwróceniem pierwotnej animacji klatka po klatce.** `manim-slides` cofa dokładnie, bo gra
nagrany klip od końca (`REVERSE`, domyślnie `V`, plus `reversed_playback_rate`). Rewind klatkowy
w żywej scenie wymagałby nagrywania klatek każdego cue do bufora — osobna decyzja, nie ta.

_Pierwotna wersja D3 mówiła „skok, nie animacja". Zmienione na wniosek prelegenta po obejrzeniu
fazy 0; skok został uznany za zbyt ostry w odczuciu._

**D4. Cue sheet w TOML.** _Skreślone przez D19._ Rozstrzyga pierwsze otwarte pytanie fazy 1: TOML, bo resztę ekosystemu
`uv` już w nim stoi, a `tomllib` jest w stdlib od 3.11 — zero nowych zależności. Pola na cue:
nazwa, kolejność, notatka dla prelegenta.

**D5. Cue może być kilkoma animacjami.** Rozstrzyga drugie otwarte pytanie: tak. Cue jest
callable'em, a nie jedną animacją — `pulse` już dziś woła `play()` dwa razy.

**D6. Cue nie ma deklarowanego czasu trwania.** Rozstrzyga trzecie otwarte pytanie: nie.
Czas wynika z animacji w środku; pole `duration` w cue sheet byłoby drugim źródłem prawdy
i rozjechałoby się z kodem przy pierwszej zmianie `run_time`.

**D7. Widok prelegenta: terminal jako minimum, drugie okno dopuszczone.** _Załatwione przez
okno Info manim-slides (D19)._ Bieżące cue,
następne cue, notatka i pozycja (`3/8`) idą na stdout — to działa od razu i bez zależności.

_Zmiana względem pierwotnej wersji D7:_ zakaz drugiego okna **został zdjęty przez prelegenta**
(„wątek GUI mi nie przeszkadza"). Zastrzeżenie techniczne zostaje zapisane, a nie usunięte:
drugie okno GUI wprowadza drugą pętlę zdarzeń obok pętli manimgl, co jest **jedynym miejscem
w projekcie łamiącym zasadę „jeden wątek"** z `CLAUDE.md`. Jeśli wejdzie, to jako świadomy wyjątek
od tej zasady, z własną decyzją — nie po cichu.

**D8. Wizualny podgląd następnego cue — odroczony, a jeśli wejdzie, to przez prerenderowane
miniatury.** Trzy rozważone drogi i powody:
- **Spekulatywny render** (`save_state` → `force_skipping` → zagraj następne cue → `get_image()`
  → `undo`) jest wykonalny tym, co jest w manimgl, ale **liczy każde cue dwa razy** i dubluje
  każdy efekt uboczny cue poza mobjectami. Odrzucone jako domyślne.
- **Prerenderowane miniatury** (jednorazowy krok budowania, PNG per cue) — to w istocie to, co
  robi `manim-slides`, który też pokazuje materiał nagrany wcześniej. Wymaga przebudowy po zmianie
  sceny, ale nie łamie żadnej zasady projektu. **To jest droga wybrana, gdyby podgląd wszedł.**
- **Drugie okno GUI** — odrzucone jak w D7.

Do czasu tej decyzji „podglądem" jest nazwa następnego cue plus jego notatka w terminalu (D7).

**D9. Zapętlenie cue.** Cue z listy `LOOPS` powtarza się, dopóki nie przyjdzie klawisz albo
komenda; przerwanie następuje **na końcu powtórzenia**, nie w jego środku — ta sama semantyka co
`next_slide(loop=True)` w manim-slides. Pętla musi między powtórzeniami dociągnąć gniazdo
(`poll_once()`), bo `play()` go nie czyta; bez tego komenda zdalna nigdy by pętli nie przerwała.

**D10. Przerywalne animacje.** `self.play()` w cue'ach pozostaje zwykłym `play()`, ale pętla
klatek (`Scene.progress_through_animations`) jest nadpisana tak, że klawisz albo komenda **urywa
animację w dowolnej klatce**. Po urwaniu `play()` manimgl i tak woła `finish_animations()`, więc
mobjecty domykają się do stanu końcowego — przerwanie daje skok do końca, jak przewinięcie klipu
w manim-slides, a nie scenę w połowie przekształcenia. Flaga `abort_cue` sprawia, że kolejne
`play()` w tym samym cue też przelatują natychmiast; bez niej dwuetapowe cue (`sweep`) zagrałoby
drugą połowę mimo przerwania.

Powód powstania: zmierzony. Prelegent zgłosił lag przy cofaniu i zaproponował cache albo
prerender. Pomiar pokazał, że **praca własna cofania to 0,2 ms, a domknięcie stanu 1-2 ms** —
całe 600 ms to zadany `REWIND_TIME`. Nie ma czego cachować; odczuwalny lag brał się z **czekania
na koniec trwającego cue**, do 6 s przy `sweep`. Przerywalność jest naprawą tej przyczyny.
`wait()` ma w manimgl własną pętlę i **nie** jest przerywany — żadne cue go dziś nie używa,
a gdy zacznie, trzeba podać mu `stop_condition=self.interrupt_requested`.

**D11. Selektywny live-render — kierunek na fazę 2.** _Odwrócone przez D14: domyślny jest
prerender, live się wstrzykuje; „ruch prerenderowany w żywej scenie” wraca jako warstwy (D16)._
Wniosek prelegenta: nie każdy element scen
musi być liczony na żywo; live dałoby się włączać i wyłączać per element albo per cue, a resztę
brać z prerenderu. To **zbiega się z pierwotną motywacją projektu**: w scenie czterowidokowej
seminarium trzy panele są statyczne, a żywy render potrzebny jest tylko dla panelu NV⁻, który dziś
stoi na sześciu kadrach PNG.

Co z tego jest tanie i wchodzi razem z cue sheet (D4):
- cue dostaje w TOML flagę `live = true|false`;
- cue nie-live pokazuje **prerenderowaną klatkę** jako `ImageMobject` — jedna scena, jeden
  renderer, żadnego kompozytowania;
- krok prerenderu, który tę klatkę wytwarza, **za darmo daje miniatury do podglądu następnego
  cue** (D8) i materiał dla paneli statycznych.

Co **nie** jest tanie i zostaje poza tą decyzją: pokazywanie prerenderowanego **ruchu** wewnątrz
żywej sceny. manimgl nie ma odpowiednika `VideoMobject`, więc to oznacza dwa źródła na ekranie,
czyli dokładnie „synchronizację wielu źródeł" z fazy 3 — odrzuconą z podanymi powodami.
Klatki statyczne wystarczają do przypadku seminarium i nie łamią żadnej zasady.

**D12. Silnik zostaje manimgl; manimgx odroczony.** _Kolejność silników zmieniona przez D18;
warunek wejścia manimgx zostaje._ Ustalone wspólnie po researchu: manimgx nie
ma udokumentowanego trybu interaktywnego (ani okna, ani pętli zdarzeń, ani krokowania klatek,
ani zdarzeń klawiatury), jego `present` to sekcje nagranej linii czasu, w Pyodide nie ma gniazd
TCP, a wersja 0.1.1 ma tydzień. Prelegent sam ocenił go jako „bardzo młody i niestabilny".
Sprawdzone też, czy alternatywą jest nowy renderer Manim CE: **nie ma go.** Najnowsze CE v0.21.0
(10 sierpnia 2026) przyspieszyło istniejący renderer Cairo 2,2× na scenach animacyjnych; plan
nowego backendu z wiki 2022 nie ma potwierdzenia w 2026. CE ma natomiast `-l/--live-preview`
otwierające żywe okno na rendererze OpenGL — czyli żywe okno nie jest wyłączną cechą manimgl,
gdyby kiedyś przyszło migrować.

---

## Decyzje zmiany kierunku (2026-10-21)

Powód: prelegent opisał docelowy kształt — fork manim-slides, scena jako obiekt w innej scenie,
notatki i podgląd, domyślnie prerender z wstrzykiwanym live, silniki CE → GL → GX. Decyzje
podjęte w rozmowie, po sprawdzeniu kodu manim-slides 5.7.0 i Manim CE 0.22 w pobranych wheelach.

**Zweryfikowane przed decyzjami:**
- manim-slides 5.7.0 (MIT): player to `QMainWindow` z `QVideoWidget` wpiętym w `Player.__init__`
  (`present/player.py:258`) i `QMediaPlayer`. Okno `Info` ma notatki (markdown), podgląd
  następnego slajdu (wideo albo obraz), zegar; player rozdziela okna na dwa ekrany.
  `BaseSlideConfig`: `loop`, `auto_next`, `playback_rate`, `reversed_playback_rate`, `notes`,
  `skip_animations`, `src`, typ `Video`/`Image`. Render CE w `slide/manim.py`, GL
  w `slide/manimlib.py`.
- Manim CE 0.22 ma pętlę okna OpenGL analogiczną do manimgl (`renderer.render(...)` plus
  `window.is_closing`, `scene/scene.py:1523-1600`), a oba renderery CE mają `get_frame()`
  zwracające tablicę pikseli także bez okna.

**D13. Pełny fork manim-slides 5.7.0, wchłonięty w `src/manimcue/slides/`.** Tag `v5.7.0`,
commit `305bd8a`. Importy przemianowane na `manimcue.slides`, CLI `manim-cue` — jeden pakiet,
bez kolizji z oryginałem w środowisku seminarium. Podklasy nie wystarczą: warstwy (D16) wymagają
wymiany `QVideoWidget` w `Player.__init__`, a `SceneView` — zmian w `Slide`. Upstream śledzony
ręcznie, diffem między wydaniami. Usunięte: `%%manim_slides` (IPython) i dyrektywa Sphinx.
Zostają: `convert`, `wizard`, `checkhealth`. Licencja upstreamu leży obok kodu.
Odrzucone: `git subtree` (przemianowanie pakietu gryzie się z każdym pullem; bez przemianowania
kolizja z `manim_slides`), osobne repo-fork (dwa repo, dwa cykle wydań).

**D14. Domyślnie prerender, live wstrzykiwany.** Odwraca D11. Slajd jest klipem albo obrazem,
jak w manim-slides; live to osobny typ slajdu, a potem warstwy.

**D15. Live pokazywany jako strumień klatek.** Proces `LiveScene` renderuje bez okna
i publikuje klatki w `multiprocessing.shared_memory`; player pokazuje je jako warstwę. Sterowanie
zostaje po TCP z fazy 0. **Jeden wątek na proces** — Qt w procesie playera, `select` w procesie
live; zasada z `CLAUDE.md` obowiązuje per proces. Odrzucone: osobne okno manimgl (dwa okna na
projektorze, fokus, brak kompozycji) i kontekst GL osadzony w Qt w jednym procesie (dwie pętle
zdarzeń, `play()` blokuje Qt).

**D16. Scena jako obiekt — w dwóch miejscach.** Warstwy w playerze (czas prezentacji: pozycja,
skala, wyzwalanie, silniki mogą się mieszać) oraz `SceneView` w Manimie (czas renderu: mobject
z klatkami innej sceny, wynik to jeden klip). Kolejność: najpierw warstwy, bo strumień live
trafia właśnie tam.

**D17. Synchronizacja warstw: wspólny start i pauza.** Każda warstwa wideo ma własny
`QMediaPlayer`; player startuje i pauzuje je razem. Dryf na długich klipach zaakceptowany.
Warstwa live ma własny zegar. Odrzucone: zegar główny z seekiem (seek w `QMediaPlayer` na Windowsie
zależy od keyframe'ów, dużo pracy) i warstwy bez wideo (ogranicza „przesuwanie renderu” do kadrów).

**D18. Silniki: prerender CE i GL od razu, live GL → CE → GX.** Prerender obu silników daje
manim-slides. Live w GL już działa (faza 0); CE dochodzi potem; manimgx na warunkach z D12. Przy
warstwach w playerze seminarium na CE i tak może pokazać panel live z GL.

**D19. Skreślone i załatwione przez manim-slides.** D4 (cue sheet w TOML) skreślone: notatki
w `next_slide(notes=...)`, konfiguracja w JSON manim-slides — TOML byłby drugim źródłem prawdy,
z tego samego powodu co w D6. D7 i D8 załatwia okno `Info`; podgląd slajdu live to prerenderowana
miniatura (droga wybrana w D8).

---

## Ustalenia rundy 6 (codex, 2026-10-22) — nie powtarzać tej pracy

Pełna odpowiedź: `REVIEW-LOG.md`. Twierdzenia zweryfikowane przez codex w kodzie; oznaczone ✓
sprawdzone dodatkowo ręcznie.

**Faza 1 (zweryfikowane w praktyce, nie przez codex):**
- **manim-slides 5.7.0 nie działa z Manim CE 0.22.** CE 0.22 przebudował zapis plików (output
  plan): nie ma `config["write_to_movie"]` (`slide/manim.py:48` rzuca `AttributeError`), doszła
  walidacja `max_files_cached`. Upstream testował CE 0.19.1. Fork przypięty do `manim<0.22`.
  Seminarium stoi na CE 0.22 z załataną kopią — łatki najpewniej pokrywają właśnie to.
  **Zamknięte w fazie 7.0 (2026-10-22):** fork dostosowany do planu wyjścia CE 0.22,
  pin zmieniony na `manim>=0.22,<0.23`; zgodność z 0.21 świadomie poza wsparciem.
- `slide/manimlib.py` podmienia `sys.argv` na `[__file__]` przed importem manimlib, żeby launcher
  manimgl nie parsował argumentów cudzego procesu. Skutek uboczny: konfigurację manimgl ustala
  ten, kto zaimportuje manimlib pierwszy (`tests/conftest.py`).

**Live bez okna (faza 2):**
- ✓ **Bez okna manimgl nie trzyma tempa animacji.** `sleep()` wyrównujący czas wirtualny do
  rzeczywistego działa tylko przy oknie (`scene/scene.py:250-254`), zegary startu też
  (`:522-524`). Headless policzy sekundowe cue tak szybko, jak pozwoli GPU. Potrzebny własny
  zegar na `time.monotonic()`.
- ✓ **Launcher tworzy okno przed załadowaniem sceny** (`__main__.py:29-32`), gdy
  `show_in_window`, a to jest `not -w`. `-w` z kolei włącza zapis filmu. Zmienna środowiskowa
  w `construct()` nie wystarczy — proces live potrzebuje własnego punktu startowego, który tworzy
  `Scene(window=None)` z wyłączonym zapisem, bez launchera manimgl i bez `manim-cue render --GL`
  (ten zawsze dodaje `-w`, `render.py:54`).
- ✓ `is_window_closing()` bez okna zwraca `None` nawet przy `quit_interaction` (`scene.py:719`);
  pomijanie rysowania niezmienionej klatki też wymaga okna (`:243`). Headless potrzebuje
  zakończenia przez transport i publikacji tylko po zmianie obrazu. `on_key_press` bez okna nie
  dostaje zdarzeń — klawisze przychodzą wtedy wyłącznie z playera po TCP.
- Fundament offscreen istnieje: `Camera.init_context()` tworzy standalone ModernGL
  (`camera/camera.py:72`), `init_fbo()` własne FBO (`:81`). Pomiar samego odczytu FBO (RTX 4060):
  1920×1080 — mediana 1,8 ms; 960×540 — 0,6 ms. 1080p60 to ~498 MB/s samego payloadu.
- Publikacja tylko w `emit_frame()` gubi klatkę startową (`build_objects` rysuje przez
  `update_frame(force_draw=True)`) i końcową po przerwaniu (`finish_animations()` domyka stan bez
  renderu, `scene.py:561`).
- **`SharedMemory` nie daje synchronizacji** — to goły `memoryview`. Najprostszy poprawny protokół:
  player uruchamia proces live przez `multiprocessing.Process` i przekazuje `Lock`; producent
  renderuje poza blokadą i kopiuje gotowe bajty pod nią; `QTimer` robi `acquire(False)`, kopiuje
  i zwalnia przed malowaniem; zajęta klatka jest pomijana.

**Player i warstwy (fazy 3-4):**
- `Player.frame_changed` (`player.py:664-690`) trzyma ostatnią poprawną klatkę jednego sinka
  i przekazuje ją do `Info` — ochrona przed czarną klatką między klipami. Warstwy muszą to
  przenieść per warstwa (`QGraphicsVideoItem.videoSink()`), a `Info` musi dzielić model warstw.
- **Wspólny start nie wynika z `setSource(); play()` w pętli:** backend FFmpeg Qt 6.12 ładuje
  źródło asynchronicznie i `play()` w trakcie ładowania tylko zapamiętuje żądanie. Trzeba załadować
  wszystkie warstwy, poczekać na gotowość, dopiero potem wydać wspólny start.
- `Player` ma jeden stan odtwarzania, jeden licznik pętli, jeden replay i gotowy `rev_file`
  (`player.py:491-639`). Warstwy wymagają zapisanej semantyki: co kończy slajd, `auto_next`,
  krótszy klip, reverse.
- `SlideConfig` wymaga istniejących `file` i `rev_file` (`config.py:317`), player rozwiązuje
  ścieżkę przed rozgałęzieniem typu (`player.py:451`). Slajd live wymaga zmiany modelu danych,
  nie tylko nowej wartości enuma.

**CE i `SceneView` (fazy 5-6):**
- Cairo `get_frame()` tylko kopiuje tablicę kamery (`cairo_renderer.py:186`); render dzieje się
  w `update_frame()`. `play()` może pominąć liczenie klatek przy trafieniu w cache, a statyczne
  `wait()` idzie przez `freeze_current_frame()`. Live w CE wymaga osobnych adapterów Cairo
  i OpenGL, z wyłączonym cache.
- `play()` w CE i GL przechodzi całą animację synchronicznie — wywołanie `play()` sceny podrzędnej
  z updatera gospodarza blokuje jego klatkę. `ImageMobjectFromCamera` (CE) daje piksele, nie
  wykonanie sceny. „Scena w scenie” to dwa różne zakresy: odtwarzanie gotowych klatek i krokowana
  animacja podrzędna.

**Zasada jednego wątku:** backend FFmpeg Qt sam uruchamia wątki (`QtConcurrent::run`), a player
obsługuje sinki z innych wątków (`player.py:668`). Zasada dotyczy **kodu aplikacji**: jeden wątek
naszego kodu na proces; wewnętrzne wątki Qt i sterowników dozwolone.

---

## Decyzje po rundzie 7 (2026-10-22)

Prelegent przyjął punkty 2-6 z „Do decyzji przed fazą 2” bez zmian (progi wydajności, model
danych przed slajdem live, semantyka warstw, dwa zakresy `SceneView`, CE 0.22 przed fazą
integracji). Na punkt 1 odpowiedział: *„może użytkownik jak kliknie na dane okno?”*.

**D20. Proces live: przygotowanie przy wejściu na slajd, aktywacja kliknięciem.** _Interpretacja
odpowiedzi prelegenta, doprecyzowana z codex — do potwierdzenia._ Wejście na slajd z warstwą live
uruchamia proces i przygotowuje scenę do pierwszej klatki (do tego czasu miniatura). Kliknięcie
warstwy daje jej klawiaturę, ale samo nie wyzwala cue. Przy aktywnym live skonfigurowane
`NEXT`/`PREVIOUS` idą do sceny jako `next`/`back` i nie przesuwają slajdu; pozostałe skróty
playera zachowują znaczenie. Esc, klik poza warstwą, zmiana slajdu albo utrata aktywności okna
oddają klawiaturę playerowi. Wyjście ze slajdu zatrzymuje proces; ponowne wejście to nowa sesja.
Odrzucone: start dopiero po kliknięciu (zimny start ≥1,5 s plus `build_objects`) i start
wszystkich scen razem z playerem (każda scena headless tworzy własny kontekst GL i FBO).
Routing klawiszy to jeden router przed `Player.dispatch` (`player.py:695`), obejmujący też
zdarzenia z okna Info (`:183`).
**Aktualizacja:** D39–D41 zastępują zimny restart dla zgodnych trwałych sesji;
D45 zmienia przechwytywanie strzałek na granicy sekwencji wyłącznie w ImGui.

**D21. Proces live przez `multiprocessing` (spawn) z przekazanym `Lock` i nazwaną SharedMemory.**
Sprawdzone przez codex: spawn działa z wrapperem `manim-cue.exe` (`spawn.py:192` bierze
`__main__.__spec__.name`, a `Lock` jest duplikowany do dziecka, `synchronize.py:100`). Warunki:
target to funkcja modułowa bez importów Manima i Qt na poziomie modułu; w targecie
`sys.argv=[argv0]` przed pierwszym importem Manima i pliku sceny; przekazywane są dane, nie
obiekty sceny ani Qt; proces i blokada z jednego `mp.get_context("spawn")`.
Protokół pamięci: jeden pisarz, jeden czytelnik, nagłówek v1 (magic, wersja, wymiary, stride,
rozmiar, format RGBA8, orientacja bottom-up, `frame_id`, czas monotoniczny) i payload pod tą samą
blokadą; render i odczyt FBO poza blokadą; czytelnik `acquire(False)`, kopia, zwolnienie przed
konwersją Qt. Klatki graniczne (pierwsza, koniec cue, cofnięcie) potwierdzane komendą
`frame_seen <id>`; worker czeka na nią przed następnym cue (timeout 2 s = błąd odbiornika).
Odrzucony seqlock na gołym `memoryview`: brak operacji atomowych i porządku pamięci
(`shared_memory.py:185`), więc „licznik przed i po” nie specyfikuje gwarancji.

**D22. Korpus scen testowych w `tests/scenes/`.** Trzy rodzaje: sceny poprawne (docelowo mają
działać), sceny negatywne (sukces = czytelna diagnoza; zwykłe zielone testy z `pytest.raises`,
bez xfail) i testy infrastruktury bez sceny Manima. Brakująca funkcja z ustalonym API:
`xfail(strict=True, raises=..., reason="F<n>: ...")`, import modułu wewnątrz testu. Zapowiedź bez
API: tylko wpis w manifeście `tests/scenes/MANIFEST.md`, bez pustego testu. Brak GPU albo TeX
to jawny skip środowiskowy (znacznik `gpu`, `tex`), nie wada implementacji. Kryteria obrazu:
pozycje, maski kolorów, tolerancja — hash tylko dla syntetycznych bajtów transportu.

---

## Decyzje fazy 3 (2026-10-22, przed rundą 8)

Prelegent po próbie F1/F2 w oknach: dwa osobne okna (player i odbiornik live) to nie jest
docelowy kształt; kolejność faz bez zmian — „faza 3, potem 4, 5, 6”.

**D23. `convert` przy warstwie live: jawny błąd.** Komunikat z indeksem slajdu i nazwą sceny.
Odrzucony obraz zastępczy: każdy konwerter (HTML, PDF, PPTX) musiałby składać kompozycję.

**D24. Warstwa live to pole `layers: list[LiveLayer]` w `BaseSlideConfig`.** Ścieżki: autorskie
`scene_file` względem CWD renderu (walidowane już w `next_slide`), zapisane w JSON względem
`path.parent.parent` — jak `file`. Miniatura: PNG pierwszej klatki z procesu spawn, klucz cache
ze ścieżki, bajtów pliku, klasy, rozmiaru i wersji generatora (zależności sceny: `--flush-cache`).
`copy_to` i konwertery odrzucają warstwy (D23). Wrapper
`BaseSlideConfig.wrapper` (`config.py:202`) robi z niego argument `next_slide`, a JSON zapisuje
i czyta go bez nowej ścieżki. `rect` jako ułamki kadru (niezależne od silnika i jednostek sceny),
rozdzielczość procesu live z `rect` × `resolution`. `PresentationConfig.version = 2`, plik bez
wersji (upstream) zgodny dzięki wartości domyślnej, wersja wyższa — błąd. Slajd live nadal ma
klip bazowy: walidator upstreamu (`config.py:291`) zostaje, tło slajdu daje Manim.

**D25. Kompozycja: jedna `QGraphicsScene` na slajd, dwa widoki.** Okno główne i bieżący widok
Info to `QGraphicsView` tej samej sceny, więc Info pokazuje to samo z konstrukcji (runda 6, p. 7).
Ochrona przed czarną klatką zostaje mechanizmem upstreamu, przeniesionym na sink
`QGraphicsVideoItem`. Podgląd następnego slajdu — osobna scena tego samego typu.

**D26. Próg fps z tolerancją granic okna, nie ułamkiem.** _Po rundzie 8._ Pierwsza propozycja
(≥ 97% żądanego fps) dopuszczała 54 zgubione klatki, żeby wytłumaczyć jedną — codex wskazał, że
licznik zmian pikseli i wyzerowanie po pierwszej klatce okna dają błąd granic, nie stratę. Próg:
„różne odebrane klatki ≥ próg·T − 2” (960×540: próg 60, 1920×1080: 30). Pomiar zamraża liczniki
z końcem okna i zapisuje surowe liczby: opublikowane, odebrane, różne.

---

## Decyzje fazy 4 (2026-10-22, runda 9)

**D27. Cykl życia warstw live w playerze.** Sesje warstw należą do `LiveLayerController`
(`src/manimcue/live_layers.py`); start w `load_current_media` po kluczu (prezentacja, indeks
slajdu) — replay, pętla i powrót z reverse na tym samym slajdzie zostawiają sesje, każde wejście
na slajd (także od tyłu) startuje live od początku; reverse dotyczy tylko klipu bazowego.
Zamykanie dwufazowe: `begin_shutdown()` w `Player.close()` bez blokowania GUI, potem blokujący
odbiór (≤ 3 s) po wyjściu z `app.exec()` — po pętli Qt nie ma już GUI do zablokowania.
Okno główne i Info to jeden obszar aktywności: warstwę zwalnia przejście do innej aplikacji
(`applicationStateChanged`), nie przejście między naszymi oknami — inaczej sterowanie z Info
byłoby niemożliwe. Doprecyzowuje D20 („utrata aktywności okna”).

**D28. Nawigacja kamerą w warstwie live.** _Na wniosek prelegenta po próbie F3 („nawigacja w 3D
… jej nie ma”); recenzja w rundzie 10._ Proces live nie ma okna, więc obsługa myszy manimgl
(`d`/`f` + ruch, kółko — `scene.py:730-808`) nie działa. Player tłumaczy mysz na aktywnej
warstwie na komendy `view orbit|pan dx dy` (ułamki warstwy, y w dół), `view zoom kroki`,
`view reset`; scena przelicza je jak `Window.pixel_coords_to_space_coords` manimgl (stały kadr,
`pan_sensitivity`, pan przez `from_fixed_frame_point`). Widok nie jest cue: nie przerywa
animacji, nie rusza sekwencji, w bezczynności publikuje zwykłą klatkę — bariera czeka tylko na
klatki graniczne. Kamera należy do `SceneState`, więc `back` przywraca widok sprzed cue, a
w trakcie cue animującego kamerę nawigacja przegrywa z animacją. Reset wraca do kadru z ostatniej
klatki granicznej (READY, koniec cue, `back`), nie do domyślnego kadru `Scene`.
**Aktualizacja:** D47 zastępuje mapowanie przycisków w Qt i ImGui; protokół view,
normalizacja kontenerem i semantyka kamery pozostają.

---

## Decyzje fazy 5 (2026-10-22, runda 11 + PoC)

**D29. Warstwy z plików: `ClipLayer` obok `LiveLayer`.** Unia dyskryminowana po `kind`, format
v3 (v2 migrowany przy odczycie). Klip to wideo albo obraz — także render innej sceny, wskazany
pomocnikiem `slide_file(json, index)`. Prostokąty klipów i klatek kluczowych mogą wychodzić poza
kadr; prostokąt live — nie, bo wyznacza rozdzielczość renderu.

**D30. Ruch warstw: liniowe klatki kluczowe w aktywnym czasie slajdu.** `QElapsedTimer` od
wspólnego startu, zatrzymywany pauzą i końcem bazy, zerowany przez replay. Odrzucone:
`position()` bazy (50 ms, nieciągłości pętli i szybkości), wyzwalanie ruchu klawiszem (osobny
model wyzwalania, poza F5), easing (rozszerzenie).

**D31. Wspólny start przez przygotowanie pierwszych klatek.** Każdy player grupy gra do
pierwszej poprawnej klatki i się zatrzymuje; wspólne `play()`, gdy gotowe wszystkie. PoC: rozjazd
18 ms przy 4 źródłach 1080p60 (zamiast 67 ms z samą barierą `LoadedMedia`). Warstwy-klipy
śledzą stan bazy, więc istniejące ścieżki playera sterują grupą bez zmian.

---

## Decyzje fazy 6a (2026-10-22, runda 13)

**D32. `SceneView`: klatki gotowego klipu w scenie-gospodarzu, czas z zegara gospodarza.**
`SceneView(scene, plik, height, loop, rate)` dla CE (Cairo, `pixel_array`) i manimgl (zapis do
tekstury). Czas widoku = `scene.time` gospodarza od pierwszego odświeżenia (z pauzą, `seek`
i szybkością), nie suma `dt`. Kopie widoku dzielą stan i dekoder. Gwarantowane: geometria,
krycie, animacje gospodarza w trakcie odtwarzania, ciągłość między slajdami. Poza kontraktem:
VFR, `become`/`Transform` między dwoma widokami, sterowanie przez `.animate`.

---

## Decyzje po próbie prelegenta F4-F6a (2026-10-22, runda 16)

**D33. Trwała sesja live i cue wejścia.** _Prelegent: „jedno kliknięcie ma robić kilka rzeczy
naraz w scenie głównej, interaktywnej i innej CE; sceny nieruchome, tylko animacje”. Restart live
przy każdym slajdzie (D27) to też największy zmierzony koszt zmiany slajdu: ~1,8 s na ciepło._
- **Ciąg sesji:** `LiveLayer.session_id: str | None`; warstwy o tym samym `session_id` na
  **sąsiednich** slajdach jednej prezentacji to jeden ciąg — proces i stan sceny przechodzą.
  Zgodność wewnątrz ciągu: kanoniczna ścieżka sceny, klasa, `fps` i rozmiar renderu (szerokość,
  wysokość prostokąta); pozycja i `thumbnail` nie należą do tożsamości. `session_id` unikalny na
  slajdzie. Niezgodność → błąd walidacji z indeksami slajdów. Przerwa kończy ciąg; to samo ID
  dalej = nowa generacja. Sesji zatrzymywanej (`request_stop`) ani w ERROR nigdy się nie
  przejmuje. Bez `session_id` — D27 bez zmian.
- **Ciągłość obrazu:** ostatnia klatka, metadane i błąd należą do sesji, nie do indeksu warstwy;
  każde wejście odtwarza mapowanie sesja → indeks kompozycji i od razu wstawia ostatni obraz
  (bezczynna scena nie publikuje ponownie). Fokus zwalniany przy zmianie slajdu (D20).
- **Zdarzenia nawigacji:** player przekazuje kontrolerowi przyczynę zatwierdzonego przejścia, nie
  flagę `playing_reversed_slide` (`←` ustawia ją na `False`, `V` — przed sprawdzeniem istnienia
  slajdu). `enter_cue` idzie **tylko** przy zatwierdzonym wejściu do przodu (`next` ze zmianą
  slajdu, `auto_next`, `skip_all`); nie przy powtórzeniu pętli, przejściu reverse → normalny plik
  tego samego slajdu, wejściu od tyłu, replay ani zamknięciu.
- **Wspólny start:** koordynacja potrzebna, gdy slajd ma klipy/klatki kluczowe (D31) **albo**
  live z `enter_cue` w sesji jeszcze nie-READY — także nad bazą statyczną. Baza i klipy czekają na
  pierwszych klatkach, live na READY (≤ 5 s; bez READY live wypada, cue nie idzie, baza startuje),
  potem w jednym ticku `play()` grupy i `send(enter_cue)`. Sesja ciepła nie wstrzymuje startu.
  `start_paused`/pauza w przygotowaniu: cue idzie przy pierwszym faktycznym starcie.
- **Cue w trakcie innego cue:** `enter_cue` przerywa trwające (D10 — skok do końca), więc start
  live może się spóźnić o jedną publikację; zgłoszone, nie korygowane.
- **Poza D33 (osobny etap, protokół checkpointów — runda 16 p. 3-5):** cofanie cue wejścia przy
  `←`/`V` i ponowne cue przy replay. Do tego czasu wejście od tyłu zostawia live w bieżącym stanie;
  `back` (D3) cofa tylko cue z sekwencji `next`, nie nazwane `enter_cue`.
  **Aktualizacja F5g:** powyższe odroczenie i ciepły start bez bariery zastępują D39–D41;
  ←/V odtwarzają pozostawiony stan, R początek wejścia i cue, także w ciepłej sesji.
- Bez zmian: fokus (D20; cue wejścia nie przejmuje fokusu), brak pauzy live (D17 dla live to tylko
  wspólny start; spacja pauzuje bazę i klipy), brak zegara głównego, podgląd Info z miniaturami.

---

## Decyzje F5c (2026-10-22, runda 17)

**D34. Izotropowy obraz live i dopasowanie klipów.** Live renderuje cały domyślny kadr
16:9 w rozdzielczości dopasowanej do panelu; publikacja dodaje czarne pasy do wymiarów bufora.
Miniatura korzysta z tego samego workera. Worker ustawia domyślny `frame_config.frame_shape`
przed konstrukcją sceny. Samo rozszerzenie frame_shape nie wystarcza: test rzeczywistego GL
wykazał deformację, bo `Camera.refresh_uniforms` nadal używa stałych FRAME_WIDTH/HEIGHT.
Letterbox zachowuje treść bez łatania Manima. Wszystkie reprezentacje klipów zachowują
proporcje, wyśrodkowane w kontenerze D30; przezroczysty margines blokuje klik do warstw pod nim.
Bez zmian D17/D20/D27/D31/D33.

---

## Decyzje F5d-f (2026-10-22, runda 18)

**D35. Podgląd klipów, alfa pustego tła i styl obwódki (runda 18).** Info odtwarza normalne
klipy do przodu, wyciszone w niezależnych pętlach i przy rect_at(0), bez bariery głównej.
Ruch podglądu odroczony; D30 w głównym oknie bez zmian. `background_opacity=1` jest
skończone w [0,1], należy do tożsamości kamery w ciągu D33, ale nie globalnie do session_id.
Transport pozostaje prostym RGBA. Gwarancja alfy obejmuje puste tło kamery i pasy D34,
nie dowolną półprzezroczystą treść shaderów manimgl; Manima nie łatamy. Miniatury i klatka
zachowana utrzymują alfę. BorderStyle używa Color Pydantic, dodatniej skończonej szerokości
oraz krycia [0,1], mnożonego przez alfę koloru; null wyłącza rysowanie, nie fokus.
Aktywna rola ma pierwszeństwo, release wraca do pierwszego błędu (także gdy styl null).
Domyślne style zachowują żółtą/czerwoną obwódkę 6 px. D17/D20/D27–D34 bez innych zmian.

---

## Decyzje F7a (2026-10-23, runda 19)

**D36. Live CE Cairo 2D.** Osobny LiveSceneCE, jawny engine manimgl/ce-cairo
w LiveLayer i na końcu LiveSpec; zapis v4, v2/v3 oznacza GL. Silnik należy do obu
tożsamości D33 i miniatury. Spawn izoluje config; po imporcie autora worker narzuca
Cairo/format none/disable_caching na cały lifecycle. Własny renderer kontroluje play,
bez patchowania Manima, hashowania i encodera. Monotoniczne terminy + sleep + poll(0),
select tylko idle/bariera. D10 domyka animacje/czas bez pominiętego dt updaterów.
Warunek wait jest dynamiczny i kończy czas faktyczny, frozen+warunek jest błędem.
Construct należy do bazy; finalizer raz, pierwotny wyjątek zachowany, shutdown przerywa
callable, blokujący kod kończy nadzorca. Progi GL F2 pozostają bez zmian.

**D37. Historia sekwencji** (zatwierdzona przez prelegenta 2026-10-23). CE i GL zapisują stan tylko przed next, z pozycją kursora,
do 50 pozycji bez deduplikacji; nazwane cue nie dodaje wpisu. Back po next i nazwanym
cue wraca przed next. CE zachowuje oryginalne obiekty, graf submobjects, listy sceny i czas logiczny,
geometrię/style i referencje updaterów we wspólnym memo; zakres to standardowe panele
2D. Kopie targetów zachowują odniesienie bound updatera do żywej sceny zamiast kopiować IPC.
Bez serializacji zamknięć/zasobów i dowolnych klas użytkownika. Interpolacja zgodnych węzłów
0,6 s, potem dokładne odtworzenie grafu. Odroczenie checkpointów D33 zastąpione przez D39–D41.

**D38. Zamknięty zakres panelu fazy 8.** D28 CE (pan/zoom/reset), animowana kamera,
3D i dowolny graf snapshotu odroczone; view w CE jest no-op. D35 obejmuje puste tło
i pasy, nie dowolną półprzezroczystą treść. Cel CE: 60 różnych odebranych klatek/s
przy 960×540, 480×270, 538×648 (30 s, ≥60T−2), idle <5% rdzenia i p95 <100 ms,
trzy pełne przebiegi Qt; brak zaliczenia na podstawie mikrobenchmarku.

## Decyzje F5g (2026-10-23, runda 20)

**D39. Checkpointy wejść live.** Zastępuje odroczenie D33/D37 dla sąsiednich sesji:
before(N) zawiera graf, kursor i historię D37; previous/V odtwarza before opuszczanego
wejścia, replay before bieżącego i cue celu. Powrót nie gra cue; ponowne next tworzy
nową gałąź. Initial bez cue; zimne next z cue celu, zimne previous/V bez cue; replay
lokalnego początku z cue celu. Bez session_id nadal D27. Bez rekonstrukcji wcześniejszych
slajdów, między generacjami, prezentacjami i przerwami. Reverse live nie odwraca czasu.

**D40. Graf i pamięć checkpointu.** Osobny adapter bez get_state/undo GL: wspólne memo,
oryginały i krawędzie, style/geometria/updatery/czas standardowego panelu, potem dokładny
restore po interpolacji 0,6 s zgodnych węzłów D3. Zależności updaterów, pola sceny,
I/O i RNG poza gwarancją; nie obiecujemy ich wykrywania. Do 50 checkpointów, 256 MiB
rozliczonych snapshotów/historii i rezerwa 4× bieżący graf na kopie robocze; bez limitu RSS.
Rachunek obejmuje utrzymywane oryginały także poza sceną; rezerwa restore uwzględnia ich
bieżący rozmiar obok rozmiaru sceny i zapisanego grafu.
Nieobsługiwane typy albo brak rezerwy oznaczają odmowę przed kopią. Po braku checkpointu
zachować obraz i trwałą degradację; częściowo nieudany restore zatrzymuje proces.

**D41. Rezerwacja, korelacja i bariera.** Operacje stanu są FIFO po D10/D9, rezerwacja
blokuje ręczne cue i GL view także w pauzie, aż worker przyjmie enter/release. Nowe wejście
unieważnia stare enter. Jedna generacja/socket, ID wejścia i monotoniczne ID żądań; bez
retransmisji i cache duplikatów. Aktualna granica jest komponowana przed ACK, anulowana
odbierana i potwierdzana bez kompozycji. Status bez wskazanej klatki nie zwalnia bariery.
D31 obejmuje ciepłe sesje, replay i reverse; deadline 5 s całego przygotowania, ACK 2 s.
Timeout odcina i zatrzymuje niepewny proces, baza/klipy kontynuują. Info i nakładka
pokazują tę samą operację, początek/pozostawiony stan oraz trwałą degradację nad READY.

---

## Decyzje F10 (2026-10-23, runda 21)

**D42. Player ImGui PC/web.** imgui-bundle 1.93.0, PyOpenGL 3.1.10 na PC,
jawne GLFW/OpenGL3 i hello_imgui; wspólny kod kontrolera/geometrii/UI bez Qt,
PyAV i multiprocessing, manifest JSON zamiast importu modelu w Pyodide.
`present --player imgui|qt`, Qt domyślny. Jeden wątek aplikacji na proces;
poll live/ACK przed mediami, blokujące dekodery w nadzorowanych procesach PC.
Bramki dwóch okien Windows i importów PC/Pyodide przed portem.
Wykonawca codex zadaniami 0–11, Claude przegląda po każdym etapie;
podział i zamknięty zakres w PLAN. Bramki i zadania 3–10 wykonane; zadanie 11 pozostaje
otwarte. Po pierwszej próbie prelegenta etap 10d (D45–D48) poprzedza 10b.

**D43. Wewnętrzny zegar mediów PC.** Jawny wyjątek od ograniczenia D17:
baza i klipy plikowe PC mają wspólny czas prezentacji z barierą i pauzą;
CFR wybierane według czasu, inne materiały według zwalidowanych PTS/czasów GIF.
Spóźnione obrazy pomijane, bez nadrabiania w UI i bez gwarancji frame-lock.
Czas mediów, aktywny czas ruchu D30 i czas rzeczywisty Info są oddzielne.
Bez publicznego seek i synchronizacji czasu live; web zachowuje własne zegary
video, wspólny start/pauzę i zaakceptowany dryf. D31/D39–41 nadal obowiązują:
bariera czeka na gotowy obraz restore, ACK po trwałym przyjęciu do kompozycji,
przed startem/enter, nie po fizycznym wyświetleniu. Ruch preview w F10 ma własny
czas niezależny od pauzy/barier głównych (wyjątek od rect_at(0) w D35 dla plików).

**D44. Audio — decyzja prelegenta zachowana.** 10a PC bez dźwięku, ostrzeżenie
raz na materiał bazy ze strumieniem audio; Qt pozostaje ścieżką dźwiękową.
Implementacja audio wymaga osobnej decyzji przed usunięciem Qt. W 10b audio
tylko z bazy głównego okna, po udanym play odblokowanym gestem użytkownika;
odmowa blokuje wspólny start i pokazuje komunikat, Info/preview/klipy wyciszone.
PoC web z muted nie dowodzi działania audio.

Domyślne warianty **do potwierdzenia** przez prelegenta: fullscreen bez ramek,
ruch preview według czasu każdego źródła/reset przy jego pętli, dryf repliki web 100 ms.
Nie zmieniają decyzji D44 ani wykonania etapami; szczegóły i budżety w PLAN.

**D45. Oddanie fokusu na granicy sekwencji live — ImGui (zmienia D20).**
Decyzja prelegenta po próbie 2026-10-23: NEXT na końcu sekwencji i PREVIOUS na jej
początku zwalniają fokus i wykonują raz zwykłą akcję next/previous playera, ze wszystkimi
regułami pauzy, pętli, reverse i końca decku. Klik aktywuje, hover nie; samo dojście
ostatnim cue do końca nie zmienia slajdu — robi to następne naciśnięcie.
Powód: płynne przejście z interakcji do prezentacji bez dodatkowego Esc.

Źródłem prawdy jest worker: cursor/SEQUENCE oraz możliwość undo. Obecny `SEQUENCE_END`
nie ma ID, a komunikat początku to tylko log; `EntryHistory.cue_state` opisuje enter cue,
nie pozycję sekwencji. Nowa opt-in komenda `step <request_id> next|back` zwraca
`STEP_RESULT <request_id> <done|start|end|error> <frame_id>`. Kontrakt FIFO, walidacji
granicy, korelacji session/generation/entry_id, publikacji klatki i ACK opisuje PLAN 10d.
Na początku wystarcza cursor==0 lub pusty undo_stack; pusta sekwencja ma obie granice.
Nawigacja dopiero po aktualnym start/end oraz kompozycji/ACK wskazanej klatki;
stary wynik, error i timeout nie powodują skoku. Repeat jest konsumowany aż do key-up
również po oddaniu fokusu. Rezerwacja blokuje wysyłkę; cue w locie domyka/przerywa się
według D9/D10, bez zgadywania granicy z kursora w trakcie animacji i bez kolejki repeat.
Krok wykonywany i jeden oczekujący FIFO są osobne: po key-up drugi fizyczny press
dociera do workera i domyka/przerywa pierwszy krok z LOOPS. Skorelowany
`STEP_STATUS <request_id> <waiting|running|looping>` rozróżnia oczekiwanie i wykonanie.
Przyjęcie/status w 5 s; waiting odnawiane tylko przy potwierdzonym postępie poprzednika.
Running/looping co ≤1 s jako skorelowany heartbeat potwierdzonego postępu cue/pętli
(także wait), nie samego transportu; watchdog 5 s braku postępu, bez limitu długości cue
ani pętli. Od żądania przerwania/domknięcia nieodnawialny deadline 5 s na wynik,
także przy dalszych heartbeat. ACK 2 s; szczegóły w PLAN 10d.
Timeout zatrzymuje niepewną sesję według D41, utrwala degradację i nie nawiguje.

Granica dotyczy całej sesji, nie zakresu checkpointu danego slajdu. Trwały live zachowuje
D39–D41, historię before(N), enter_cue i barierę; fokus nie przechodzi sam na nowy slajd.
V/reverse i R zachowują znaczenie playera, bez odwracania czasu live. Qt ma jawny wyjątek:
strzałki pozostają przechwycone na granicy. Rekomendowany wyjątek teraz, koszt późniejszego
parytetu 3 h/stop 6 h i osobny zakres. Odrzucone: hover focus, parsowanie logów,
liczenie cue w playerze, automatyczny skok po ostatnim cue i obejście bariery.

**D46. Info jak widok prezentera PowerPoint — tylko ImGui (rozszerza D42).**
Skrajnie po lewej pionowa, przewijana kolumna miniatur wszystkich slajdów bieżącego decku
(sorter PowerPoint, runda 27). Obok kolumna: duża bieżąca kompozycja współdzielona ze sceną,
nad nią zegar lokalny, elapsed i pauza/restart czasu prelegenta, niezależne od pauzy mediów.
Prawa: następny slajd i pod nim większe przewijane notatki. Klik miniatury wywołuje start_at i pełną barierę nawigacji; bieżący cel to no-op
w reducerze po normalizacji indeksu, przed _enter(): entry_id, pauza, reverse
i przygotowanie bez zmian, brak efektów.
Skok niesąsiedni daje zimny lokalny początek live bez enter_cue i bez rekonstrukcji drogi;
sąsiedni start_at może zachować sesję, lecz rozpoczyna lokalną historię bez cue.
`p/live.py` i `m/live_entry.py` odcinają stos, stare oczekiwania i checkpointy
EntryHistory także podczas restore; nowy checkpoint ma has_predecessor=False.
Nie resetować generacji ani monotonicznych liczników zachowanego socketu; nowe
entry_id odrzuca późne statusy/wyniki/ACK. Previous/V/R nie wracają do starej historii.
Powód: prelegent widzi jednocześnie scenę, następny cel i czytelne notatki oraz może
wybrać dowolny slajd bez serii strzałek. A+/A− zmienia tylko font notatek i matematyki;
domyślnie 28 logicznych px (runda 30), wzory 1,2× tekstu, krok 2, zakres 16–48, stan sesji.
Układ początkowo 60/40.

Markdown pozostaje, dochodzą inline `$...$` i display `$$...$$`. PC preferuje MicroTeX;
offline zweryfikowano imgui-bundle 1.93.0: has_latex False przed init, True po init,
działający raster wzoru bez okna i lokalne fonty. Inicjalizacja with_latex obejmuje
AddOnsParams i MarkdownOptions. Fallback PC: dostępny matplotlib 3.11.2 mathtext/Agg
do tekstur, z metrykami baseline, ograniczonym podzbiorem TeX i widocznym błędem wzoru.
Roboto plus merge Inconsolata przez MarkdownOptions.font_options.merge_fonts zapewnia ←→.
Wspólny kod D42 nie importuje matplotlib. Pyodide ma ścieżkę MicroTeX według lokalnych
helperów pakietu, ale slim wheel pobiera fonty osobno; brak dowodu runtime wasm offline.
10b wymaga próby po inicjalizacji, fontów/licencji w eksporcie offline i braku obowiązkowego
CDN. Fallback web to rastry przygotowane na PC; brak wzoru pokazuje źródło z komunikatem.

Miniatury: reprezentacja końcowa niezależnych źródeł (runda 28): rect_at(+∞) każdej warstwy,
end_thumbnail albo ostatnia klatka wideo/GIF; obraz bez zmian; live zapisany thumbnail jako
reprezentacja zastępcza, bez aktywnej sesji i bez uruchamiania scen.
Ekstraktor długożyjący (runda 29): jeden proces na deck renderuje żądania po jednym, wynik od razu
po odbiorze; kończy się po 2 s bezczynności, ukryciu Info, zmianie decku lub odzysku. Nawigacja
w decku nie anuluje pracy; zakres widoczne ±1 zastępuje oczekujące. Lazy widoczne+po jednej obok, jeden job
ekstrakcji (jeden proces, także w trakcie kończenia), niezależnie od dekoderów sceny
i obowiązkowego ruchomego preview. Pula 4 to zapas bezczynnych ciepłych procesów,
uzupełniany po pobraniu; każdy obsługuje jedno źródło do końca życia. Brak globalnego
limitu 4: osobno liczyć aktywne scena/preview/miniatura, bezczynne ≤4 i kończące się
do potwierdzonego exit oraz sumę żywych; odbiór przy pełnym obciążeniu.
LRU 64 obrazy/16 MiB buforów i tekstur miniatur playera (CPU+GPU), 256×144 RGBA;
dekodowanie w ekstraktorze poza tym limitem, z limitem wejścia ≤3840×2160 (runda 26).
Przy 20 obrazach ok. 5,6 MiB CPU+GPU, bez N dekoderów; web eksportuje miniatury na PC.
Formuły: LRU 128/16 MiB CPU+GPU, limit 4096 znaków/2048×2048 px; bez pracy co klatkę.
Szczegóły anulowania, błędów, fontów/DPI i odbioru w PLAN 10d.
Odrzucone: dekodery wszystkich slajdów naraz, drugi rendering bieżącej sceny,
zewnętrzny proces TeX i zależność wspólnego UI od matplotlib. Qt Info bez zmian.

**D47. Gesty kamery jak Defect-Studio/Blender — ImGui i Qt (zmienia D28).**
MMB orbit, Shift+MMB pan, wheel zoom; skróty touchpada dostępne równolegle:
Alt+LMB orbit, Alt+Shift+LMB pan, Alt+RMB zoom. LMB-drag przestaje obracać;
dwuklik LMB resetuje do ostatniej granicy jak D28. Powód: znane prelegentowi sterowanie
3D. Gesty wymagają fokusu z kliknięcia (D20), nie hover; capture i anulowanie w PLAN 10d.
Pan ma pierwszeństwo nad orbit. Normalizacja Δx/width, Δy/height aktywnego kontenera,
y w dół, jednostki logiczne, bez mnożnika dt/fps; orbit/pan czułość ×1 według D28.
Wheel dodatni przybliża, Qt angleDelta/120 lub pixelDelta/40; Alt+RMB zoom −20×Δy/height
kroków, backend nadal 0.9**steps. Reset, kamera w historii, rezerwacja D41,
nieprzerywanie cue przez view i no-op CE Cairo (D38) pozostają.
Referencja ViewportInput.cpp z Defect-Studio odczytana; nie przejmujemy jej dt×60.
Odrzucone: obrót LMB-drag, różne gesty Qt/ImGui i uzależnienie czułości od fps/DPI.
Testy wymagają macierzy przycisków/modyfikatorów obu adapterów, focus/capture/release,
repeat/rezerwacji, znaków i czułości, DPI/fps, resetu oraz regresji CE no-op.

**D48. Szybkie wejście: pula live, potem prefetch N+1 — decyzja 2026-10-23.**
Powód: zimny import backendu dominuje wejście na slajd. Pomiar Claude, Windows,
i7-13700KF: live manimgl 1,6–1,8 s, import manimlib ~1,4 s przy
`pyglet.options["shadow_window"]=False`, spawn ~0,15 s, budowa/pierwsza klatka
~0,2–0,3 s; import CE ~0,9 s. Istniejąca pula dekoderów plików daje 83–130 ms.
To pomiar wejściowy, nie zaliczenie D48. Zmienia odroczenie optymalizacji live w 10d;
nie zmienia D31/D39–D41 ani historii i semantyki nawigacji.

Pula GL i CE osobno, **2 bezczynne procesy na silnik użyty w bieżącym decku**,
uzupełnianie asynchroniczne po pobraniu. Silnik z manifestu/modelu, domyślnie manimgl;
nie rozgrzewać nieużytych. POOL_READY oznacza import, READY nadal pierwszą klatkę sceny.
Bez pliku autora/sceny/kontekstu GPU przed przydziałem; GL bez shadow_window, CE
tempconfig dopiero dla spec. Jedna scena na proces do końca życia, nigdy powrót do puli:
globalny stan GL/config/cache shaderów i izolacja błędów wykluczają podmianę sceny;
trwały live 5g nadal może utrzymywać dwie sesje równocześnie.

Lock i kanały control/bootstrap trzeba utworzyć przy spawn (SemLock nie przesyłamy
później zwykłym Pipe); LiveSpec i nazwę SharedMemory można dosłać po starcie.
SHM o rozmiarze spec tworzy rodzic dopiero po przydziale, sprząta po exit.
Wspólny LiveSession daje **parytet puli Qt/ImGui**; capture_first_frame bez puli pozostaje
zimny. Brak gotowego workera dopuszcza zimny start w budżecie, bez blokowania GUI.
take zwraca worker albo None natychmiast; LiveSession.start i Source.prepare/start
zgłaszają żądanie, a waiting_slot ponawia admisję przez poll wraz z odbiorem exit.
Bez blokującego oczekiwania w GUI. Nowe entry_id anuluje stare żądanie (prefetch wiąże
token); deadline D41 od nawigacji obejmuje czekanie, nie restartuje po zwolnieniu slotu.
Właściciel decku Qt przekazuje pełną konfigurację silników, pompuje pulę także bez
aktywnego live (również na początkowym slajdzie plikowym), zamyka nieużyty zapas po
zmianie decku i obejmuje pulę końcowym shutdown.
Czekający worker wykrywa EOF/śmierć rodzica co ≤0,25 s i kończy w ≤1 s; deadline importu
5 s, najwyżej jedna ponowna próba. Shutdown zatrzymuje refill, zamyka kanały, poll odbiera
exit/join; po 2 s kill i reap, bez pozostawionych procesów/SHM.

**Prefetch tylko ImGui PC**; Qt otrzymuje pulę, prefetch Qt i web poza 10d.
Podczas gotowego N przygotować jeden normalny N+1 w tym samym decku, także przy ukrytym
Info. Token wiąże rewizję decku, źródłowe entry_id, cel i pełne spec źródeł.
Pliki mają osobne źródła zatrzymane na pierwszej klatce t=0; po przejęciu nowa generacja,
entry_id i kotwica zegara/show_at w barierze, bez ponownego dekodowania początku.
Preview Info pozostaje osobne: własne pętle, ruch i czas; przejęcie wymagałoby resetu.
Miniatury D46 też nie są prefetchem; live preview nadal używa zapisanego thumbnail.

Live z puli buduje pierwszą klatkę bez enter_cue, wpisu EntryHistory, checkpointu ani
rezerwacji. Po READY zatrzymuje postęp sceny/updaterów, ale obsługuje transport/stop.
Tryb `LiveSpec.prefetch=False` domyślnie wyłączony; włączony pomija także aktualizacje
dt=0, kończy hold dopiero przy właściwych operacjach wejścia D41, bez sztucznego cue.
Techniczna granica READY prefetcha dostaje ACK w 2 s bez postępu i zwolnienia D31;
właściwa granica wejścia ma nowy frame_id i osobny ACK po kompozycji. Live bez session_id,
także bez cue, po przyjętym next dostaje adopt_prefetch skorelowane
session/generation/entry_id/request_id: granica wejścia → kompozycja/ACK → release na
wspólnym starcie D31. Release kończy hold i zachowuje pauzę do resume; stare komendy/ACK
ignorowane. Bez sztucznego cue/historii.
build_objects może mieć efekty I/O autora; nie gwarantujemy ich cofnięcia.
Zgodne sąsiednie przejęcie D39 ma pierwszeństwo per warstwa, bez duplikowania tej sesji.
Dopiero zatwierdzony normalny next przyjmuje prefetch, nadaje entry_id i wykonuje zwykłe
przygotowanie D39–D41 (before, rezerwacja, cue jak zimne next, granica, kompozycja, ACK,
release); samo READY nie zwalnia bariery. Własność procesu/buforów przekazywana raz.
Przy częściowym trafieniu reszta startuje normalnie. Deadline przygotowania wejścia 5 s
od faktycznego next, ACK 2 s; spekulacja osobno 5 s do przygotowania wraz z technicznym
ACK. Potem jej deadline wygasa; gotowy cel czeka do przyjęcia/anulowania także >5 s,
bez timeoutu pierwszej granicy transportowej.
←/V/R, skok start_at poza no-op, inny cel, zmiana decku/spec, błąd i timeout odrzucają
prefetch i stare wyniki, bez zmiany historii/degradacji aktywnej sesji. Bez retry błędnego
celu do zmiany wejścia. Reverse i skoki bez prefetcha. Pętla N utrzymuje przygotowany cel;
auto_next/skip_all przejmują go tylko po faktycznej decyzji reducera o normalnym N+1.
Koniec decku/wrap i exit_after_last_slide nie uruchamiają spekulacji między deckami;
shutdown zamyka ją wraz z pulami.

Budżet PC doprecyzowuje D46: **B = 2S + P + F + 1 + 4 + 2E** żywych dzieci playera,
S = maks. źródła procesowe slajdu (pliki/live), P = maks. plikowe źródła preview,
F≤S = maks. źródła prefetcha, E≤2 = użyte silniki decku. 2S obejmuje bieżące i poprzednie/
kończące sesje, 1 miniaturę, 4 zapas dekoderów, 2E zapas live; przy S=P=F=4, E=2: 25.
Kończące zajmują sloty do exit także przy wielokrotnym anulowaniu.
Importujące/uruchamiane procesy także zajmują sloty; przy zmianie decku do zebrania
starych dzieci limit max(B starego, B nowego), następnie B nowego, bez sumowania pul.
Admisja wszystkich startów PC respektuje B; scena/restore 5g > preview > prefetch > miniatury > zapas,
zwalniać od końca. Prefetch może być częściowy/pominięty. To rozszerza brak globalnej
admisji z rundy 22, nie zmienia puli plików w limit czterech aktywnych procesów.
Bufory/tekstury i kopie robocze prefetcha ≤128 MiB CPU+GPU; poza limitem warstwa pomijana.
RSS importów oraz RAM/VRAM scen/backendów mierzyć osobno, bez gwarancji całkowitego
limitu pamięci; przy błędzie alokacji wycofać spekulację. Checkpointy nadal według D40.

Odbiór: nowy live z rozgrzanej puli **≤0,5 s p95** od next do kompozycji/ACK pierwszej
klatki, bez enter_cue i bez prefetcha; GL/CE osobno, 10 wejść rozgrzewki + 100 pomiarów,
3 serie na sprzęcie powyżej. Powtórzyć z prefetchem przy pełnym obciążeniu D46;
raportować zimne nietrafienia, RSS/VRAM i wszystkie procesy. Testy obejmują brak mutacji
historii przez prefetch przy ←, pierwszeństwo adjacent, barierę/ACK, anulowanie/stare wyniki,
pełne B z opóźnionym exit i nową nawigacją bez blokowania GUI, hold >5 s przed
checkpointem/kompozycją/ACK wejścia, next bez session_id/cue i podczas pauzy (GL/CE),
pulę Qt na początkowym slajdzie plikowym offscreen i śmierć osieroconych workerów.
Szczegóły, pliki, kolejność i stop 2× w PLAN 10d.

Odrzucone: **cache wyrenderowanych animacji live** — obraz zależy od czasu cue i kamery
prelegenta; deterministyczne treści są zwykłymi slajdami plikowymi. Także: wiele scen
w jednym procesie, przejęcie ruchomego preview, spekulacyjne enter_cue/historia,
prefetch wszystkich slajdów i nieograniczony zapas procesów.

**D49. Edycja notatek w Info z zapisem obok decku — ImGui PC (rozszerza D46), 2026-10-25.**
Decyzja prelegenta po próbie 2026-10-24: notatki edytowane w Info podczas prezentacji,
z obsługą Markdown i podpowiedziami, zapis do pliku obok decku `<folder>/<Scene>.notes.md`.
Plik to nakładka: zawiera tylko slajdy z nadpisaniem i wygrywa z notatkami z renderu; kod
sceny (`next_slide(notes=...)`), JSON decku i katalog plików renderu bez zmian, więc nakładka
przetrwa ponowny render. Nagłówek `<!-- manim-cue notes slides=K -->` kontroluje strukturę:
K ≠ liczba slajdów renderu (albo brak nagłówka) wstrzymuje nakładkę w obu playerach do
świadomego „Zastosuj do obecnych slajdów” — H nie wykrywa wstawienia slajdu z pustymi
notatkami (runda 31). Sekcja zaczyna się od wiersza `<!-- manim-cue slide N base=H -->`
(N od 1, H = 8 znaków hex SHA-256 notatek modelu po normalizacji LF), treść z dokładnie jednym
terminatorem `\n`, round-trip bez strip. Treść równa notatkom z renderu usuwa sekcję —
„przywróć z renderu” jest zwykłą, cofalną edycją. Różne H oznacza zmianę notatek w kodzie po
edycji: nakładka nadal wygrywa, Info pokazuje konflikt. Zapis atomowy (zamknięty plik
tymczasowy w tym samym katalogu, `os.replace`) z ponownym odczytem i podmianą tylko sekcji
brudnych slajdów; równoczesne zapisy innych procesów nieobsługiwane. Plik niepoprawny
składniowo lub z błędnym UTF-8 przełącza Info w tryb tylko do odczytu i nie jest nadpisywany;
sekcje spoza zakresu decku są zachowywane. Ochrona danych: brudne bufory per (ścieżka, N) żyją
poza widokiem Info do udanego zapisu; błąd zapisu (także sharing violation) zostawia bufor
i ponawia; przy wyjściu ratunek z unikalną nazwą bez nadpisania obok decku, potem w katalogu
tymczasowym, a gdy oba zawiodą — treść na stderr i do schowka z komunikatem.

Edytor: `imgui_color_text_edit.TextEditor` z imgui-bundle 1.93 (Markdown, zawijanie, undo),
przełącznik podgląd/edycja w panelu notatek, font notatek. Fokus edytora lub jego popupu
ustawia `editing_markdown` routera — klawisze i gesty playera, łącznie z Q i strzałkami, nie
działają podczas pisania; Esc najpierw zamyka podpowiedzi, potem oddaje fokus. Podpowiedzi:
składnia Markdown na początku wiersza, fragmenty inline (Ctrl+Space, otoczenie zaznaczenia),
komendy LaTeX po `\` w `$…$`/`$$…$$` z listy obsługiwanej przez ścieżkę wzorów D46;
Ctrl+B/Ctrl+I (Ctrl bez Alt — AltGr). Wykonalność przejęcia klawiszy przez popup, AltGr,
fokusu i undo własnych komend warunkowa do bramek B1–B6 w PLAN.
Autozapis 500 ms po zmianie oraz przy zmianie slajdu, przejściu do podglądu, ukryciu Info
i wyjściu. Qt czyta nakładkę bez edycji (te same notatki w obu playerach). Web (10b) dzieli
model, komendy i podpowiedzi; trwały zapis w przeglądarce ustali kontrakt 10b.
Odrzucone: zapis do JSON decku (ginie przy renderze), edycja kodu sceny, mapowanie po treści
lub nazwie pliku wideo (hash zmienia się z animacją), autouzupełnianie słów z decku (YAGNI).
Bramki, testy i budżet w PLAN 10e.

---

## Zakres, którego nie wolno rozszerzyć bez decyzji

**Synchronizacja co do klatki.** Warstwy startują i pauzują razem (D17); D43 dopuszcza wewnętrzny zegar plików PC, bez gwarancji frame-lock/live sync.
Publiczny zegar główny, seek i frame-lock to dni pracy i realne ryzyko (dryf, różne długości klipów, seek).
Do czterowidokowej sceny seminarium wystarczy jedna scena Manima z czterema panelami albo warstwy
o równej długości.

**Odrzucone kierunki, z powodami:** łatanie trzech równolegle żyjących wersji Manima (CE 0.22,
manimgl 1.7.2, manimgx 0.1.1) — scena nad istniejącym API daje ten sam efekt bez trzech upstreamów
do utrzymania; fork manim-slides (D13) tego nie zmienia, bo manim-slides to nie Manim.
Przechwytywanie przez OBS jako architektura — kompozytuje niezależne źródła, więc nie daje jednego
punktu sterowania (był przykładem, nie celem).

---

## Konwencja nazw

Identyfikatory **po angielsku** (`build_objects`, `next_command`, `PRESETS`, `pop_line`).
Docstringi i komentarze po polsku. Projekt macierzysty ma dziś stan mieszany i to jest uznane
za błąd — nie powtarzać go tutaj.

**Wyjątek: kod z forka (`src/manimcue/slides/`).** Komentarze i docstringi upstreamu zostają po
angielsku, żeby diff z kolejnym wydaniem manim-slides dał się nałożyć. Nasze zmiany w tym kodzie —
po polsku.

---

## Punkt integracji z seminarium

Gdy projekt będzie gotowy do podłączenia, wchodzi **przez klasy bazowe** z decyzji D10 tamtego
planu (`SeminarScene` / `SeminarScene3D` w `deck/base.py`), nie przez sceny treściowe. Wtedy panel
NV⁻ w scenie czterowidokowej (D9 tamtego planu) można podmienić z sześciu kadrów PNG na warstwę
live — ale **do tego czasu nic w S1 od tego nie zależy** (R8 tamtego planu).
