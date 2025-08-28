# Quant Trading System (Streamlit)

本プロジェクト�E、Streamlit を用ぁE�� 7 つの売買シスチE��の可視化・バックチE��ト�Eシグナル生�Eを行うアプリです。タブで吁E��スチE��を個別に試せるほか、一括実行モードで全シスチE��のバックチE��トをまとめて実行できます、E
## 特長
- Streamlit UI: `app_integrated.py` から System1、E を�E替表示
- 一括実衁E 全シスチE��のバックチE��チEシグナル検�Eをまとめて実衁E- キャチE��ュ: `data_cache/` にチE��チE��ー毎�E時系列CSVを保孁E- 共通ロジチE��: `common/` にユーチE��リチE��とバックチE��ト補助
- 戦略実裁E `strategies/` に吁E��スチE��の戦略クラスを�E置

## セチE��アチE�E
1) Python 仮想環墁E�E作�E�E�任意！E- Windows (PowerShell)
  ```powershell
  python -m venv .venv
  .\\.venv\\Scripts\\Activate.ps1
  ```
- macOS/Linux
  ```bash
  python -m venv .venv
  source .venv/bin/activate
  ```

2) 依存関係�Eインスト�Eル
```bash
pip install -r requirements.txt
```

3) 環墁E��数の設宁E- `.env.example` めE`.env` にリネ�Eムし、忁E��な値を設定してください、E- 少なくとも以下�E値を確誁E設定します、E  - `EODHD_API_KEY`: EOD Historical Data の API キー
  - 忁E��に応じてスレチE��数めE��イムアウト、保存�EチE��レクトリを調整

## 実行方況E- Streamlit アプリの起勁E  ```bash
  streamlit run app_integrated.py
  ```
- チE�EタキャチE��ュの作�E�E�任意！E  ```bash
  python cache_daily_data.py
  ```
  - `.env` の `EODHD_API_KEY` を使用して EODHD API から取得します、E  - 成功した銘柄のCSVは `data_cache/` に保存されます、E
## チE��チE- 事前に pytest をインスト�Eル�E�忁E��な場合！E  ```bash
  pip install pytest
  ```
- 実衁E  ```bash
  pytest -q
  ```

## 設宁E(config/)
- `config/settings.py` に設定�E雛形を用意してぁE��す、E  ```python
  from config import get_settings
  settings = get_settings(create_dirs=True)  # 忁E��なら�E力系チE��レクトリを�E動作�E
  print(settings.DATA_CACHE_DIR)
  ```
- 主な環墁E��数
  - `EODHD_API_KEY`: EODHD の API キー
  - `THREADS_DEFAULT`: スレチE��数の既宁E  - `REQUEST_TIMEOUT`: リクエスト�EタイムアウチE私E
  - `DOWNLOAD_RETRIES`: リトライ回数
  - `API_THROTTLE_SECONDS`: API スロチE��リング(私E
  - `DATA_CACHE_DIR`, `RESULTS_DIR`, `LOGS_DIR`: 吁E��存�Eパス
  - `MARKET_CAL_TZ`: 市場カレンダーのタイムゾーン

## チE��レクトリ構�E
- `app_integrated.py`: メインUIエントリ
- `app_system*_ui2.py`: 吁E��スチE��のUIタチE- `strategies/`: 戦略クラス群
- `common/`: 共通ユーチE��リチE���E�バチE��チE��ト補助、UI部品等！E- `config/`: 設定雛形�E�環墁E��数を集紁E��E- `data_cache/`: キャチE��ュ済みチE�Eタ�E�Egitignore 対象�E�E- `results_csv/`: バックチE��ト結果�E�Egitignore 対象�E�E- `tests/`: 吁E��スチE��のユニットテスチE
## 補足
- `requirements.txt` は実コード�E import 解析に基づき最小構�Eへ整琁E��みです、E- 既存コード�E直接 `config` を参照してぁE��せん。段階的に `from config import get_settings` を導�Eすることで設定�E一允E��が可能です、E
## 今後�E改喁E��裁E- 主要モジュールへの `get_settings()` 導�E・置揁E- GitHub Actions 等でのチE��ト�E動化
- 追加の使用手頁E��戦略別の操作ガイド）�E README 追訁E

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
  - �i��/�c�莞�ԕt�����O�� `common.ui_components.log_with_progress` �ɓ���B
  - ��: `log_with_progress(i, total, start_time, prefix="?? �C���W�P�[�^�[�v�Z", log_func=log_callback)`

- �L���b�V�����j�i���ʃx�[�X + �y�ʃV�X�e���ʁj:
  - `data_cache/base/` �� OHLCV + ���ʎw�W�iSMA25/100/150/200, EMA20/50, ATR10/14/40/50, RSI3/14, ROC200, HV20�j��ۑ��B
  - �ǂݍ��݂� `utils.cache_manager.load_base_cache(symbol)` ��D��B����Ȃ��ŗL�J������ on-the-fly �v�Z�B
  - �����̃V�X�e���ʕۑ��͓��ʈێ����A�i�K�I�� base �����ֈڍs�iSystem7 �������ڈ��j�B

- �e�X�g�|���V�[�i���ʂ̒Z���Ή��j:
  - �e�헪�Ɂu�ŏ��C���W�����v�֐����������Apytest �ł͕K�{�w�W�̗L�����������؁B
  - �{�i�I�� backtest ���؂͓���C���^�[�t�F�[�X������ɒi�K�I�Ɋg�[�B

