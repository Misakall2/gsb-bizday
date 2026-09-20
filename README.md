# bizday

Multi-market business-day calendar library: weekends, observed holidays,
T+N settlement, end-of-month stickiness, and trading-day cutoffs.

- Python >= 3.9, **standard library only** (`datetime` + `zoneinfo`).
  No runtime dependencies, nothing to `pip install` for the library itself.
- Not a CLI, not a service. Embed it:

```python
from bizday import Calendar
```

## Run the tests

The one and only test entry point, from the repository root:

```sh
python3 -m unittest discover
```

No pytest, no tox, no third-party packages required. A system IANA tz
database must be present (it is, on any normal Linux/macOS install; on
minimal containers run e.g. `apt-get install tzdata`). If tz data is
missing, `Calendar` raises a `RuntimeError` saying so instead of silently
assuming UTC.

## Install

```sh
python3 -m pip install .
```

After that, `from bizday import Calendar` works from anywhere. The `tests/`
directory is not part of the installed package.

## Build a source distribution

```sh
python3 -m pip install build   # build-time tool only, not a runtime dep
python3 -m build --sdist
```

The version is defined once, in `bizday/__init__.py` (`__version__`), and
`pyproject.toml` picks it up from there.

## Usage

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

## CI

`.github/workflows/ci.yml` runs the same `python -m unittest discover`
on clean GitHub-hosted runners across Python 3.9-3.12. It installs nothing.
