import pandas as pd

def summarize_results(results_df, capital):
    """
    バックテスト結果から共通サマリーを返す
    """
    if results_df.empty:
        return {}

    total_return = results_df["pnl"].sum()
    win_rate = (results_df["return_%"] > 0).mean() * 100

    results_df = results_df.sort_values("exit_date")
    results_df["cumulative_pnl"] = results_df["pnl"].cumsum()
    results_df["cum_max"] = results_df["cumulative_pnl"].cummax()
    results_df["drawdown"] = results_df["cumulative_pnl"] - results_df["cum_max"]
    max_dd = results_df["drawdown"].min()

    return {
        "trades": len(results_df),
        "total_return": total_return,
        "win_rate": win_rate,
        "max_dd": max_dd,
    }
