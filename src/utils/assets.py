"""Assets come from the source tree while developing, and from the Qt resource once frozen."""
from pathlib import Path

from PyQt6.QtCore import QFile, QIODevice

# Importing the compiled resource registers :/assets for the whole process.
from src.assets import resources_rc  # noqa: F401

ASSETS = Path(__file__).resolve().parents[1] / "assets"


def asset(name):
    """A path Qt can load, whichever of the two places the file lives in."""
    path = ASSETS / name
    return path.as_posix() if path.is_file() else f":/assets/{name}"


def read_asset(name):
    path = ASSETS / name
    if path.is_file():
        return path.read_text(encoding="utf-8")
    stream = QFile(f":/assets/{name}")
    if not stream.open(QIODevice.OpenModeFlag.ReadOnly):
        raise FileNotFoundError(f"{name} is missing from the source tree and the bundle.")
    try:
        return bytes(stream.readAll()).decode("utf-8")
    finally:
        stream.close()
