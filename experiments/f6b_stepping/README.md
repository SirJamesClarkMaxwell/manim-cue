# PoC F6b — krokowanie sceny-dziecka w gospodarzu (greenlet, jeden wątek)

Nie jest częścią pakietu: wymaga `greenlet`, którego projekt nie deklaruje (decyzja w `PLAN.md`,
faza 6b). Uruchomienie z katalogu tego pliku:

```bash
uv run --project ../.. --with greenlet python -m manim render host_scene.py Host -ql --disable_caching
uv run --project ../.. --with greenlet python -m manim render bench_scene.py BusyHost -qm --disable_caching
```

`host_scene.py`: dziecko (zwykła `Scene` CE) wchodzi, jedzie, czeka przez `wait_until` na kropkę
gospodarza, zmienia kolor i znika — w ramce, którą gospodarz w tym czasie przesuwa i zmniejsza.
