"""Przeklikanie PoC web przez Playwright na zainstalowanym Edge (bez pobierania przeglądarki).

uv run --frozen --with playwright python experiments/f5i_imgui/drive_web.py --clips 3 --screenshot shot.png
Uruchamia serve.py --no-browser, otwiera stronę, naciska spację (pauza i wznowienie), robi zrzut,
czeka na metryki. Konsola strony trafia na stderr.
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--clips", type=int, default=3)
    parser.add_argument("--seconds", type=float, default=8.0)
    parser.add_argument("--warmup", type=float, default=2.0)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--channel", default="msedge")
    parser.add_argument("--screenshot", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or HERE / ".." / ".." / ".tmp" / "f5i-drive-web.json"
    server = subprocess.Popen(
        [
            sys.executable,
            str(HERE / "serve.py"),
            "--no-browser",
            "--clips",
            str(args.clips),
            "--seconds",
            str(args.seconds),
            "--warmup",
            str(args.warmup),
            "--output",
            str(output),
        ],
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    url = ""
    while not url.startswith("http"):
        url = server.stderr.readline().strip()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel=args.channel, headless=not args.headed)
        page = browser.new_page(viewport={"width": 1600, "height": 900})
        page.on("console", lambda message: print(f"[console] {message.text}", file=sys.stderr))
        page.on("pageerror", lambda error: print(f"[pageerror] {error}", file=sys.stderr))
        page.goto(url)
        page.wait_for_selector("#loader", state="detached", timeout=180_000)
        canvas = page.locator("#canvas")
        canvas.click(position={"x": 1500, "y": 850})
        time.sleep(args.warmup + 1)
        page.keyboard.press("Space")
        time.sleep(0.5)
        paused = page.evaluate("[...document.querySelectorAll('video')].map(v => v.paused)")
        page.keyboard.press("Space")
        time.sleep(0.5)
        resumed = page.evaluate("[...document.querySelectorAll('video')].map(v => v.paused)")
        print(f"pauza: {paused}\nwznowienie: {resumed}", file=sys.stderr)
        if args.screenshot:
            page.screenshot(path=str(args.screenshot))
        server.wait(args.seconds + args.warmup + 60)
        browser.close()
    result = json.loads(Path(output).read_text(encoding="utf-8"))
    result["pause_check"] = {"paused": paused, "resumed": resumed}
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
