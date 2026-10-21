"""Klient testowy: wysyła komendy do działającej ``LiveScene``.

    uv run python -m manimcue.cue rotate pulse            # po jednej, z odstępem
    uv run python -m manimcue.cue --mode together a b     # dwie komendy w jednym pakiecie
    uv run python -m manimcue.cue --mode split rotate     # jedna komenda w dwóch pakietach
    uv run python -m manimcue.cue --hold 5 rotate         # trzyma połączenie po wysłaniu

Tryby odpowiadają kryteriom akceptacji 4 i 5 z SPEC.md.
"""

from __future__ import annotations

import argparse
import os
import socket
import time

from manimcue import DEFAULT_PORT, HOST, PORT_ENV_VAR

GAP = 0.3
"""Odstęp między pakietami w trybach `line` i `split` [s]."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Wysyla komendy do LiveScene")
    parser.add_argument("commands", nargs="+", help="Nazwy komend z PRESETS")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get(PORT_ENV_VAR, DEFAULT_PORT)),
        help=f"Port sceny (domyslnie {PORT_ENV_VAR} albo {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--mode",
        choices=("line", "together", "split"),
        default="line",
        help="line: osobny pakiet na komende; together: wszystkie w jednym; "
        "split: pierwsza komenda rozcieta na dwa pakiety",
    )
    parser.add_argument("--delay", type=float, default=0.0, help="Pauza przed wyslaniem [s]")
    parser.add_argument("--hold", type=float, default=0.0, help="Pauza przed rozlaczeniem [s]")
    return parser.parse_args()


def send(sock: socket.socket, commands: list[str], mode: str) -> None:
    payload = b"".join(f"{name}\n".encode() for name in commands)
    if mode == "together":
        sock.sendall(payload)
    elif mode == "split":
        middle = max(1, len(payload) // 2)
        sock.sendall(payload[:middle])
        time.sleep(GAP)
        sock.sendall(payload[middle:])
    else:
        for name in commands:
            sock.sendall(f"{name}\n".encode())
            time.sleep(GAP)


def main() -> None:
    args = parse_args()
    time.sleep(args.delay)
    with socket.create_connection((HOST, args.port), timeout=5) as sock:
        send(sock, args.commands, args.mode)
        print(f"wyslano {args.commands} w trybie {args.mode} na {HOST}:{args.port}")
        time.sleep(args.hold)


if __name__ == "__main__":
    main()
