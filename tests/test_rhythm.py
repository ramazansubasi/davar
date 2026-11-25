"""Tests measuring the rhythm of finished episodes."""

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import rhythm  # noqa: E402
from common import WINDOW, DavarError  # noqa: E402


def levels(pattern):
    """Levels from (seconds, loud) pairs: -15 dB when loud, -60 dB when quiet."""
    return np.concatenate([np.full(int(round(s / WINDOW)), -15.0 if loud else -60.0) for s, loud in pattern])


class Pauses(unittest.TestCase):
    def test_only_pauses_between_two_sounds_count(self):
        db = levels([(1.0, False), (1.0, True), (0.3, False), (1.0, True), (0.03, False), (1.0, True),
                     (2.0, False)])
        self.assertEqual([round(p, 2) for p in rhythm.pauses(db, -40)], [0.3],
                         "the silence at the start and the end, and a dip of 30 ms, are not pauses")

    def test_no_pause_in_silence(self):
        self.assertEqual(len(rhythm.pauses(np.full(100, -60.0), -40)), 0)


class Settings(unittest.TestCase):
    def test_a_cut_pause_keeps_the_usual_length_two_thirds_after_the_speech(self):
        found = [0.1] * 60 + [0.35] * 40 + [0.6] * 10
        s = rhythm.settings(found)
        self.assertAlmostEqual(s["phrase"], 0.35, "the median of the pauses between phrases")
        self.assertEqual((s["pad_before"], s["pad_after"]), (0.1, 0.2))
        self.assertEqual(s["min_silence"], 0.6, "95 in 100 pauses are shorter")

    def test_the_shortest_silence_cut_is_longer_than_what_is_kept(self):
        s = rhythm.settings([0.25] * 50)
        self.assertGreater(s["min_silence"], s["pad_before"] + s["pad_after"])

    def test_too_few_pauses_are_refused(self):
        with self.assertRaises(DavarError):
            rhythm.settings([0.3] * 5)


if __name__ == "__main__":
    unittest.main()
