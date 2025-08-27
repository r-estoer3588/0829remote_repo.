# Quant Trading System (Streamlit)

本プロジェクトは、Streamlit を用いた 7 つの売買システムの可視化・バックテスト・シグナル生成を行うアプリです。タブで各システムを個別に試せるほか、一括実行モードで全システムのバックテストをまとめて実行できます。

## 特長
- Streamlit UI: `app_integrated.py` から System1〜7 を切替表示
- 一括実行: 全システムのバックテスト/シグナル検出をまとめて実行
- キャッシュ: `data_cache/` にティッカー毎の時系列CSVを保存
- 共通ロジック: `common/` にユーティリティとバックテスト補助
- 戦略実装: `strategies/` に各システムの戦略クラスを配置

## セットアップ
1) Python 仮想環境の作成（任意）
- Windows (PowerShell)
  ```powershell
  python -m venv .venv
  .\\.venv\\Scripts\\Activate.ps1
  ```
- macOS/Linux
  ```bash
  python -m venv .venv
  source .venv/bin/activate
  ```

2) 依存関係のインストール
```bash
pip install -r requirements.txt
```

3) 環境変数の設定
- `.env.example` を `.env` にリネームし、必要な値を設定してください。
- 少なくとも以下の値を確認/設定します。
  - `EODHD_API_KEY`: EOD Historical Data の API キー
  - 必要に応じてスレッド数やタイムアウト、保存先ディレクトリを調整

## 実行方法
- Streamlit アプリの起動
  ```bash
  streamlit run app_integrated.py
  ```
- データキャッシュの作成（任意）
  ```bash
  python cache_daily_data.py
  ```
  - `.env` の `EODHD_API_KEY` を使用して EODHD API から取得します。
  - 成功した銘柄のCSVは `data_cache/` に保存されます。

## テスト
- 事前に pytest をインストール（必要な場合）
  ```bash
  pip install pytest
  ```
- 実行
  ```bash
  pytest -q
  ```

## 設定 (config/)
- `config/settings.py` に設定の雛形を用意しています。
  ```python
  from config import get_settings
  settings = get_settings(create_dirs=True)  # 必要なら出力系ディレクトリを自動作成
  print(settings.DATA_CACHE_DIR)
  ```
- 主な環境変数
  - `EODHD_API_KEY`: EODHD の API キー
  - `THREADS_DEFAULT`: スレッド数の既定
  - `REQUEST_TIMEOUT`: リクエストのタイムアウト(秒)
  - `DOWNLOAD_RETRIES`: リトライ回数
  - `API_THROTTLE_SECONDS`: API スロットリング(秒)
  - `DATA_CACHE_DIR`, `RESULTS_DIR`, `LOGS_DIR`: 各保存先パス
  - `MARKET_CAL_TZ`: 市場カレンダーのタイムゾーン

## ディレクトリ構成
- `app_integrated.py`: メインUIエントリ
- `app_system*_ui2.py`: 各システムのUIタブ
- `strategies/`: 戦略クラス群
- `common/`: 共通ユーティリティ（バックテスト補助、UI部品等）
- `config/`: 設定雛形（環境変数を集約）
- `data_cache/`: キャッシュ済みデータ（.gitignore 対象）
- `results_csv/`: バックテスト結果（.gitignore 対象）
- `tests/`: 各システムのユニットテスト

## 補足
- `requirements.txt` は実コードの import 解析に基づき最小構成へ整理済みです。
- 既存コードは直接 `config` を参照していません。段階的に `from config import get_settings` を導入することで設定の一元化が可能です。

## 今後の改善候補
- 主要モジュールへの `get_settings()` 導入・置換
- GitHub Actions 等でのテスト自動化
- 追加の使用手順（戦略別の操作ガイド）の README 追記


## �J���K�C�h�i�헪�C���^�[�t�F�[�X�Ƌ��ʃV�~�����[�^�[�j
���̃v���W�F�N�g�ł́A�e�헪�iSystem1?7�j������̃����^�C���_��œ��삷��悤�ɓ��ꂵ�Ă��܂��B���ɁA�����Ǘ��͋��ʃV�~�����[�^�[�ňꌳ�Ǘ����A�헪���͔������[���ɏW�����܂��B

- �������S�̌���:
  - �헪�iStrategyBase�p���j: �f�[�^�O�����iprepare_data�j�A��⒊�o�igenerate_candidates�j�A�G���g���[/�G�O�W�b�g/PnL�̃t�b�N�icompute_*�j�B
  - ���ʃV�~�����[�^�[: �����Ǘ��E�|�W�V�����g�Ǘ��E�i���ʒm��S���icommon/backtest_utils.py::simulate_trades_with_risk�j�B

- side �̋K��i�����w��j:
  - ����� long�B�V���[�g�헪�� run_backtest �� `side="short"` ��n���܂��B
  - ��: `simulate_trades_with_risk(..., self, on_progress=..., on_log=..., side="short")`

- compute_* �̐Ӗ��ƑO��:
  - compute_entry(df, candidate, current_capital) -> (entry_price, stop_price) | None
    - long: stop_price < entry_price�Ashort: stop_price > entry_price ��K�����������ƁB
    - candidate["entry_date"] �� df.index �ɑ��݂��Ȃ��ꍇ�� None ��Ԃ��ăX�L�b�v�B
  - compute_exit(df, entry_idx, entry_price, stop_price) -> (exit_price, exit_date) | None
    - �헪�Ǝ��̗��m/���؂�/�Ďd�|�����������BNone �̏ꍇ�̓V�~�����[�^�[�̃f�t�H���g�ɈϏ��B
  - compute_pnl(entry_price, exit_price, shares) -> float
    - ������������΃V�~�����[�^�[�� side �ɉ����Ď����v�Z�ilong: (exit-entry)*shares�Ashort: (entry-exit)*shares�j�B

- ���ʃV�~�����[�^�[�̋����i�T�v�j:
  - long �f�t�H���g: 25%�g���[�����O�AATR20 ����ɊȈՃX�g�b�v�i�t�b�N���������̃t�H�[���o�b�N�j�B
  - short �f�t�H���g: 25%�㑤�g���[�����O�A���l�u���C�N�ŃX�g�b�v�i����j�B
  - �����Ǘ�: 1�g���[�h�̃��X�N=2%�A�����ۗL���=10�Aexit �ŃL���b�V�����X�V�iYAML�ŏ㏑���j�B
  - �i��: `on_progress(done, total, start_time)`�A���O: `on_log(msg)` ��ʂ��Ēʒm�B

- run_backtest �̓���Ăяo��:
  - �e�헪�� `run_backtest` �͕K���ȉ��̌`�ɂ���i�����Ǘ����W�b�N�͏����Ȃ��j�B
    ```python
    trades_df, _ = simulate_trades_with_risk(
        candidates_by_date,
        prepared_dict,
        capital,
        self,
        on_progress=on_progress,
        on_log=on_log,
        # �V���[�g�헪�̂�
        side="short",
    )
    return trades_df
    ```

- �i�����O�̓���:
  - �i��/�c�莞�ԕt�����O�� `ui_components.log_with_progress` �ɓ���B
  - ��: `log_with_progress(i, total, start_time, prefix="?? �C���W�P�[�^�[�v�Z", log_func=log_callback)`

- �L���b�V�����j�i���ʃx�[�X + �y�ʃV�X�e���ʁj:
  - `data_cache/base/` �� OHLCV + ���ʎw�W�iSMA25/100/150/200, EMA20/50, ATR10/14/40/50, RSI3/14, ROC200, HV20�j��ۑ��B
  - �ǂݍ��݂� `utils.cache_manager.load_base_cache(symbol)` ��D��B����Ȃ��ŗL�J������ on-the-fly �v�Z�B
  - �����̃V�X�e���ʕۑ��͓��ʈێ����A�i�K�I�� base �����ֈڍs�iSystem7 �������ڈ��j�B

- �e�X�g�|���V�[�i���ʂ̒Z���Ή��j:
  - �e�헪�Ɂu�ŏ��C���W�����v�֐����������Apytest �ł͕K�{�w�W�̗L�����������؁B
  - �{�i�I�� backtest ���؂͓���C���^�[�t�F�[�X������ɒi�K�I�Ɋg�[�B
