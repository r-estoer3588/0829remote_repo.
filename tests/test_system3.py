import pandas as pd
import pytest
from system3 import System3Strategy


@pytest.fixture
def dummy_data():
    dates = pd.date_range("2024-01-01", periods=200, freq="B")
    df = pd.DataFrame({
        "Open": [100] * 200,
        "High": [101] * 200,
        "Low": [99] * 200,
        "Close": [100] * 200,
        "Volume": [1_500_000] * 200
    }, index=dates)
    return {"DUMMY": df}


def test_prepare_data(dummy_data):
    strategy = System3Strategy()
    processed = strategy.prepare_data(dummy_data)
    assert "SMA150" in processed["DUMMY"].columns


def test_run_backtest(dummy_data):
    strategy = System3Strategy()
    processed = strategy.prepare_data(dummy_data)
    spy_df = processed["DUMMY"]
    candidates_by_date = {spy_df.index[0]: ["DUMMY"]}
    trades_df = strategy.run_backtest(
        processed, candidates_by_date, capital=10000)
    assert hasattr(trades_df, "empty")
