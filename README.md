# Quant Trading System (Streamlit)

譛ｬ繝励Ο繧ｸ繧ｧ繧ｯ繝医・縲ヾtreamlit 繧堤畑縺・◆ 7 縺､縺ｮ螢ｲ雋ｷ繧ｷ繧ｹ繝・Β縺ｮ蜿ｯ隕門喧繝ｻ繝舌ャ繧ｯ繝・せ繝医・繧ｷ繧ｰ繝翫Ν逕滓・繧定｡後≧繧｢繝励Μ縺ｧ縺吶ゅち繝悶〒蜷・す繧ｹ繝・Β繧貞句挨縺ｫ隧ｦ縺帙ｋ縺ｻ縺九∽ｸ諡ｬ螳溯｡後Δ繝ｼ繝峨〒蜈ｨ繧ｷ繧ｹ繝・Β縺ｮ繝舌ャ繧ｯ繝・せ繝医ｒ縺ｾ縺ｨ繧√※螳溯｡後〒縺阪∪縺吶・
## 迚ｹ髟ｷ
- Streamlit UI: `app_integrated.py` 縺九ｉ System1縲・ 繧貞・譖ｿ陦ｨ遉ｺ
- 荳諡ｬ螳溯｡・ 蜈ｨ繧ｷ繧ｹ繝・Β縺ｮ繝舌ャ繧ｯ繝・せ繝・繧ｷ繧ｰ繝翫Ν讀懷・繧偵∪縺ｨ繧√※螳溯｡・- 繧ｭ繝｣繝・す繝･: `data_cache/` 縺ｫ繝・ぅ繝・き繝ｼ豈弱・譎らｳｻ蛻佑SV繧剃ｿ晏ｭ・- 蜈ｱ騾壹Ο繧ｸ繝・け: `common/` 縺ｫ繝ｦ繝ｼ繝・ぅ繝ｪ繝・ぅ縺ｨ繝舌ャ繧ｯ繝・せ繝郁｣懷勧
- 謌ｦ逡･螳溯｣・ `strategies/` 縺ｫ蜷・す繧ｹ繝・Β縺ｮ謌ｦ逡･繧ｯ繝ｩ繧ｹ繧帝・鄂ｮ

## 繧ｻ繝・ヨ繧｢繝・・
1) Python 莉ｮ諠ｳ迺ｰ蠅・・菴懈・・井ｻｻ諢擾ｼ・- Windows (PowerShell)
  ```powershell
  python -m venv .venv
  .\\.venv\\Scripts\\Activate.ps1
  ```
- macOS/Linux
  ```bash
  python -m venv .venv
  source .venv/bin/activate
  ```

2) 萓晏ｭ倬未菫ゅ・繧､繝ｳ繧ｹ繝医・繝ｫ
```bash
pip install -r requirements.txt
```

3) 迺ｰ蠅・､画焚縺ｮ險ｭ螳・- `.env.example` 繧・`.env` 縺ｫ繝ｪ繝阪・繝縺励∝ｿ・ｦ√↑蛟､繧定ｨｭ螳壹＠縺ｦ縺上□縺輔＞縲・- 蟆代↑縺上→繧ゆｻ･荳九・蛟､繧堤｢ｺ隱・險ｭ螳壹＠縺ｾ縺吶・  - `EODHD_API_KEY`: EOD Historical Data 縺ｮ API 繧ｭ繝ｼ
  - 蠢・ｦ√↓蠢懊§縺ｦ繧ｹ繝ｬ繝・ラ謨ｰ繧・ち繧､繝繧｢繧ｦ繝医∽ｿ晏ｭ伜・繝・ぅ繝ｬ繧ｯ繝医Μ繧定ｪｿ謨ｴ

## 螳溯｡梧婿豕・- Streamlit 繧｢繝励Μ縺ｮ襍ｷ蜍・  ```bash
  streamlit run app_integrated.py
  ```
- 繝・・繧ｿ繧ｭ繝｣繝・す繝･縺ｮ菴懈・・井ｻｻ諢擾ｼ・  ```bash
  python cache_daily_data.py
  ```
  - `.env` 縺ｮ `EODHD_API_KEY` 繧剃ｽｿ逕ｨ縺励※ EODHD API 縺九ｉ蜿門ｾ励＠縺ｾ縺吶・  - 謌仙粥縺励◆驫俶氛縺ｮCSV縺ｯ `data_cache/` 縺ｫ菫晏ｭ倥＆繧後∪縺吶・
## 繝・せ繝・- 莠句燕縺ｫ pytest 繧偵う繝ｳ繧ｹ繝医・繝ｫ・亥ｿ・ｦ√↑蝣ｴ蜷茨ｼ・  ```bash
  pip install pytest
  ```
- 螳溯｡・  ```bash
  pytest -q
  ```

## 險ｭ螳・(config/)
- `config/settings.py` 縺ｫ險ｭ螳壹・髮帛ｽ｢繧堤畑諢上＠縺ｦ縺・∪縺吶・  ```python
  from config import get_settings
  settings = get_settings(create_dirs=True)  # 蠢・ｦ√↑繧牙・蜉帷ｳｻ繝・ぅ繝ｬ繧ｯ繝医Μ繧定・蜍穂ｽ懈・
  print(settings.DATA_CACHE_DIR)
  ```
- 荳ｻ縺ｪ迺ｰ蠅・､画焚
  - `EODHD_API_KEY`: EODHD 縺ｮ API 繧ｭ繝ｼ
  - `THREADS_DEFAULT`: 繧ｹ繝ｬ繝・ラ謨ｰ縺ｮ譌｢螳・  - `REQUEST_TIMEOUT`: 繝ｪ繧ｯ繧ｨ繧ｹ繝医・繧ｿ繧､繝繧｢繧ｦ繝・遘・
  - `DOWNLOAD_RETRIES`: 繝ｪ繝医Λ繧､蝗樊焚
  - `API_THROTTLE_SECONDS`: API 繧ｹ繝ｭ繝・ヨ繝ｪ繝ｳ繧ｰ(遘・
  - `DATA_CACHE_DIR`, `RESULTS_DIR`, `LOGS_DIR`: 蜷・ｿ晏ｭ伜・繝代せ
  - `MARKET_CAL_TZ`: 蟶ょｴ繧ｫ繝ｬ繝ｳ繝繝ｼ縺ｮ繧ｿ繧､繝繧ｾ繝ｼ繝ｳ

## 繝・ぅ繝ｬ繧ｯ繝医Μ讒区・
- `app_integrated.py`: 繝｡繧､繝ｳUI繧ｨ繝ｳ繝医Μ
- `app_system*_ui2.py`: 蜷・す繧ｹ繝・Β縺ｮUI繧ｿ繝・- `strategies/`: 謌ｦ逡･繧ｯ繝ｩ繧ｹ鄒､
- `common/`: 蜈ｱ騾壹Θ繝ｼ繝・ぅ繝ｪ繝・ぅ・医ヰ繝・け繝・せ繝郁｣懷勧縲ゞI驛ｨ蜩∫ｭ会ｼ・- `config/`: 險ｭ螳夐屁蠖｢・育腸蠅・､画焚繧帝寔邏・ｼ・- `data_cache/`: 繧ｭ繝｣繝・す繝･貂医∩繝・・繧ｿ・・gitignore 蟇ｾ雎｡・・- `results_csv/`: 繝舌ャ繧ｯ繝・せ繝育ｵ先棡・・gitignore 蟇ｾ雎｡・・- `tests/`: 蜷・す繧ｹ繝・Β縺ｮ繝ｦ繝九ャ繝医ユ繧ｹ繝・
## 陬懆ｶｳ
- `requirements.txt` 縺ｯ螳溘さ繝ｼ繝峨・ import 隗｣譫舌↓蝓ｺ縺･縺肴怙蟆乗ｧ区・縺ｸ謨ｴ逅・ｸ医∩縺ｧ縺吶・- 譌｢蟄倥さ繝ｼ繝峨・逶ｴ謗･ `config` 繧貞盾辣ｧ縺励※縺・∪縺帙ｓ縲よｮｵ髫守噪縺ｫ `from config import get_settings` 繧貞ｰ主・縺吶ｋ縺薙→縺ｧ險ｭ螳壹・荳蜈・喧縺悟庄閭ｽ縺ｧ縺吶・
## 莉雁ｾ後・謾ｹ蝟・呵｣・- 荳ｻ隕√Δ繧ｸ繝･繝ｼ繝ｫ縺ｸ縺ｮ `get_settings()` 蟆主・繝ｻ鄂ｮ謠・- GitHub Actions 遲峨〒縺ｮ繝・せ繝郁・蜍募喧
- 霑ｽ蜉縺ｮ菴ｿ逕ｨ謇矩・ｼ域姶逡･蛻･縺ｮ謫堺ｽ懊ぎ繧､繝会ｼ峨・ README 霑ｽ險・

## 開発ガイド（戦略インターフェースと共通シミュレーター）
このプロジェクトでは、各戦略（System1?7）が同一のランタイム契約で動作するように統一しています。特に、資金管理は共通シミュレーターで一元管理し、戦略側は売買ルールに集中します。

- 役割分担の原則:
  - 戦略（StrategyBase継承）: データ前処理（prepare_data）、候補抽出（generate_candidates）、エントリー/エグジット/PnLのフック（compute_*）。
  - 共通シミュレーター: 資金管理・ポジション枠管理・進捗通知を担当（common/backtest_utils.py::simulate_trades_with_risk）。

- side の規約（方向指定）:
  - 既定は long。ショート戦略は run_backtest で `side="short"` を渡します。
  - 例: `simulate_trades_with_risk(..., self, on_progress=..., on_log=..., side="short")`

- compute_* の責務と前提:
  - compute_entry(df, candidate, current_capital) -> (entry_price, stop_price) | None
    - long: stop_price < entry_price、short: stop_price > entry_price を必ず満たすこと。
    - candidate["entry_date"] が df.index に存在しない場合は None を返してスキップ。
  - compute_exit(df, entry_idx, entry_price, stop_price) -> (exit_price, exit_date) | None
    - 戦略独自の利確/損切り/再仕掛け等を実装。None の場合はシミュレーターのデフォルトに委譲。
  - compute_pnl(entry_price, exit_price, shares) -> float
    - 実装が無ければシミュレーターが side に応じて自動計算（long: (exit-entry)*shares、short: (entry-exit)*shares）。

- 共通シミュレーターの挙動（概要）:
  - long デフォルト: 25%トレーリング、ATR20 を基準に簡易ストップ（フック未実装時のフォールバック）。
  - short デフォルト: 25%上側トレーリング、高値ブレイクでストップ（同上）。
  - 資金管理: 1トレードのリスク=2%、同時保有上限=10、exit でキャッシュを更新（YAMLで上書き可）。
  - 進捗: `on_progress(done, total, start_time)`、ログ: `on_log(msg)` を通じて通知。

- run_backtest の統一呼び出し:
  - 各戦略の `run_backtest` は必ず以下の形にする（資金管理ロジックは書かない）。
    ```python
    trades_df, _ = simulate_trades_with_risk(
        candidates_by_date,
        prepared_dict,
        capital,
        self,
        on_progress=on_progress,
        on_log=on_log,
        # ショート戦略のみ
        side="short",
    )
    return trades_df
    ```

- 進捗ログの統一:
  - 進捗/残り時間付きログは `common.ui_components.log_with_progress` に統一。
  - 例: `log_with_progress(i, total, start_time, prefix="?? インジケーター計算", log_func=log_callback)`

- キャッシュ方針（共通ベース + 軽量システム別）:
  - `data_cache/base/` に OHLCV + 共通指標（SMA25/100/150/200, EMA20/50, ATR10/14/40/50, RSI3/14, ROC200, HV20）を保存。
  - 読み込みは `utils.cache_manager.load_base_cache(symbol)` を優先。足りない固有カラムは on-the-fly 計算。
  - 既存のシステム別保存は当面維持し、段階的に base 統合へ移行（System7 完了後を目安）。

- テストポリシー（当面の短期対応）:
  - 各戦略に「最小インジ生成」関数を持たせ、pytest では必須指標の有無だけを検証。
  - 本格的な backtest 検証は統一インターフェース完成後に段階的に拡充。

