"""Interest-rate coupon schedules with stubs, EOM stickiness and
per-period business-day adjustment.

Design rules (pinned by tests):

* **Unadjusted anchors first.** The regular anchor grid is rolled back
  from maturity (so the final full coupon lands on maturity); when a
  front stub is given the grid instead steps forward from the stub.
  Each anchor is then adjusted *independently* on the payment calendar;
  the whole string is never shifted together.
* **Stubs.** ``front_stub`` (an unadjusted date between the first two
  back-rolled anchors) produces a short/long front period; ``back_stub``
  (a date between the last regular anchor and maturity) produces a
  short/long back period.
* **Maturity adjusts on its own.** If maturity lands on a weekend or
  holiday it is adjusted per the convention, but the intermediate
  unadjusted anchors are NOT rewritten to follow it.
* **Collisions.** If an adjusted coupon date coincides with the *next*
  period's unadjusted anchor, :class:`CouponCollisionError` is raised.
  This is the single, fixed policy for every path - nothing is silently
  dropped or nudged.
"""

from __future__ import annotations

import calendar as _cal
from datetime import date, datetime

from .calendar import Calendar
from .composite import CompositeCalendar
from .conventions import FOLLOWING, normalize_convention


class CouponCollisionError(ValueError):
    """Raised when an adjusted coupon date hits the next unadjusted anchor."""


class CouponPeriod:
    """One coupon period.

    ``unadjusted_start``/``unadjusted_end`` are the raw anchor dates;
    ``start``/``end`` are adjusted payment dates; ``stub`` marks a
    front/back stub period that is not a regular ``frequency``-month span.
    """

    __slots__ = ("unadjusted_start", "unadjusted_end", "start", "end", "stub")

    def __init__(self, unadjusted_start, unadjusted_end, start, end, stub=False):
        self.unadjusted_start = unadjusted_start
        self.unadjusted_end = unadjusted_end
        self.start = start
        self.end = end
        self.stub = stub

    @property
    def is_stub(self) -> bool:
        return bool(self.stub)

    def __iter__(self):
        yield self.start
        yield self.end

    def __eq__(self, other):
        if isinstance(other, tuple):
            return (self.start, self.end) == other
        return NotImplemented

    def __repr__(self):
        tag = f", stub={self.stub!r}" if self.stub else ""
        return f"CouponPeriod({self.start} -> {self.end}{tag})"


def _add_months_raw(d: date, months: int, sticky_eom: bool) -> date:
    """Calendar-month arithmetic on raw dates, EOM-sticky when asked.

    Independent of any business calendar: this builds the unadjusted
    anchor grid.
    """
    total = d.year * 12 + (d.month - 1) + months
    year, month = divmod(total, 12)
    month += 1
    last_day = _cal.monthrange(year, month)[1]
    if sticky_eom and d.day == _cal.monthrange(d.year, d.month)[1]:
        return date(year, month, last_day)
    return date(year, month, min(d.day, last_day))


def coupon_schedule(effective: date, maturity: date, frequency: int,
                    cal, convention=FOLLOWING, sticky_eom=True,
                    front_stub=None, back_stub=None):
    """Build a coupon schedule from ``effective`` to ``maturity``.

    Parameters
    ----------
    effective, maturity:
        Unadjusted value/start and maturity/end dates.
    frequency:
        Regular period length in months (e.g. 3, 6, 12).
    cal:
        Payment calendar (``Calendar`` or ``CompositeCalendar``) used to
        adjust each period boundary independently.
    convention:
        Adjustment applied to every boundary (existing names, Chinese
        aliases included).
    sticky_eom:
        If True (default), rolling month-end dates keeps landing on the
        calendar month end (Jan 31 -> Feb 28/29 style).
    front_stub, back_stub:
        Optional unadjusted stub boundary dates. A front stub sits
        between ``effective`` and the first regular anchor; a back stub
        sits between the last regular anchor and ``maturity``.

    Returns a list of :class:`CouponPeriod` ordered oldest to newest.
    Raises :class:`CouponCollisionError` on an adjusted/unadjusted clash.
    """
    if isinstance(effective, datetime):
        effective = effective.date()
    if isinstance(maturity, datetime):
        maturity = maturity.date()
    if not isinstance(effective, date) or not isinstance(maturity, date):
        raise TypeError("effective and maturity must be dates")
    if not isinstance(frequency, int) or frequency <= 0:
        raise ValueError("frequency must be a positive int (months)")
    if maturity <= effective:
        raise ValueError("maturity must be after effective")
    if not isinstance(cal, (Calendar, CompositeCalendar)):
        raise TypeError("cal must be a Calendar or CompositeCalendar")
    convention = normalize_convention(convention)

    for name, stub in (("front_stub", front_stub), ("back_stub", back_stub)):
        if stub is not None:
            if isinstance(stub, datetime):
                raise TypeError(f"{name} must be a date, not datetime")
            if not isinstance(stub, date):
                raise TypeError(f"{name} must be a date")
            if not effective < stub < maturity:
                raise ValueError(f"{name} must lie strictly between effective and maturity")

    # ------------------------------------------------------------------
    # 1. Regular anchor grid.
    #
    #    Without a front stub the grid is rolled back from maturity, so
    #    the final full coupon always lands on the maturity roll; an
    #    anchor that would land on/before the effective date is dropped
    #    (it becomes the open of the first, possibly long, period).
    #
    #    With a front stub the stub boundary OPENS the regular schedule:
    #    anchors step forward from it by ``frequency`` months, so the
    #    first full coupon after the stub is properly frequency-aligned
    #    to the stub. Maturity remains the fixed final anchor and is
    #    never rewritten (a tail gap becomes the back period/stub).
    # ------------------------------------------------------------------
    anchors = []
    if front_stub is not None:
        cur = _add_months_raw(front_stub, frequency, sticky_eom)
        while cur < maturity:
            anchors.append(cur)
            cur = _add_months_raw(cur, frequency, sticky_eom)
    else:
        cur = _add_months_raw(maturity, -frequency, sticky_eom)
        while cur > effective:
            anchors.insert(0, cur)
            cur = _add_months_raw(cur, -frequency, sticky_eom)

    # With a back stub the final regular anchor must precede it; any
    # regular anchor on/after the back stub belongs to the stub gap.
    if back_stub is not None:
        anchors = [a for a in anchors if a < back_stub]

    # ------------------------------------------------------------------
    # 2. Insert / validate stub boundaries into the unadjusted boundary
    #    list: [effective, (front_stub), ... anchors ..., (back_stub),
    #    maturity].
    # ------------------------------------------------------------------
    boundaries = [effective]
    if front_stub is not None:
        if front_stub in anchors:
            raise ValueError("front_stub must not coincide with a regular anchor")
        # Must sit between effective and the first regular anchor.
        if not (anchors and effective < front_stub < anchors[0]):
            raise ValueError("front_stub must be in the first regular period")
        boundaries.append(front_stub)
    boundaries.extend(anchors)
    if back_stub is not None:
        if back_stub in anchors:
            raise ValueError("back_stub must not coincide with a regular anchor")
        # In the final regular gap: after the last anchor (or effective
        # when there are no regular anchors) and before maturity.
        gap_start = anchors[-1] if anchors else effective
        if not gap_start < back_stub < maturity:
            raise ValueError("back_stub must be in the final regular period")
        boundaries.append(back_stub)
    boundaries.append(maturity)
    boundaries = sorted(set(boundaries))

    # ------------------------------------------------------------------
    # 3. Adjust every boundary independently (never as a moving string),
    #    then build periods from consecutive boundary pairs.
    # ------------------------------------------------------------------
    adjusted = [cal.adjust(b, convention) for b in boundaries]

    front_set = {front_stub} if front_stub is not None else set()
    back_set = {back_stub} if back_stub is not None else set()
    periods = []
    for i in range(len(boundaries) - 1):
        raw_start, raw_end = boundaries[i], boundaries[i + 1]
        adj_start, adj_end = adjusted[i], adjusted[i + 1]
        stub_flag = raw_end in front_set or raw_start in back_set
        periods.append(CouponPeriod(raw_start, raw_end, adj_start, adj_end, stub=stub_flag))

    # ------------------------------------------------------------------
    # 4. Fixed collision policy: an adjusted coupon reaching the next
    #    period's unadjusted END anchor is an error on every code path.
    # ------------------------------------------------------------------
    # Period i covers raw boundaries[i] -> boundaries[i+1]. Its adjusted
    # payment must not move so far that it reaches a LATER raw boundary
    # than its own end - i.e. boundaries[i+2] is the first forbidden
    # target (the next period's raw END anchor). Adjacent periods share a
    # boundary (boundaries[i+1] is both this end and next start), which
    # is normal and never a collision.
    for i, per in enumerate(periods[:-1]):
        next_per = periods[i + 1]
        forbidden = boundaries[i + 2] if i + 2 < len(boundaries) else None
        moved = per.end != per.unadjusted_end
        if forbidden is not None and moved and per.end >= forbidden:
            raise CouponCollisionError(
                f"adjusted coupon {per.end} collides with the next "
                f"unadjusted anchor {forbidden}"
            )
        if per.end > next_per.end:
            raise CouponCollisionError(
                f"adjusted coupons out of order: {per.end} after "
                f"{next_per.end}"
            )

    return periods


def coupon_dates(*args, **kwargs):
    """Convenience wrapper returning just the adjusted payment dates."""
    return [p.end for p in coupon_schedule(*args, **kwargs)]
