import pandas as pd
import pytest
from strategies.system1_strategy import System1Strategy


@pytest.fixture
def dummy_data():
    dates = pd.date_range("2024-01-01", periods=250, freq="B")
    df = pd.DataFrame(
        {
            "Open": [100 + i * 0.1 for i in range(250)],
            "High": [101 + i * 0.1 for i in range(250)],
            "Low": [99 + i * 0.1 for i in range(250)],
            "Close": [100 + i * 0.1 for i in range(250)],
            "Volume": [1_000_000] * 250,
        },
        index=dates,
    )
    return {"DUMMY": df}


def test_prepare_data(dummy_data):
    strategy = System1Strategy()
    processed = strategy.prepare_data(dummy_data)
    assert isinstance(processed, dict)
    assert "DUMMY" in processed
    assert "SMA25" in processed["DUMMY"].columns


def test_placeholder_run(dummy_data):
    pytest.skip("System1 full backtest inputs require candidate records; skipping")
