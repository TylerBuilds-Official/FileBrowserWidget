# File Browser

A Windows tray utility for browsing desktop files and folders.

## Launch and pin

Run `tools/create-shortcuts.ps1` from PowerShell. It creates two shortcuts in `launchers/`, using this checkout's `.venv\Scripts\pythonw.exe` so no console window opens.

- **File Browser.lnk**: opens the browser, or asks the already-running instance to open. Right-click this shortcut in File Explorer, choose **Show more options**, then **Pin to taskbar**. You can also copy it to the Desktop.
- **File Browser (Startup).lnk**: starts quietly in the tray. You can use **Settings → Start with Windows** instead of copying this shortcut into the Startup folder.

The generated shortcuts contain absolute paths. Regenerate them and replace any copied/pinned shortcuts if you move the project or its virtual environment. These are development launchers using Python; a standalone packaged executable can replace them when the app is ready to distribute.

## Global shortcut

**Alt+B** opens the browser from any application while File Browser is running. Change it under **Settings → Open browser shortcut**, or use **Reset** to return to Alt+B. Record one combination containing Ctrl or Alt, optionally Shift, plus a letter, number, or function key other than F12.

It uses [Windows hotkey registration](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registerhotkey). If a new combination is unavailable, the app reports the conflict and keeps your previous shortcut active. If the saved shortcut is unavailable when the app starts, the tray menu and launcher still work. Use **Quit** in the tray menu to exit and release the shortcut.

## Search, filters, and sorting

- **Ctrl+F** focuses the search box. Search matches filenames in the current folder, including their extensions, without scanning subfolders. **Escape** clears a search first, then closes the browser.
- The type dropdown contains only categories and extensions detected in the current folder, with counts. Search and type filtering work together. Empty results say **No matching files**.
- Programs include executable files, installers, batch files, and Windows shortcuts targeting executables. Games are detected from known launcher URLs (Steam, Epic, Ubisoft, Battle.net) or executable targets under `steamapps/common`; unrecognized shortcuts remain under Shortcuts and their extension.
- Sort by name in either direction, newest first, largest first, or type. The sort choice is remembered. Folder sizes are not calculated recursively.
- Refresh preserves the query and scroll position. Moving to another folder clears the query; a type filter stays selected if that category exists there.

## Favorites and navigation

Click a row's star or right-click **Add to favorites**. Favorites are remembered and pinned above other matching items in their folder. The **Favorites** menu opens saved files and folders from anywhere and includes a removal menu for moved or deleted items.

Click breadcrumb segments to navigate to ancestors; **…** opens earlier segments when the path is too long. **Desktop** or **Alt+Home** returns to the Windows Desktop location, including redirected desktops. Alt+Left/Right, mouse side buttons, and Backspace navigate history; Alt+Up opens the parent. Back/Forward restore scroll positions. F5 or Ctrl+R refreshes.

## Start with Windows

Enable **Settings → Start with Windows** to launch quietly in the tray when you sign in. It manages only the `FileBrowserWidget` value in the current user's [Windows Run registry key](https://learn.microsoft.com/en-us/windows/win32/setupapi/run-and-runonce-registry-keys); no administrator access is needed. Turning it off removes that entry. If you previously copied a launcher into `shell:startup`, remove that copy separately.

Startup uses absolute paths. Toggle the setting off and on after moving this checkout or virtual environment. Windows may delay startup apps or disable them through its own Startup Apps settings.

## Command line

From the project directory:

```powershell
.\.venv\Scripts\python.exe -m src.app
.\.venv\Scripts\python.exe -m src.app --background
```

Normal launches open the browser. `--background` leaves it hidden, including when an instance is already running. There is one running instance per Windows user.

## Tests

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests
```
