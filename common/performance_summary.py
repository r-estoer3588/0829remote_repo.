import pandas as pd


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
