"""bizday: multi-market business-day calendars, T+N settlement, EOM, cutoffs.

Standard library only (datetime + zoneinfo).
"""

__version__ = "1.0.0"

from .calendar import Calendar
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
]
