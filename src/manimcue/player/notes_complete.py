"""Czyste podpowiedzi Markdown i wspólnego podzbioru LaTeX; pozycje liczone w glifach."""

import re

# Ten sam podział kodu, escaped dollar i matematyki co w notes_math; test pilnuje zgodności.
TOKEN = re.compile(
    r"```[\s\S]*?```|`[^`\n]*`|\\\$|(?<!\\)\$\$([\s\S]*?)(?<!\\)\$\$|(?<!\\)\$([^$\n]*?)(?<!\\)\$"
)
LATEX = tuple(
    ("\\" + name, "\\" + name, "\\" + name)
    for name in [
        "alpha",
        "beta",
        "gamma",
        "delta",
        "epsilon",
        "varepsilon",
        "zeta",
        "eta",
        "theta",
        "vartheta",
        "iota",
        "kappa",
        "lambda",
        "mu",
        "nu",
        "xi",
        "pi",
        "varpi",
        "rho",
        "varrho",
        "sigma",
        "varsigma",
        "tau",
        "upsilon",
        "phi",
        "varphi",
        "chi",
        "psi",
        "omega",
        "Gamma",
        "Delta",
        "Theta",
        "Lambda",
        "Xi",
        "Pi",
        "Sigma",
        "Upsilon",
        "Phi",
        "Psi",
        "Omega",
        "sum",
        "int",
        "cdot",
        "times",
        "leq",
        "geq",
        "neq",
        "infty",
        "to",
        "pm",
        "partial",
        "nabla",
    ]
) + (
    (r"\frac", r"\frac{|}{}", r"\frac{a}{b}"),
    (r"\sqrt", r"\sqrt{|}", r"\sqrt{x}"),
    (r"\mathrm", r"\mathrm{|}", r"\mathrm{x}"),
    (r"\mathbb", r"\mathbb{|}", r"\mathbb{R}"),
    (r"\vec", r"\vec{|}", r"\vec{x}"),
    (r"\hat", r"\hat{|}", r"\hat{x}"),
    (r"\bar", r"\bar{|}", r"\bar{x}"),
    (r"\left", r"\left(|\right)", r"\left(x\right)"),
)
BLOCKS = (
    ("#", "# |"),
    ("##", "## |"),
    ("###", "### |"),
    ("-", "- |"),
    ("*", "* |"),
    (">", "> |"),
    ("1", "1. |"),
    ("```", "```\n|\n```"),
    ("$$", "$$\n|\n$$"),
)
INLINE = (
    ("Pogrubienie", "**|**"),
    ("Kursywa", "*|*"),
    ("Kod", "`|`"),
    ("Link", "[|](url)"),
    ("Matematyka", "$|$"),
)


def offset(text, position):
    line, index = position
    return sum(len(part) + 1 for part in text.split("\n")[:line]) + index


def position(text, index):
    before = text[:index]
    return before.count("\n"), len(before.rsplit("\n", 1)[-1])


def blocks(text):
    """Zakresy bez separatorów; zamknięte i otwarte ogrodzenia chronią puste wiersze."""
    protected = []
    scanner = re.compile(
        r"```(?:[\s\S]*?```|[\s\S]*$)|`[^`\n]*`|\\\$|"
        r"(?<!\\)\$\$(?:[\s\S]*?(?<!\\)\$\$|[\s\S]*$)|"
        r"(?<!\\)\$([^$\n]*?)(?<!\\)\$"
    )
    for token in scanner.finditer(text):
        if token[0].startswith(("```", "$$")):
            protected.append(token.span())
    result = []
    start = None
    offset = 0
    previous_end = 0
    for line in text.splitlines(keepends=True):
        end = offset + len(line.rstrip("\n"))
        blank = not line.strip(" \t\n") and not any(a <= offset < b for a, b in protected)
        if blank:
            if start is not None:
                result.append((start, previous_end))
                start = None
        else:
            if start is None:
                start = offset
            previous_end = end
        offset += len(line)
    if start is not None:
        result.append(
            (start, len(text) if protected and protected[-1][1] == len(text) else previous_end)
        )
    return result or [(len(text), len(text))]


def compose(text, span, replacement):
    return text[: span[0]] + replacement + text[span[1] :]


def shifted_offset(target, span, replacement):
    """Cel kliknięcia za widgetem przesuwa się o zmianę długości widgetu."""
    return target + (len(replacement) - (span[1] - span[0]) if target >= span[1] else 0)


def block_target(text, span, replacement, direction, *, merge=False):
    """Sąsiad po ponownym podziale; scalenie kasuje jeden znak separatora jak Obsidian."""
    full = compose(text, span, replacement)
    edge = span[0] if direction < 0 else span[0] + len(replacement)
    ranges = blocks(full)
    candidates = (
        [part for part in ranges if part[1] < edge]
        if direction < 0
        else [part for part in ranges if part[0] > edge]
    )
    if not candidates:
        return None
    neighbor = candidates[-1] if direction < 0 else candidates[0]
    if merge:
        # Separator "\n\n" po jednym znaku daje "\n": akapity łączą się bez sklejenia słów.
        cut = edge - 1 if direction < 0 else edge
        full = full[:cut] + full[cut + 1 :]
        ranges = blocks(full)
        inside = [part for part in ranges if part[0] <= cut <= part[1]]
        after = [part for part in ranges if part[0] >= cut]
        before = [part for part in ranges if part[1] <= cut]
        # Edytor zaczynający się pustym wierszem: cięcie wypada w separatorze, zostań w swoim bloku.
        ordered = (after[:1], before[-1:]) if direction < 0 else (before[-1:], after[:1])
        active = (inside or ordered[0] or ordered[1])[0]
        return full, active, min(max(cut - active[0], 0), active[1] - active[0])
    return full, neighbor, neighbor[1] - neighbor[0] if direction < 0 else 0


def suggestions(text, cursor, *, explicit=False, cursors=1):
    """Zwróć (etykieta, początek, koniec, szablon), najwyżej osiem pozycji."""
    if cursors != 1:
        return []
    end = offset(text, cursor)
    if explicit:
        return [(label, end, end, template) for label, template in INLINE]

    def latex(start):
        prefix = text[start:end]
        return [
            (label, start, end, template)
            for label, template, _ in LATEX
            if label.startswith(prefix)
        ][:8]

    for token in TOKEN.finditer(text):
        if token.start() < end <= token.end():
            group = 1 if token.group(1) is not None else 2
            if token.group(group) is None:
                return []
            if token.start(group) <= end <= token.end(group):
                match = re.search(r"\\[a-zA-Z]*$", text[token.start(group) : end])
                if match:
                    return latex(token.start(group) + match.start())
            return []
    # Wzór jeszcze bez zamykającego $ (zwykłe pisanie `$\fr`): zamaskuj pełne tokeny
    # przed kursorem (poza pustym `$$`, który jest otwarciem bloku) i szukaj otwartego $/$$.
    masked = TOKEN.sub(
        lambda token: token[0] if token[0] == "$$" else " " * len(token[0]), text[:end]
    )
    if re.search(r"(?<!\\)\$\$[^$]*$|(?<!\\)\$[^$\n]*$", masked):
        match = re.search(r"\\[a-zA-Z]*$", masked)
        if match:
            return latex(match.start())
    line = text[:end].rsplit("\n", 1)[-1]
    prefix = line.lstrip(" ")
    if prefix and prefix[0] in "#-*>1`$":
        return [
            (label, end - len(prefix), end, template)
            for label, template in BLOCKS
            if label.startswith(prefix)
        ][:8]
    return []


def insertion(text, start, end, template, selection=None):
    """Jedna podmiana oraz pozycja kursora po niej; zaznaczenie trafia w znacznik |."""
    if selection is not None:
        start, end = sorted(selection)
    selected = text[start:end] if selection is not None else ""
    left, marker, right = template.partition("|")
    replacement = left + selected + right
    result = text[:start] + replacement + text[end:]
    cursor = start + len(left) + len(selected) if marker else start + len(replacement)
    return position(text, start), position(text, end), replacement, position(result, cursor)


def shortcut(key, ctrl, alt, cursors=1):
    if ctrl and not alt and cursors == 1:
        return {"b": "**|**", "i": "*|*", "space": "popup"}.get(key)
    return None


def continue_list(text, cursor):
    """Kontynuuj element lub usuń pusty znacznik; pozycje są liczone w glifach."""
    line, column = cursor
    current = text.split("\n")[line]
    match = re.match(r"([ \t]*)([-*+>]|\d+[.)])([ \t]+|$)(\[[ xX]\][ \t]*)?", current)
    if match is None or column < match.end():
        return None
    indent, marker, spacing, task = match.groups()
    start = offset(text, (line, 0))
    if not current[match.end() :].strip():
        return insertion(text, start, start + len(current), "")
    if marker[0].isdigit():
        marker = str(int(marker[:-1]) + 1) + marker[-1]
    prefix = indent + marker + spacing + ("[ ] " if task else "")
    at = offset(text, cursor)
    return insertion(text, at, at, "\n" + prefix)


def ghost_remainder(text, cursor, item):
    """Reszta szablonu po wpisanym prefiksie, bez znacznika kursora."""
    _, start, _, template = item
    prefix = text[start : offset(text, cursor)]
    template = template.replace("|", "")
    return template[len(prefix) :] if prefix and template.startswith(prefix) else ""


def delete_word(text, cursor, direction):
    """Ctrl+Backspace/Delete: znak nowego wiersza albo odstęp i słowo lub ciąg interpunkcji."""
    at = offset(text, cursor)
    part = text[:at][::-1] if direction < 0 else text[at:]
    size = len(re.match(r"\n|[ \t]*(?:\w+|[^\w\s]+)?", part)[0])
    if not size:
        return None
    return insertion(text, *((at - size, at) if direction < 0 else (at, at + size)), "")
