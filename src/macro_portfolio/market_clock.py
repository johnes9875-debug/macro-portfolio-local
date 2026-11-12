from __future__ import annotations

from datetime import timedelta
import pandas as pd
import pandas_market_calendars as mcal


def latest_closed_session(now_utc=None, minutes_after_close: int = 30, calendar_name: str = "NYSE"):
    now_utc = pd.Timestamp.now(tz="UTC") if now_utc is None else pd.Timestamp(now_utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.tz_localize("UTC")
    else:
        now_utc = now_utc.tz_convert("UTC")

    cal = mcal.get_calendar(calendar_name)
    start = (now_utc - pd.Timedelta(days=14)).date()
    end = (now_utc + pd.Timedelta(days=1)).date()
    schedule = cal.schedule(start_date=start, end_date=end)
    if schedule.empty:
        return None
    eligible = schedule[
        schedule["market_close"] + pd.Timedelta(minutes=minutes_after_close) <= now_utc
    ]
    if eligible.empty:
        return None
    session = eligible.index[-1]
    close_ts = eligible.iloc[-1]["market_close"]
    return {
        "session_date": pd.Timestamp(session).date(),
        "market_close_utc": pd.Timestamp(close_ts).to_pydatetime(),
    }
