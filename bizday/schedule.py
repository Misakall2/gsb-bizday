"""Coupon / payment schedules with stubs and per-period adjustment.

Unadjusted anchor dates are generated first (rolled from the maturity
backward or from the start forward); every period's payment date is
then adjusted individually. The whole string is never shifted as one.
"""

from __future__ import annotations

import calendar as _cal
from dataclasses import dataclass
from datetime import date

from .calendar import Calendar
from .conventions import MODIFIED_FOLLOWING, normalize_convention

FRONT = "front"
BACK = "back"

DROP = "drop"
ERROR = "error"


@dataclass(frozen=True)
class CouponPeriod:
    """One coupon period: unadjusted anchors plus the adjusted payment."""
    start: date          # unadjusted period start
    end: date            # unadjusted period end
    payment_date: date   # adjusted end date (when the coupon is paid)


def _is_cal_month_end(d: date) -> bool:
    return d.day == _cal.monthrange(d.year, d.month)[1]


def _add_months_unadjusted(d: date, months: int, eom_sticky: bool) -> date:
    """Pure calendar-month arithmetic on unadjusted anchors."""
    total = d.year * 12 + (d.month - 1) + months
    year, month = divmod(total, 12)
    month += 1
    if eom_sticky and _is_cal_month_end(d):
        day = _cal.monthrange(year, month)[1]
    else:
        day = min(d.day, _cal.monthrange(year, month)[1])
    return date(year, month, day)


def coupon_schedule(calendar: Calendar, start: date, end: date,
                    step_months: int,
                    convention=MODIFIED_FOLLOWING,
                    eom_sticky: bool = True,
                    stub: str = BACK,
                    long_stub: bool = False,
                    on_collision: str = DROP) -> list:
    """Build a coupon schedule between ``start`` and ``end``.

    stub="back":  anchors roll backward from the maturity; any residual
                  stub period sits at the front of the schedule.
    stub="front": anchors roll forward from the start; the residual
                  sits at the end.
    long_stub=True merges a residual into its neighbouring period,
    producing one long stub instead of a short one.

    Each period's payment date is its own unadjusted end date adjusted
    per ``convention`` on ``calendar`` -- anchors never move. If an
    adjusted payment date collides with the *next* period's unadjusted
    end anchor, ``on_collision`` decides: "drop" (default) removes the
    colliding payment, "error" raises ValueError.
    """
    if not isinstance(calendar, Calendar):
        raise TypeError("calendar must be a Calendar")
    if not isinstance(step_months, int) or step_months <= 0:
        raise ValueError("step_months must be a positive int")
    if end <= start:
        raise ValueError("end must be after start")
    if stub not in (FRONT, BACK):
        raise ValueError(f"stub must be {FRONT!r} or {BACK!r}")
    if on_collision not in (DROP, ERROR):
        raise ValueError(f"on_collision must be {DROP!r} or {ERROR!r}")
    convention = normalize_convention(convention)

    if stub == BACK:
        anchors = [end]
        while True:
            prev = _add_months_unadjusted(anchors[-1], -step_months, eom_sticky)
            if prev <= start:
                break
            anchors.append(prev)
        anchors.reverse()
        if anchors[0] > start:
            if long_stub and len(anchors) > 1:
                anchors = anchors[1:]          # merge residual into 1st period
            anchors = [start] + anchors
    else:
        anchors = [start]
        while True:
            nxt = _add_months_unadjusted(anchors[-1], step_months, eom_sticky)
            if nxt >= end:
                break
            anchors.append(nxt)
        if anchors[-1] < end:
            if long_stub and len(anchors) > 1:
                anchors = anchors[:-1]         # merge residual into last period
            anchors = anchors + [end]

    periods = []
    for i in range(len(anchors) - 1):
        p_start, p_end = anchors[i], anchors[i + 1]
        payment = calendar.adjust(p_end, convention)
        # Collision rule (pinned): an adjusted payment that lands exactly
        # on the NEXT period's unadjusted end anchor is dropped by default.
        if i + 2 < len(anchors) and payment == anchors[i + 2]:
            if on_collision == ERROR:
                raise ValueError(
                    f"adjusted payment {payment} collides with next "
                    f"unadjusted anchor {anchors[i + 2]}")
            continue
        periods.append(CouponPeriod(start=p_start, end=p_end,
                                    payment_date=payment))
    return periods
