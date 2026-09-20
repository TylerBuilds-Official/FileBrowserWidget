import argparse
import sys

from src.ui.win_tray_app import WinTrayApp


def show_exception(error_type, error, traceback):
    sys.__excepthook__(error_type, error, traceback)


def main(argv=None):
    parser = argparse.ArgumentParser(description="File Browser tray utility")
    parser.add_argument("--background", action="store_true",
                        help="Start without announcing the app or opening a running one (for Windows Startup).")
    args = parser.parse_args(argv)
    sys.excepthook = show_exception
    app = WinTrayApp(user_launch=not args.background)
    if not app.is_primary:
        return 0
    try:
        return app.exec()
    finally:
        app.global_hotkey.unregister()
        app.instance.close()


if __name__ == "__main__":
    sys.exit(main())
