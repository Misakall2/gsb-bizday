"""Business day adjustment conventions (Business Day Convention, BDC).

Accepted names (English + Chinese, spaces/underscores/hyphens insensitive):
    following               顺延 / 下一工作日 / 向后
    preceding               提前 / 上一工作日 / 向前
    modified following      修正顺延 /  modified_following / modfollow
    modified preceding      修正提前 /  modified_preceding / modprecede
    unadjusted              未调整 / 不调整 / none
"""
from __future__ import annotations

from enum import Enum


class Convention(str, Enum):
    FOLLOWING = "following"
    PRECEDING = "preceding"
    MODIFIED_FOLLOWING = "modified_following"
    MODIFIED_PRECEDING = "modified_preceding"
    UNADJUSTED = "unadjusted"


# Singleton-style aliases are convenient for static calls / annotations.
following = Convention.FOLLOWING
preceding = Convention.PRECEDING
modified_following = Convention.MODIFIED_FOLLOWING
modified_preceding = Convention.MODIFIED_PRECEDING
unadjusted = Convention.UNADJUSTED


_ALIASES = {
    # following
    "following": Convention.FOLLOWING,
    "follow": Convention.FOLLOWING,
    "f": Convention.FOLLOWING,
    "\u987a\u5ef6": Convention.FOLLOWING,
    "\u5411\u540e": Convention.FOLLOWING,
    "\u4e0b\u4e00\u4e2a\u5de5\u4f5c\u65e5": Convention.FOLLOWING,
    "\u4e0b\u4e00\u5de5\u4f5c\u65e5": Convention.FOLLOWING,
    # preceding
    "preceding": Convention.PRECEDING,
    "previous": Convention.PRECEDING,
    "p": Convention.PRECEDING,
    "\u63d0\u524d": Convention.PRECEDING,
    "\u5411\u524d": Convention.PRECEDING,
    "\u4e0a\u4e00\u4e2a\u5de5\u4f5c\u65e5": Convention.PRECEDING,
    "\u4e0a\u4e00\u5de5\u4f5c\u65e5": Convention.PRECEDING,
    # modified following
    "modifiedfollowing": Convention.MODIFIED_FOLLOWING,
    "modfollowing": Convention.MODIFIED_FOLLOWING,
    "modfollow": Convention.MODIFIED_FOLLOWING,
    "mf": Convention.MODIFIED_FOLLOWING,
    "\u4fee\u6b63\u987a\u5ef6": Convention.MODIFIED_FOLLOWING,
    "\u4fee\u6b63\u5411\u540e": Convention.MODIFIED_FOLLOWING,
    # modified preceding
    "modifiedpreceding": Convention.MODIFIED_PRECEDING,
    "modpreceding": Convention.MODIFIED_PRECEDING,
    "modprecede": Convention.MODIFIED_PRECEDING,
    "mp": Convention.MODIFIED_PRECEDING,
    "\u4fee\u6b63\u63d0\u524d": Convention.MODIFIED_PRECEDING,
    "\u4fee\u6b63\u5411\u524d": Convention.MODIFIED_PRECEDING,
    # unadjusted
    "unadjusted": Convention.UNADJUSTED,
    "none": Convention.UNADJUSTED,
    "na": Convention.UNADJUSTED,
    "\u672a\u8c03\u6574": Convention.UNADJUSTED,
    "\u4e0d\u8c03\u6574": Convention.UNADJUSTED,
    "\u65e0": Convention.UNADJUSTED,
}


def _normalize(name: str) -> str:
    return "".join(ch for ch in name.strip().lower() if ch not in " _-\t")


def get_convention(value: "Convention | str") -> Convention:
    """Resolve a Convention from an enum or a Chinese/English name."""
    if isinstance(value, Convention):
        return value
    if not isinstance(value, str):
        raise TypeError(f"unsupported convention: {value!r}")
    key = _normalize(value)
    try:
        return _ALIASES[key]
    except KeyError:
        raise ValueError(f"unknown business day convention: {value!r}") from None
