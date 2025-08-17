import pandas as pd
import pytest
from system6 import System6Strategy

@pytest.fixture
def dummy_data():
    dates = pd.date_range("2024-01-01", periods=50, freq="B")
    df = pd.DataFrame({
        "Open": [100]*50,
        "High": [101]*50,
        "Low":  [99]*50,
        "Close": [100]*50,
        "Volume": [1_000_000]*50
    }, index=dates)
    return {"DUMMY": df}

def test_prepare_data(dummy_data):
    strategy = System6Strategy()
    processed = strategy.prepare_data(dummy_data)
    assert "ATR10" in processed["DUMMY"].columns

def test_run_backtest(dummy_data):
    strategy = System6Strategy()
    processed = strategy.prepare_data(dummy_data)
    spy_df = processed["DUMMY"]
    candidates_by_date = {spy_df.index[0]: ["DUMMY"]}
    trades_df = strategy.run_backtest(processed, candidates_by_date, capital=10000)
    assert hasattr(trades_df, "empty")
