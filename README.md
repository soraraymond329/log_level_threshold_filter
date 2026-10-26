# Log Level Threshold Filter

A `logging.Filter` subclass that accepts records whose level falls within a **closed** `[min_level, max_level]` range — the stdlib only gives you a minimum, this adds the ceiling.

```python
import logging
from log_level_threshold_filter import LogLevelThresholdFilter

handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)  # let the filter decide, not the handler
handler.addFilter(LogLevelThresholdFilter(min_level=logging.WARNING, max_level=logging.ERROR))

logging.basicConfig(handlers=[handler])
logging.warning("routed through")   # WARNING -> kept
logging.error("routed through")     # ERROR   -> kept
logging.debug("dropped")             # DEBUG   -> dropped
logging.critical("dropped")         # CRITICAL-> dropped
```

Exported names: `LogLevelThresholdFilter` (a subclass of `logging.Filter`).

## Why

`logging.Handler.level` is a floor; there is no built-in ceiling. If you route WARNING and ERROR to a paging channel, CRITICAL will ride straight through unless you remember to exclude it — and remembering is exactly what fails at 3am. This filter lets a handler say "between these two levels, inclusive, nothing else".

The trade-off: the range is closed on both ends. The brief names ERROR as a level to *accept*, and that is only true if the upper bound is inclusive. A half-open `[min, max)` was considered and rejected because it would drop ERROR — the canonical case — and that would make the README lie.

## Awkward edge

`logging.NOTSET` is `0`, a perfectly valid integer. `LogLevelThresholdFilter(logging.NOTSET, logging.ERROR)` will accept records at level 0 (the ones no one ever called `setLevel` on). That is usually not what you want, but the filter honours it rather than rewriting your intent silently. If you mean "everything", pass `logging.DEBUG` explicitly.

Level *names* are resolved at construction; a name unknown to the `logging` module raises `ValueError` immediately. `bool` is rejected even though it subclasses `int`, because `True` would silently mean level 1.

## Design notes

The window stores values eagerly rather than keeping running aggregates. Running
sums drift with floating point over long streams, and recomputing from a small
buffer is cheap enough that the drift is not worth the speed.

