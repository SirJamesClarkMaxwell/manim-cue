"""Te same nazwane przypadki na PC i w Pyodide; bez adapterów platformowych."""

import json
import sys
from pathlib import Path

MODULES = ("__init__", "manifest", "clock", "controller", "geometry", "state")
FORBIDDEN = (
    "qtpy",
    "PySide6",
    "PyQt6",
    "av",
    "multiprocessing",
    "pydantic",
    "rtoml",
    "manim",
    "manimlib",
    "click",
    "manimcue.slides",
)


def run_shared_cases() -> dict:
    """Nazwane próby bramki; nie zastępują pełnej tabeli nawigacji zadania 4."""
    from manimcue.player.clock import media_time, new_clock, set_playing
    from manimcue.player.controller import reduce
    from manimcue.player.geometry import clip, fit, layer_box
    from manimcue.player.manifest import validate_manifest
    from manimcue.player.state import initial_state, snapshot

    manifest = {
        "version": 1,
        "resolution": [1920, 1080],
        "presentations": [
            {
                "slides": [
                    {"kind": "video", "file": "first.mp4", "duration": 2.0, "rate": 1.0},
                    {"kind": "image", "file": "second.png"},
                ]
            }
        ],
    }
    validated = validate_manifest(manifest)
    assert validated == manifest and validated is not manifest
    invalid = [
        {**manifest, "version": 2},
        {**manifest, "version": True},
        {**manifest, "resolution": [0, 1080]},
        {**manifest, "resolution": [1920, float("inf")]},
    ]
    for field, value in (("duration", float("nan")), ("rate", 0), ("reverse_rate", float("inf"))):
        invalid.append(
            {**manifest, "presentations": [{"slides": [{"kind": "video", field: value}]}]}
        )
    for item in invalid:
        try:
            validate_manifest(item)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Przyjęto niepoprawny manifest: {item}")

    clock = set_playing(new_clock(10, 2), True, 10)
    assert media_time(clock, 11) == 2
    clock = set_playing(clock, False, 11)
    assert media_time(clock, 100) == 2
    clock = set_playing(clock, True, 100)
    assert media_time(clock, 101) == 4

    frame = fit(16 / 9, (0, 0, 1000, 1000))
    assert frame == (0, 218.75, 1000, 562.5)
    box = layer_box(frame, (-0.1, 0, 0.5, 1))
    clipped = clip(box, frame)
    assert clipped == (0, 218.75, 400, 562.5)

    state = initial_state(validated)
    waiting, effects = reduce(state, {"type": "next"}, 1)
    assert waiting["preparing"] and waiting["requested_playing"] and effects == []
    ready, effects = reduce(waiting, {"type": "ready", "entry_id": 1}, 2)
    assert not ready["preparing"] and not ready["paused"]
    assert effects == [{"type": "start", "entry_id": 1}]
    paused, _ = reduce(ready, {"type": "pause"}, 3)
    resumed, effects = reduce(paused, {"type": "next"}, 4)
    assert resumed["index"] == [0, 0] and not resumed["paused"]
    assert effects == [{"type": "start", "entry_id": 1}]
    next_state, effects = reduce(resumed, {"type": "next"}, 5)
    assert next_state["index"] == [0, 1] and next_state["entry_id"] == 2
    assert effects == [{"type": "cancel", "entry_id": 1}, {"type": "prepare", "entry_id": 2}]
    stale, effects = reduce(next_state, {"type": "ready", "entry_id": 1}, 6)
    assert stale == next_state and not effects and stale["preparing"]
    copy = snapshot(stale)
    copy["index"][0] = 99
    assert stale["index"] == [0, 1]
    return {
        "clock_pause": {"position": media_time(clock, 101)},
        "navigation_table": {"index": next_state["index"], "entry_id": 2},
        "geometry_clip": {"frame": list(frame), "clip": list(clipped)},
        "stale_entry": {"ignored": stale == next_state},
        "manifest_validation": {"rejected": len(invalid)},
    }


def check_shared_imports() -> dict:
    """Zablokuj zabronione importy tranzytywne także przed uruchomieniem prób."""

    class Blocker:
        def find_spec(self, fullname, path=None, target=None):
            if any(fullname == name or fullname.startswith(name + ".") for name in FORBIDDEN):
                raise ImportError(f"Zabroniony import wspólnego kodu: {fullname}")

    blocker = Blocker()
    sys.meta_path.insert(0, blocker)
    try:
        cases = run_shared_cases()
        forbidden = [
            name
            for name in sys.modules
            if any(name == prefix or name.startswith(prefix + ".") for prefix in FORBIDDEN)
        ]
        assert not forbidden, forbidden
        return {"cases": cases, "forbidden_imports": forbidden}
    finally:
        sys.meta_path.remove(blocker)


def run_import_gate(channel="msedge") -> dict:
    """Uruchom osobny interpreter PC i headless Edge, porównaj wyniki JSON."""
    import subprocess

    from playwright.sync_api import sync_playwright

    root = Path(__file__).resolve().parents[2]
    process = subprocess.run(
        [sys.executable, "-I", str(Path(__file__).resolve()), "--pc"],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    pc = json.loads(process.stdout)
    html = Path(__file__).with_name("pyodide.html").read_text(encoding="utf-8")
    sources = {
        "manimcue/__init__.py": (root / "src/manimcue/__init__.py").read_text(encoding="utf-8")
    }
    for name in MODULES:
        path = f"manimcue/player/{name}.py"
        sources[path] = (root / "src" / path).read_text(encoding="utf-8")
    sources["shared_cases.py"] = Path(__file__).read_text(encoding="utf-8")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel=channel, headless=True)
        try:
            page = browser.new_page()

            def serve(route):
                path = route.request.url.removeprefix("http://f10.invalid/")
                if path == "sources.json":
                    route.fulfill(body=json.dumps(sources), content_type="application/json")
                elif path == "":
                    route.fulfill(body=html, content_type="text/html")
                else:
                    route.fulfill(status=404, body="")

            page.route("http://f10.invalid/**", serve)
            page.goto("http://f10.invalid/")
            page.wait_for_function("window.gateResult !== undefined", timeout=120_000)
            web = page.evaluate("window.gateResult")
            assert "error" not in web, web
            assert pc == web, {"pc": pc, "pyodide": web}
            return {"status": "ok", "channel": channel, "pc": pc, "pyodide": web}
        finally:
            browser.close()


if __name__ == "__main__":
    if "--pc" in sys.argv:
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
        print(json.dumps(check_shared_imports()))
    else:
        import argparse

        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--channel", default="msedge")
        parser.add_argument(
            "--output", type=Path, default=Path(".tmp/MEASUREMENT-10a-imports.json")
        )
        args = parser.parse_args()
        try:
            result = run_import_gate(args.channel)
        except Exception as error:  # noqa: BLE001 — raport bramki musi zachować błąd środowiska.
            result = {"status": "error", "error": f"{type(error).__name__}: {error}"}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result))
        raise SystemExit(0 if result["status"] == "ok" else 1)
