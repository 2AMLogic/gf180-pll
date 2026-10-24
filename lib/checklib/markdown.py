"""Markdown helpers shared by the spec claim checkers.

``plain`` normalizes one table cell's text and ``tables`` splits a Markdown
section into its tables. Both were pasted into several
``spec/lib/check-*.sh`` heredocs and the copies drifted (different
docstrings, and two different escaped-pipe implementations); the checks grade
the same documents, so the bodies live here once.

The escape handling follows GitHub-flavoured Markdown: a literal pipe inside
a cell is written ``\\|``, and only an unescaped pipe is a column boundary.
"""

import re

ESCAPED_PIPE = "\x00"


def plain(cell, minus_is_dash=False):
    """Cell text with Markdown emphasis, escapes and Unicode dashes removed.

    Links keep their text (``[x](y)`` reads as ``x``), ``**`` and backticks
    are stripped, an escaped ``\\|`` reads as ``|``, the four Unicode dashes
    these documents use (em, en, figure, non-breaking hyphen) read as ``-``,
    and whitespace collapses to single spaces.

    ``minus_is_dash`` folds U+2212 MINUS SIGN into ``-`` as well, and is an
    explicit parameter on purpose: the tree is not of one mind on U+2212. A
    label matcher that only compares words can treat it as one more dash;
    a figure parser must not, because there it is a signed number's sign and
    is handled by that parser instead. Callers pass ``True`` only where
    their tolerance already did that.
    """
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", cell)
    text = text.replace("**", "").replace("`", "").replace("\\|", "|")
    dashes = ("—", "–", "‒", "‑")
    if minus_is_dash:
        dashes += ("−",)
    for dash in dashes:
        text = text.replace(dash, "-")
    return re.sub(r"\s+", " ", text).strip()


def tables(block):
    """Every Markdown table in ``block``, header row first, rows as cell lists.

    A table runs from its first ``|`` line until the next line that does not
    start with ``|``, so a section holding more than one table yields more
    than one table rather than one impossible table with three different
    column counts -- section 5 of the proposal gained exactly that shape when
    5.1's value-provenance and exclusion tables landed (issue #237).
    ``|---|`` separator rows are skipped.

    The step table's first row is ``... \\|q_up + q_dn\\|, worst corner``: a
    naive split reads its escaped pipes as column boundaries, the value
    column shifts, and the number a check grades is no longer in it.
    """
    found, current = [], None
    for line in block.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            current = None
            continue
        if re.fullmatch(r"\|[\s:|-]+\|", line):
            continue
        line = line.replace("\\|", ESCAPED_PIPE)
        cells = [
            c.strip().replace(ESCAPED_PIPE, "\\|") for c in line.strip("|").split("|")
        ]
        if current is None:
            current = [cells]
            found.append(current)
        else:
            current.append(cells)
    return found
