"""Tests checking the joins of a cut and marking them on the timeline."""

import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import roughcut  # noqa: E402

FPS = 25
INFO = {"fps": Fraction(FPS), "frames": 250, "duration": 10.0, "width": 1920, "height": 1080,
        "audio_channels": 2, "audio_rate": 48000}


def levels(loud):
    """Levels for 10 s: quiet (-60 dB) except the (start, end) seconds in `loud` (-15 dB)."""
    db = np.full(int(10 / roughcut.WINDOW), -60.0)
    for start, end in loud:
        db[int(start / roughcut.WINDOW):int(end / roughcut.WINDOW)] = -15.0
    return db


class Joins(unittest.TestCase):
    WORDS = [("bir", 1.0, 1.4), ("kelime", 1.6, 2.4), ("daha", 2.6, 3.0)]

    def test_a_cut_through_a_word_with_sound_is_listed(self):
        db = levels([(1.0, 1.4), (1.6, 2.4), (2.6, 3.0)])
        cuts = [(int(1.8 * FPS), int(2.6 * FPS))]  # cuts away the second half of "kelime"
        self.assertEqual(roughcut.joins_to_check(cuts, self.WORDS, db, -15.0, FPS, 250),
                         [(int(2.6 * FPS), "kelime")])

    def test_a_cut_in_a_silence_is_not(self):
        db = levels([(1.0, 1.4), (1.6, 2.4), (2.6, 3.0)])
        cuts = [(int(1.42 * FPS), int(1.58 * FPS)), (int(3.2 * FPS), int(4 * FPS))]
        self.assertEqual(roughcut.joins_to_check(cuts, self.WORDS, db, -15.0, FPS, 250), [])

    def test_a_whole_word_cut_away_is_not(self):
        db = levels([(1.0, 1.4), (1.6, 2.4), (2.6, 3.0)])
        cuts = [(int(1.6 * FPS), int(2.6 * FPS))]
        self.assertEqual(roughcut.joins_to_check(cuts, self.WORDS, db, -15.0, FPS, 250), [])

    def test_a_word_cut_through_where_it_is_quiet_is_not(self):
        db = levels([(1.0, 1.4), (1.6, 1.8)])  # the transcript's word is longer than its sound
        cuts = [(int(1.9 * FPS), int(2.6 * FPS))]
        self.assertEqual(roughcut.joins_to_check(cuts, self.WORDS, db, -15.0, FPS, 250), [])

    def test_no_check_at_the_start_and_end_of_the_programme(self):
        db = levels([(0, 10)])
        cuts = [(0, int(1.8 * FPS)), (int(1.8 * FPS) + 10, 250)]
        found = roughcut.joins_to_check(cuts, self.WORDS, db, -15.0, FPS, 250)
        self.assertEqual(found, [])


class Markers(unittest.TestCase):
    def test_markers_are_written_on_their_clip_and_read_back(self):
        parts = [(0, 50), (70, 120), (150, 250)]
        with tempfile.TemporaryDirectory() as folder:
            video, timeline = Path(folder) / "talk.mp4", Path(folder) / "talk_cut.fcpxml"
            roughcut.write_fcpxml(timeline, video, INFO, parts, markers=[(150, "listen"), (70, "here & there")])
            text = timeline.read_text(encoding="utf-8")
            self.assertEqual(text.count("<marker"), 2)
            self.assertIn('value="here &amp; there"', text)
            self.assertEqual(roughcut.read_timeline(timeline, video, INFO)["markers"],
                             [(70, "here & there"), (150, "listen")])

    def test_a_marker_on_a_frame_cut_away_goes_to_the_next_clip(self):
        with tempfile.TemporaryDirectory() as folder:
            video, timeline = Path(folder) / "talk.mp4", Path(folder) / "talk_cut.fcpxml"
            roughcut.write_fcpxml(timeline, video, INFO, [(0, 50), (70, 120)], markers=[(60, "x"), (200, "gone")])
            self.assertEqual(roughcut.read_timeline(timeline, video, INFO)["markers"], [(70, "x")])


if __name__ == "__main__":
    unittest.main()
