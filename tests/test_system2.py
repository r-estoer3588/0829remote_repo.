import pandas as pd
import pytest
from strategies.system2_strategy import System2Strategy


@pytest.fixture
def dummy_data():
    dates = pd.date_range("2024-01-01", periods=100, freq="B")
    df = pd.DataFrame(
        {
            "Open": [100] * 100,
            "High": [101] * 100,
            "Low": [99] * 100,
            "Close": [100] * 100,
            "Volume": [2_000_000] * 100,
        },
        index=dates,
    )
    return {"DUMMY": df}


def test_minimal_indicators(dummy_data):
    strategy = System2Strategy()
    processed = strategy.prepare_minimal_for_test(dummy_data)
    assert isinstance(processed, dict)
    assert "DUMMY" in processed
    assert "RSI3" in processed["DUMMY"].columns


def test_placeholder_run(dummy_data):
    # 短期対応: 実バックテストは未完成UIに依存するためスキップ扱い
    pytest.skip("System2 full backtest integration pending")
