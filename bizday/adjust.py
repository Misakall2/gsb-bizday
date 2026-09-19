"""Adjust a possibly non-business date to a business date."""
from __future__ import annotations

from datetime import date

from .calendar import BusinessCalendar
from .convention import Convention, get_convention


def adjust(d: date, convention, calendar: BusinessCalendar) -> date:
    """Roll ``d`` onto a business day of ``calendar`` per ``convention``.

    Business input is returned unchanged. UNADJUSTED always returns ``d``.
    """
    conv = get_convention(convention)
    if conv is Convention.UNADJUSTED or calendar.is_business_day(d):
        return d

    if conv is Convention.FOLLOWING:
        return calendar.next_business_day(d)
    if conv is Convention.PRECEDING:
        return calendar.previous_business_day(d)
    if conv is Convention.MODIFIED_FOLLOWING:
        nxt = calendar.next_business_day(d)
        if nxt.month != d.month:
            return calendar.previous_business_day(d)
        return nxt
    if conv is Convention.MODIFIED_PRECEDING:
        prv = calendar.previous_business_day(d)
        if prv.month != d.month:
            return calendar.next_business_day(d)
        return prv
    raise AssertionError(conv)
