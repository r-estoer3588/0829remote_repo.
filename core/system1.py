"""System1 core logic (alias layer).

Exports the same functions but imports the implementation
from `system.core` to avoid duplication.
"""

from system.core import (
    prepare_data_vectorized_system1,
    generate_roc200_ranking_system1,
    get_total_days_system1,
)

__all__ = [
    "prepare_data_vectorized_system1",
    "generate_roc200_ranking_system1",
    "get_total_days_system1",
]

