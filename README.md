# gsb-bizday

Python 3 stdlib only. `python3 -m unittest discover -s . -v`

## bizday

Multi-market business-day calendar library. No dependencies, no CLI.

```python
from datetime import date, datetime, time
from bizday import Calendar

us = Calendar(
    weekend=(5, 6),                      # Sat/Sun; a Fri/Sat market uses (4, 5)
    holidays={date(2024, 11, 28)},       # caller-supplied
    observance="modified_following",     # also: following / preceding /
                                         # modified_preceding / unadjusted,
                                         # Chinese names OK ("修正顺延" ...)
    tz="America/New_York",
    cutoff=time(17, 0),                  # 17:00 ET inclusive; strictly later
                                         # rolls to the next business day
)

us.is_business_day(date(2024, 3, 9))           # False (Saturday)
us.adjust(date(2024, 3, 9), "顺延")            # 2024-03-11
us.shift(date(2024, 3, 7), 1)                  # T+1 -> 2024-03-08
us.shift(date(2024, 3, 11), -2)                # negative N rolls back
us.add_months(date(2024, 1, 31), 1)            # EOM sticky -> 2024-02-29
us.settle_date(datetime(2024, 3, 8, 17, 30), 1)  # Fri after cutoff -> Tue
```

Rules worth knowing:

- Holidays that hit a weekend are observed per the calendar's `observance`.
- `T+N` counts business days; consecutive holidays/weekends are skipped as
  one run. `N` may be 0 (adjust to a business day) or negative.
- `add_months` is end-of-month sticky: from a last-business-day-of-month it
  lands on the target month's last business day; otherwise the day-of-month
  is clamped (Jan 31 + 1mo -> Feb 28/29) then adjusted.
- Naive datetimes are read in the calendar's timezone; aware ones are
  converted. DST transitions are handled by `zoneinfo`.

## Composite calendars

Two markets can be composed without flattening their holiday tables.
Each leg keeps its own weekend (Sat/Sun vs Fri/Sat) and observance rule.

```python
from bizday import composite_calendar, JOIN, EITHER

both_open = composite_calendar(ny, london, JOIN,   tz="UTC")  # both must be open
any_open = composite_calendar(shanghai, ny, EITHER, tz="UTC") # one open suffices

both_open.is_business_day(date(2024, 11, 28))  # False: US Thanksgiving, London open
any_open.is_business_day(date(2024, 2, 12))    # True:  NY open during Spring Festival
both_open.shift(date(2024, 3, 7), 1)           # composite T+N
both_open.settle_date(trade_dt, 1)             # with the composite's own cutoff
```

A composite requires an explicit `tz` and two leg calendars that each
carry an IANA timezone; bad weekend numbers and missing zones raise.

## Multi-leg fixing/payment

`LegSchedule` chains trade -> fixing -> payment across three calendars
(any two may be the same object, including a join composite).

```python
from bizday import LegSchedule

sch = LegSchedule(trade_cal=ny, fix_cal=london, pay_cal=dubai,
                  n_fix=2, n_pay=2)
trade, fixing, payment = sch.schedule(datetime(2024, 3, 8, 17, 30))

LegSchedule(ny, london, ny, n_fix=-2, n_pay=0)  # negative / zero legs OK
sch.resolve(dt).cutoff_owner                    # payment cal when fix==pay day
```

- The trade timestamp first lands on a trade date using the **trade**
  calendar's inclusive cutoff.
- Fixing is `n_fix` business days on the fixing calendar (0 or negative
  allowed); payment is `n_pay` on the payment calendar.
- Tie-break (pinned by tests): when fixing and payment are the same
  date, the **payment** calendar owns the cutoff.
- Naive datetimes use that leg's timezone; aware ones convert. NY/London
  DST gaps do not raise.

## Coupon schedules

`coupon_schedule` builds unadjusted anchors first, then adjusts each
period independently (the string is never shifted as a whole).

```python
from bizday import coupon_schedule, CouponCollisionError

periods = coupon_schedule(
    effective=date(2024, 1, 31), maturity=date(2024, 7, 31),
    frequency=1, cal=cal, convention="修正顺延", sticky_eom=True,
    front_stub=date(2024, 2, 15),   # optional short/long front stub
    back_stub=date(2024, 6, 30),    # optional short/long back stub
)
for p in periods:
    p.unadjusted_start, p.unadjusted_end  # raw anchors
    p.start, p.end                        # independently adjusted payments
    p.is_stub
```

- EOM stickiness walks month ends (Jan 31 -> Feb 29 in a leap year).
- A maturity on a Sunday adjusts per the convention (e.g. following can
  cross the month) without moving the intermediate anchors.
- Fixed collision policy: if an adjusted coupon reaches the next
  period's unadjusted anchor, `CouponCollisionError` is raised on every
  path - nothing is silently dropped or nudged.
