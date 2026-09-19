"""Windowless entry point used by the Windows launcher shortcuts."""
import sys

from src.app import main


if __name__ == "__main__":
    sys.exit(main())
