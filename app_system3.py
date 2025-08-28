import app_system3_ui2 as _ui


def main_process(*, ui_manager=None):
    """System3のメイン処理。統合タブ/単体実行の双方から呼び出し可能。"""
    return _ui.run_tab(ui_manager=ui_manager)


def run_tab(*, ui_manager=None):
    return main_process(ui_manager=ui_manager)


def main():
    _ui.run_tab()


if __name__ == "__main__":
    main()
