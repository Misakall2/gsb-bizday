"""Business-day stepping and date-adjustment conventions.

Dependencies: a :class:`~bizday.observance.HolidayTable` for the
is-business-day predicate, plus the convention name normalization.
"""

from __future__ import annotations

from datetime import date, timedelta

from .conventions import (
    FOLLOWING,
    PRECEDING,
    MODIFIED_FOLLOWING,
    MODIFIED_PRECEDING,
    UNADJUSTED,
    normalize_convention,
)

_ONE_DAY = timedelta(days=1)


def step(table, d: date, direction: int) -> date:
    """Nearest business day strictly before (``-1``) or after (``+1``).

    A whole run of consecutive weekends/holidays is crossed in one
    call, so stepping from inside a multi-day break lands past it.
    """
    d += direction * _ONE_DAY
    while not table.is_business_day(d):
        d += direction * _ONE_DAY
    return d


def adjust_raw(table, d: date, convention: str) -> date:
    """Adjust a non-business day; caller guarantees the convention."""
    if convention == UNADJUSTED:
        return d
    if convention == FOLLOWING:
        return step(table, d, +1)
    if convention == PRECEDING:
        return step(table, d, -1)
    if convention == MODIFIED_FOLLOWING:
        fwd = step(table, d, +1)
        return fwd if fwd.month == d.month else step(table, d, -1)
    if convention == MODIFIED_PRECEDING:
        back = step(table, d, -1)
        return back if back.month == d.month else step(table, d, +1)
    raise ValueError(f"unknown convention: {convention!r}")


def adjust(table, d: date, convention=FOLLOWING) -> date:
    """Adjust ``d`` to a business day per the convention.

    ``unadjusted`` returns ``d`` unchanged, even on weekends/holidays.
    Convention names are normalized here, the single entry point for
    English/Chinese aliases on adjustment.
    """
    convention = normalize_convention(convention)
    if convention == UNADJUSTED:
        return d
    if table.is_business_day(d):
        return d
    return adjust_raw(table, d, convention)


def shift(table, start: date, n: int, convention=FOLLOWING) -> date:
    """Move ``n`` business days from ``start``.

    ``n == 0`` adjusts ``start`` itself (per ``convention``). Positive
    ``n`` rolls forward, negative rolls backward; each step crosses a
    whole consecutive non-business run.
    """
    if not isinstance(n, int):
        raise TypeError("n must be an int")
    if n == 0:
        return adjust(table, start, convention)
    direction = +1 if n > 0 else -1
    d = start
    for _ in range(abs(n)):
        d = step(table, d, direction)
    return d


def business_days_between(table, start: date, end: date) -> int:
    """Signed count of business-day steps from start to end."""
    if start == end:
        return 0
    direction = +1 if end > start else -1
    d, count = start, 0
    while d != end:
        d = step(table, d, direction)
        count += direction
    return count
