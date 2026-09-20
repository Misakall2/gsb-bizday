# gsb-bizday

Multi-market business-day calendar library. Python >= 3.9, standard library
only (`datetime` + `zoneinfo`). No runtime dependencies, no CLI, no web
service.

## Run the tests (the only entry point)

From the repository root:

```sh
python3 -m unittest discover
```

That is the whole test workflow. No pytest, no tox, nothing to install.
The same command runs in CI (`.github/workflows/ci.yml`) on a clean machine.

Time zone handling uses the standard-library `zoneinfo` module, which reads
the host's IANA time zone database. Linux/macOS systems have it; on a minimal
container install the OS `tzdata` package. If the data is missing, `Calendar`
raises a `ZoneInfoNotFoundError` telling you exactly that -- it never falls
back to UTC silently.

## Install / package

```sh
python3 -m pip install .          # or: pip install git+<repo-url>
python3 -m build --sdist          # produces dist/bizday-<version>.tar.gz
```

After installation the public import contract is unchanged:

```python
from bizday import Calendar
```

`bizday.__version__` matches the `version` field in `pyproject.toml`.
`dependencies` there is empty on purpose: the library is stdlib-only and
must stay that way. The `tests/` directory is not part of the installed
package.

## bizday

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
