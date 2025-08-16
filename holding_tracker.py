# holding_tracker.py
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from collections import defaultdict
import streamlit as st

def generate_holding_matrix(results_df: pd.DataFrame) -> pd.DataFrame:
    """
    日次ごとの保有銘柄マトリックスを生成。
    - 行: 日付（entry_date〜exit_date）
    - 列: 銘柄シンボル
    - 値: 1（保有中）、0（非保有）
    """
    holding_dict = defaultdict(set)
    for _, row in results_df.iterrows():
        current_date = pd.to_datetime(row["entry_date"])
        end_date = pd.to_datetime(row["exit_date"])
        while current_date <= end_date:
            holding_dict[current_date.date()].add(row["symbol"])
            current_date += pd.Timedelta(days=1)

    all_dates = sorted(holding_dict.keys())
    all_symbols = sorted(set(results_df["symbol"].unique()))
    holding_matrix = pd.DataFrame(index=all_dates, columns=all_symbols)

    for date in all_dates:
        for sym in all_symbols:
            holding_matrix.loc[date, sym] = 1 if sym in holding_dict[date] else 0

    return holding_matrix.fillna(0).astype(int)

def display_holding_heatmap(matrix: pd.DataFrame, title: str = "日別保有ヒートマップ") -> None:
    """
    Streamlitで保有銘柄のヒートマップを表示。
    - matrix: generate_holding_matrixの出力
    - title: 表示タイトル
    """
    st.subheader(title)

    # 表示行数が多い場合の制限（例: 最大100行）
    max_rows = 100
    if len(matrix) > max_rows:
        st.info(f"表示行数を制限中（最新{max_rows}日分）")
        matrix = matrix.tail(max_rows)

    fig, ax = plt.subplots(figsize=(12, max(4, len(matrix) // 3)))
    sns.heatmap(matrix, cmap="Greens", cbar=False, linewidths=0.5, linecolor="gray")
    ax.set_xlabel("銘柄")
    ax.set_ylabel("日付")
    ax.set_title(title)
    st.pyplot(fig)

def download_holding_csv(matrix: pd.DataFrame, filename: str = "holding_status.csv") -> None:
    """
    保有銘柄の遷移をCSV形式でダウンロード提供。
    """
    csv = matrix.to_csv().encode("utf-8")
    st.download_button("保有銘柄の遷移をCSVで保存", data=csv, file_name=filename, mime="text/csv")
