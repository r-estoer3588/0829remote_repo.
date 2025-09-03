# Repository Guidelines

本リポジトリへの貢献のための最小限で実践的なガイドです。開発・検証はローカルで完結し、結果やキャッシュは所定のディレクトリに保存してください。

## Project Structure & Module Organization
- エントリ: `app_integrated.py`（Streamlit UI、System1–7 のタブ統合）
- 戦略: `strategies/`（例: `system1_strategy.py`, `base_strategy.py`）
- 共通: `common/`（`backtest_utils.py`, `ui_components.py` ほか）
- 設定: `config/settings.py`（`.env` を読む `get_settings()`）
- データ/出力: `data_cache/`, `results_csv/`, `logs/`（git 追跡外）
- テスト: `tests/`（`test_system1.py` … `test_system7.py`）
- ツール: `tools/`（インポート解析や補助スクリプト）
- スクリプト: `scripts/`（キャッシュ更新やユニバース作成など）

## Build, Test, and Development Commands
- 依存関係: `pip install -r requirements.txt`
- UI 起動: `streamlit run app_integrated.py`
- データキャッシュ: `python scripts/cache_daily_data.py`（`EODHD_API_KEY` 必須）
- テスト: `pytest -q`（例: 集中実行 `pytest tests/test_system3.py::test_entry_rules`）
- 単体モジュール実行: `python -m strategies.system1_strategy`

## Coding Style & Naming Conventions
- インデント 4 スペース、PEP 8 準拠。公開 API は型ヒント推奨。
- 命名: ファイル/関数は `snake_case`、クラスは `PascalCase`。
- 配置: 新戦略は `strategies/systemX_strategy.py`、共有ロジックは `common/`。
- インポートは 標準/サードパーティ/ローカル の順に整理。循環依存を回避。
- ドキュメンテーション: 簡潔な docstring（入出力と前提）を付与。

## Testing Guidelines
- フレームワーク: `pytest`。テスト名は `test_*.py`、可能ならモジュール構成に追随。
- 決定性: 乱数シード固定と日付固定を徹底。ネットワーク呼び出しを避ける。
- 実行: `pytest -q`。失敗時は対象範囲を絞ってデバッグ。

## Commit & Pull Request Guidelines
- コミット: 命令形・現在形、件名は 72 文字以内。例:
  - `feat(strategies): add SMA/EMA crossover for System2`
  - `fix(common): guard empty price series`
- PR: 目的/背景、関連 Issue、検証手順、（UI 変更時）スクリーンショットを記載。
- チェック: テスト合格、新規警告なし、README/設定の更新（環境変数変更時）。

## Security & Configuration Tips
- 秘密情報は `.env` に保存しコミットしない。必須: `EODHD_API_KEY`。
- パス/ディレクトリは `get_settings(create_dirs=True)` を利用して安全に作成。
- I/O は `data_cache/`, `results_csv/`, `logs/` の配下に限定。

