import pandas as pd
import pytest
from system4 import System4Strategy

@pytest.fixture
def dummy_data():
    dates = pd.date_range("2024-01-01", periods=250, freq="B")
    df = pd.DataFrame({
        "Open": [100]*250,
        "High": [101]*250,
        "Low":  [99]*250,
        "Close": [100]*250,
        "Volume": [2_000_000]*250
    }, index=dates)
    return {"DUMMY": df}

def test_prepare_data(dummy_data):
    strategy = System4Strategy()
    processed = strategy.prepare_data(dummy_data)
    assert "SMA200" in processed["DUMMY"].columns

def test_run_backtest(dummy_data):
    strategy = System4Strategy()
    processed = strategy.prepare_data(dummy_data)
    spy_df = processed["DUMMY"]
    candidates_by_date = {spy_df.index[0]: ["DUMMY"]}
    trades_df = strategy.run_backtest(processed, candidates_by_date, capital=10000)
    assert hasattr(trades_df, "empty")
