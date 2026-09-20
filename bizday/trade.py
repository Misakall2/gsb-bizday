"""Multi-leg trades: trade date -> fixing date -> payment date.

Each leg can live on a different calendar (which may itself be a
CompositeCalendar). A trade is an aware or naive datetime; naive
datetimes are read in the trade calendar's timezone.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .calendar import Calendar
from .conventions import FOLLOWING


@dataclass(frozen=True)
class TradeSchedule:
    trade_date: date
    fixing_date: date
    payment_date: date


def schedule_trade(trade_dt, trade_calendar: Calendar,
                   fixing_calendar: Calendar, n_fix: int,
                   payment_calendar: Calendar, n_pay: int,
                   convention=FOLLOWING) -> TradeSchedule:
    """Resolve the three dates of a multi-leg trade.

    1. Trade date: ``trade_calendar``'s cutoff lands the trade datetime
       on a business date (cutoff inclusive, strictly-after rolls).
    2. Fixing date: ``n_fix`` business days from the trade date on
       ``fixing_calendar``. ``n_fix`` may be 0 or negative (fixing
       *before* the trade date, e.g. NDFs fixed off an earlier rate).
    3. Payment date: ``n_pay`` business days from the fixing date on
       ``payment_calendar``.

    Pinned rule: when fixing and payment fall on the trade date itself
    (``n_fix == 0`` and ``n_pay == 0``), the *payment* calendar's cutoff
    is authoritative for the trade datetime, not the trade/fixing
    calendar's.
    """
    for cal in (trade_calendar, fixing_calendar, payment_calendar):
        if not isinstance(cal, Calendar):
            raise TypeError(f"expected a Calendar, got {type(cal).__name__}")
    if not isinstance(n_fix, int) or not isinstance(n_pay, int):
        raise TypeError("n_fix and n_pay must be ints")

    if n_fix == 0 and n_pay == 0:
        trade_d = payment_calendar.trade_date(trade_dt)
    else:
        trade_d = trade_calendar.trade_date(trade_dt)
    fixing_d = fixing_calendar.shift(trade_d, n_fix, convention)
    payment_d = payment_calendar.shift(fixing_d, n_pay, convention)
    return TradeSchedule(trade_date=trade_d, fixing_date=fixing_d,
                         payment_date=payment_d)
