# File Browser

A Windows tray utility for browsing desktop files and folders.

## Launch and pin

Run `tools/create-shortcuts.ps1` from PowerShell. It creates two shortcuts in `launchers/`, using this checkout's `.venv\Scripts\pythonw.exe` so no console window opens.

- **File Browser.lnk**: opens the browser, or asks the already-running instance to open. Right-click this shortcut in File Explorer, choose **Show more options**, then **Pin to taskbar**. You can also copy it to the Desktop.
- **File Browser (Startup).lnk**: starts quietly in the tray. When you want automatic startup, press **Win+R**, enter `shell:startup`, and copy this shortcut into that folder.

The generated shortcuts contain absolute paths. Regenerate them and replace any copied/pinned shortcuts if you move the project or its virtual environment. These are development launchers using Python; a standalone packaged executable can replace them when the app is ready to distribute.

## Global shortcut

**Alt+B** opens the browser from any application while File Browser is running. It uses Windows hotkey registration, not a keyboard hook. Escape closes the browser while leaving the tray app running. Use **Quit** in the tray menu to exit and release Alt+B.

If another app has reserved Alt+B, File Browser reports that the shortcut is unavailable; its tray menu and launcher still work.

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
