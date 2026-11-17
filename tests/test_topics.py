"""Tests the topic titles: reading the lines, when each opens on the timeline, the capitals
and the drawing. Needs neither ffmpeg nor a video."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import topics  # noqa: E402
from common import DavarError  # noqa: E402


class Lines(unittest.TestCase):
    def test_lines_are_read_in_time_order(self):
        found = topics.parse_topics(["12:30 | Second", "", "0:41 | First | GUEST: SOMEONE"])
        self.assertEqual(found, [{"time": 41.0, "headline": "First", "line": "GUEST: SOMEONE"},
                                 {"time": 750.0, "headline": "Second", "line": None}])

    def test_a_line_without_a_headline_or_with_a_bad_time_is_refused(self):
        for bad in (["12:30"], ["12:30 |  "], ["soon | Headline"], ["1:00 | a | b | c"]):
            with self.assertRaises(DavarError, msg=bad):
                topics.parse_topics(bad)

    def test_capitals_the_turkish_way(self):
        self.assertEqual(topics.upper("tuzla'nın imar sorunu"), "TUZLA'NIN İMAR SORUNU")
        self.assertEqual(topics.file_name(3, "Tuzla'nın İmar Sorunu?"), "topic_03_tuzlanin_imar_sorunu.mov")


class Starts(unittest.TestCase):
    def test_a_title_opens_a_few_seconds_into_its_chapter(self):
        self.assertEqual(topics.plan_starts([100.0, 300.0], 8.0), [100.0 + topics.DELAY, 300.0 + topics.DELAY])

    def test_a_title_waits_for_a_name_on_screen(self):
        starts = topics.plan_starts([100.0], 8.0, busy=[(101.0, 107.0)])
        self.assertEqual(starts, [107.0 + topics.GAP])
        self.assertEqual(topics.plan_starts([100.0], 8.0, busy=[(111.0, 117.0)]), [117.0 + topics.GAP],
                         "it would still be on screen when the name comes")

    def test_titles_never_overlap_one_another(self):
        starts = topics.plan_starts([100.0, 102.0], 8.0)
        self.assertGreaterEqual(starts[1], starts[0] + 8.0)

    def test_a_title_that_does_not_fit_before_the_end_is_dropped(self):
        self.assertEqual(topics.plan_starts([95.0], 8.0, total=100.0), [None])


class Drawing(unittest.TestCase):
    def test_the_pieces_are_drawn_and_the_lower_third_opens_and_closes(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is not installed")
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            logo = Path(folder) / "logo.png"
            Image.new("RGB", (200, 50), (238, 39, 46)).save(logo)
            parts, box = topics.layers("PROGRAMME", "A VERY LONG HEADLINE " * 5, "GUEST: SOMEONE", 960, 540, logo)
            self.assertEqual(len(parts), 6)
            first = topics.frame(parts, box, 0.0, 8.0)
            middle = topics.frame(parts, box, 4.0, 8.0)
            last = topics.frame(parts, box, 7.99, 8.0)
            covered = lambda image: sum(image.getchannel("A").histogram()[1:])  # noqa: E731
            self.assertLess(covered(first), covered(middle) / 20, "closed at the start")
            self.assertLess(covered(last), covered(middle) / 5, "closed again at the end")
            text = parts[4].getchannel("A").getbbox()
            self.assertLess(text[2], box[2] - topics.LOGO_ZONE * 960 / 1920, "a long headline shrinks before the logo")


if __name__ == "__main__":
    unittest.main()
