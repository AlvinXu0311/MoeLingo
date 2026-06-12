"""Convenience launcher: `python run.py`."""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "moelingo"))
from app import App

if __name__ == "__main__":
    App().run()
