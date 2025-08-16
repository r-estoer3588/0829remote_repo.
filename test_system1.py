# test_system1.py
import pandas as pd
import pytest
from system1 import prepare_data_vectorized_system1, run_backtest

@pytest.fixture
def dummy_data():
    dates = pd.date_range("2024-01-01", periods=250, freq="B")
    df = pd.DataFrame({
        "Open": [100 + i*0.1 for i in range(250)],
        "High": [101 + i*0.1 for i in range(250)],
        "Low":  [ 99 + i*0.1 for i in range(250)],
        "Close":[100 + i*0.1 for i in range(250)],
        "Volume":[1_000_000] * 250
    }, index=dates)
    return {"DUMMY": df}

def test_prepare_data(dummy_data):
    processed = prepare_data_vectorized_system1(dummy_data)
    assert isinstance(processed, dict)
    assert "DUMMY" in processed
    df = processed["DUMMY"]
    assert "SMA25" in df.columns
    assert not df.empty

def test_run_backtest(dummy_data):
    processed = prepare_data_vectorized_system1(dummy_data)
    spy_df = processed["DUMMY"]  # 簡易的に同じDFをSPYとして使う
    equity_curve_df, trades, summary = run_backtest(processed, spy_df, capital=10000)
    assert isinstance(trades, list)
    assert isinstance(equity_curve_df, pd.DataFrame)
    assert "equity" in equity_curve_df.columns
    assert isinstance(summary, dict)

def test_empty_data():
    processed = prepare_data_vectorized_system1({})
    assert processed == {}
