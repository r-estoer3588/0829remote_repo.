import pandas as pd
import pytest
from strategies.system4_strategy import System4Strategy


@pytest.fixture
def dummy_data():
    dates = pd.date_range("2024-01-01", periods=250, freq="B")
    df = pd.DataFrame(
        {
            "Open": [100] * 250,
            "High": [101] * 250,
            "Low": [99] * 250,
            "Close": [100] * 250,
            "Volume": [2_000_000] * 250,
        },
        index=dates,
    )
    return {"DUMMY": df}


def test_minimal_indicators(dummy_data):
    strategy = System4Strategy()
    processed = strategy.prepare_minimal_for_test(dummy_data)
    assert "SMA200" in processed["DUMMY"].columns


def test_placeholder_run(dummy_data):
    pytest.skip("System4 full backtest integration pending")
