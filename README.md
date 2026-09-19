# File Browser

A Windows tray utility for browsing desktop files and folders.

## Desktop locations and file errors

The Desktop view combines the configured user Desktop and Public Desktop. Windows Known Folders resolves local, OneDrive, relocated, and network-redirected paths; the app does not guess which OneDrive account owns the Desktop. User items take precedence when both locations contain the same filename. Each item retains its real path for opening and **Open file location**.

If one Desktop location cannot be read, readable locations remain available and the status tooltip shows the errors. Online-only cloud shortcuts use a generic icon without reading their contents to trigger a download; opening them lets Windows handle availability. Virtual Shell objects such as Recycle Bin are not filesystem entries and are not included.

File launches are attempted once. Failures appear in the browser status, a tray notification, and the log. The thread executor also treats `OSError` and its subclasses as non-retryable; other tasks retain their configurable retries.

## Launch and pin

Run `tools/create-shortcuts.ps1` from PowerShell. It creates two shortcuts in `launchers/`, using this checkout's `.venv\Scripts\pythonw.exe` so no console window opens.

- **File Browser.lnk**: opens the browser, or asks the already-running instance to open. Right-click this shortcut in File Explorer, choose **Show more options**, then **Pin to taskbar**. You can also copy it to the Desktop.
- **File Browser (Startup).lnk**: starts quietly in the tray. You can use **Settings → Start with Windows** instead of copying this shortcut into the Startup folder.

The generated shortcuts contain absolute paths. Regenerate them and replace any copied/pinned shortcuts if you move the project or its virtual environment. These are development launchers using Python; a standalone packaged executable can replace them when the app is ready to distribute.

## Global shortcut

**Alt+B** opens the browser from any application while File Browser is running. Change it under **Settings → Open browser shortcut**, or use **Reset** to return to Alt+B. Record one combination containing Ctrl or Alt, optionally Shift, plus a letter, number, or function key other than F12.

It uses [Windows hotkey registration](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registerhotkey). If a new combination is unavailable, the app reports the conflict and keeps your previous shortcut active. If the saved shortcut is unavailable when the app starts, the tray menu and launcher still work. Use **Quit** in the tray menu to exit and release the shortcut.

## Search, filters, and sorting

- **Filter** opens search, type filtering, and sorting in a dropdown overlay; **Ctrl+F** opens it with search focused. Search matches filenames in the current folder, including their extensions, without scanning subfolders. **Enter**, **Done**, or **Escape** dismisses the overlay and keeps the results. Outside the overlay, **Escape** clears a search first, then closes the browser.
- A dot on **Filter** marks an active search, type filter, or non-default sort. **Clear filters** resets search and type without changing your sort.
- The type dropdown contains only categories and extensions detected in the current folder, with counts. Search and type filtering work together. Empty results say **No matching files**.
- Programs include executable files, installers, batch files, and Windows shortcuts targeting executables. Games are detected from known launcher URLs (Steam, Epic, Ubisoft, Battle.net) or executable targets under `steamapps/common`; unrecognized shortcuts remain under Shortcuts and their extension.
- Sort by name in either direction, newest first, largest first, or type. The sort choice is remembered. Folder sizes are not calculated recursively.
- Refresh preserves the query and scroll position. Moving to another folder clears the query; a type filter stays selected if that category exists there.

## Scrolling and refresh performance

Mouse-wheel scrolling is animated in the file list, settings, and combo dropdowns. Touchpad pixel scrolling remains direct. Scrollbar dragging, keyboard navigation, and restored history positions cancel pending animation. Scrolling over a closed settings combo does not change its value.

Unchanged reopens reuse the loaded list without scanning files or extracting icons. Filesystem changes are debounced; hidden panels refresh on their next open. A 30-second fallback checks for changes missed by a watcher, including on shares. Unchanged metadata, icons, and row widgets are reused; filtering and extension display changes do not scan the filesystem. Caches are limited to the current folder. **F5/Ctrl+R** forces metadata and icon refresh, including a shortcut's externally changed icon.

Initial loads and actual rescans still perform filesystem I/O and depend on disk/network responsiveness. A local 300-file benchmark measured the unchanged-reopen list work at about 83 ms before caching and under 1 ms after; this is not an end-to-end window-opening measurement.

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
