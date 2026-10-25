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
