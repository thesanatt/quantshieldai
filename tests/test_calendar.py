from datetime import date, datetime

from quantshield.calendar import (
    INDIA_HOLIDAYS,
    IST,
    US_HOLIDAYS,
    is_india_holiday,
    is_india_market_hours,
    is_us_holiday,
)


def test_current_year_has_holiday_entries() -> None:
    year = datetime.now(IST).year
    assert INDIA_HOLIDAYS.get(year)
    assert US_HOLIDAYS.get(year)


def test_india_2026_list_matches_exchange_circular() -> None:
    assert len(INDIA_HOLIDAYS[2026]) == 16
    assert is_india_holiday(date(2026, 10, 20))
    assert is_india_holiday(date(2026, 11, 10))
    assert not is_india_holiday(date(2026, 11, 9))
    assert all(d.weekday() < 5 for d in INDIA_HOLIDAYS[2026])


def test_us_2026_includes_juneteenth() -> None:
    assert is_us_holiday(date(2026, 6, 19))


def test_india_market_hours_closed_on_holiday() -> None:
    assert not is_india_market_hours(IST.localize(datetime(2026, 10, 20, 10, 0)))
    assert is_india_market_hours(IST.localize(datetime(2026, 10, 21, 10, 0)))
    assert not is_india_market_hours(IST.localize(datetime(2026, 10, 21, 16, 0)))
