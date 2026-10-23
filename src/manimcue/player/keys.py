"""Kody klawiszy Qt z konfiguracji przeliczane na klawisze ImGui, bez importu Qt."""

# Wartości Qt::Key zapisane na sztywno; Key_Enter to Enter z klawiatury numerycznej.
QT_KEYS: dict[str, int] = {
    **{c: ord(c) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"},
    **{str(d): 0x30 + d for d in range(10)},
    **{f"F{n}": 0x01000030 + n - 1 for n in range(1, 25)},
    "Space": 0x20,
    "Escape": 0x01000000,
    "Tab": 0x01000001,
    "Backspace": 0x01000003,
    "Return": 0x01000004,
    "Enter": 0x01000005,
    "Insert": 0x01000006,
    "Delete": 0x01000007,
    "Pause": 0x01000008,
    "Print": 0x01000009,
    "Home": 0x01000010,
    "End": 0x01000011,
    "Left": 0x01000012,
    "Up": 0x01000013,
    "Right": 0x01000014,
    "Down": 0x01000015,
    "PageUp": 0x01000016,
    "PageDown": 0x01000017,
    "CapsLock": 0x01000024,
    "NumLock": 0x01000025,
    "ScrollLock": 0x01000026,
    "Menu": 0x01000055,
    "Minus": 0x2D,
    "Equal": 0x3D,
    "Comma": 0x2C,
    "Period": 0x2E,
    "Slash": 0x2F,
    "Semicolon": 0x3B,
    "Apostrophe": 0x27,
    "BracketLeft": 0x5B,
    "BracketRight": 0x5D,
    "Backslash": 0x5C,
    "QuoteLeft": 0x60,
    "Plus": 0x2B,
    "Asterisk": 0x2A,
}

# Qt::Key -> nazwa atrybutu imgui.Key; klawisze bez odpowiednika pominięte.
QT_TO_IMGUI: dict[int, str] = {
    **{QT_KEYS[c]: c.lower() for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"},
    **{QT_KEYS[str(d)]: f"_{d}" for d in range(10)},
    **{QT_KEYS[f"F{n}"]: f"f{n}" for n in range(1, 25)},
    QT_KEYS["Space"]: "space",
    QT_KEYS["Escape"]: "escape",
    QT_KEYS["Tab"]: "tab",
    QT_KEYS["Backspace"]: "backspace",
    QT_KEYS["Return"]: "enter",
    QT_KEYS["Enter"]: "keypad_enter",
    QT_KEYS["Insert"]: "insert",
    QT_KEYS["Delete"]: "delete",
    QT_KEYS["Pause"]: "pause",
    QT_KEYS["Print"]: "print_screen",
    QT_KEYS["Home"]: "home",
    QT_KEYS["End"]: "end",
    QT_KEYS["Left"]: "left_arrow",
    QT_KEYS["Up"]: "up_arrow",
    QT_KEYS["Right"]: "right_arrow",
    QT_KEYS["Down"]: "down_arrow",
    QT_KEYS["PageUp"]: "page_up",
    QT_KEYS["PageDown"]: "page_down",
    QT_KEYS["CapsLock"]: "caps_lock",
    QT_KEYS["NumLock"]: "num_lock",
    QT_KEYS["ScrollLock"]: "scroll_lock",
    QT_KEYS["Menu"]: "menu",
    QT_KEYS["Minus"]: "minus",
    QT_KEYS["Equal"]: "equal",
    QT_KEYS["Comma"]: "comma",
    QT_KEYS["Period"]: "period",
    QT_KEYS["Slash"]: "slash",
    QT_KEYS["Semicolon"]: "semicolon",
    QT_KEYS["Apostrophe"]: "apostrophe",
    QT_KEYS["BracketLeft"]: "left_bracket",
    QT_KEYS["BracketRight"]: "right_bracket",
    QT_KEYS["Backslash"]: "backslash",
    QT_KEYS["QuoteLeft"]: "grave_accent",
    QT_KEYS["Plus"]: "keypad_add",
    QT_KEYS["Asterisk"]: "keypad_multiply",
}


class UnknownKeyError(ValueError):
    """Kod Qt bez odpowiednika w ImGui."""


def imgui_key(qt_code: int):
    """Zwraca imgui.Key odpowiadający kodowi Qt."""
    from imgui_bundle import imgui  # leniwy import, żeby moduł był tani

    name = QT_TO_IMGUI.get(qt_code)
    if name is None:
        qt_name = next((n for n, c in QT_KEYS.items() if c == qt_code), None)
        label = f", {qt_name}" if qt_name else ""
        raise UnknownKeyError(
            f"Qt key code {qt_code} (0x{qt_code:X}{label}) has no ImGui equivalent"
        )
    return getattr(imgui.Key, name)


def imgui_keys(qt_codes) -> list:
    """Mapuje kolejne kody Qt; podnosi UnknownKeyError na pierwszym nieznanym."""
    return [imgui_key(code) for code in qt_codes]


DEFAULT_KEYS = {
    "QUIT": "Q",
    "PLAY_PAUSE": "Space",
    "NEXT": "Right",
    "PREVIOUS": "Left",
    "REVERSE": "V",
    "REPLAY": "R",
    "FULL_SCREEN": "F",
    "HIDE_MOUSE": "H",
    "PRESENTER_STATE": "S",
}


def bindings(config: dict) -> dict:
    """Zamień liczbowe kody TOML na klawisz fizyczny i zestaw modyfikatorów."""
    result = {}
    configured = config.get("keys", config)
    for action, default in DEFAULT_KEYS.items():
        codes = configured.get(action, {"ids": [QT_KEYS[default]]})["ids"]
        for code in codes:
            name = QT_TO_IMGUI.get(code)
            if name is None:
                label = next((name for name, value in QT_KEYS.items() if value == code), None)
                raise UnknownKeyError(
                    f"{action}: Qt key code {code} (0x{code:X})" + (f", {label}" if label else "")
                )
            candidates = [(name, frozenset())]
            if code == QT_KEYS["Plus"]:
                candidates.append(("equal", frozenset({"shift"})))
            elif code == QT_KEYS["Asterisk"]:
                candidates.append(("_8", frozenset({"shift"})))
            for candidate in candidates:
                if candidate in result:
                    raise ValueError(f"Duplicate binding: {action}, {code}")
                result[candidate] = "pause" if action == "PLAY_PAUSE" else action.lower()
    return result
