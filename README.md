# gsb-bizday

Python 3 stdlib only. `python3 -m unittest discover -s . -v`

## What

Importable market-calendar business-day library. No CLI, no web service,
only `datetime` / `zoneinfo` from the standard library.

```python
from datetime import date, datetime, time
from bizday import BusinessCalendar, t_plus_n, add_months

us = BusinessCalendar(
    "us",
    holidays=[date(2024, 11, 28), date(2024, 11, 29), date(2024, 12, 25)],
    observance="following",          # holiday on weekend -> observed date
    weekend="sat_sun",               # or "fri_sat" per market
    tz="America/New_York",
    cutoff_time=time(17, 0),         # 17:00 NY equity cutoff
)

t_plus_n(date(2024, 11, 27), 1, us)   # date(2024, 12, 2)  (T+1 skips Thu+Fri)
t_plus_n(date(2024, 11, 27), 2, us)   # date(2024, 12, 3)
t_plus_n(date(2024, 11, 27), 0, us)   # same day; negative N rolls backward

# Cutoff: Friday 18:00 NY books onto Monday's session.
t_plus_n(datetime(2024, 11, 22, 18, tzinfo=...), 1, us)  # Tuesday

add_months(date(2024, 1, 31), 1, us)  # date(2024, 2, 29) EOM-aware
```

## Semantics

- Calendars are independent instances; the same date can differ across
  markets. Weekend rules: `sat_sun`, `fri_sat`, `fri_sun`, `thu_fri`.
- Adjustment conventions, bilingual names:
  `following`/`顺延`, `preceding`/`提前`,
  `modified following`/`修正顺延`, `modified preceding`/`修正提前`,
  `unadjusted`/`未调整`.
- Holiday observance uses the same conventions. A Saturday holiday observed
  preceding closes that Friday; observed following closes Monday. Raw and
  observed dates are both treated as non-business.
- T+N counts business days from the effective trade session, stepping over
  whole holiday blocks (Spring Festival week, Thanksgiving + Friday). N may
  be 0 or negative.
- Cutoff boundary is exclusive of the current day: `time < cutoff` stays on
  today, `time >= cutoff` rolls to the next business day. Naive datetimes
  use the calendar timezone; aware datetimes are converted into it. DST
  transitions are handled by `zoneinfo`.
- EOM: if the start date is the last calendar day of its month (or
  `end_of_month=True`), month rolls land on the last business day of the
  target month; Jan 31 + 1m gives Feb 28/29, never a date in March.

## Tests

`python3 -m unittest discover -s . -v`
