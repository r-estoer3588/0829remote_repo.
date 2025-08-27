import pandas as pd
import pytest
from strategies.system3_strategy import System3Strategy


@pytest.fixture
def dummy_data():
    dates = pd.date_range("2024-01-01", periods=200, freq="B")
    df = pd.DataFrame(
        {
            "Open": [100] * 200,
            "High": [101] * 200,
            "Low": [99] * 200,
            "Close": [100] * 200,
            "Volume": [1_500_000] * 200,
        },
        index=dates,
    )
    return {"DUMMY": df}


def test_minimal_indicators(dummy_data):
    strategy = System3Strategy()
    processed = strategy.prepare_minimal_for_test(dummy_data)
    assert "SMA150" in processed["DUMMY"].columns


def test_placeholder_run(dummy_data):
    pytest.skip("System3 full backtest integration pending")
