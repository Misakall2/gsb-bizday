"""Local-time interpretation and the daily cutoff rule.

Dependency direction: sits above ``workdays`` (to roll a post-cutoff
trade onto the next business day) and ``zoneinfo``. Knows nothing
about month arithmetic.
"""

from __future__ import annotations

from datetime import date, datetime

from .conventions import FOLLOWING
from .workdays import Workdays


class CutoffClock:
    """Map trade timestamps to business dates for one market."""

    __slots__ = ("tz", "cutoff", "workdays")

    def __init__(self, tz, cutoff, workdays: Workdays):
        self.tz = tz
        self.cutoff = cutoff
        self.workdays = workdays

    def localize(self, dt: datetime) -> datetime:
        """Interpret a datetime in this calendar's timezone.

        Aware datetimes are converted; naive ones are assumed to already
        be in the market's local time. DST transitions are handled by
        zoneinfo, so spring-forward/fall-back days do not blow up.
        """
        if not isinstance(dt, datetime):
            raise TypeError("expected a datetime")
        if dt.tzinfo is None:
            return dt.replace(tzinfo=self.tz)
        return dt.astimezone(self.tz)

    def trade_date(self, dt) -> date:
        """The business date a trade belongs to, after the cutoff rule.

        Local time strictly after the cutoff rolls to the next business
        day; exactly at the cutoff stays on the same day. The result is
        always a business day.
        """
        if isinstance(dt, datetime):
            local = self.localize(dt)
            d = local.date()
            if self.cutoff is not None and local.timetz().replace(tzinfo=None) > self.cutoff:
                d = self.workdays.step(d, +1)
        elif isinstance(dt, date):
            d = dt
        else:
            raise TypeError("expected a date or datetime")
        return self.workdays.adjust(d, FOLLOWING)
