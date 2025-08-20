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
from common.performance_summary import summarize_results
from tickers_loader import get_all_tickers
from common.backtest_utils import log_progress
import matplotlib.ticker as mticker


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
):
    """System1形式の進捗ログ＋進捗バーを表示"""
    if i % batch == 0 or i == total:
        elapsed = time.time() - start_time
        remain = (elapsed / i) * (total - i) if i > 0 else 0
        msg = (
            f"{prefix}: {i}/{total} 件 完了 "
            f"| 経過: {int(elapsed // 60)}分{int(elapsed % 60)}秒 "
            f"/ 残り: 約 {int(remain // 60)}分{int(remain % 60)}秒"
        )
        if extra_msg:
            msg += f"\n{extra_msg}"
        if log_area:
            log_area.text(msg)
        if progress_bar:
            progress_bar.progress(i / total)


# ============================================================
# データ取得（共通）
# ============================================================
def load_symbol(symbol, cache_dir="data_cache"):
    path = os.path.join(cache_dir, f"{safe_filename(symbol)}.csv")
    if not os.path.exists(path):
        return symbol, None
    return symbol, get_cached_data(symbol)


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
# バックテストアプリ共通本体
# ============================================================
def run_backtest_app(
    strategy, system_name="SystemX", system_title=None, limit_symbols=500, **kwargs
):
    # --- タイトル ---
    if system_title:
        st.title(system_title)
    else:
        st.title(f"{system_name} バックテスト")

    # --- キャッシュクリア ---
    if st.button("⚠️ Streamlitキャッシュ全クリア"):
        st.cache_data.clear()
        st.success("Streamlit cache cleared.")

    # --- ティッカー選択 ---
    use_auto = st.checkbox("自動ティッカー取得（全銘柄）", value=True)
    capital = st.number_input("総資金（USD）", min_value=1000, value=1000, step=100)

    all_tickers = get_all_tickers()
    max_allowed = len(all_tickers)
    default_value = min(10, max_allowed)

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

    # --- 実行ボタン ---
    if st.button("バックテスト実行", key=f"{system_name}_run"):

        # --- symbols を決定 ---
        if system_name == "System7":
            # System7はSPYのみを対象
            symbols = ["SPY"]

        else:
            if use_auto:
                symbols = all_tickers[:limit_symbols]
            else:
                if not symbols_input:
                    st.error("銘柄を入力してください")
                    return
                symbols = [s.strip().upper() for s in symbols_input.split(",")]

            # System1はSPYをフィルター用に追加（対象銘柄にはしない）
            if system_name == "System1" and "SPY" not in symbols:
                # フィルター専用なので別途読み込む、symbolsには追加しない
                spy_df = get_cached_data("SPY")
                if spy_df is None or spy_df.empty:
                    st.error(
                        "SPYデータが取得できません。キャッシュを更新してください。"
                    )
                    return

        # --- データ取得 ---
        data_dict = fetch_data(symbols)
        if not data_dict:
            st.error("有効なデータがありません")
            return

        # --- インジケーター計算 ---
        st.info("📊 インジケーター計算中...")
        ind_progress = st.progress(0)
        ind_log = st.empty()
        start_time = time.time()

        prepared_dict = strategy.prepare_data(
            data_dict,
            progress_callback=lambda done, total: log_with_progress(
                done,
                total,
                start_time,
                prefix="📊 指標計算",
                batch=50,
                log_area=ind_log,
                progress_bar=ind_progress,
            ),
            **kwargs,
        )
        ind_progress.empty()

        # --- 候補抽出 ---
        st.info("📊 セットアップ抽出中...")
        cand_progress = st.progress(0)
        cand_log = st.empty()
        start_time = time.time()

        if system_name == "System1":
            # SPYフィルターを使って候補抽出
            candidates_by_date, merged_df = strategy.generate_candidates(
                prepared_dict,
                spy_df,  # フィルター専用
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

        elif system_name == "System7":
            # SPYのみが対象なのでprepared_dictにSPYだけが入っている想定
            candidates_by_date = strategy.generate_candidates(
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

        else:
            # System2〜6はSPYを使わず通常通り
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

        # --- バックテスト ---
        st.info("💹 バックテスト実行中...")
        bt_progress = st.progress(0)
        bt_log = st.empty()
        start_time = time.time()

        results_df = strategy.run_backtest(
            prepared_dict,
            candidates_by_date,
            capital,
            on_progress=lambda i, total, start: log_with_progress(
                i,
                total,
                start,
                prefix="💹 バックテスト",
                batch=50,
                log_area=bt_log,
                progress_bar=bt_progress,
            ),
            **kwargs,
        )
        bt_progress.empty()

        if results_df.empty:
            st.info("トレードは発生しませんでした。")
            return

        st.success("✅ バックテスト完了")

        # --- 結果表示 ---
        st.subheader("バックテスト結果")
        st.dataframe(results_df)

        summary, results_df = summarize_results(results_df, capital)
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("トレード回数", summary["trades"])
        col2.metric("最終損益 (USD)", f"{summary['total_return']:.2f}")
        col3.metric("勝率 (%)", f"{summary['win_rate']:.2f}")
        col4.metric("最大ドローダウン (USD)", f"{summary['max_dd']:.2f}")

        # --- 損益グラフ ---
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

        # --- サマリー ---
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

        st.subheader("📊 日別保有銘柄ヒートマップ")
        # 日別保有銘柄ヒートマップ生成の進捗表示
        st.info("📊 日別保有銘柄ヒートマップ生成中...")
        progress_heatmap = st.progress(0)
        heatmap_log = st.empty()

        start_time = time.time()

        # UIを即反映させるための短い遅延
        time.sleep(0.1)

        # ヒートマップ生成のために、results_df を日付単位で処理
        unique_dates = sorted(results_df["entry_date"].dt.normalize().unique())
        total_dates = len(unique_dates)

        for i, date in enumerate(unique_dates, 1):
            # 1日分の保有状況計算
            sub_df = results_df[
                (results_df["entry_date"] <= date) & (results_df["exit_date"] >= date)
            ]
            # 進捗バー更新
            progress_heatmap.progress(i / total_dates)
            # 経過時間と残り時間の計算
            elapsed = time.time() - start_time
            remain = elapsed / i * (total_dates - i)

            # ログ表示（10日ごと or 最終日）
            if i % 10 == 0 or i == total_dates:
                heatmap_log.text(
                    f"📊 日別保有銘柄ヒートマップ: {i}/{total_dates} 日処理完了"
                    f" | 経過: {int(elapsed // 60)}分{int(elapsed % 60)}秒 "
                    f"/ 残り: 約 {int(remain // 60)}分{int(remain % 60)}秒"
                )
            time.sleep(0.01)  # 表示のための小さな遅延

        # 完了後にメッセージ切り替え
        heatmap_log.text("✅ 日別保有銘柄データ処理完了。図を生成中...")
        time.sleep(1.0)  # 少し待機してからヒートマップ生成
        heatmap_log.text("📊 ヒートマップ描画中...")

        # --- ヒートマップ生成と表示 ---
        holding_matrix = generate_holding_matrix(results_df)
        display_holding_heatmap(
            holding_matrix, title=f"{system_name}：日別保有銘柄ヒートマップ"
        )
        download_holding_csv(
            holding_matrix, filename=f"holding_status_{system_name}.csv"
        )

        progress_heatmap.empty()
        heatmap_log.success("📊 ヒートマップ生成完了")

        # --- 保存処理 ---
        today_str = pd.Timestamp.today().date().isoformat()
        save_dir = "results_csv"
        os.makedirs(save_dir, exist_ok=True)

        # 戻り値として返す
        if system_name in [
            "System1",
            "System2",
            "System3",
            "System4",
            "System5",
            "System6",
        ]:
            return results_df, merged_df, prepared_dict
        else:
            return results_df, None, prepared_dict

    return None, None, None


# ============================================================
# Signal件数 + Trade件数 共通表示
# ============================================================
def show_signal_trade_summary(
    signal_counts_df: pd.DataFrame,
    trades_df: pd.DataFrame,
    system_name: str = "SystemX",
) -> pd.DataFrame:
    """
    銘柄別 Signal_Count + Trade_Count を集計し表示する共通UI
    - signal_counts_df: DataFrame(columns=["symbol", "Signal_Count"])
    - trades_df: バックテスト結果 DataFrame
    - system_name: 表示用のシステム名
    """
    # Trade_Count 集計
    if not trades_df.empty:
        trade_counts = (
            trades_df.groupby("symbol").size().reset_index(name="Trade_Count")
        )
    else:
        trade_counts = pd.DataFrame(columns=["symbol", "Trade_Count"])

    # マージ
    summary_df = pd.merge(
        signal_counts_df, trade_counts, on="symbol", how="outer"
    ).fillna(0)
    summary_df["Signal_Count"] = summary_df["Signal_Count"].astype(int)
    summary_df["Trade_Count"] = summary_df["Trade_Count"].astype(int)

    # 表示
    with st.expander(
        f"📊 {system_name} 銘柄別シグナル発生件数とトレード件数（全期間）",
        expanded=False,
    ):
        st.dataframe(summary_df.sort_values("Signal_Count", ascending=False))

    return summary_df


# ============================================================
# Signal件数・Tradeログ・加工済データ保存 共通関数
# ============================================================
def save_signal_and_trade_logs(signal_counts_df, results_df, system_name, capital):
    """Signal件数とTradeログをCSV保存"""
    today_str = pd.Timestamp.today().date().isoformat()
    save_dir = "results_csv"
    os.makedirs(save_dir, exist_ok=True)

    # Signal件数
    signal_path = os.path.join(
        save_dir,
        "signals",
        f"{system_name.lower()}_signals_{today_str}_{int(capital)}.csv",
    )
    os.makedirs(os.path.dirname(signal_path), exist_ok=True)
    signal_counts_df.to_csv(signal_path, index=False)
    st.write(f"✅ signal件数も保存済み: {signal_path}")

    # Tradeログ
    trade_path = os.path.join(
        save_dir, f"{system_name.lower()}_{today_str}_{int(capital)}.csv"
    )
    results_df.to_csv(trade_path, index=False)
    st.write(f"📂 売買ログを自動保存: {trade_path}")


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
