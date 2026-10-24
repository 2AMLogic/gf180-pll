"""checklib -- helpers shared by the repository's claim-checker scripts.

The ``spec/``, ``sim/`` and ``design/`` check scripts each embed their
grading logic in a ``python3 - <<'PY'`` heredoc, which leaves nowhere to
share code: helpers used by more than one check had to be pasted into each
copy, and the copies drifted. This package is the shared home those heredocs
import from (the scripts run python with ``PYTHONPATH=$REPO_ROOT/lib``).

A checker grades a claim against evidence, so a tolerance difference between
two copies of "the same" helper is a silent difference in what counts as a
pass. Where two checks legitimately disagree -- such as whether U+2212 is a
dash -- the difference is an explicit parameter of the shared helper, not a
fork of its body.
"""
