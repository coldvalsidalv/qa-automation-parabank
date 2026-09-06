"""Helper for the tests that prove ParaBank's write paths are not concurrency-safe.

Defects D-25 (registration) and D-26 (account opening) are races: a single
concurrent burst reproduces them with high probability, not certainty. Under a
saturated server the probability actually *drops* — requests queue and end up
effectively serialised, which is the condition the defect needs to avoid.

A strict xfail cannot live with "usually fails": one clean burst reads as
XPASS, i.e. "the defect is fixed", and turns CI red for no reason. Repeating
the burst until one of them trips converts a probabilistic observation into a
stable assertion: the defect is reported absent only if *every* burst comes
back clean, which is p**BURSTS rather than p.
"""

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar

T = TypeVar("T")

# Three bursts: with a per-burst clean probability well under 0.5 in every
# probe, a spurious XPASS needs three clean bursts in a row.
BURSTS = 3


def burst_until_failure(
    call: Callable[[int], T],
    size: int,
    is_failure: Callable[[T], bool],
    bursts: int = BURSTS,
) -> Sequence[T]:
    """Run `call` `size`-way concurrently, repeating until a result fails.

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
