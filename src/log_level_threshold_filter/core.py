"""A logging filter that accepts records within a closed level range.

Why this exists
---------------
Python's logging module lets a handler attach a single `level`, which acts as a
*minimum* threshold — records *below* it are dropped. There is no built-in way
to also drop records *above* a ceiling. That matters in practice: a team may
want WARNING and ERROR routed to a paging channel while CRITICAL, which uses a
separate escalation path, must stay out of it, and DEBUG/INFO chatter belongs
elsewhere entirely.

Design decision (picked one interpretation, stated plainly)
--------------------------------------------------------
The range is **closed** on both ends: a record whose level equals `min_level`
or `max_level` is accepted. The canonical example — "between WARNING and ERROR"
— therefore accepts WARNING, ERROR, and the levels between them (of which
there are none in the stdlib by default, but a user may have registered one).
It rejects DEBUG, INFO, and CRITICAL.

A half-open `[min, max)` interpretation was considered and rejected because
the brief names ERROR as a level to *accept*, which is only true under a
closed range. Changing that one decision would flip every assertion below.

Edge you will hit
-----------------
`logging` resolves a level *name* to an integer lazily via
`logging.getLevelName(name)` *only* when the name is one of the stdlib's.
`NOTSET` (0) is a valid value, so a filter constructed with
`min_level=logging.NOTSET` accepts *every* record whose level is 0, which is
exactly the records that never had `setLevel` called on them. That is usually
not what you want; treat NOTSET on either bound as a footgun. The constructor
does not reject it, because some loggers genuinely emit at level 0, and a
library that silently rewrote the caller's intent would be worse than one
that honours it.
"""

import logging
from typing import Union


class LogLevelThresholdFilter(logging.Filter):
    """Accept records whose effective level is within ``[min_level, max_level]``.

    Subclasses ``logging.Filter`` so it composes with the stdlib: attach it to
    any handler via ``handler.addFilter(f)`` and records outside the range are
    dropped before formatting. The filter is stateless per record; it does not
    track a logger name, so the ``name`` attribute inherited from
    ``logging.Filter`` is unused and deliberately not honoured.

    Parameters
    ----------
    min_level:
        Lowest level (inclusive) that passes. May be an int (e.g.
        ``logging.WARNING``) or a level name (e.g. ``"WARNING"``).
    max_level:
        Highest level (inclusive) that passes. Same typing rules as
        ``min_level``.

    Notes
    -----
    Level *names* are resolved at construction time. If a name is not known to
    the ``logging`` module at that moment, ``ValueError`` is raised — better to
    fail fast than to silently accept everything because the bound resolved to
    ``None`` and then to a sentinel like ``0``.
    """

    def __init__(
        self,
        min_level: Union[int, str] = logging.WARNING,
        max_level: Union[int, str] = logging.ERROR,
    ) -> None:
        super().__init__()
        self._min_level = self._coerce_level(min_level, "min_level")
        self._max_level = self._coerce_level(max_level, "max_level")
        if self._min_level > self._max_level:
            raise ValueError(
                "min_level (%d) must not exceed max_level (%d)"
                % (self._min_level, self._max_level)
            )

    @staticmethod
    def _coerce_level(value: Union[int, str], param_name: str) -> int:
        """Resolve a level given as int or name to a stable int.

        Resolving at construction (rather than per-record) keeps the hot path
        — ``filter`` — to two integer comparisons. It also means renaming a
        level after the filter is built does not retroactively change its
        bounds, which is the least surprising option.
        """
        if isinstance(value, bool):
            # bool is a subclass of int; reject it explicitly because
            # ``True`` would silently mean level 1, which is never useful.
            raise TypeError(
                "%s must be an int level or level name, not bool" % param_name
            )
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            resolved = logging.getLevelName(value)
            # getLevelName returns the same string back if the name is unknown,
            # and returns the integer level for a known name.
            if not isinstance(resolved, int):
                raise ValueError(
                    "Unknown level name %r for %s" % (value, param_name)
                )
            return resolved
        raise TypeError(
            "%s must be int or str, got %s"
            % (param_name, type(value).__name__)
        )

    @property
    def min_level(self) -> int:
        return self._min_level

    @property
    def max_level(self) -> int:
        return self._max_level

    def filter(self, record: logging.LogRecord) -> bool:
        """Return True iff ``record.levelno`` is within ``[min, max]``.

        Uses ``levelno`` (the integer) rather than ``level`` (the name) so the
        filter is immune to records whose ``level`` string was customised by a
        formatter or factory. ``levelno`` is set by ``Logger.log`` from the
        numeric argument and is not mutated downstream.
        """
        return self._min_level <= record.levelno <= self._max_level
