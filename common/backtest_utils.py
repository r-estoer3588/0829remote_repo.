import time


def log_progress(processed, total, start_time, buffer, prefix, log_callback):
    """
    バッチごとの進捗ログ出力（system2/3スタイルを共通化）
    """
    elapsed = time.time() - start_time
    remain = (elapsed / processed) * (total - processed)
    log_callback(
        f"{prefix}: {processed}/{total} 件 完了"
        f" | 残り: 約{int(remain // 60)}分{int(remain % 60)}秒\n"
        f"銘柄: {', '.join(buffer)}"
    )
    buffer.clear()
