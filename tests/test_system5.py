import pandas as pd
import pytest
from system5 import System5Strategy

@pytest.fixture
def dummy_data():
    dates = pd.date_range("2024-01-01", periods=100, freq="B")
    df = pd.DataFrame({
        "Open": [100]*100,
        "High": [101]*100,
        "Low":  [99]*100,
        "Close": [100]*100,
        "Volume": [1_000_000]*100
    }, index=dates)
    return {"DUMMY": df}

def test_prepare_data(dummy_data):
    strategy = System5Strategy()
    processed = strategy.prepare_data(dummy_data)
    assert "SMA100" in processed["DUMMY"].columns

def test_run_backtest(dummy_data):
    strategy = System5Strategy()
    processed = strategy.prepare_data(dummy_data)
    spy_df = processed["DUMMY"]
    candidates_by_date = {spy_df.index[0]: ["DUMMY"]}
    trades_df = strategy.run_backtest(processed, candidates_by_date, capital=10000)
    assert hasattr(trades_df, "empty")
