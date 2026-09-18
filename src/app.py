import sys
from src.ui.win_tray_app import WinTrayApp

def show_exception(error_type, error, traceback):
    sys.__excepthook__(error_type, error, traceback)

def main():
    sys.excepthook = show_exception
    app = WinTrayApp()
    app.exec()
if __name__ == "__main__":
    main()
