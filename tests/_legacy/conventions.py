"""Business-day adjustment / holiday-observance conventions.

Names are accepted in English and Chinese so callers on both desks
can use what they are used to.
"""

from __future__ import annotations

FOLLOWING = "following"
PRECEDING = "preceding"
MODIFIED_FOLLOWING = "modified_following"
MODIFIED_PRECEDING = "modified_preceding"
UNADJUSTED = "unadjusted"

_ALIASES = {
    # following
    "following": FOLLOWING,
    "follow": FOLLOWING,
    "f": FOLLOWING,
    "顺延": FOLLOWING,
    "往后": FOLLOWING,
    "向后": FOLLOWING,
    "下一工作日": FOLLOWING,
    # preceding
    "preceding": PRECEDING,
    "precede": PRECEDING,
    "p": PRECEDING,
    "提前": PRECEDING,
    "往前": PRECEDING,
    "向前": PRECEDING,
    "上一工作日": PRECEDING,
    # modified following
    "modifiedfollowing": MODIFIED_FOLLOWING,
    "modified following": MODIFIED_FOLLOWING,
    "modfollowing": MODIFIED_FOLLOWING,
    "mf": MODIFIED_FOLLOWING,
    "修正顺延": MODIFIED_FOLLOWING,
    "修正往后": MODIFIED_FOLLOWING,
    "调整后顺延": MODIFIED_FOLLOWING,
    # modified preceding
    "modifiedpreceding": MODIFIED_PRECEDING,
    "modified preceding": MODIFIED_PRECEDING,
    "modpreceding": MODIFIED_PRECEDING,
    "mp": MODIFIED_PRECEDING,
    "修正提前": MODIFIED_PRECEDING,
    "修正往前": MODIFIED_PRECEDING,
    "调整后提前": MODIFIED_PRECEDING,
    # unadjusted
    "unadjusted": UNADJUSTED,
    "none": UNADJUSTED,
    "raw": UNADJUSTED,
    "不调整": UNADJUSTED,
    "未调整": UNADJUSTED,
}


class Convention(str):
    """Marker type so callers can use Convention.FOLLOWING style too."""

    def __new__(cls, value):
        return super().__new__(cls, normalize_convention(value))


Convention.FOLLOWING = FOLLOWING
Convention.PRECEDING = PRECEDING
Convention.MODIFIED_FOLLOWING = MODIFIED_FOLLOWING
Convention.MODIFIED_PRECEDING = MODIFIED_PRECEDING
Convention.UNADJUSTED = UNADJUSTED


def normalize_convention(name) -> str:
    """Map an English/Chinese convention name to its canonical form."""
    if not isinstance(name, str):
        raise TypeError(f"convention must be a string, got {type(name).__name__}")
    key = name.strip().lower().replace("-", " ").replace("_", " ")
    key = " ".join(key.split())
    candidates = (key, key.replace(" ", "_"), key.replace(" ", ""))
    for candidate in candidates:
        if candidate in _ALIASES:
            return _ALIASES[candidate]
    raise ValueError(f"unknown convention: {name!r}")
