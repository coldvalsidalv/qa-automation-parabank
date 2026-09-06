"""Concurrent-burst probe for the tests that prove D-25 and D-26.

Both defects are races: one burst reproduces them with high probability, not
certainty, and under a saturated server the probability *falls* — queuing
serialises the requests, which is what the defect needs to avoid. A strict
xfail cannot live with "usually fails", so a burst that comes back clean is
repeated: the defect is reported fixed only if every burst is clean.
"""

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar

T = TypeVar("T")

BURSTS = 3


def burst_until_failure(
    call: Callable[[int], T],
    size: int,
    is_failure: Callable[[T], bool],
    bursts: int = BURSTS,
) -> Sequence[T]:
    """Run `call` `size`-way concurrently until a result fails.

    Returns the first batch containing a failure, or the last batch if every
    burst came back clean.
    """
    results: Sequence[T] = ()
    for _ in range(bursts):
        with ThreadPoolExecutor(size) as pool:
            results = list(pool.map(call, range(size)))
        if any(is_failure(result) for result in results):
            break
    return results
