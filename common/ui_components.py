# ============================================================
# 1. インポート
# ============================================================
import os
import time
import streamlit as st
import matplotlib.pyplot as plt
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
from common.utils import safe_filename, get_cached_data
from holding_tracker import (
    generate_holding_matrix,
    display_holding_heatmap,
    download_holding_csv,
)
from tickers_loader import get_all_tickers
import matplotlib.ticker as mticker
from system.core import generate_roc200_ranking_system1


# ============================================================
# 2. ヘルパー系（共通ユーティリティ）
# ============================================================
# - clean_date_column
def clean_date_column(df: pd.DataFrame, col_name="Date") -> pd.DataFrame:
    """日付カラムをdatetime型に変換し、NaTを除去"""
    if col_name in df.columns:
        df = df.copy()
        df[col_name] = pd.to_datetime(df[col_name], errors="coerce")
        df = df.dropna(subset=[col_name])
    return df


# - log_with_progress
# ============================================================
# 共通進捗ログ関数（System1 形式）
# ============================================================
def log_with_progress(
    i,
    total,
    start_time,
    prefix="処理",
    batch=50,
    log_area=None,
    progress_bar=None,
    extra_msg=None,
    unit="件",
):
    """進捗ログ＋進捗バーを表示"""
    if i % batch == 0 or i == total:
        elapsed = time.time() - start_time
        remain = (elapsed / i) * (total - i) if i > 0 else 0
        msg = (
            f"{prefix}: {i}/{total} {unit} 完了 "
            f"| 経過: {int(elapsed // 60)}分{int(elapsed % 60)}秒 "
            f"/ 残り: 約 {int(remain // 60)}分{int(remain % 60)}秒"
        )
        if extra_msg:
            msg += f"\n{extra_msg}"
        if log_area:
            log_area.text(msg)
        if progress_bar:
            progress_bar.progress(i / total)


# - default_log_callback
def default_log_callback(processed, total, start_time, prefix="📊"):
    import time

    elapsed = time.time() - start_time
    remain = (elapsed / processed) * (total - processed)
    return (
        f"{prefix}: {processed}/{total} 件 完了"
        f" | 経過: {int(elapsed//60)}分{int(elapsed%60)}秒"
        f" / 残り: 約 {int(remain//60)}分{int(remain%60)}秒"
    )


# ============================================================
# 3. データ取得処理
# ============================================================
# - load_symbol
def load_symbol(symbol, cache_dir="data_cache"):
    path = os.path.join(cache_dir, f"{safe_filename(symbol)}.csv")
    if not os.path.exists(path):
        return symbol, None
    return symbol, get_cached_data(symbol)


# - fetch_data
def fetch_data(symbols, max_workers=8):
    data_dict = {}
    total = len(symbols)
    st.info(f"📄 データ取得開始 | {total} 銘柄を処理中...")
    progress_bar = st.progress(0)
    log_area = st.empty()
    buffer, start_time = [], time.time()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(load_symbol, sym): sym for sym in symbols}
        for i, future in enumerate(as_completed(futures), 1):
            sym, df = future.result()
            if df is not None and not df.empty:
                data_dict[sym] = df
                buffer.append(sym)

            # --- System1形式の進捗ログ ---
            if i % 50 == 0 or i == total:
                log_with_progress(
                    i,
                    total,
                    start_time,
                    prefix="📄 データ取得",
                    batch=50,
                    log_area=log_area,
                    progress_bar=progress_bar,
                    extra_msg=f"銘柄: {', '.join(buffer)}" if buffer else None,
                )
                buffer.clear()

    progress_bar.empty()
    return data_dict


# ============================================================
# 4. バックテスト関連（ロジック実行）
# ============================================================
# - prepare_backtest_data
def prepare_backtest_data(
    strategy, symbols, system_name="SystemX", spy_df=None, **kwargs
):
    """
    データ取得 + インジケーター計算 + 候補生成 を共通処理化
    戻り値: (prepared_dict, candidates_by_date, merged_df)
    """
    # --- データ取得 ---
    data_dict = fetch_data(symbols)
    if not data_dict:
        st.error("有効なデータがありません")
        return None, None, None

    # --- インジケーター計算 ---#
    st.info("📊 インジケーター計算中...")
    ind_progress = st.progress(0)
    ind_log = st.empty()
    ind_buffer = []
    start_time = time.time()

    prepared_dict = strategy.prepare_data(
        data_dict,
        progress_callback=lambda done, total: ind_progress.progress(done / total),
        log_callback=lambda msg: ind_log.text(msg),  # ✅ 引数は msg 1つ
        **kwargs,
    )
    ind_progress.empty()

    # --- 候補生成 ---
    st.info("📊 セットアップ抽出中...")
    cand_log = st.empty()
    start_time = time.time()

    if system_name in ["System1", "System4"]:
        if spy_df is None or spy_df.empty:
            st.error(f"{system_name}: SPYデータが必要ですが取得できませんでした。")
            return prepared_dict, None, None

        if system_name == "System1":
            # --- ROC200ランキング生成（日別 / 内部でSPYフィルター済み） ---#
            st.info("SYSTEM1: 📊 ROC200ランキング生成中...")
            cand_log = st.empty()
            cand_progress = st.progress(0)
            start_time = time.time()

            candidates_by_date, merged_df = generate_roc200_ranking_system1(
                prepared_dict,
                spy_df,
                on_progress=lambda i, total, start: log_with_progress(
                    i,
                    total,
                    start,
                    prefix="📊 ROC200ランキング",
                    log_area=cand_log,
                    progress_bar=cand_progress,
                    unit="日",
                ),
                on_log=None,
            )
            cand_progress.empty()
            cand_log.text("✅ ROC200ランキング生成完了")

        elif system_name == "System4":
            st.info("SYSTEM4: 📊 RSI4ランキング生成中...")
            cand_log = st.empty()
            cand_progress = st.progress(0)
            start_time = time.time()

            candidates_by_date = strategy.generate_candidates(
                prepared_dict,
                market_df=spy_df,  # ✅ SPYを渡す
                progress_callback=lambda i, total, start: log_with_progress(
                    i,
                    total,
                    start,
                    prefix="📊 RSI4ランキング",
                    log_area=cand_log,
                    progress_bar=cand_progress,
                    unit="件",
                ),
            )
            cand_progress.empty()
            cand_log.text("✅ RSI4ランキング生成完了")
            merged_df = None

    elif system_name == "System2":
        st.info("SYSTEM2: 📊 ADX7ランキング生成中...")
        cand_log = st.empty()
        cand_progress = st.progress(0)
        start_time = time.time()

        candidates_by_date, merged_df = strategy.generate_candidates(
            prepared_dict,
            progress_callback=lambda i, total, start: log_with_progress(
                i,
                total,
                start,
                prefix="📊 ADX7ランキング",
                log_area=cand_log,
                progress_bar=cand_progress,
                unit="日",
            ),
            **kwargs,
        )
        cand_progress.empty()
        cand_log.text("✅ ADX7ランキング生成完了")
        merged_df = None

    elif system_name == "System7":
        cand_progress = st.progress(0)
        candidates_by_date, merged_df = (
            strategy.generate_candidates(  # ← タプルで受け取る
                prepared_dict,
                progress_callback=lambda done, total, start: log_with_progress(
                    done,
                    total,
                    start,
                    prefix="📊 候補抽出",
                    batch=10,
                    log_area=cand_log,
                    progress_bar=cand_progress,
                ),
                **kwargs,
            )
        )
        cand_progress.empty()
        merged_df = None  # ← System7はランキング不要なので常にNone

    else:
        # System2〜6はSPYを使わず通常通り
        cand_progress = st.progress(0)  # ← 追加
        candidates_by_date, merged_df = strategy.generate_candidates(
            prepared_dict,
            progress_callback=lambda done, total: log_with_progress(
                done,
                total,
                start_time,
                prefix="📊 候補抽出",
                batch=10,
                log_area=cand_log,
                progress_bar=cand_progress,
            ),
            **kwargs,
        )
        cand_progress.empty()
        merged_df = None

    if not candidates_by_date:
        st.warning(f"{system_name}: セットアップ条件を満たす銘柄がありません。")
        return prepared_dict, None, None

    # 🔽 候補がある場合はこちらで返す
    return prepared_dict, candidates_by_date, merged_df


# - run_backtest_with_logging
def run_backtest_with_logging(
    strategy, prepared_dict, candidates_by_date, capital, system_name="SystemX"
):
    st.info("💹 バックテスト実行中...")
    progress = st.progress(0)
    log_area = st.empty()
    debug_area = st.empty()  # 実行中のリアルタイムログ用
    start_time = time.time()

    debug_logs = []  # 資金推移ログを溜めるリスト

    # 共通ログコールバック
    def log_callback(i=None, total=None, start=None, msg=None):
        if msg is not None:
            if st.session_state.get("show_debug_logs", True):
                debug_logs.append(msg)
                debug_area.text(msg)  # 最新状態だけを更新
        elif i is not None and total is not None:
            log_with_progress(
                i,
                total,
                start,
                prefix="💹 バックテスト",
                batch=50,
                log_area=log_area,
                progress_bar=progress,
            )

    results_df = strategy.run_backtest(
        prepared_dict,
        candidates_by_date,
        capital,
        on_progress=lambda i, total, start: log_with_progress(
            i,
            total,
            start,
            prefix="💹 バックテスト",
            log_area=log_area,  # ← プログレス用のログ
            progress_bar=progress,
            unit="日",
        ),
        on_log=lambda msg: (
            debug_logs.append(msg) if msg.startswith("💰") else log_area.text(msg)
        ),
    )

    progress.empty()  # ← 完了後にプログレスバーを消す

    # --- 実行後にexpanderでまとめて表示 ---
    if st.session_state.get("show_debug_logs", True) and debug_logs:
        with st.expander("💰 資金推移ログ（全件表示・折りたたみ）", expanded=False):
            st.text("\n".join(debug_logs))

    return results_df


# ============================================================
# 5. UIアプリ本体
# ============================================================
# - run_backtest_app
def run_backtest_app(
    strategy,
    system_name="SystemX",
    limit_symbols=10,
    system_title=None,
    spy_df=None,
    **kwargs,
):

    st.title(system_title or f"{system_name} バックテスト")

    if st.button("⚠️ Streamlitキャッシュ全クリア"):
        st.cache_data.clear()
        st.success("Streamlit cache cleared.")

    # --- 詳細ログ表示切り替え ---
    if "show_debug_logs" not in st.session_state:
        st.session_state["show_debug_logs"] = True

    st.checkbox("詳細ログを表示", key="show_debug_logs")

    use_auto = st.checkbox("自動ティッカー取得（全銘柄）", value=True)
    capital = st.number_input("総資金（USD）", min_value=1000, value=1000, step=100)

    all_tickers = get_all_tickers()
    max_allowed = len(all_tickers)
    default_value = min(10, max_allowed)

    if system_name != "System7":
        # 🔽 取得銘柄数指定UI
        limit_symbols = st.number_input(
            "取得銘柄数（上限）",
            min_value=10,
            max_value=max_allowed,
            value=default_value,
            step=100,
            key=f"{system_name}_limit",
        )

        # 🔽 全銘柄を対象にするオプション
        if st.checkbox("全銘柄を対象に実施", key=f"{system_name}_all"):
            limit_symbols = max_allowed

    symbols_input = None
    if not use_auto:
        symbols_input = st.text_input(
            "ティッカーをカンマ区切りで入力",
            "AAPL,MSFT,TSLA,NVDA,META",
            key=f"{system_name}_symbols_main",
        )

    if system_name == "System7":
        # 🔽 System7はSPY専用
        symbols = ["SPY"]

    elif use_auto:
        symbols = all_tickers[:limit_symbols]

    else:
        if not symbols_input:
            st.error("銘柄を入力してください")
            return None, None, None, None, None
        symbols = [s.strip().upper() for s in symbols_input.split(",")]

    # --- 実行ボタン ---#
    if st.button("バックテスト実行", key=f"{system_name}_run"):

        prepared_dict, candidates_by_date, merged_df = prepare_backtest_data(
            strategy,
            symbols,
            system_name=system_name,
            spy_df=spy_df,
            **kwargs,
        )
        if candidates_by_date is None:
            return None, None, None, None, None

        # --- バックテスト実行（共通化） ---#
        results_df = run_backtest_with_logging(
            strategy, prepared_dict, candidates_by_date, capital, system_name
        )
        show_results(results_df, capital, system_name)

        # --- 戻り値をシステムごとに切り替え ---#
        if system_name == "System1":
            return results_df, merged_df, prepared_dict, capital, candidates_by_date
        else:
            return results_df, None, prepared_dict, capital, candidates_by_date

    # ⚠️ 実行ボタンが押されなかった場合も必ず5要素返す
    return None, None, None, None, None


# ============================================================
# 6. UI表示用関数
# ============================================================
# - show_results
def show_results(results_df, capital, system_name="SystemX"):
    """
    結果表示共通化:
    - サマリー
    - グラフ
    - 年次・月次サマリー
    - ヒートマップ
    - 保存
    """
    if results_df.empty:
        st.info("トレードは発生しませんでした。")
        return

    st.success("✅ バックテスト完了")

    # --- 結果表示 ---#
    st.subheader("バックテスト結果")
    st.dataframe(results_df)

    summary, results_df = summarize_results(results_df, capital)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("トレード回数", summary["trades"])
    col2.metric("最終損益 (USD)", f"{summary['total_return']:.2f}")
    col3.metric("勝率 (%)", f"{summary['win_rate']:.2f}")
    col4.metric("最大ドローダウン (USD)", f"{summary['max_dd']:.2f}")

    # --- 損益グラフ ---#
    st.subheader("📈 累積損益")
    plt.figure(figsize=(10, 4))
    plt.plot(
        results_df["exit_date"],
        results_df["cumulative_pnl"],
        label="Cumulative PnL",
    )
    plt.xlabel("日付")
    plt.ylabel("損益 (USD)")
    plt.title("累積損益")
    plt.legend()
    st.pyplot(plt)

    # --- サマリー ---#
    st.subheader("📅 年次サマリー")
    st.dataframe(
        results_df.groupby(results_df["exit_date"].dt.to_period("Y"))["pnl"]
        .sum()
        .reset_index()
    )

    st.subheader("📆 月次サマリー")
    st.dataframe(
        results_df.groupby(results_df["exit_date"].dt.to_period("M"))["pnl"]
        .sum()
        .reset_index()
    )

    # --- 日別保有銘柄ヒートマップ ---
    st.subheader("📊 日別保有銘柄ヒートマップ")
    st.info("📊 日別保有銘柄ヒートマップ生成中...")
    progress_heatmap = st.progress(0)
    heatmap_log = st.empty()
    start_time = time.time()

    unique_dates = sorted(results_df["entry_date"].dt.normalize().unique())
    total_dates = len(unique_dates)

    for i, date in enumerate(unique_dates, 1):
        _ = results_df[
            (results_df["entry_date"] <= date) & (results_df["exit_date"] >= date)
        ]
        log_with_progress(
            i,
            total_dates,
            start_time,
            prefix="📊 日別保有銘柄ヒートマップ",
            batch=10,
            log_area=heatmap_log,
            progress_bar=progress_heatmap,
            unit="日",
        )
        time.sleep(0.01)

    # 完了後にメッセージ切り替え
    heatmap_log.text("✅ 日別保有銘柄データ処理完了。図を生成中...")
    time.sleep(1.0)  # 少し待機してからヒートマップ生成
    heatmap_log.text("📊 ヒートマップ描画中...")

    # --- ヒートマップ生成と表示 ---#
    holding_matrix = generate_holding_matrix(results_df)
    display_holding_heatmap(
        holding_matrix, title=f"{system_name}：日別保有銘柄ヒートマップ"
    )
    download_holding_csv(holding_matrix, filename=f"holding_status_{system_name}.csv")

    progress_heatmap.empty()
    heatmap_log.success("📊 ヒートマップ生成完了")


# - show_signal_trade_summary
def show_signal_trade_summary(source_df, trades_df, system_name: str):
    """
    銘柄別 Signal 件数と Trade 件数を表示し、DataFrameを返す
    - System1: source_df = merged_df を渡す
    - 他System: source_df = prepared_dict を渡す
    """
    import pandas as pd

    # --- Signal_Count 集計 ---
    if system_name == "System1":
        signal_counts = source_df["symbol"].value_counts().reset_index()
        signal_counts.columns = ["symbol", "Signal_Count"]
    else:
        signal_counts = {
            sym: int(df["setup"].sum())
            for sym, df in source_df.items()
            if "setup" in df.columns
        }
        signal_counts = pd.DataFrame(
            signal_counts.items(), columns=["symbol", "Signal_Count"]
        )

    # --- Trade_Count 集計 ---
    if trades_df is not None and not trades_df.empty:
        trade_counts = (
            trades_df.groupby("symbol").size().reset_index(name="Trade_Count")
        )
    else:
        trade_counts = pd.DataFrame(columns=["symbol", "Trade_Count"])

    # --- マージ ---
    summary_df = pd.merge(signal_counts, trade_counts, on="symbol", how="outer").fillna(
        0
    )
    summary_df["Signal_Count"] = summary_df["Signal_Count"].astype(int)
    summary_df["Trade_Count"] = summary_df["Trade_Count"].astype(int)

    # --- 表示 ---
    with st.expander(
        f"📊 {system_name} 銘柄別シグナル発生件数とトレード件数（全期間）",
        expanded=False,
    ):
        st.dataframe(summary_df.sort_values("Signal_Count", ascending=False))

    return summary_df


# - display_roc200_ranking
def display_roc200_ranking(
    ranking_df, years=5, top_n=10, title="📊 System1 日別ROC200ランキング"
):
    """
    ROC200ランキングを表示するUI専用関数。
    - バックテストには全期間の ranking_df を渡す
    - 表示では直近 years 年 / 上位 top_n 銘柄に絞る
    - ROC200_Rank が無ければ自動で付与する
    """
    if ranking_df is None or ranking_df.empty:
        st.warning("ROC200ランキングが空です。")
        return

    df = ranking_df.copy()

    # --- 必要なら ROC200_Rank を付与 ---
    if "ROC200_Rank" not in df.columns and "ROC200" in df.columns:
        df["ROC200_Rank"] = df.groupby("Date")["ROC200"].rank(
            ascending=False, method="first"
        )

    # --- 表示用フィルタリング ---
    if years:
        start_date = pd.Timestamp.now() - pd.DateOffset(years=years)
        df = df[df["Date"] >= start_date]
    if top_n:
        df = df.groupby("Date").head(top_n)

    # 🔽 日付昇順＋ランキング昇順にソート
    df = df.sort_values(["Date", "ROC200_Rank"], ascending=[True, True])

    with st.expander(f"{title}（直近{years}年 / 上位{top_n}銘柄）", expanded=False):
        st.dataframe(
            df.reset_index(drop=True)[["Date", "ROC200_Rank", "symbol"]],
            column_config={
                "Date": st.column_config.DatetimeColumn(format="YYYY-MM-DD"),
                "ROC200_Rank": st.column_config.NumberColumn(width="small"),
                "symbol": st.column_config.TextColumn(width="small"),
            },
            hide_index=False,
        )


# - summarize_results
def summarize_results(results_df, capital):
    """
    バックテスト結果から共通サマリーを返しつつ、
    results_df に cumulative_pnl / drawdown も追加して返す
    """
    if results_df.empty:
        return {}, results_df

    results_df = results_df.copy()
    results_df["exit_date"] = pd.to_datetime(results_df["exit_date"])
    results_df = results_df.sort_values("exit_date")

    # 累積PnLとドローダウンを追加
    results_df["cumulative_pnl"] = results_df["pnl"].cumsum()
    results_df["cum_max"] = results_df["cumulative_pnl"].cummax()
    results_df["drawdown"] = results_df["cumulative_pnl"] - results_df["cum_max"]

    total_return = results_df["pnl"].sum()
    win_rate = (results_df["return_%"] > 0).mean() * 100
    max_dd = results_df["drawdown"].min()

    summary = {
        "trades": len(results_df),
        "total_return": total_return,
        "win_rate": win_rate,
        "max_dd": max_dd,
    }
    return summary, results_df


# ============================================================
# 7. 保存系
# ============================================================
# - save_signal_and_trade_logs
def save_signal_and_trade_logs(signal_counts_df, results, system_name, capital):
    """Signal件数とTradeログをCSV保存"""
    today_str = pd.Timestamp.today().strftime("%Y-%m-%d_%H%M")
    save_dir = "results_csv"
    os.makedirs(save_dir, exist_ok=True)

    # --- Signal件数 ---
    sig_dir = os.path.join(save_dir, "signals")
    os.makedirs(sig_dir, exist_ok=True)
    signal_path = os.path.join(
        sig_dir, f"{system_name}_signals_{today_str}_{int(capital)}.csv"
    )
    if signal_counts_df is not None and not signal_counts_df.empty:
        signal_counts_df.to_csv(signal_path, index=False)
        st.write(f"✅ signal件数も保存済み: {signal_path}")

    # --- Tradeログ ---
    trade_dir = os.path.join(save_dir, "trades")
    os.makedirs(trade_dir, exist_ok=True)
    trade_path = os.path.join(
        trade_dir, f"{system_name}_trades_{today_str}_{int(capital)}.csv"
    )

    # list → DataFrame 変換
    if isinstance(results, list):
        trades_df = pd.DataFrame(results) if results else pd.DataFrame()
    else:
        trades_df = results

    if trades_df is not None and not trades_df.empty:
        trades_df.to_csv(trade_path, index=False)
        st.write(f"📂 売買ログを自動保存: {trade_path}")


# - save_prepared_data_cache
def save_prepared_data_cache(data_dict, system_name="SystemX"):
    """加工済み日足データキャッシュ保存"""
    st.info(f"💾 {system_name} 加工済日足データキャッシュ保存開始...")
    if not data_dict:
        st.warning("⚠️ 保存対象のデータがありません")
        return

    total = len(data_dict)
    progress_bar = st.progress(0)
    for i, (sym, df) in enumerate(data_dict.items(), 1):
        path = os.path.join("data_cache", f"{safe_filename(sym)}.csv")
        df.to_csv(path)
        progress_bar.progress(i / total)

    st.write(f"💾 加工済日足データキャッシュ保存完了 ({total} 件)")
    progress_bar.empty()

    st.success("🔚 バックテスト終了")
# 7-x. 旧APIの委譲E後方互換EE# ============================================================
"""
# ============================================================
# 7-x. 旧APIの委譲（後方互換）
# ============================================================
"""
# 7-x. 旧APIの委譲（後方互換）
# ============================================================
def save_prepared_data_cache(data_dict, system_name="SystemX"):
    """加工済みデータキャッシュ保存（共通ユーティリティへ委譲）"""
    from common.cache_utils import save_prepared_data_cache as _save

    return _save(data_dict, system_name)
