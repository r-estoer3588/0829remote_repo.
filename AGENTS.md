# Repository Guidelines

## Project Structure & Module Organization
- App entry: `app_integrated.py` (Streamlit UI combining System1–7 tabs).
- Strategies: `strategies/` (e.g., `system1_strategy.py`, `base_strategy.py`).
- Common utilities: `common/` (`backtest_utils.py`, `ui_components.py`, caching helpers).
- Config: `config/settings.py` with `get_settings()` reading `.env`.
- Data/outputs: `data_cache/`, `results_csv/`, `logs/` (git-ignored).
- Tests: `tests/` (e.g., `test_system1.py` … `test_system7.py`).
- Tools: `tools/` (import analysis and helper scripts).

## Build, Test, and Development Commands
- Install deps: `pip install -r requirements.txt`.
- Run UI: `streamlit run app_integrated.py`.
- Warm data cache: `python cache_daily_data.py` (uses `EODHD_API_KEY`).
- Run tests: `pytest -q` (requires `pip install pytest` if not installed).
- Quick module check: `python -m strategies.system1_strategy` (example for ad‑hoc runs).

## Coding Style & Naming Conventions
- Indentation: 4 spaces; follow PEP 8; prefer type hints for public APIs.
- Names: `snake_case` for files/functions, `PascalCase` for classes (e.g., `System1Strategy`).
- Modules: place new strategies under `strategies/` as `systemX_strategy.py`; shared logic in `common/`.
- Imports: keep standard/third‑party/local grouped; avoid circular deps; prefer pure functions in `common/`.
- Docstrings: concise module/class/function docstrings explaining inputs/outputs and assumptions.

## Testing Guidelines
- Framework: `pytest`. Name tests `test_*.py` and mirror module paths where practical.
- Scope: prioritize `strategies/` logic, `common/backtest_utils.py`, and config behavior.
- Determinism: seed randomness and freeze dates where needed; avoid network calls in tests.
- Run locally: `pytest -q`; add focused runs like `pytest tests/test_system3.py::test_entry_rules`.

## Commit & Pull Request Guidelines
- Commits: imperative, present tense; concise subject (≤72 chars) + context in body.
  - Examples: `feat(strategies): add SMA/EMA crossover for System2`; `fix(common): guard empty price series`.
- PRs: clear description, linked issue, steps to validate, and screenshots/GIFs for UI changes.
- Checks: ensure tests pass, no new warnings, and README/config notes updated when behavior or env vars change.

## Security & Configuration Tips
- Secrets: store API keys in `.env` (never commit). Required: `EODHD_API_KEY`.
- Paths: prefer `get_settings(create_dirs=True)` to create/cache directories safely.
- I/O: write outputs only under `data_cache/`, `results_csv/`, `logs/`.

