"""bizday: multi-market business-day calendars, T+N settlement, EOM, cutoffs.

Standard library only (datetime + zoneinfo).
"""

from .calendar import Calendar
from .composite import CompositeCalendar, composite_calendar, JOIN, EITHER
from .legs import LegSchedule, LegResult, multi_leg_schedule
from .coupons import CouponPeriod, CouponCollisionError, coupon_schedule, coupon_dates
from .conventions import (
    Convention,
    normalize_convention,
    FOLLOWING,
    PRECEDING,
    MODIFIED_FOLLOWING,
    MODIFIED_PRECEDING,
    UNADJUSTED,
)

__all__ = [
    "Calendar",
    "Convention",
    "normalize_convention",
    "FOLLOWING",
    "PRECEDING",
    "MODIFIED_FOLLOWING",
    "MODIFIED_PRECEDING",
    "UNADJUSTED",
    "CompositeCalendar",
    "composite_calendar",
    "JOIN",
    "EITHER",
    "LegSchedule",
    "LegResult",
    "multi_leg_schedule",
    "CouponPeriod",
    "CouponCollisionError",
    "coupon_schedule",
    "coupon_dates",
]
