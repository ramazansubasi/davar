"""Tests the views of the Rough Cut review list. Loads the window's code without opening a window."""

import importlib.machinery
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
loader = importlib.machinery.SourceFileLoader("davar_gui_for_tests", str(ROOT / "davar_gui.pyw"))
spec = importlib.util.spec_from_loader("davar_gui_for_tests", loader)
gui = importlib.util.module_from_spec(spec)
loader.exec_module(gui)


class Views(unittest.TestCase):
    CANDIDATES = [
        {"kind": "alone", "confidence": "high", "selected": True},
        {"kind": "before_word", "confidence": "medium", "selected": True},
        {"kind": "text_only", "confidence": "low", "selected": False},
        {"kind": "unknown", "confidence": "low", "selected": False},
        {"kind": "noise", "confidence": "high", "selected": True},
    ]

    def shown(self, view):
        return [n for n, c in enumerate(self.CANDIDATES) if gui.shown_in(view, c)]

    def test_each_view_shows_its_own(self):
        self.assertEqual(self.shown("all"), [0, 1, 2, 3, 4])
        self.assertEqual(self.shown("ticked"), [0, 1, 4])
        self.assertEqual(self.shown("unticked"), [2, 3], "what Davar will not cut, to be looked through one by one")
        self.assertEqual(self.shown("uncertain"), [1, 2, 3])
        self.assertEqual(self.shown("sounds"), [3, 4], "coughs and sounds no word was written for")


if __name__ == "__main__":
    unittest.main()
