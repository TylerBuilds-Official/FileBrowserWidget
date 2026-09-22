# Changelog

## 0.1.1 — 2026-09-22

- Folder hover setting: rest on a folder to fan its contents out in cascading menus.
- Cascade menus open to one side, edge to edge, and scroll instead of spreading into columns.
- Folder listings and icons are read on worker threads; the UI thread never asks the shell.
- New logo: multi-size app, tray, and installer icon, plus an About card in Settings.
- Fluent motion: the panel and flyout slide and fade in and out; Settings and folder navigation drill.
- Tray click and Alt+B toggle the panel.
- Right and Left on a focused folder row open and close the cascade from the keyboard.
- Type to jump to a name, Explorer style; Ctrl+F still searches.
- Alt+Enter opens Properties; middle-click shows an item in File Explorer.
- "Reopen where I left off" setting, off by default.
- Folder rows skip their tooltip while the cascade is on.
- The Settings scrollbar sits where the file list's does.
- The exe carries version info, so Task Manager shows "File Browser"; the installer wizard shows the logo.
- The version lives in `src/version.py`; the debug Test entry is gone from the tray menu.
