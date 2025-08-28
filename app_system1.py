import app_system1_ui2 as _ui


def main_process(*, spy_df=None, ui_manager=None):
    """System1のメイン処理。統合タブ/単体実行の双方から呼び出し可能。

    spy_df: 統合UI側でキャッシュ済みのSPYデータを再利用する場合に渡す
    ui_manager: 統合UIの段階的ログ/進捗表示ハンドラ（任意）
    """
    return _ui.run_tab(spy_df=spy_df, ui_manager=ui_manager)


def run_tab(*, spy_df=None, ui_manager=None):
    return main_process(spy_df=spy_df, ui_manager=ui_manager)


def main():
    _ui.run_tab()


if __name__ == "__main__":
    main()
