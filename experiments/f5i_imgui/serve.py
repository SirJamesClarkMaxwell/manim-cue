"""Serwer PoC web: strona, pliki .py dla Pyodide, filmy z obsługą Range i odbiór metryk.

uv run --frozen python experiments/f5i_imgui/serve.py --clips 3            # otwiera Edge/Chrome w trybie --app
uv run --frozen python experiments/f5i_imgui/serve.py --clips 1 --headless --seconds 3
Kończy się po odebraniu metryk (POST /metrics) albo po --timeout; JSON na stdout albo do --output.
"""

import argparse
import json
import re
import shutil
import subprocess
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from desktop import ROOT, media

HERE = Path(__file__).resolve().parent
PYTHON_FILES = {"stage.py", "sources_web.py", "web_main.py"}
TYPES = {
    ".html": "text/html; charset=utf-8",
    ".py": "text/plain; charset=utf-8",
    ".mp4": "video/mp4",
}
BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "msedge",
    "google-chrome",
    "chromium",
]


def find_browser():
    for candidate in BROWSERS:
        path = shutil.which(candidate) or (candidate if Path(candidate).exists() else None)
        if path:
            return path
    return None


class Handler(BaseHTTPRequestHandler):
    media_dir: Path
    result = None

    def log_message(self, *args):
        pass

    def resolve(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            return HERE / "web" / "index.html"
        if path.lstrip("/") in PYTHON_FILES:
            return HERE / path.lstrip("/")
        match = re.fullmatch(r"/media/(\d)\.mp4", path)
        return self.media_dir / f"{match.group(1)}.mp4" if match else None

    def do_GET(self):
        target = self.resolve()
        if target is None or not target.exists():
            self.send_error(404)
            return
        data = target.read_bytes()
        start, end = 0, len(data) - 1
        match = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
        if match and (match.group(1) or match.group(2)):
            if match.group(1):
                start = int(match.group(1))
                end = int(match.group(2)) if match.group(2) else end
            else:
                start = len(data) - int(match.group(2))
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{len(data)}")
        else:
            self.send_response(200)
        self.send_header("Content-Type", TYPES.get(target.suffix, "application/octet-stream"))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data[start : end + 1])

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        type(self).result = json.loads(body or b"{}")
        self.send_response(204)
        self.end_headers()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--clips", type=int, default=3)
    parser.add_argument("--resolution", default="1920x1080")
    parser.add_argument("--warmup", type=float, default=3.0)
    parser.add_argument("--seconds", type=float, default=20.0)
    parser.add_argument("--no-info", action="store_true")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--no-browser", action="store_true", help="tylko serwer; adres na stderr")
    parser.add_argument("--timeout", type=float, default=240.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    paths = media(tuple(int(v) for v in args.resolution.split("x")))
    Handler.media_dir = paths[0].parent
    server = HTTPServer(("127.0.0.1", args.port), Handler)
    server.timeout = 0.2
    query = f"clips={args.clips}&warmup={args.warmup}&seconds={args.seconds}&info={0 if args.no_info else 1}"
    url = f"http://127.0.0.1:{server.server_port}/?{query}"
    print(url, flush=True, file=__import__("sys").stderr)

    browser = None
    if not args.no_browser:
        executable = find_browser()
        if executable is None:
            raise SystemExit("Brak Edge/Chrome; uruchom z --no-browser i otwórz adres ręcznie")
        profile = ROOT / ".tmp" / "f5i-browser"
        command = [
            executable,
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--no-default-browser-check",
            "--autoplay-policy=no-user-gesture-required",
            "--window-size=1600,900",
            # Zasłonięte okno nie może wstrzymywać requestAnimationFrame w trakcie pomiaru.
            "--disable-features=CalculateNativeWinOcclusion",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--ignore-gpu-blocklist",
            f"--app={url}",
        ]
        if args.headless:
            command += ["--headless=new", "--enable-unsafe-swiftshader"]
        browser = subprocess.Popen(command)

    deadline = time.monotonic() + args.timeout
    try:
        while Handler.result is None and time.monotonic() < deadline:
            server.handle_request()
    finally:
        if browser is not None:
            browser.terminate()
            browser.wait(10)
        server.server_close()
    result = Handler.result or {"error": f"brak metryk po {args.timeout} s"}
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()
