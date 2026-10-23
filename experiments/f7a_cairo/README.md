# Pomiar przed kontraktem 7a

Pełny pomiar po implementacji: `uv run --frozen python experiments/f7a_cairo/measure_live.py`.
Wynik: `reports/MEASUREMENT-7a.json` (lokalnie, poza repo). Trzy niezależne przebiegi ze zmienną kolejnością
rozmiarów, 2 s idle i 2 s rozgrzewki ruchu, następnie dokładnie 30 s próbek: porównanie
bajtów kolejnych obrazów całej treści, pełny payload SHM, OwnedFrame, QImage i QPixmap
jak w playerze (bez dodatkowej kopii QImage). Qt pompowane przez processEvents + sleep
1 ms jak w pomiarze F2; nie jest to pomiar rozkładu ticków QTimer ani fizycznego ekranu.
Ruch jest nieokresowym przejazdem markera przez 35 s; idle nie jest w liczniku fps.
Liczniki i timestampy są zamrożone na granicy okna. Po nim 20 ciepłych komend na przebieg,
CPU idle jako procent jednego rdzenia; render/update/publikacja z sum liczników workera
dla całej sesji, osobno kopia odbiornika i Qt dla okna. Normalizacja alfy: brak (0 ms),
gwarancja obejmuje wyłącznie puste tło i pasy. Maksymalne odstępy i licznik >25 ms w JSON.
Koszt historii: `uv run --frozen python experiments/f7a_cairo/measure_snapshot.py`, wynik
`reports/MEASUREMENT-7a-snapshot.json`, 200 zapisów z limitem 50, zmiana liczby dzieci/wspólny
członek, osobno zapis/przygotowanie/odtworzenie i tracemalloc (z narzutem pomiaru).
Wyniki i ograniczenia końcowe: `../../reports/REPORT-7a.md`.

Z korzenia repozytorium, PowerShell (bez okna):

```powershell
$env:UV_CACHE_DIR='D:/Programming/Python/manim/manim-cue/.cache/uv'
$env:UV_OFFLINE='1'
$env:TMP='D:/Programming/Python/manim/manim-cue/.tmp'
$env:TEMP=$env:TMP
$env:QT_QPA_PLATFORM='offscreen'
uv run --frozen python experiments/f7a_cairo/measure.py
```

`results.json` zawiera środowisko, 30 klatek rozgrzewki i 240 próbek na przypadek,
medianę/p95 renderu oraz kopii, fps = 1000/średni czas renderu z kopią i surowe próbki.
Powtórne uruchomienie zastępuje wynik. TeX używa `.tmp/f7a-cairo`, nie zapisuje filmu.

Mierzymy `CairoRenderer.update_frame(scene)` z pełnym przerysowaniem, bez optymalizacji
`static_image`. Osobno `np.copyto` z `camera.pixel_array[::-1]` do wcześniej przydzielonego
bufora RGBA8: odwrócenie wierszy wymagane przez istniejący transport bottom-up.
Przy panelu bufor ma 538×648 (`round(0.28*1920)`, `round(0.6*1080)`), treść 538×303,
wyśrodkowana w pasach D34. Dwa pozostałe rozmiary: 960×540 i 480×270.
Pasy są inicjalizowane raz; tutaj nie zmieniają się między klatkami.

Geometrię aktualizujemy przed stoperem: to mikrobenchmark rysowania i kopii, bez
kosztu `play`, interpolacji, updaterów, TCP, blokady, SharedMemory i kopii odbiornika Qt.
FPS oznacza przepustowość tych dwóch operacji bez ograniczenia zegarem, a nie odebrane
różne klatki F2. Statyczne przypadki celowo renderują powtarzający się obraz.
Nie wolno przedstawiać wyniku jako zaliczenia F2 ani wydajności dowolnej sceny CE.

Odpowiedniki D22: first_frame, corners, move, interrupt_two_plays (geometria przejazdu),
add_remove (dwa obiekty z wygaszaniem), updater_wait (kropka), loop (obrót), tex.
Panel 2D: rotate, pulse, sweep; ThreePanel: zielony obracany kwadrat.
To odpowiedniki obciążenia, nie porty klas ani testy semantyki cue. StaticWait,
IdleUpdater, SlowBuild i wyjątki mają tę samą/prostszą geometrię; ich zachowanie musi
sprawdzić przyszły adapter. 3D pozostaje poza 7a. TeX ma jawny skip przy błędzie
kompilacji; pominięcia i przyczyna są zapisane w JSON.

Samokontrola: wyjście CE wyłączone, kształt/dtype RGBA, zgodność kopii wraz z orientacją
oraz czerwony piksel środka pierwszej sceny. Konstrukcja i kompilacja TeX są poza pomiarem.
Krótki mikrobenchmark ma zmienność CPU; raport pokazuje p95, nie wybiera najszybszej próby.
Wynik nie obejmuje przezroczystego tła ani normalizacji alfy — to bramka implementacji.
