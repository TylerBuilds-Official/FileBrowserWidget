# Changelog

## 0.1.2 -- 2026-09-30

- **Folders and drives** menu beside Filter: the Desktop, your Downloads, Documents, Pictures, Music, and Videos, then local drives, then mapped network drives, named the way Explorer names them, with Windows' own drive icons and a red X on a disconnected share. It opens at once; names and icons fill in behind it and are kept for next time.
- **Address bar**: Ctrl+L, Alt+D, a click beside the breadcrumbs, or **Go to path** in that menu. Paste anything Explorer takes: quotes from Copy as path, %VARIABLES%, a bare drive letter, a relative path, `\\server\share`, or a server alone, which opens as the folder of its shares.
- **Start in** setting: the Desktop, Downloads, Documents, a drive, any folder of your own through the folder button, or **Where I left off**. Replaces the old reopen toggle, which carries over. A start on a drive that is gone falls back to the Desktop.
- **Default sort** setting: the order a folder opens in. A sort picked in Filter lasts until the panel reopens, and the dot on Filter marks a sort other than your default. The sort you had picked carries over as the default.
- **Show favorites at the top** setting, on by default: in your start folder, favorites lead the list wherever they live, in the order you starred them. Drilled into any other folder the list keeps its order.
- Drive roots are titled the way Explorer titles them and show free space: **Boot (C:)**, **412 GB free of 931 GB**.
- Up from a share goes to its server, and the breadcrumbs show the server before the share.
- Hover with a cascade open: the next row lights the moment the pointer reaches it, and the row you left goes out at once, level and all. Only a level's start waits the menu delay, never its end. A move aimed at the level keeps it while the pointer crosses the rows beneath.
- A row no longer stays lit after the pointer has gone.
- Cascade icons paint from the cache as they land instead of resizing and repainting the menu once per icon. A level of a few hundred items used to hold the UI thread for over a second after it opened.
- The list is laid out once when it is built, not once per row, and a refresh of an unchanged folder costs next to nothing. A 350-item folder opens in about a quarter of the time.
- Nothing touches a share or the shell on the UI thread anymore: folders, look-ups, deletes, drive names, icons, and free space all run on workers, and a wait of more than a moment says what it is waiting on. Folders on another machine are polled, not watched.
- Switching folders fades the new list in place: no sideways slide, no doubled icons.
- Clicking a row, or anywhere off the address bar, drops it back to breadcrumbs.
- An empty card reader or disc drive reports an error instead of raising the "insert a disk" dialog.
- Upgrading clears every file of the previous build first, old DLLs at the top of the folder included, and uninstalling leaves the folder empty.

## 0.1.1 -- 2026-09-22

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
