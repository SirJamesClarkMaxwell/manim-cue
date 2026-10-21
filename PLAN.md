# manim-cue — plan rozwoju

Stan: **faza 0 zamknięta — dziewięć na dziewięć kryteriów (2026-10-19, Windows 11).**
Faza 1 ma spisane decyzje w `SPEC.md` (D1-D8), kodu fazy 1 jeszcze nie ma.
Kod fazy 0: `src/manimcue/live_scene.py` (scena), `src/manimcue/cue.py` (klient testowy),
`tests/test_live_scene.py` (21 testów). Procedura testu w oknie: `README.md`, sekcja „Testowanie".

---

## Faza 0 — PoC żywej sceny (jedyna aktywna)

**Cel:** `Scene` manimgl, która żyje, przyjmuje komendy po TCP z `127.0.0.1` i wyzwala animacje
z tablicy presetów. Architektura, transport i protokół są już wybrane w `SPEC.md` z podanymi
powodami — faza 0 je implementuje, nie rozważa od nowa.

**Pliki:** `src/manimcue/live_scene.py` (klasa `LiveScene`), `tests/`.

**Zakres:** jeden klient, jeden proces, jeden system (Windows). Komendy UTF-8, jedna na linię.
Model bezpieczeństwa jawnie niezabezpieczony.

**Kryteria akceptacji:** dziewięć punktów z `SPEC.md`. Wszystkie, nie większość.
**Wynik: 9/9.** Szczegóły i dowody w `SPEC.md` pod kryteriami.

**Co wyszło dopiero w teście wizualnym:** trzecia pułapka — `select` iterowany z listenerem
przed klientem gubił komendy, gdy poprzedni klient rozłączył się w czasie animacji. Opis
i test regresyjny w `SPEC.md`. Ani pięć rund recenzji, ani testy bez okna tego nie wyłapały;
wyłapał pierwszy przebieg na żywej scenie.

**Limit:** pierwotny szacunek ~1 h. Przy przekroczeniu ~2 h — zatrzymać się i zgłosić, zamiast
dociągać. Zakres był wyceniany jako zamknięty właśnie po to, żeby ten limit miał sens.

**Dwie pułapki opisane w `SPEC.md`** (brak `accept()`, dekodowanie UTF-8 per `recv()`) są znane
i mają podane rozwiązania. Jeśli implementacja na nie wpadnie, to znaczy, że `SPEC.md` nie został
przeczytany.

---

## Faza 1 — cue sheet i prowadzenie prezentacji (następna w kolejce)

Presety przestają być słownikiem w kodzie i stają się **plikiem**: nazwana lista cue'ów, każdy
z notatką dla prelegenta. Scenę da się przestawić bez edycji Pythona, a lista cue'ów jest
dokumentem, który można czytać przed wystąpieniem.

**Trzy otwarte pytania są rozstrzygnięte** w `SPEC.md`: TOML (D4), cue może być kilkoma
animacjami (D5), cue nie ma deklarowanego czasu trwania (D6).

**Doszedł drugi powód tej fazy.** Po przejściu fazy 0 prelegent ocenił, że brakuje nie żywego
renderu, a sposobu prowadzenia: niezależnych strzałek, informacji co będzie dalej i notatek —
czyli tego, co daje `manim-slides`. Decyzje D1-D3 (transport klawiaturowy, priorytet klawisza,
cofanie jako skok stanu) i D7 (widok prelegenta w terminalu, nie drugie okno) odpowiadają na to.

**Zrobione zaliczkowo, przed resztą fazy 1:** strzałki `→`/`←` z sekwencją cue'ów i pozycją
w logu, **animowane cofanie** (D3) oraz **zapętlenie cue** (D9). `→` i `←` potwierdzone w oknie
na docelowym sprzęcie.

**Zostaje do zrobienia:** cue sheet w TOML (z flagą `live` per cue, D11), notatki, widok
prelegenta w terminalu (bieżące cue, następne, notatka, pozycja `3/8`), krok prerenderu
wytwarzający klatki dla cue nie-live i miniatury do podglądu.

**Zrobione dodatkowo:** przerywalne animacje (D10) — klawisz albo komenda urywa cue w dowolnej
klatce, zamiast czekać do jego końca; zmierzone i potwierdzone w oknie. Plus komendy `next`/`back`
w gniazde, żeby ta sama ścieżka dała się skryptować i mierzyć.

**Odroczone, nie w tej fazie:** wizualny podgląd następnego cue (D8) — jeśli wejdzie, to przez
prerenderowane miniatury, nie przez spekulatywny render ani drugie okno GUI.

---

## Faza 2 — integracja z seminarium

Podłączenie do `scientific-student-seminaries`. **Punkt wejścia: klasy bazowe `SeminarScene`
i `SeminarScene3D` w tamtym `deck/base.py`**, nie sceny treściowe — tak stanowi decyzja D10 tamtego
planu.

Efekt docelowy: panel NV⁻ w scenie czterowidokowej (decyzja D9 tamtego planu) przestaje być
sześcioma prerenderowanymi kadrami PNG i staje się żywym renderem.

**Kształt techniczny doszedł w fazie 1:** selektywny live-render (D11 w `SPEC.md`). Panel NV⁻
liczony na żywo, pozostałe trzy z prerenderowanych klatek, wszystko w **jednej** scenie manimgl —
bez kompozytowania dwóch źródeł, które jest fazą 3.

**Warunek wejścia:** faza 0 przechodzi na docelowym komputerze prelegenta — dwa monitory i fokus
po powrocie były wymieniane jako do sprawdzenia na sprzęcie. Dopóki to nie nastąpi, seminarium stoi
na kadrach PNG i **nic w nim od tego projektu nie zależy** (ryzyko R8 tamtego planu).

---

## Faza 3 — warunkowa: wiele źródeł

Synchronizacja kilku niezależnych źródeł, np. żywe okno manimgl obok nagranego decku.

**Nie wchodzi, dopóki nie pojawi się realna potrzeba.** Powód jest zapisany w `SPEC.md`: do scen
wielopanelowych to **nie** jest potrzebne, bo jedna scena Manima z czterema panelami renderuje się
do jednego klipu zsynchronizowanego z konstrukcji. Dni pracy i realne ryzyko (dryf, różne długości
klipów, seek) za efekt, który w głównym przypadku użycia jest darmowy inaczej.

---

## Poza zakresem całego projektu

- Fork albo łatanie Manima (CE, GL, GX) — projekt jest sterownikiem nad API.
- Przechwytywanie ekranu / OBS jako architektura.
- Uwierzytelnianie i transport sieciowy między hostami. Zakres to lokalne `127.0.0.1`.
- Back-pressure i kolejka aplikacyjna — bufor gniazda wystarcza dla kilku komend na sekundę,
  a obietnica jest w `SPEC.md` świadomie zawężona.
- Dane grupowe i cokolwiek z teorii grup — to jest `groupy`, nie tutaj.
