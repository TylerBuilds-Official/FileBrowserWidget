# Changelog

## 0.1.3 — 2026-09-30

- With a cascade open, the next row lights the moment the pointer reaches it, and the row it left goes out. Qt hands every mouse event to the open menu, so the rows heard nothing until their own level opened; the cascade tells them now, and a row no longer stays lit after the pointer has gone.
- A level's icons no longer make the menu size and repaint itself once per icon as they land. A level of a few hundred items held the UI thread for over a second after it opened, and the next row's hover waited on that; the items paint their icons from the cache instead, and only the rows that got one are painted again.
- The list is laid out once when it is built rather than once per row, and a render that changes nothing no longer lays every row out twice and elides every name again. A 350-item folder opens in about a quarter of the time; a refresh of an unchanged folder costs next to nothing.
- Rows no longer put every event through two Python filters: Enter, Space, a press, and a hidden row tell the panel directly.

## 0.1.2 — 2026-09-28

- **Folders and drives** menu, a new button beside Filter: the Desktop and your Downloads, Documents, Pictures, Music, and Videos, then local drives, then mapped network drives, named as Explorer names them (**Boot (C:)**, **Media (\\nas) (M:)**), with Windows' own drive icons and a red X for a disconnected share. It opens at once; labels and icons are read in the background and kept for next time.
- **Address bar**: **Ctrl+L**, **Alt+D**, a click beside the breadcrumbs, or **Go to path…** in that menu turns the path into text to type or paste a place into, a share such as `\\server\share` included. Quotes from **Copy as path**, `%VARIABLES%`, a bare drive letter, and relative paths all work.
- **Start in** setting: open on the Desktop (default), Downloads, Documents, a drive, or where you left off. A start on a drive that is no longer there falls back to the Desktop. Replaces the "Reopen where I left off" toggle, which carries over.
- Drive roots are titled and show free space as Explorer does: **Boot (C:)**, **412 GB free of 931 GB**.
- Folders are read on worker threads, so a slow or sleeping network share never freezes the panel. Opening an item, opening a favorite, deleting to the Recycle Bin, and reading a drive's name, icon, and space all happen off the UI thread; a wait of more than a moment says what it is doing.
- Folders on another machine are refreshed on a timer and on each open rather than watched, since setting a watch would touch the share on the UI thread.
- An empty card reader or disc drive reports an error instead of raising Windows' "insert a disk" dialog.
- Switching folders fades the new list in place: the old page goes at once and the new fades up without a sideways slide, so icons never double or jitter mid-animation.
- Clicking a row, a folder, or anywhere off the address bar drops it back to breadcrumbs; the input no longer keeps focus after a click away.

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
- Upgrading removes the previous build's files first, so nothing stale is left behind.
- The version lives in `src/version.py`; the debug Test entry is gone from the tray menu.
