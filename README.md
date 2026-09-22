# File Browser

A Windows tray utility for browsing desktop files and folders.

## Desktop locations and file errors

The Desktop view combines the configured user Desktop and Public Desktop. Windows Known Folders resolves local, OneDrive, relocated, and network-redirected paths; the app does not guess which OneDrive account owns the Desktop. User items take precedence when both locations contain the same filename. Each item retains its real path for opening and **Open file location**.

If one Desktop location cannot be read, readable locations remain available and the status tooltip shows the errors. A folder that cannot be read at all replaces the list with the reason and a **Try again** button, and is retried on the next open. Online-only cloud shortcuts use a generic icon without reading their contents to trigger a download; opening them lets Windows handle availability. Hidden items such as `desktop.ini` are left out, the way Explorer leaves them out. Virtual Shell objects such as Recycle Bin are not filesystem entries and are not included.

File launches are attempted once. Failures appear in the browser status, a tray notification, and the log. The thread executor also treats `OSError` and its subclasses as non-retryable; other tasks retain their configurable retries.

## Looking like Windows

The panel follows the Windows 11 type ramp (Segoe UI Variable, 14px body, 12px captions, 20px
semibold headings), Fluent neutrals, and 4px corners on controls with 8px on flyouts and cards.
Buttons are glyphs from Segoe Fluent Icons, the icon font Windows draws Explorer with.

Accent colour comes from the user's own Windows accent rather than a fixed blue. Windows stores
seven shades of it; fills use the shade Windows itself picks, while text and focus rings step
through the shades until one clears a 3:1 contrast ratio against the surface, which matters when
someone's accent is very dark or very light.

Qt already rounds popup corners on Windows 11, so `utils/window_effects.py` covers what it does
not: the frame colour, the dark-frame flag, and a backdrop request that asks for acrylic only when
the user has transparency effects switched on, since Windows drops acrylic from its own flyouts
when they are off. Each `DwmSetWindowAttribute` call returns its HRESULT so a wrong attribute is a
runtime answer rather than a silent no-op.

## Logo

The logo lives in `src/assets/logo`. `fb_icon.png` is the master; the other two files are built
from it by `tools/build-icon.py`, so run that again after changing the master. `fb_icon.ico` is the
square, multi-size Windows icon, with the mark letterboxed on a transparent square at every size
Windows draws, from 16px in the tray to 256px tiles; it is the tray icon, the app and installer
icon, and the icon on the launcher shortcuts. `fb_icon_header.png` is the mark at its own
proportions and is what the **About** card at the end of Settings shows, with the version from
`src/version.py`, which the build script and installer also read.

## Motion

Every move in the app follows the Windows 11 motion language, in `ui/motion.py`: a few fixed
durations (100, 167 and 250 ms) and three curves, decelerating for anything arriving, accelerating
for anything leaving, and the standard curve for anything moving while on screen. The panel slides in
from the edge it is docked against and fades up, the way a tray flyout opens, and leaves the same
way; the picture that slides out is a snapshot, so the real window is already gone, focus has moved
on, and the click that dismissed it lands where it should. Settings drills in over the files from the
right and back out again; navigating between folders drills the list in or out in the direction you
went; the filter flyout drops from its button; and a docking change glides the open panel to its new
corner. Turning off **Animation effects** in Windows makes all of it snap instead, as Windows does.

## Launch and pin

Run `tools/create-shortcuts.ps1` from PowerShell. It creates two shortcuts in `launchers/`, using this checkout's `.venv\Scripts\pythonw.exe` so no console window opens.

- **File Browser.lnk**: starts the app in the tray without opening the panel, and says so once in a tray notification. Running it again while the app is already running opens the panel, so a pinned copy works as an open button. Right-click this shortcut in File Explorer, choose **Show more options**, then **Pin to taskbar**. You can also copy it to the Desktop.
- **File Browser (Startup).lnk**: starts quietly in the tray. You can use **Settings → Start with Windows** instead of copying this shortcut into the Startup folder.

The generated shortcuts contain absolute paths. Regenerate them and replace any copied/pinned shortcuts if you move the project or its virtual environment. These are development launchers using Python; a standalone packaged executable can replace them when the app is ready to distribute.

## Global shortcut

**Alt+B** opens the browser from any application while File Browser is running, and closes it again while it is open; a click on the tray icon does the same. Change it under **Settings → Open browser shortcut**, or use **Reset** to return to Alt+B. Record one combination containing Ctrl or Alt, optionally Shift, plus a letter, number, or function key other than F12. A registered combination reaches this app and nothing else, so combinations Windows and other apps rely on, such as Ctrl+C, Ctrl+V, and Alt+F4, are refused.

It uses [Windows hotkey registration](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registerhotkey). If a new combination is unavailable, the app reports the conflict and keeps your previous shortcut active. If the saved shortcut is unavailable when the app starts, the tray menu and launcher still work. Use **Quit** in the tray menu to exit and release the shortcut.

## Search, filters, and sorting

- **Filter** opens search, type filtering, and sorting in a dropdown overlay; **Ctrl+F** opens it with search focused, and **Tab** moves on to the Type and Sort boxes. Search matches filenames in the current folder, including their extensions, without scanning subfolders. Typing settles briefly before the list is rebuilt, so a long folder does not stutter between keystrokes. **Enter**, **Done**, **Escape**, or a click outside dismisses the overlay and keeps the results. Outside the overlay, **Escape** clears a search first, then closes the browser.
- A dot on **Filter** marks an active search, type filter, or non-default sort. **Clear filters** resets search and type without changing your sort.
- Typing while the list has focus jumps to the next name starting with those letters, the way Explorer does; the same letter again steps through the names that start with it. Search stays **Ctrl+F**.
- The type dropdown contains only categories and extensions detected in the current folder, with counts. Search and type filtering work together. Empty results say **No matching files**.
- Programs include executable files, installers, batch files, and Windows shortcuts targeting executables. Games are detected from known launcher URLs (Steam, Epic, Ubisoft, Battle.net) or executable targets under `steamapps/common`; unrecognized shortcuts remain under Shortcuts and their extension.
- Sort by name in either direction, newest first, largest first, or type. The sort choice is remembered. Folder sizes are not calculated recursively.
- Refresh preserves the query and scroll position. Moving to another folder clears the query; a type filter stays selected if that category exists there.

## Scrolling and refresh performance

Mouse-wheel scrolling is animated in the file list, settings, and combo dropdowns. Touchpad pixel scrolling remains direct. Scrollbar dragging, keyboard navigation, and restored history positions cancel pending animation. Scrolling over a closed combo scrolls the page it sits on instead of changing its value.

Unchanged reopens reuse the loaded list without scanning files or extracting icons. Filesystem changes are debounced; hidden panels refresh on their next open. A 30-second fallback checks for changes missed by a watcher, including on shares. Metadata, icons, and row widgets are reused whenever a file's timestamps, size, and attributes are unchanged, so filtering, sorting, extension display, and back/forward do not re-read the filesystem. Icons are kept as drawn pixmaps: asking Windows for a `.lnk` or `.exe` icon again costs milliseconds each time. Both caches span folders and are capped at 2000 entries, so a folder larger than that keeps only itself. **F5/Ctrl+R** forces metadata and icon refresh, including a shortcut's externally changed icon.

A hidden panel drops its directory watches, because those handles stop Explorer renaming or moving any folder above the one last opened. On its next open the folders themselves are checked, and the list is only rebuilt if one of them changed. A cold folder is read after the panel is on screen rather than before it.

Rows appear before their icons are read. Every row starts with the generic file or folder icon,
which costs one shell call for the whole list, and the real icons are read on a worker through the
thread executor, a batch at a time, and painted in as each batch lands; the list is scrollable and
clickable throughout. An icon Windows has to read out of a `.lnk` or `.exe` costs milliseconds each,
and one on a network share can take seconds, which is why the UI thread never asks for one.

Initial loads and actual rescans still perform filesystem I/O and depend on disk/network responsiveness. Measured locally with the window hidden, so paint and layout are excluded: a 74-item Desktop is listed in about 380 ms with its icons landing over the next 730 ms, and reopens unchanged in 0 ms; re-rendering it for a search keystroke, a star, or an extension change takes 2-6 ms; back and forward between two read folders take about 20 ms each. A 4878-item folder is listed in about 1.5 s, rescans unchanged in 84 ms, and re-renders in 30-380 ms.

## Opening, dragging, and file actions

Clicking a row opens it on release, so a press that turns into a drag never launches anything. Drag
a row onto any other window to hand it the file, the way a drag out of Explorer does; the drop
target decides whether that copies, moves, or links.

Right-click a row for **Open**, **Open file location**, **Copy**, **Delete**, favorites, and
**Properties**. **Copy** puts the file itself on the clipboard, so Explorer and mail clients paste
the file rather than its path. **Delete** sends the item to the Recycle Bin through Windows, which
shows its own confirmation if that is switched on and leaves the item recoverable either way.
**Properties** opens the Windows properties dialog. **Ctrl+C**, **Delete**, and **Alt+Enter** do the
same to the row that has focus. A middle click shows an item in File Explorer: a folder itself, a
file in the folder it lives in.

## Folder hover

**Settings → Folder hover** chooses what resting the pointer on a folder row does. **Nothing**, the
default, leaves the row alone until it is clicked. **Cascade contents** fans the folder out beside the
panel in a menu, the way the taskbar's toolbar menus do: subfolders open further menus on hover,
folders come first, and a file opens when clicked. Clicking a folder in the panel or in a menu still
opens it in the panel, and a right-click anywhere in the cascade shows that item's own menu. Folder
rows keep their path tooltip to themselves while this is on, so it does not compete with the menu.
From the keyboard, **Right** on a focused folder row fans it out whatever the hover setting, the
arrows then move through the menu, and **Left** at its first level hands the keyboard back to the row.

The menu opens after the Windows menu delay, and only pointer movement counts as resting, so a folder
that lands under a still pointer after a scroll or a click does not fan out. Scrolling the list cancels a
pending menu, closes an open one, and asks for a real move before resting counts again, and a wheel over
the panel while a menu is open scrolls the list rather than the menu. Resting on another folder row moves
the cascade there, resting on a file row closes it, and a click on any row reaches the row.
Nothing in the cascade waits on the disk or the shell on the UI thread. A folder is read on a worker
through the thread executor as soon as the pointer rests on its row or item, so a level is usually
ready before it is due to open; a slow folder shows **Loading…** until its items arrive. Icons are read
the same way, a few at a time, and painted in behind the open menu. Listings use `os.scandir`, which
Windows answers from the directory itself instead of a round trip per file.

Every level opens on the same side, away from the screen edge the panel sits against, and only crosses
over when a menu would otherwise leave the screen. A tall menu scrolls rather than spreading into columns,
and long folders stop at 250 items with a **Show all** entry that opens the folder in the panel. Icons fill
in behind the open menu the way the panel's rows do.

## Favorites and navigation

Click a row's star or right-click **Add to favorites**. Favorites are remembered and pinned above other matching items in their folder. The **Favorites** menu opens saved files and folders from anywhere and includes a removal menu for moved or deleted items.

Click breadcrumb segments to navigate to ancestors; **…** opens earlier segments when the path is too long. **Desktop** or **Alt+Home** returns to the Windows Desktop location, including redirected desktops. Opening the panel starts at the Desktop, the way the shell's own chevron menus do, and history is dropped with it, unless **Settings → Reopen where I left off** is on: then the panel comes back to the last folder with its history, across restarts too. Alt+Left/Right, mouse side buttons, and Backspace navigate history; Alt+Up opens the parent. Back/Forward restore scroll positions. F5 or Ctrl+R refreshes.

## Start with Windows

Enable **Settings → Start with Windows** to launch quietly in the tray when you sign in. It manages only the `FileBrowserWidget` value in the current user's [Windows Run registry key](https://learn.microsoft.com/en-us/windows/win32/setupapi/run-and-runonce-registry-keys); no administrator access is needed. Turning it off removes that entry. If you previously copied a launcher into `shell:startup`, remove that copy separately.

Startup uses absolute paths. Toggle the setting off and on after moving this checkout or virtual environment. Windows may delay startup apps, and disabling this app under Task Manager's Startup tab or Startup Apps settings is recorded separately from the Run entry: the checkbox reads that veto as off, and turning it back on clears it.

## Command line

From the project directory:

```powershell
.\.venv\Scripts\python.exe -m src.app
.\.venv\Scripts\python.exe -m src.app --background
```

A launch starts the app in the tray; the panel opens from the tray icon, the global shortcut, or a second launch. `--background` also skips the first-run notification and never asks a running instance to open, which is what Windows Startup uses. There is one running instance per Windows user.

## Tests

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests
```
