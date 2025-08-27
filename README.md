# Quant Trading System (Streamlit)

æœ¬ãƒ—ãƒ­ã‚¸ã‚§ã‚¯ãƒˆã¯ã€Streamlit ã‚’ç”¨ã„ãŸ 7 ã¤ã®å£²è²·ã‚·ã‚¹ãƒ†ãƒ ã®å¯è¦–åŒ–ãƒ»ãƒãƒƒã‚¯ãƒ†ã‚¹ãƒˆãƒ»ã‚·ã‚°ãƒŠãƒ«ç”Ÿæˆã‚’è¡Œã†ã‚¢ãƒ—ãƒªã§ã™ã€‚ã‚¿ãƒ–ã§å„ã‚·ã‚¹ãƒ†ãƒ ã‚’å€‹åˆ¥ã«è©¦ã›ã‚‹ã»ã‹ã€ä¸€æ‹¬å®Ÿè¡Œãƒ¢ãƒ¼ãƒ‰ã§å…¨ã‚·ã‚¹ãƒ†ãƒ ã®ãƒãƒƒã‚¯ãƒ†ã‚¹ãƒˆã‚’ã¾ã¨ã‚ã¦å®Ÿè¡Œã§ãã¾ã™ã€‚

## ç‰¹é•·
- Streamlit UI: `app_integrated.py` ã‹ã‚‰ System1ã€œ7 ã‚’åˆ‡æ›¿è¡¨ç¤º
- ä¸€æ‹¬å®Ÿè¡Œ: å…¨ã‚·ã‚¹ãƒ†ãƒ ã®ãƒãƒƒã‚¯ãƒ†ã‚¹ãƒˆ/ã‚·ã‚°ãƒŠãƒ«æ¤œå‡ºã‚’ã¾ã¨ã‚ã¦å®Ÿè¡Œ
- ã‚­ãƒ£ãƒƒã‚·ãƒ¥: `data_cache/` ã«ãƒ†ã‚£ãƒƒã‚«ãƒ¼æ¯ã®æ™‚ç³»åˆ—CSVã‚’ä¿å­˜
- å…±é€šãƒ­ã‚¸ãƒƒã‚¯: `common/` ã«ãƒ¦ãƒ¼ãƒ†ã‚£ãƒªãƒ†ã‚£ã¨ãƒãƒƒã‚¯ãƒ†ã‚¹ãƒˆè£œåŠ©
- æˆ¦ç•¥å®Ÿè£…: `strategies/` ã«å„ã‚·ã‚¹ãƒ†ãƒ ã®æˆ¦ç•¥ã‚¯ãƒ©ã‚¹ã‚’é…ç½®

## ã‚»ãƒƒãƒˆã‚¢ãƒƒãƒ—
1) Python ä»®æƒ³ç’°å¢ƒã®ä½œæˆï¼ˆä»»æ„ï¼‰
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

2) ä¾å­˜é–¢ä¿‚ã®ã‚¤ãƒ³ã‚¹ãƒˆãƒ¼ãƒ«
```bash
pip install -r requirements.txt
```

3) ç’°å¢ƒå¤‰æ•°ã®è¨­å®š
- `.env.example` ã‚’ `.env` ã«ãƒªãƒãƒ¼ãƒ ã—ã€å¿…è¦ãªå€¤ã‚’è¨­å®šã—ã¦ãã ã•ã„ã€‚
- å°‘ãªãã¨ã‚‚ä»¥ä¸‹ã®å€¤ã‚’ç¢ºèª/è¨­å®šã—ã¾ã™ã€‚
  - `EODHD_API_KEY`: EOD Historical Data ã® API ã‚­ãƒ¼
  - å¿…è¦ã«å¿œã˜ã¦ã‚¹ãƒ¬ãƒƒãƒ‰æ•°ã‚„ã‚¿ã‚¤ãƒ ã‚¢ã‚¦ãƒˆã€ä¿å­˜å…ˆãƒ‡ã‚£ãƒ¬ã‚¯ãƒˆãƒªã‚’èª¿æ•´

## å®Ÿè¡Œæ–¹æ³•
- Streamlit ã‚¢ãƒ—ãƒªã®èµ·å‹•
  ```bash
  streamlit run app_integrated.py
  ```
- ãƒ‡ãƒ¼ã‚¿ã‚­ãƒ£ãƒƒã‚·ãƒ¥ã®ä½œæˆï¼ˆä»»æ„ï¼‰
  ```bash
  python cache_daily_data.py
  ```
  - `.env` ã® `EODHD_API_KEY` ã‚’ä½¿ç”¨ã—ã¦ EODHD API ã‹ã‚‰å–å¾—ã—ã¾ã™ã€‚
  - æˆåŠŸã—ãŸéŠ˜æŸ„ã®CSVã¯ `data_cache/` ã«ä¿å­˜ã•ã‚Œã¾ã™ã€‚

## ãƒ†ã‚¹ãƒˆ
- äº‹å‰ã« pytest ã‚’ã‚¤ãƒ³ã‚¹ãƒˆãƒ¼ãƒ«ï¼ˆå¿…è¦ãªå ´åˆï¼‰
  ```bash
  pip install pytest
  ```
- å®Ÿè¡Œ
  ```bash
  pytest -q
  ```

## è¨­å®š (config/)
- `config/settings.py` ã«è¨­å®šã®é››å½¢ã‚’ç”¨æ„ã—ã¦ã„ã¾ã™ã€‚
  ```python
  from config import get_settings
  settings = get_settings(create_dirs=True)  # å¿…è¦ãªã‚‰å‡ºåŠ›ç³»ãƒ‡ã‚£ãƒ¬ã‚¯ãƒˆãƒªã‚’è‡ªå‹•ä½œæˆ
  print(settings.DATA_CACHE_DIR)
  ```
- ä¸»ãªç’°å¢ƒå¤‰æ•°
  - `EODHD_API_KEY`: EODHD ã® API ã‚­ãƒ¼
  - `THREADS_DEFAULT`: ã‚¹ãƒ¬ãƒƒãƒ‰æ•°ã®æ—¢å®š
  - `REQUEST_TIMEOUT`: ãƒªã‚¯ã‚¨ã‚¹ãƒˆã®ã‚¿ã‚¤ãƒ ã‚¢ã‚¦ãƒˆ(ç§’)
  - `DOWNLOAD_RETRIES`: ãƒªãƒˆãƒ©ã‚¤å›æ•°
  - `API_THROTTLE_SECONDS`: API ã‚¹ãƒ­ãƒƒãƒˆãƒªãƒ³ã‚°(ç§’)
  - `DATA_CACHE_DIR`, `RESULTS_DIR`, `LOGS_DIR`: å„ä¿å­˜å…ˆãƒ‘ã‚¹
  - `MARKET_CAL_TZ`: å¸‚å ´ã‚«ãƒ¬ãƒ³ãƒ€ãƒ¼ã®ã‚¿ã‚¤ãƒ ã‚¾ãƒ¼ãƒ³

## ãƒ‡ã‚£ãƒ¬ã‚¯ãƒˆãƒªæ§‹æˆ
- `app_integrated.py`: ãƒ¡ã‚¤ãƒ³UIã‚¨ãƒ³ãƒˆãƒª
- `app_system*_ui2.py`: å„ã‚·ã‚¹ãƒ†ãƒ ã®UIã‚¿ãƒ–
- `strategies/`: æˆ¦ç•¥ã‚¯ãƒ©ã‚¹ç¾¤
- `common/`: å…±é€šãƒ¦ãƒ¼ãƒ†ã‚£ãƒªãƒ†ã‚£ï¼ˆãƒãƒƒã‚¯ãƒ†ã‚¹ãƒˆè£œåŠ©ã€UIéƒ¨å“ç­‰ï¼‰
- `config/`: è¨­å®šé››å½¢ï¼ˆç’°å¢ƒå¤‰æ•°ã‚’é›†ç´„ï¼‰
- `data_cache/`: ã‚­ãƒ£ãƒƒã‚·ãƒ¥æ¸ˆã¿ãƒ‡ãƒ¼ã‚¿ï¼ˆ.gitignore å¯¾è±¡ï¼‰
- `results_csv/`: ãƒãƒƒã‚¯ãƒ†ã‚¹ãƒˆçµæœï¼ˆ.gitignore å¯¾è±¡ï¼‰
- `tests/`: å„ã‚·ã‚¹ãƒ†ãƒ ã®ãƒ¦ãƒ‹ãƒƒãƒˆãƒ†ã‚¹ãƒˆ

## è£œè¶³
- `requirements.txt` ã¯å®Ÿã‚³ãƒ¼ãƒ‰ã® import è§£æã«åŸºã¥ãæœ€å°æ§‹æˆã¸æ•´ç†æ¸ˆã¿ã§ã™ã€‚
- æ—¢å­˜ã‚³ãƒ¼ãƒ‰ã¯ç›´æ¥ `config` ã‚’å‚ç…§ã—ã¦ã„ã¾ã›ã‚“ã€‚æ®µéšçš„ã« `from config import get_settings` ã‚’å°å…¥ã™ã‚‹ã“ã¨ã§è¨­å®šã®ä¸€å…ƒåŒ–ãŒå¯èƒ½ã§ã™ã€‚

## ä»Šå¾Œã®æ”¹å–„å€™è£œ
- ä¸»è¦ãƒ¢ã‚¸ãƒ¥ãƒ¼ãƒ«ã¸ã® `get_settings()` å°å…¥ãƒ»ç½®æ›
- GitHub Actions ç­‰ã§ã®ãƒ†ã‚¹ãƒˆè‡ªå‹•åŒ–
- è¿½åŠ ã®ä½¿ç”¨æ‰‹é †ï¼ˆæˆ¦ç•¥åˆ¥ã®æ“ä½œã‚¬ã‚¤ãƒ‰ï¼‰ã® README è¿½è¨˜


## ŠJ”­ƒKƒCƒhií—ªƒCƒ“ƒ^[ƒtƒF[ƒX‚Æ‹¤’ÊƒVƒ~ƒ…ƒŒ[ƒ^[j
‚±‚ÌƒvƒƒWƒFƒNƒg‚Å‚ÍAŠeí—ªiSystem1?7j‚ª“¯ˆê‚Ìƒ‰ƒ“ƒ^ƒCƒ€Œ_–ñ‚Å“®ì‚·‚é‚æ‚¤‚É“ˆê‚µ‚Ä‚¢‚Ü‚·B“Á‚ÉA‘‹àŠÇ—‚Í‹¤’ÊƒVƒ~ƒ…ƒŒ[ƒ^[‚ÅˆêŒ³ŠÇ—‚µAí—ª‘¤‚Í”„”ƒƒ‹[ƒ‹‚ÉW’†‚µ‚Ü‚·B

- –ğŠ„•ª’S‚ÌŒ´‘¥:
  - í—ªiStrategyBaseŒp³j: ƒf[ƒ^‘Oˆ—iprepare_datajAŒó•â’Šoigenerate_candidatesjAƒGƒ“ƒgƒŠ[/ƒGƒOƒWƒbƒg/PnL‚ÌƒtƒbƒNicompute_*jB
  - ‹¤’ÊƒVƒ~ƒ…ƒŒ[ƒ^[: ‘‹àŠÇ—Eƒ|ƒWƒVƒ‡ƒ“˜gŠÇ—Ei’»’Ê’m‚ğ’S“–icommon/backtest_utils.py::simulate_trades_with_riskjB

- side ‚Ì‹K–ñi•ûŒüw’èj:
  - Šù’è‚Í longBƒVƒ‡[ƒgí—ª‚Í run_backtest ‚Å `side="short"` ‚ğ“n‚µ‚Ü‚·B
  - —á: `simulate_trades_with_risk(..., self, on_progress=..., on_log=..., side="short")`

- compute_* ‚ÌÓ–±‚Æ‘O’ñ:
  - compute_entry(df, candidate, current_capital) -> (entry_price, stop_price) | None
    - long: stop_price < entry_priceAshort: stop_price > entry_price ‚ğ•K‚¸–‚½‚·‚±‚ÆB
    - candidate["entry_date"] ‚ª df.index ‚É‘¶İ‚µ‚È‚¢ê‡‚Í None ‚ğ•Ô‚µ‚ÄƒXƒLƒbƒvB
  - compute_exit(df, entry_idx, entry_price, stop_price) -> (exit_price, exit_date) | None
    - í—ª“Æ©‚Ì—˜Šm/‘¹Ø‚è/ÄdŠ|‚¯“™‚ğÀ‘•BNone ‚Ìê‡‚ÍƒVƒ~ƒ…ƒŒ[ƒ^[‚ÌƒfƒtƒHƒ‹ƒg‚ÉˆÏ÷B
  - compute_pnl(entry_price, exit_price, shares) -> float
    - À‘•‚ª–³‚¯‚ê‚ÎƒVƒ~ƒ…ƒŒ[ƒ^[‚ª side ‚É‰‚¶‚Ä©“®ŒvZilong: (exit-entry)*sharesAshort: (entry-exit)*sharesjB

- ‹¤’ÊƒVƒ~ƒ…ƒŒ[ƒ^[‚Ì‹““®iŠT—vj:
  - long ƒfƒtƒHƒ‹ƒg: 25%ƒgƒŒ[ƒŠƒ“ƒOAATR20 ‚ğŠî€‚ÉŠÈˆÕƒXƒgƒbƒviƒtƒbƒN–¢À‘•‚ÌƒtƒH[ƒ‹ƒoƒbƒNjB
  - short ƒfƒtƒHƒ‹ƒg: 25%ã‘¤ƒgƒŒ[ƒŠƒ“ƒOA‚’lƒuƒŒƒCƒN‚ÅƒXƒgƒbƒvi“¯ãjB
  - ‘‹àŠÇ—: 1ƒgƒŒ[ƒh‚ÌƒŠƒXƒN=2%A“¯•Û—LãŒÀ=10Aexit ‚ÅƒLƒƒƒbƒVƒ…‚ğXViYAML‚Åã‘‚«‰ÂjB
  - i’»: `on_progress(done, total, start_time)`AƒƒO: `on_log(msg)` ‚ğ’Ê‚¶‚Ä’Ê’mB

- run_backtest ‚Ì“ˆêŒÄ‚Ño‚µ:
  - Šeí—ª‚Ì `run_backtest` ‚Í•K‚¸ˆÈ‰º‚ÌŒ`‚É‚·‚éi‘‹àŠÇ—ƒƒWƒbƒN‚Í‘‚©‚È‚¢jB
    ```python
    trades_df, _ = simulate_trades_with_risk(
        candidates_by_date,
        prepared_dict,
        capital,
        self,
        on_progress=on_progress,
        on_log=on_log,
        # ƒVƒ‡[ƒgí—ª‚Ì‚İ
        side="short",
    )
    return trades_df
    ```

- i’»ƒƒO‚Ì“ˆê:
  - i’»/c‚èŠÔ•t‚«ƒƒO‚Í `ui_components.log_with_progress` ‚É“ˆêB
  - —á: `log_with_progress(i, total, start_time, prefix="?? ƒCƒ“ƒWƒP[ƒ^[ŒvZ", log_func=log_callback)`

- ƒLƒƒƒbƒVƒ…•ûji‹¤’Êƒx[ƒX + Œy—ÊƒVƒXƒeƒ€•Êj:
  - `data_cache/base/` ‚É OHLCV + ‹¤’Êw•WiSMA25/100/150/200, EMA20/50, ATR10/14/40/50, RSI3/14, ROC200, HV20j‚ğ•Û‘¶B
  - “Ç‚İ‚İ‚Í `utils.cache_manager.load_base_cache(symbol)` ‚ğ—DæB‘«‚è‚È‚¢ŒÅ—LƒJƒ‰ƒ€‚Í on-the-fly ŒvZB
  - Šù‘¶‚ÌƒVƒXƒeƒ€•Ê•Û‘¶‚Í“––ÊˆÛ‚µA’iŠK“I‚É base “‡‚ÖˆÚsiSystem7 Š®—¹Œã‚ğ–ÚˆÀjB

- ƒeƒXƒgƒ|ƒŠƒV[i“––Ê‚Ì’ZŠú‘Î‰j:
  - Šeí—ª‚ÉuÅ¬ƒCƒ“ƒW¶¬vŠÖ”‚ğ‚½‚¹Apytest ‚Å‚Í•K{w•W‚Ì—L–³‚¾‚¯‚ğŒŸØB
  - –{Ši“I‚È backtest ŒŸØ‚Í“ˆêƒCƒ“ƒ^[ƒtƒF[ƒXŠ®¬Œã‚É’iŠK“I‚ÉŠg[B
