# manim-cue — specyfikacja

_Wyjęte z planu seminarium (`STUDIA/scientific-student-seminaries/group-theory/PLAN.md`, decyzja D18)
po pięciu rundach adwersaryjnej recenzji z codex, 2026-10-19._
Ten plik istnieje po to, żeby nie wygrzebywać od nowa ustaleń, które już zostały
zweryfikowane w kodzie manimgl i przepuszczone przez pięć rund adwersaryjnej recenzji.
Pełna historia argumentów: `PLAN-REVIEW-LOG.md` w `scientific-student-seminaries/group-theory/`.

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

Obie wyłapane w rundzie 5 recenzji — nie powtarzać:

1. **Brak `accept()`.** Pierwsza wersja robiła `select.select([self.sock], ...)`, co zakłada **już
   połączone** gniazdo. Bez listenera i `accept()` pętla nie przyjmie pierwszego klienta i kod
   nie da się uruchomić. `select` musi patrzeć na **listener, dopóki klienta nie ma, i na klienta,
   gdy jest**.

2. **Dekodowanie UTF-8 per `recv()`.** `recv(...).decode("utf-8")` rzuci wyjątkiem, gdy pakiet TCP
   rozdzieli znak wielobajtowy — i framing po `\n` tego **nie** ratuje, bo kolejność operacji jest
   odwrotna. Poprawnie: buforować **bajty**, dzielić po `b"\n"`, dopiero kompletną linię dekodować.

---

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

**D4. Cue sheet w TOML.** Rozstrzyga pierwsze otwarte pytanie fazy 1: TOML, bo resztę ekosystemu
`uv` już w nim stoi, a `tomllib` jest w stdlib od 3.11 — zero nowych zależności. Pola na cue:
nazwa, kolejność, notatka dla prelegenta.

**D5. Cue może być kilkoma animacjami.** Rozstrzyga drugie otwarte pytanie: tak. Cue jest
callable'em, a nie jedną animacją — `pulse` już dziś woła `play()` dwa razy.

**D6. Cue nie ma deklarowanego czasu trwania.** Rozstrzyga trzecie otwarte pytanie: nie.
Czas wynika z animacji w środku; pole `duration` w cue sheet byłoby drugim źródłem prawdy
i rozjechałoby się z kodem przy pierwszej zmianie `run_time`.

**D7. Widok prelegenta: terminal jako minimum, drugie okno dopuszczone.** Bieżące cue,
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

**D11. Selektywny live-render — kierunek na fazę 2.** Wniosek prelegenta: nie każdy element scen
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

**D12. Silnik zostaje manimgl; manimgx odroczony.** Ustalone wspólnie po researchu: manimgx nie
ma udokumentowanego trybu interaktywnego (ani okna, ani pętli zdarzeń, ani krokowania klatek,
ani zdarzeń klawiatury), jego `present` to sekcje nagranej linii czasu, w Pyodide nie ma gniazd
TCP, a wersja 0.1.1 ma tydzień. Prelegent sam ocenił go jako „bardzo młody i niestabilny".
Sprawdzone też, czy alternatywą jest nowy renderer Manim CE: **nie ma go.** Najnowsze CE v0.21.0
(10 sierpnia 2026) przyspieszyło istniejący renderer Cairo 2,2× na scenach animacyjnych; plan
nowego backendu z wiki 2022 nie ma potwierdzenia w 2026. CE ma natomiast `-l/--live-preview`
otwierające żywe okno na rendererze OpenGL — czyli żywe okno nie jest wyłączną cechą manimgl,
gdyby kiedyś przyszło migrować.

---

## Zakres, którego nie wolno rozszerzyć bez decyzji

**Synchronizacja wielu strumieni wideo.** Osobna sprawa, dni pracy, realne ryzyko (dryf, różne
długości klipów, seek). **I nie jest potrzebna** do czterowidokowej sceny w seminarium: jedna scena
Manima z czterema panelami renderuje się do **jednego klipu**, zsynchronizowanego z konstrukcji.
Multi-video ma sens tylko dla naprawdę niezależnych źródeł — np. żywe okno manimgl obok nagranego
decku.

**Odrzucone kierunki, z powodami:** łatanie trzech równolegle żyjących wersji Manima (CE 0.22,
manimgl 1.7.2, manimgx 0.1.1) — scena nad istniejącym API daje ten sam efekt bez trzech upstreamów
do utrzymania. Przechwytywanie przez OBS jako architektura — kompozytuje niezależne źródła, więc nie
daje jednego punktu sterowania (był przykładem, nie celem).

---

## Konwencja nazw

Identyfikatory **po angielsku** (`build_objects`, `next_command`, `PRESETS`, `pop_line`).
Docstringi i komentarze po polsku. Projekt macierzysty ma dziś stan mieszany i to jest uznane
za błąd — nie powtarzać go tutaj.

---

## Punkt integracji z seminarium

Gdy projekt będzie gotowy do podłączenia, wchodzi **przez klasy bazowe** z decyzji D10
(`SeminarScene` / `SeminarScene3D` w `deck/base.py`), nie przez sceny treściowe. Wtedy panel NV⁻
w scenie czterowidokowej (D9) można podmienić z sześciu kadrów PNG na żywy render — ale **do tego
czasu nic w S1 od tego nie zależy** (R8).
