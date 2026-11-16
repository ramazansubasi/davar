"""Tests what a social clip keeps of its range when the Rough Cut's cuts are applied.
Needs neither ffmpeg nor a video."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import clips  # noqa: E402
import roughcut  # noqa: E402


class KeptInRange(unittest.TestCase):
    # at 30 frames per second the Rough Cut keeps 0-10 s, 12-20 s and 25-40 s
    PARTS = [(0, 300), (360, 600), (750, 1200)]

    def test_the_range_keeps_what_the_cut_keeps(self):
        self.assertEqual(clips.kept_in_range(self.PARTS, 30.0, 8.0, 30.0), [(0, 60), (120, 360), (510, 660)],
                         "counted in frames from the start of the range")

    def test_a_range_inside_one_part_is_kept_whole(self):
        self.assertEqual(clips.kept_in_range(self.PARTS, 30.0, 26.0, 30.0), [(0, 120)])

    def test_a_range_that_was_cut_away_keeps_nothing(self):
        self.assertEqual(clips.kept_in_range(self.PARTS, 30.0, 20.5, 24.5), [])

    def test_slivers_are_dropped(self):
        self.assertEqual(clips.kept_in_range(self.PARTS, 30.0, 9.95, 15.0), [(62, 152)],
                         "the two frames left before 10 s are dropped")

    def test_subtitles_follow_the_pieces(self):
        pieces = clips.kept_in_range(self.PARTS, 30.0, 8.0, 30.0)
        words = [("one", 9.0 - 8.0, 9.5 - 8.0), ("cut", 11.0 - 8.0, 11.5 - 8.0), ("two", 13.0 - 8.0, 13.5 - 8.0)]
        moved = roughcut.timeline_words(words, pieces, 30.0)
        self.assertEqual([(w[0], w[1]) for w in moved], [("one", 1.0), ("two", 3.0)],
                         "the word that was cut away is gone; the next follows two seconds earlier")


if __name__ == "__main__":
    unittest.main()
