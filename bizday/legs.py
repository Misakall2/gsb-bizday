"""Multi-leg fixing/payment scheduling (FX swaps, NDFs, cross-market).

A trade flows through three calendar stages:

1. **Trade date** - the trade timestamp lands on a business date of the
   trade calendar, after that calendar's own (inclusive) cutoff.
2. **Fixing date** - ``n_fix`` business days from the trade date on the
   fixing calendar. ``n_fix`` may be 0 or negative.
3. **Payment date** - ``n_pay`` business days from the fixing date on
   the payment calendar. ``n_pay`` may be 0 or negative.

Any of the three calendars may be the same object, including a
:class:`~bizday.composite.CompositeCalendar` shared by two stages.

Tie-break rule (pinned by tests): when fixing and payment fall on the
same calendar date, any cutoff question is decided by the **payment**
calendar, because money movement owns that instant.
"""

from __future__ import annotations

from datetime import date, datetime

from .calendar import Calendar
from .composite import CompositeCalendar
from .conventions import FOLLOWING, normalize_convention


def _as_cal(obj):
    if not isinstance(obj, (Calendar, CompositeCalendar)):
        raise TypeError(f"expected a Calendar or CompositeCalendar, got {type(obj).__name__}")
    if getattr(obj, "tz", None) is None:
        raise ValueError("calendar must carry an IANA timezone")
    return obj


class LegSchedule:
    """Three-stage trade -> fixing -> payment schedule."""

    def __init__(self, trade_cal, fix_cal, pay_cal,
                 n_fix=0, n_pay=0, convention=FOLLOWING):
        self.trade_cal = _as_cal(trade_cal)
        self.fix_cal = _as_cal(fix_cal)
        self.pay_cal = _as_cal(pay_cal)
        if not isinstance(n_fix, int) or isinstance(n_fix, bool):
            raise TypeError("n_fix must be an int")
        if not isinstance(n_pay, int) or isinstance(n_pay, bool):
            raise TypeError("n_pay must be an int")
        self.n_fix = n_fix
        self.n_pay = n_pay
        self.convention = normalize_convention(convention)

    # ------------------------------------------------------------------
    # individual stages
    # ------------------------------------------------------------------
    def trade_date(self, dt) -> date:
        """Business date on the trade calendar after its cutoff.

        Naive datetimes are read in the trade calendar's own timezone;
        aware datetimes are converted. Same inclusive-cutoff semantics
        as ``Calendar.trade_date``.
        """
        return self.trade_cal.trade_date(dt)

    def fixing_date(self, trade) -> date:
        """Fixing date counted on the fixing calendar.

        ``trade`` may be the raw trade datetime (it is resolved via the
        trade calendar first) or an already-resolved trade ``date``.
        """
        if not isinstance(trade, date):
            raise TypeError("trade must be a date or datetime")
        if isinstance(trade, datetime):
            trade = self.trade_date(trade)
        return self.fix_cal.shift(trade, self.n_fix, self.convention)

    def payment_date(self, fixing) -> date:
        """Payment date counted on the payment calendar from ``fixing``."""
        if isinstance(fixing, datetime):
            fixing = fixing.date()
        if not isinstance(fixing, date):
            raise TypeError("fixing must be a date")
        return self.pay_cal.shift(fixing, self.n_pay, self.convention)

    # ------------------------------------------------------------------
    # full schedule
    # ------------------------------------------------------------------
    def schedule(self, dt):
        """Return ``(trade_date, fixing_date, payment_date)``."""
        t = self.trade_date(dt)
        f = self.fixing_date(t)
        p = self.payment_date(f)
        return t, f, p

    def __call__(self, dt):
        return self.schedule(dt)

    # ------------------------------------------------------------------
    # datetime-aware tie-break
    # ------------------------------------------------------------------
    def resolve(self, dt):
        """Like :meth:`schedule` but records which calendar owns a
        same-day fixing/payment cutoff: always the payment calendar.

        Returns a :class:`LegResult`.
        """
        t, f, p = self.schedule(dt)
        same_day = f == p
        owner = self.pay_cal if same_day else self.fix_cal
        return LegResult(trade=t, fixing=f, payment=p,
                         same_day_fix_pay=same_day, cutoff_owner=owner)


class LegResult:
    """Resolved three-stage schedule."""

    __slots__ = ("trade", "fixing", "payment", "same_day_fix_pay", "cutoff_owner")

    def __init__(self, trade, fixing, payment, same_day_fix_pay, cutoff_owner):
        self.trade = trade
        self.fixing = fixing
        self.payment = payment
        self.same_day_fix_pay = same_day_fix_pay
        self.cutoff_owner = cutoff_owner

    def __iter__(self):
        yield self.trade
        yield self.fixing
        yield self.payment

    def __eq__(self, other):
        if isinstance(other, tuple):
            return (self.trade, self.fixing, self.payment) == other
        return NotImplemented

    def __repr__(self):
        return (f"LegResult(trade={self.trade}, fixing={self.fixing}, "
                f"payment={self.payment}, same_day_fix_pay={self.same_day_fix_pay})")


def multi_leg_schedule(dt, trade_cal, fix_cal, pay_cal,
                       n_fix=0, n_pay=0, convention=FOLLOWING):
    """One-shot helper: resolve a trade datetime through all three legs."""
    return LegSchedule(trade_cal, fix_cal, pay_cal,
                       n_fix=n_fix, n_pay=n_pay,
                       convention=convention).schedule(dt)
