import pytest

pytest.importorskip("pandas_market_calendars")

import pandas as pd
from macro_portfolio.market_clock import latest_closed_session


def test_latest_closed_session_returns_session():
    # Friday after the U.S. close in UTC.
    result = latest_closed_session(pd.Timestamp("2026-09-18 22:00:00", tz="UTC"), 30, "NYSE")
    assert result is not None
    assert str(result["session_date"]) == "2026-09-18"
