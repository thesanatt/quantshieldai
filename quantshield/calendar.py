from datetime import date, datetime

import pytz

ET = pytz.timezone('US/Eastern')
IST = pytz.timezone('Asia/Kolkata')

US_HOLIDAYS: dict[int, set[date]] = {
    2026: {
        date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16), date(2026, 4, 3),
        date(2026, 5, 25), date(2026, 6, 19), date(2026, 7, 3), date(2026, 9, 7),
        date(2026, 11, 26), date(2026, 12, 25),
    },
}

INDIA_HOLIDAYS: dict[int, set[date]] = {
    2026: {
        date(2026, 1, 15), date(2026, 1, 26), date(2026, 3, 3), date(2026, 3, 26),
        date(2026, 3, 31), date(2026, 4, 3), date(2026, 4, 14), date(2026, 5, 1),
        date(2026, 5, 28), date(2026, 6, 26), date(2026, 9, 14), date(2026, 10, 2),
        date(2026, 10, 20), date(2026, 11, 10), date(2026, 11, 24), date(2026, 12, 25),
    },
}


def is_us_holiday(d: date | None = None) -> bool:
    d = d or datetime.now(ET).date()
    return d in US_HOLIDAYS.get(d.year, set())


def is_india_holiday(d: date | None = None) -> bool:
    d = d or datetime.now(IST).date()
    return d in INDIA_HOLIDAYS.get(d.year, set())


def is_us_market_hours(now: datetime | None = None) -> bool:
    now = now or datetime.now(ET)
    if now.weekday() >= 5 or is_us_holiday(now.date()):
        return False
    return (9, 30) <= (now.hour, now.minute) <= (16, 0)


def is_india_market_hours(now: datetime | None = None) -> bool:
    now = now or datetime.now(IST)
    if now.weekday() >= 5 or is_india_holiday(now.date()):
        return False
    return (9, 15) <= (now.hour, now.minute) <= (15, 30)
