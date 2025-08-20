import pandas as pd
import pytest
from system7 import System7Strategy


@pytest.fixture
def dummy_data():
    dates = pd.date_range("2024-01-01", periods=70, freq="B")
    df = pd.DataFrame(
        {
            "Open": [100] * 70,
            "High": [101] * 70,
            "Low": [99] * 70,
            "Close": [100] * 70,
            "Volume": [1_000_000] * 70,
        },
        index=dates,
    )
    return {"SPY": df}


def test_prepare_data(dummy_data):
    strategy = System7Strategy()
    processed = strategy.prepare_data(dummy_data)
    assert "ATR50" in processed["SPY"].columns


def test_run_backtest(dummy_data):
    strategy = System7Strategy()
    processed = strategy.prepare_data(dummy_data)
    spy_df = processed["SPY"]
    candidates_by_date = {spy_df.index[0]: ["SPY"]}
    trades_df = strategy.run_backtest(processed, candidates_by_date, capital=10000)
    assert hasattr(trades_df, "empty")
