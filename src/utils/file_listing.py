import configparser
import os
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QFileInfo


@dataclass
class FileEntry:
    path: Path
    kinds: set[str]
    modified: float = 0
    size: int = 0


def read_shortcut(file):
    """Read InternetShortcut metadata without opening its target."""
    data = file.read_bytes()
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = data.decode("utf-16")
    else:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = data.decode("mbcs" if os.name == "nt" else "cp1252")
    shortcut = configparser.ConfigParser(interpolation=None, strict=False)
    shortcut.read_string(text)
    return shortcut


def is_game_target(target):
    target = target.lower().replace("\\", "/")
    return target.startswith(("steam://rungameid/", "steam://run/",
                              "com.epicgames.launcher://apps/", "uplay://launch/",
                              "battlenet://")) or "/steamapps/common/" in target


def describe_file(file):
    file = Path(file)
    if file.is_dir():
        kinds = {"folders"}
    else:
        extension = file.suffix.lower()
        kinds = {"ext:" + extension} if extension else {"no_extension"}
        if extension in (".exe", ".com", ".bat", ".cmd", ".msi"):
            kinds.add("programs")
        if extension in (".lnk", ".url"):
            kinds.add("shortcuts")
            try:
                if extension == ".url":
                    shortcut = read_shortcut(file)
                    target = shortcut.get("InternetShortcut", "URL", fallback="")
                else:
                    target = QFileInfo(str(file)).symLinkTarget()
                    if Path(target).suffix.lower() in (".exe", ".com", ".bat", ".cmd"):
                        kinds.add("programs")
                if is_game_target(target):
                    kinds.add("games")
            except (OSError, UnicodeError, ValueError, configparser.Error):
                pass
        elif is_game_target(str(file)) and extension == ".exe":
            kinds.add("games")
    try:
        stat = file.stat()
        return FileEntry(file, kinds, stat.st_mtime, stat.st_size if "folders" not in kinds else 0)
    except OSError:
        return FileEntry(file, kinds)


def filter_options(entries):
    counts = {}
    for entry in entries:
        for kind in entry.kinds:
            counts[kind] = counts.get(kind, 0) + 1
    options = [("All types", "all")]
    for kind, label in (("folders", "Folders"), ("programs", "Programs"),
                        ("games", "Games"), ("shortcuts", "Shortcuts"),
                        ("no_extension", "No extension")):
        if kind in counts:
            options.append((f"{label} ({counts[kind]})", kind))
    for kind in sorted(counts):
        if kind.startswith("ext:"):
            options.append((f"{kind[4:]} ({counts[kind]})", kind))
    return options


def visible_entries(entries, query="", kind="all", sort="name"):
    query = query.strip().casefold()
    entries = [entry for entry in entries
               if query in entry.path.name.casefold() and (kind == "all" or kind in entry.kinds)]
    # Name breaks ties so refreshes don't shuffle equally-sized files.
    entries.sort(key=lambda entry: (entry.path.name.casefold(), str(entry.path)))
    if sort == "name_desc":
        entries.reverse()
    elif sort == "modified":
        entries.sort(key=lambda entry: entry.modified, reverse=True)
    elif sort == "size":
        entries.sort(key=lambda entry: entry.size, reverse=True)
    elif sort == "type":
        entries.sort(key=lambda entry: ("folders" not in entry.kinds, entry.path.suffix.lower()))
    return entries
