"""
Thin wrapper that re-exports System1 core functions from system.core.

Kept for backward compatibility; prefer importing from `system.core`.
"""

from system.core import (
    prepare_data_vectorized_system1,
    get_total_days_system1,
    generate_roc200_ranking_system1,
)

__all__ = [
    "prepare_data_vectorized_system1",
    "get_total_days_system1",
    "generate_roc200_ranking_system1",
]
