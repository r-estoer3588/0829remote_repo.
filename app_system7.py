import app_system7_ui2 as _ui


def main_process(*, single_mode=None, ui_manager=None):
    """System7のメイン処理。統合タブ/単体実行の双方から呼び出し可能。"""
    return _ui.run_tab(single_mode=single_mode, ui_manager=ui_manager)


def run_tab(*, single_mode=None, ui_manager=None):
    return main_process(single_mode=single_mode, ui_manager=ui_manager)


def main():
    _ui.run_tab()


if __name__ == "__main__":
    main()
