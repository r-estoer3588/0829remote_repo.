import pandas as pd
import pytest
from strategies.system5_strategy import System5Strategy


@pytest.fixture
def dummy_data():
    dates = pd.date_range("2024-01-01", periods=100, freq="B")
    df = pd.DataFrame(
        {
            "Open": [100] * 100,
            "High": [101] * 100,
            "Low": [99] * 100,
            "Close": [100] * 100,
            "Volume": [1_000_000] * 100,
        },
        index=dates,
    )
    return {"DUMMY": df}


def test_minimal_indicators(dummy_data):
    strategy = System5Strategy()
    processed = strategy.prepare_minimal_for_test(dummy_data)
    assert "SMA100" in processed["DUMMY"].columns


def test_placeholder_run(dummy_data):
    pytest.skip("System5 full backtest integration pending")
