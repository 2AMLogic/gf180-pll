"""Markdown helpers shared by the claim checkers.

``plain`` and ``normalize`` reduce one table cell's text to the part a check
compares, and ``tables`` splits a Markdown section into its tables. Each was
pasted into several ``spec/``, ``design/`` and ``sim/`` ``check-*.sh``
heredocs and the copies drifted (different docstrings, and four different
table splitters, two of which read an escaped pipe as a column boundary); the
checks grade the same documents, so the bodies live here once.

The escape handling follows GitHub-flavoured Markdown: a literal pipe inside
a cell is written ``\\|``, and only an unescaped pipe is a column boundary.
"""

import re

ESCAPED_PIPE = "\x00"

#: A ``|---|`` / ``| :-: |`` row: a table's alignment line, never data.
_SEPARATOR = re.compile(r"\|[\s:|-]+\|")


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


def normalize(cell):
    """Link text, no emphasis, no backticks, one dash, one space, casefolded.

    The label-matching tolerance: two documents name the same row or column
    and only the spelling differs, so this folds away everything that is not
    the words. It is deliberately NOT ``plain(cell, minus_is_dash=True)``
    with a ``.casefold()`` on the end, and the two differences are the reason:

    - this strips a single ``*`` where ``plain`` strips only ``**``, so
      ``*emphasised*`` and ``**bold**`` both read as the bare word; and
    - this leaves ``\\|`` alone where ``plain`` reads it as ``|``.

    Both are safe here and neither is safe in ``plain``: a name is being
    compared against another name, never parsed as a figure, so an asterisk
    that was part of a footnote marker costs nothing -- while ``plain``
    feeds value-grading code that must not silently eat a lone ``*``. Folding
    the two would be the "tolerance difference" this package exists to keep
    out: the looser rule would quietly start deciding which numbers pass.
    """
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", cell)
    text = text.replace("*", "").replace("`", "")
    for dash in ("—", "–", "‒", "‑", "−"):
        text = text.replace(dash, "-")
    return re.sub(r"\s+", " ", text).strip().casefold()


def tables(block, require_separator=False):
    """Every Markdown table in ``block``, header row first, rows as cell lists.

    A table runs from its first ``|`` line until the next line that does not
    start with ``|``, so a section holding more than one table yields more
    than one table rather than one impossible table with three different
    column counts -- section 5 of the proposal gained exactly that shape when
    5.1's value-provenance and exclusion tables landed (issue #237).
    ``|---|`` separator rows are skipped, wherever in the table they appear:
    a repeated separator is a separator, not a row of dashes to grade.

    The step table's first row is ``... \\|q_up + q_dn\\|, worst corner``: a
    naive split reads its escaped pipes as column boundaries, the value
    column shifts, and the number a check grades is no longer in it.

    ``require_separator`` makes a ``|`` line a table header only when the line
    directly below it is a ``|---|`` separator. It is an explicit parameter
    rather than the one behaviour because the two readings differ on real
    files and both are right where they are used: a document whose tables are
    the only pipe lines in it wants the permissive reading, while a sim record
    wraps prose mid-paragraph and so can begin a continuation line with
    ``|i_div|) and there is no fourth domain`` -- one line, no separator under
    it, and under the permissive reading a one-row "table" that a check
    scanning for a table by its first column could pick up.
    """
    lines = block.splitlines()
    found, current = [], None
    for index, raw in enumerate(lines):
        line = raw.strip()
        if not line.startswith("|"):
            current = None
            continue
        if current is None and require_separator:
            below = lines[index + 1].strip() if index + 1 < len(lines) else ""
            if not _SEPARATOR.fullmatch(below):
                continue
            # Falling through without the separator test below is deliberate:
            # `| | |` -- a header of empty cells, which several PROOF.md files
            # open their run table with -- is itself `[\s:|-]+` between pipes.
            # Under this reading the line BELOW decides, so that header is a
            # header and its table is not silently dropped.
        elif _SEPARATOR.fullmatch(line):
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
