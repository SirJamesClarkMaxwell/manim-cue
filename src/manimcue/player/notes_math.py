"""Adapter PC wzorów: lokalny MicroTeX, awaryjnie mathtext/Agg, bez procesu TeX."""

import re
from collections import OrderedDict

from .textures import upload

MATH_SCALE = 1.2
MAX_FORMULAS = 128
MAX_BYTES = 16 * 1024 * 1024
_cache = OrderedDict()
_bytes = 0
_retired = []
_native_dirty = False
TOKEN = re.compile(
    r"```[\s\S]*?```|`[^`\n]*`|\\\$|(?<!\\)\$\$([\s\S]*?)(?<!\\)\$\$|(?<!\\)\$([^$\n]*?)(?<!\\)\$"
)
FORBIDDEN = re.compile(
    r"\\(?:input|include|write|openout|read|usepackage|newcommand|def|gdef|csname)\b"
)


def math_tokens(text):
    """Kod i escaped dollar pozostają dosłownym Markdownem."""
    return [
        match
        for match in TOKEN.finditer(text)
        if match.group(1) is not None or match.group(2) is not None
    ]


def _discard(value):
    global _bytes, _native_dirty
    value["evicted"] = True
    _bytes -= value.get("bytes", 0)
    if value.get("lease"):
        _retired.append(value["lease"])
    _native_dirty = True


def clear_cache():
    """Tekstury zwalnia adapter po wykonaniu draw data."""
    for value in _cache.values():
        _discard(value)
    _cache.clear()


def render_formula(
    text: str, size: float, dpi: float, style: str, *, color=(1, 1, 1, 1), native=True
) -> dict:
    """Raster i baseline w fizycznych pikselach; cache uwzględnia styl, DPI i kolor."""
    global _bytes
    key = text, size, dpi, style, tuple(color), native
    if key in _cache:
        _cache.move_to_end(key)
        return _cache[key]
    result = {"rgba": b"", "width": 0, "height": 0, "baseline": 0, "error": None}
    try:
        if len(text) > 4096 or FORBIDDEN.search(text):
            raise ValueError("Wzór przekracza limit lub zawiera niedozwolone makro")
        if not 0 < size <= 57.6 or not 0 < dpi <= 8 or style not in ("inline", "display"):
            raise ValueError("Niepoprawny rozmiar, DPI lub styl wzoru")
        try:
            from imgui_bundle import imgui_microtex
        except ImportError:
            imgui_microtex = None

        if native and imgui_microtex is not None and imgui_microtex.is_initialized():
            from imgui_bundle import imgui

            formula = imgui_microtex.render(
                text,
                size * dpi,
                imgui.ImVec4(*color),
                imgui_microtex.TexStyle.display
                if style == "display"
                else imgui_microtex.TexStyle.text,
            )
            width, height = formula.width, formula.height
            baseline = formula.baseline_y
            if not 0 < width <= 2048 or not 0 < height <= 2048:
                raise ValueError("Wzór przekracza limit 2048×2048 px")
            pixels = formula.pixels_as_array().tobytes()
        else:
            import numpy as np
            from matplotlib.font_manager import FontProperties
            from matplotlib.mathtext import MathTextParser

            parsed = MathTextParser("agg").parse(
                f"${text}$", dpi=96 * dpi, prop=FontProperties(size=size * 72 / 96)
            )
            alpha = np.asarray(parsed.image)
            height, width = alpha.shape
            baseline = height - parsed.depth
            if not 0 < width <= 2048 or not 0 < height <= 2048:
                raise ValueError("Wzór przekracza limit 2048×2048 px")
            rgba = np.empty((height, width, 4), dtype=np.uint8)
            rgba[:, :, :3] = [round(c * 255) for c in color[:3]]
            rgba[:, :, 3] = (alpha * color[3]).astype(np.uint8)
            pixels = rgba.tobytes()
        # Owned raster, tekstura i kopia robocza podczas uploadu.
        cost = len(pixels) * 3
        if cost > MAX_BYTES:
            raise ValueError("Wzór przekracza budżet 16 MiB")
        result.update(rgba=pixels, width=width, height=height, baseline=baseline, bytes=cost)
    except Exception as error:  # noqa: BLE001 — błędny wzór pozostaje widocznym źródłem
        result["error"] = str(error)
    while _cache and (len(_cache) >= MAX_FORMULAS or _bytes + result.get("bytes", 0) > MAX_BYTES):
        _, value = _cache.popitem(last=False)
        _discard(value)
    _cache[key] = result
    _bytes += result.get("bytes", 0)
    return result


class NotesRenderer:
    """Natywny Markdown zachowuje skład, fallback używa baseline rastrów Agg."""

    def render(self, text, size, dpi):
        global _native_dirty
        from imgui_bundle import imgui, imgui_md

        try:
            from imgui_bundle import imgui_microtex
        except ImportError:
            imgui_microtex = None

        native = imgui_microtex is not None and imgui_md.has_latex()
        color = tuple(imgui.get_style().color_(imgui.Col_.text))
        tokens = math_tokens(text)
        prepared = []
        for index, token in enumerate(tokens):
            style = "display" if token.group(1) is not None else "inline"
            source = token.group(1) if style == "display" else token.group(2)
            if native:
                source = rf"\scalebox{{{MATH_SCALE}}}{{{source}}}"
            formula = (
                render_formula(
                    source,
                    size if native else size * MATH_SCALE,
                    dpi,
                    style,
                    color=color,
                    native=native,
                )
                if index < MAX_FORMULAS
                else {"error": "Limit 128 wzorów w notatce"}
            )
            prepared.append((token, style, formula))
        if native:
            if _native_dirty:
                imgui_microtex.clear_texture_cache()
                _native_dirty = False
            for token, style, formula in reversed(prepared):
                if formula["error"]:
                    text = (
                        text[: token.start()]
                        + f"`{token.group(0)}` (math: {formula['error']})"
                        + text[token.end() :]
                    )
                else:
                    delimiter = "$$" if style == "display" else "$"
                    source = token.group(1) if style == "display" else token.group(2)
                    text = (
                        text[: token.start()]
                        + delimiter
                        + rf"\scalebox{{{MATH_SCALE}}}{{{source}}}"
                        + delimiter
                        + text[token.end() :]
                    )
            imgui_md.render(text)
            return
        # Fallback dzieli Markdown przy wzorze; formatowanie przez wzór wymaga integracji z parserem.
        position = 0
        for token, style, formula in prepared:
            prefix = text[position : token.start()]
            if prefix:
                imgui_md.render(prefix)
            if formula["error"]:
                imgui.text_wrapped(f"{token.group(0)} — {formula['error']}")
            else:
                if not formula.get("lease"):
                    try:
                        formula["lease"] = upload(formula)
                        # Eksmisja podczas prepared poprzedza upload; zasób żyje do draw data.
                        if formula.get("evicted"):
                            _retired.append(formula["lease"])
                    except Exception as error:  # noqa: BLE001 — awaria GL pokazuje źródło
                        imgui.text_wrapped(f"{token.group(0)} — {error}")
                        position = token.end()
                        continue
                text_y = imgui.get_cursor_pos_y()
                if style == "inline" and prefix and not prefix.endswith("\n"):
                    imgui.same_line(0, 0)
                    text_y = imgui.get_cursor_pos_y()
                    font = imgui_md.get_font(imgui_md.MarkdownFontSpec())
                    ascent = font.font.get_font_baked(font.size).ascent
                    imgui.set_cursor_pos_y(text_y + ascent - formula["baseline"] / dpi)
                elif style == "display":
                    imgui.set_cursor_pos_x(
                        max(
                            imgui.get_cursor_pos_x(),
                            (imgui.get_content_region_avail().x - formula["width"] / dpi) / 2,
                        )
                    )
                imgui.image(
                    imgui.ImTextureRef(formula["lease"].texture),
                    (formula["width"] / dpi, formula["height"] / dpi),
                )
                if style == "inline":
                    imgui.same_line(0, 0)
                    imgui.set_cursor_pos_y(text_y)
            position = token.end()
        if position < len(text):
            imgui_md.render(text[position:])

    def after_render(self, closing=False):
        """Kontekst GL jest nadal aktywny, oba viewporty skończyły draw data."""
        if closing:
            clear_cache()
        while _retired:
            _retired.pop().close()
