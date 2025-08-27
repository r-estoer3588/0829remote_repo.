import pandas as pd
import pytest
from strategies.system7_strategy import System7Strategy


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


def test_minimal_indicators(dummy_data):
    strategy = System7Strategy()
    processed = strategy.prepare_minimal_for_test(dummy_data)
    assert "ATR50" in processed["SPY"].columns


def test_placeholder_run(dummy_data):
    pytest.skip("System7 full backtest integration pending")
