# F5, kryterium 8 — diagnoza sondy i dekodowania

Data: 2026-10-23. `develop`, główne drzewo, bez commita i zmian `.venv`.

## Przyczyna i zakres wniosku

**Sonda pikselowa nie jest warunkiem blokady. Problem reprodukuje się w samym Qt,
bez kodu playera/warstw manim-cue.** Przy wielu równoczesnych dekoderach i malowaniu
podglądu Info główny wątek zatrzymuje się w natywnej ścieżce mapowania/konwersji
klatek. W auto uchwycono oczekiwanie NVIDIA podczas transferu D3D11/GPU → CPU.
Wywołuje tę ścieżkę również `QGraphicsVideoItem::paint()`, zatem usunięcie
`toImage()` z sondy nie usuwa odczytów GPU wykonywanych przez renderer Qt.

Dowód rozstrzygający: [reproduktor w samym Qt](f5-crit8-qt-reproducer.py)
tworzy dwie kompozycje (bieżąca i następna, każda baza + N klipów) oraz drugi widok
bieżącej kompozycji. Nie importuje manim-cue ani Manim, nie mapuje klatek, nie
wywołuje `toImage()`, nie zachowuje `QVideoFrame`, nie ma bariery, pauzowania ani
live. Używa zwykłej `QApplication.exec()`, zamiast `pump/processEvents` sondy.
Dla N=3 odtworzono timeout; [stos natywny](f5-crit8-qt-only-native-3.txt)
pokazuje w głównym wątku:

```text
NtWaitForSingleObject
nvwgf2umx.dll
 d3d11.dll
 avutil-61.dll
 ffmpegmediaplugin.dll
 QVideoFrame::map
 QVideoFrame::paint
 QGraphicsVideoItem::paint
 QGraphicsView::paintEvent
 ... QEventLoop / obsługa zdarzeń Qt
```

Zrzuty wykonano Windows DbgHelp (`StackWalk64`, kontekst wątków własnego procesu).
Symbole prywatne Qt/FFmpeg/NVIDIA nie były dostępne: nazwy najbliższych eksportów
z dużym offsetem nie identyfikują dokładnej funkcji wewnętrznej. Istotny jest
łańcuch modułów i eksportowane `QVideoFrame::map/paint`.

Powtórzono też dokładnie zapisaną wersję reproduktora: ponowny timeout 65 s
([status](f5-crit8-qt-exact-status.json)). Jej [drugi stos](f5-crit8-qt-exact-native.txt)
zatrzymuje GUI w konwersji `qImageFromVideoFrame → QVideoFrame::toImage → paint`
i pokazuje `QCoreApplication::exec/QEventLoop::exec` poniżej. Odczyt/konwersja
obrazów pozostają więc w rendererze nawet przy całkowitym braku sondy pikselowej.

**Nie ustalono wewnętrznego mechanizmu sterownika/backendu:** wyczerpanie puli
powierzchni, synchronizacja sterownika i inne przyczyny oczekiwania pozostają
hipotezami. Sam stos nie dowodzi wyczerpania puli ani trwałego deadlocka; występują
również wielosekundowe zastoje zakończone powrotem. Zmiana trybu HW nie jest
uniwersalnym rozwiązaniem dla całej macierzy. Timeoutów trybu programowego nie
przypisuję automatycznie temu samemu oczekiwaniu NVIDIA.

Nie zmieniono playera ani warstw: problem występuje bez ich kodu, a eksperyment
ze zwalnianiem ich referencji nie usunął objawu. Nie ma dowodu uzasadniającego
usunięcie ochrony przed czarną klatką lub wymuszenie globalnego backendu.
To diagnoza natywnej ścieżki Qt/FFmpeg/NVIDIA pod obciążeniem, a nie naprawa Qt.

## Hipotezy A i B — sprawdzenie kodu

- Domyślna sonda przechowuje wyłącznie pary liczb `startTime()/endTime()`.
  Nie mapuje pamięci i nie zatrzymuje referencji do `QVideoFrame`.
  `--pixel-probe` zachowuje wcześniejsze `toImage()` + CRC32 pełnego obrazu.
  Live w obu trybach nadal liczy CRC32 `frame.pixels`.
- Poprzednia sonda podpinała się do bazy i klipów bieżącej kompozycji, **nie** do
  sinków następnego slajdu w Info. Odczyty Info wynikają z malowania widoków Qt.
- `ClipGroup.frames` trzyma ostatnią klatkę każdego klipu (nadpisuje wpis),
  `base_frame` pierwszą klatkę bariery aż do `clear()`, a `Player.frame` ostatnią
  bazę. To ograniczona liczba referencji, nie lista rosnąca z czasem.
  `PreviewClips` nie ma własnego magazynu klatek.
- Przywracanie niepoprawnej klatki jest synchroniczne; poprawna przywrócona
  klatka kończy rekurencję. Sonda odcina nieaktualny sygnał porównaniem z sinkiem.
- Kontrola diagnostyczna zwalniająca referencje `frames`, `base_frame` i
  `Player.frame` po barierze nadal zatrzymała N=3. Wyłączenie tylko dekoderów
  następnego slajdu, przy widocznym Info i obu widokach bieżącej sceny,
  zakończyło N=2 i N=3. To kontrola diagnostyczna, nie zmiana produktu.
- Liczba dekoderów przy Info: `2 × (1 + N)`, czyli 4/6/8; bez Info: 2/3/4.
  Live jest osobnym procesem OpenGL i nie jest konieczny do odtworzenia.

`uv run --frozen --with py-spy py-spy --version` nie powiodło się: pakiet nie
jest w cache, a `UV_OFFLINE=1`. Nie instalowano go i nie zmieniano `.venv`.
Użyto `faulthandler`, próby `QT_LOGGING_RULES=qt.multimedia*=true` i stosów
natywnych DbgHelp. Stos Pythona nadal wskazuje `measure_player.py:79`,
`app.processEvents()`; sam ten stos nie wskazywał przyczyny natywnej.
Komunikat `[av1_mf] could not find any MFT` występuje również w zakończonych
próbach z plikami H.264. Nie jest dowodem awarii dekodera AV1 tych materiałów.

## Macierz offscreen

Windows 11 build 26200, RTX 4060, sterownik NVIDIA 610.88 (`nvidia-smi`).
Python 3.13.2, Manim CE 0.22.0, manimgl 1.7.2, PySide6/Qt 6.12.0, qtpy 2.4.3.

1920×1080, H.264/60 fps, 2-sekundowe pętle CE; rozgrzewka 1 s, żądane okno 8 s.
Każda komórka to osobny proces. Macierz rozstrzygająca była wykonywana
**sekwencyjnie**. Limit diagnostycznego nadzorcy: 65 s od startu procesu,
łącznie z renderem i inicjalizacją. `timeout` nie oznacza 0 fps. Próby mogą
przekroczyć żądane 8 s, jeśli natywna obsługa zdarzeń późno odda sterowanie.
HW „auto” oznacza usuniętą zmienną; „off” — dokładnie
`QT_FFMPEG_DECODING_HW_DEVICE_TYPES=,`. Auto nie gwarantuje HW dla każdego strumienia.

| Sonda | HW | Info | Live | N=2 | N=3 |
|---|---|---|---|---|---|
| lekka | auto | tak | nie | timeout65 | timeout65 |
| pikselowa | auto | tak | nie | timeout65 | timeout65 |
| lekka | off | tak | nie | OK 8,00 s; baza 28,6 fps | OK 8,40 s; baza 0,6 fps |
| pikselowa | off | tak | nie | OK 8,02 s; baza 22,2 fps | timeout65 |
| lekka | auto | nie | nie | OK 8,00 s; baza 46,2 fps | OK 8,02 s; baza 34,9 fps |
| pikselowa | auto | nie | nie | OK 8,03 s; baza 5,4 fps | OK 8,03 s; baza 26,5 fps |
| lekka | off | tak | tak | OK 8,03 s; baza 22,3 fps | timeout65 |
| lekka | auto | nie | tak | OK 8,01 s; baza 44,1 fps | OK 8,01 s; baza 30,8 fps |

[Pełne dane macierzy](f5-crit8-matrix.json). OK oznacza zakończony proces; fps i czas pokazują, czy zakończenie było płynne.

Pierwsze rozpoznawcze przebiegi częściowo się nakładały; ich osiągi i timeouty
nie są użyte jako rozstrzygająca macierz. Zachowano je jako materiał roboczy.
Pierwszy wrapper kontroli live nie miał ochrony `__main__` wymaganej przez
Windows multiprocessing; te wyniki odrzucono i zastąpiono powtórkami uruchamianymi
bezpośrednio przez `examples/measure_clips.py`. Wiersze z live w macierzy pochodzą
wyłącznie z poprawnych powtórek.
Kontrole bez bieżącego widoku, bez referencji i bez dekoderów podglądu opisano
osobno; nie są domyślnymi ustawieniami narzędzia.

| Kontrola (lekka, auto, bez live) | N=2 | N=3 |
|---|---|---|
| Ukryty tylko bieżący widok Info | timeout65 | timeout65 |
| Zwalnianie referencji ochronnych | OK 25,24 s; baza 0,8 fps | timeout65 |
| Zatrzymane tylko dekodery podglądu | OK 8,01 s; baza 49,2 fps | OK 8,01 s; baza 35,4 fps |

## Końcowy pomiar offscreen — lekka sonda

[Pełny wynik JSON](f5-crit8-offscreen.json),
[log](f5-crit8-offscreen.log).

```powershell
$env:UV_CACHE_DIR='D:/Programming/Python/manim/manim-cue/.cache/uv'
$env:UV_OFFLINE='1'
$env:TMP='D:/Programming/Python/manim/manim-cue/.tmp'
$env:TEMP=$env:TMP
$env:PYTHONIOENCODING='utf-8'
$env:QT_QPA_PLATFORM='offscreen'
Remove-Item Env:QT_FFMPEG_DECODING_HW_DEVICE_TYPES -ErrorAction SilentlyContinue
uv run --frozen python examples/measure_clips.py --clips 1,2,3 --resolution 1920x1080 --warmup 3 --seconds 20 --output reports/f5-crit8-offscreen.json
```

| N | Strumień | Odebrane fps | Nowe znaczniki / zmiany live fps | p50/p95/max [ms] | Straty~ |
|---|---|---:|---:|---|---:|
| 1 | base | 27,22 | 27,22 | 28,93/82,75/296,40 | 656 |
| 1 | clip_1 | 26,92 | 26,92 | 26,31/84,49/285,10 | 662 |
| 1 | live | 42,21 | 37,51 | 23,94/36,42/164,16 | 450 |
| 2 | Timeout procesu: 113.0 s | — | — | — | — |
| 3 | Timeout procesu: 113.0 s | — | — | — | — |

| N | Czas okna [s] | Info | Start [ms] | Qt opóźnienie p95/max [ms] | CPU [% rdzenia] |
|---|---:|---|---:|---|---:|
| 1 | 20,021 | True | 0,01 | 24,35/86,40 | 126,35 |
| 2 | — | — | — | — | — |
| 3 | — | — | — | — | — |

Czas całego końcowego przebiegu: **255,15 s**, z renderowaniem, inicjalizacją i timeoutami.

`received_frames` liczy zaakceptowane sygnały. W lekkiej sondzie `changed_frames`
oznacza zmianę pary znaczników czasu, nie potwierdzoną zmianę pikseli. Nieznane
znaczniki (-1) nie pozwalają wykrywać zmian — syntetyczne materiały tej próby
mają znaczniki. Pętle przechodzą z końcowego znacznika do początkowego.
Start oznacza różnicę czasu pierwszych nowych znaczników po zwolnieniu bariery,
a nie rozpoznanie czerwonego/zielonego piksela; historyczne starty z CRC mają
inną definicję obserwacji.

To odbiór w GUI, nie fizyczne wyświetlenie. Straty~ to
`max(0, round(czas × 60) - liczba_zmian)`, nie licznik dekodera.
Percentyle: najbliższa ranga; interwały i najdłuższa cisza są osobno w JSON.
QTimer 1 ms: opóźnienie = `max(0, odstęp callbacków - 1 ms)`, także końcowy
odcinek okna. Wynik zawiera koszt pompy zdarzeń, sondy i timerów Windows.
CPU = `process_time / czas × 100%` (100% = jeden rdzeń); CPU live nie zmierzono.

## Historyczne pomiary pikselowe

[Okna Claude'a](f5-crit8-window.json): RTX 4060, Windows 11, prawdziwe okna,
sonda pikselowa, Info i live, rozgrzewka 3 s, okno 20 s. Plik pozostawiono bez zmian.

| N | Strumień | Odebrane fps | Zmiany fps | p95/max [ms] |
|---|---|---:|---:|---|
| 1 | base | 6,39 | 6,39 | 400,45/633,76 |
| 1 | clip_1 | 19,53 | 19,53 | 136,23/282,43 |
| 1 | live | 34,37 | 30,28 | 45,02/173,61 |

N=1: start 549,49 ms; CPU 134,89% rdzenia.

N=2 i N=3: timeout 113 s, stos w `processEvents()`. Wynik jest historyczny:
nie porównywać jego fps ani startu z lekką sondą jako izolowanego efektu
optymalizacji aplikacji. Nie wykonano nowego pomiaru w prawdziwych oknach.
[Stary offscreen z CRC](f5-crit8-offscreen-pixel-history.json) zachowano przed
nadpisaniem: N=1 base 24,94, clip_1 14,44, live 32,46 zmian/s; N=2/3 timeout 113 s.

## Powtórzenie reproduktora Qt

Reproduktor potrzebuje niezależnych plików `0.mp4`…`3.mp4` w jednym katalogu.
W tej sesji wygenerowano je tym samym `make_video()` co pomiar, kopiując bazę
oraz trzy klipy do `.tmp/qt-media/`. Nie używa kodu aplikacji podczas odtwarzania.

```powershell
uv run --frozen python -c "import sys,shutil; from pathlib import Path; sys.path.insert(0,'examples'); from measure_clips import make_video; p=Path('.tmp/qt-media'); p.mkdir(parents=True,exist_ok=True); [shutil.copyfile(make_video(p,str(i),(1920,1080),base=i==0),p/f'{i}.mp4') for i in range(4)]"
uv run --frozen python reports/f5-crit8-qt-reproducer.py 3 .tmp/qt-media
```

Ustawić te same zmienne UV/TMP/Qt co powyżej. Uruchomić z zewnętrznym limitem
czasu i zakończyć wyłącznie własny proces po timeout — wewnętrzny QTimer 10 s
nie przerywa natywnego oczekiwania. Wykonany wariant N=2 trwał 14,55 s przy
żądanych 10 s; N=3 przekroczył 65 s. Stos N=3 zebrano przed zakończeniem procesu.
Pierwsza wersja kontroli nie dopasowywała widoków do całej sceny i pomijała
malowanie części klipów; jej wyniki odrzucono. Cytowane wyniki dotyczą
`fitInView` we wszystkich trzech widokach.

Źródło Qt potwierdza, że malowanie klatki przez QPainter zwykle odbywa się bez
akceleracji sprzętowej: [QVideoFrame::paint](https://doc.qt.io/qt-6.12/qvideoframe.html#paint).
Nie należy utożsamiać sprzętowego dekodowania z bezkopiowym malowaniem.

## Zmiany, walidacja i czas

Narzędzie: lekka sonda domyślnie, `--pixel-probe`, `--no-info`, przekazanie flag
procesom dla listy N oraz jawna metoda detekcji w JSON. Bez zmian zachowania
playera, warstw, zależności, `.venv` i istniejącego `custom_config.yml`.
Nadzorca toleruje również Windows `WinError 87`, gdy zapisany proces live
zakończył się przed sprzątaniem timeoutu; ten przypadek ma osobny test.
Test jednostkowy zabrania odczytu pikseli w lekkiej ścieżce; testy dymne używają
prawdziwego Qt, sprawdzają obie sondy, Info oraz propagację flag do N=2/3.

Walidacja (Claude, po przerwaniu codex limitem użycia): `ruff check` i `ruff format --check` dla `examples/measure_clips.py`, `tests/test_measure_clips.py` i reproduktora — OK; `pytest tests/test_measure_clips.py` — **4 passed**. Kod `src/` bez zmian, więc pełnego zestawu nie powtarzano. Surowe artefakty macierzy, do których raport nie odsyła, przeniesiono do ignorowanego `.tmp/f5-crit8-raw/`.

Czas: diagnoza codex ok. 45 min (08:36–09:21), przerwana limitem użycia przed zapisem pliku wyjściowego; raport domknął Claude.

**Decyzja prelegenta (2026-10-23):** zamiast łatania ścieżki Qt — PoC playera webowego (przeglądarka + backend Python), porównanie z obecnym Qt; `experiments/f5w_web/`.

Ograniczenia: brak nowego pomiaru w oknach, brak prywatnych symboli sterownika,
brak dowodu konkretnej awarii puli powierzchni. Offscreen nie zalicza kryterium
wydajności prelegenta. Bez commita, stash, reset, checkout i worktree.
