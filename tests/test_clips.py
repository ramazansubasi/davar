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


class Sentences(unittest.TestCase):
    # four sentences: 10-14.5 s, 15-24.5 s, 26-35 s, 36-40 s
    WORDS = [("Bir", 10.0, 10.5), ("cümle.", 14.0, 14.5), ("Sonra", 15.0, 15.5), ("ikinci", 18.0, 18.5),
             ("cümle", 22.0, 22.5), ("geliyor.", 24.0, 24.5), ("Üçüncü", 26.0, 26.5), ("ne", 30.0, 30.5),
             ("dedin?", 34.5, 35.0), ("“Son", 36.0, 36.5), ("söz.”", 39.5, 40.0)]

    def test_a_range_moves_to_whole_sentences(self):
        self.assertEqual(clips.fit_to_sentences(self.WORDS, 17.0, 33.0), (15.0, 35.0),
                         "back to the start of its sentence, on to the end of its sentence")

    def test_a_sentence_ending_in_quotation_marks_counts(self):
        self.assertEqual(clips.fit_to_sentences(self.WORDS, 26.0, 38.0), (26.0, 40.0))

    def test_too_far_from_a_sentence_it_takes_the_next(self):
        self.assertEqual(clips.fit_to_sentences(self.WORDS, 23.0, 33.0)[0], 26.0, "8 s back is too far, 3 s ahead")
        self.assertEqual(clips.fit_to_sentences(self.WORDS, 20.0, 33.0)[0], 20.0, "5 s back and 6 s ahead: it stays")
        self.assertEqual(clips.fit_to_sentences(self.WORDS, 13.0, 33.0)[0], 10.0, "3 s back")

    def test_without_words_nothing_moves(self):
        self.assertEqual(clips.fit_to_sentences([], 17.0, 33.0), (17.0, 33.0))
        self.assertEqual(clips.fit_to_sentences(None, 17.0, 33.0), (17.0, 33.0))


class ManyClips(unittest.TestCase):
    def test_the_names_hold_the_headline(self):
        clip = clips._("Clip {n}")  # in the language of the interface
        self.assertEqual(clips.clip_name(2, 'Hayali emsal: "Tuzla"/otopark?'),
                         clip.format(n=2) + " - Hayali emsal Tuzla otopark.mp4")
        self.assertEqual(clips.clip_name(3, ""), clip.format(n=3) + ".mp4")
        self.assertEqual(clips.clip_name(1, "Akköse: Bankayı soyanla oyları alıp iktidara gidenin farkı yok"),
                         clip.format(n=1) + " - Akköse Bankayı soyanla oyları alıp iktidara gidenin farkı.mp4",
                         "cut between whole words")

    def test_the_candidates_are_made_one_after_the_other(self):
        made = []
        real = clips.make_clip
        clips.make_clip = lambda video, start, end, output=None, **rest: made.append((start, end, output.name, rest)) or {
            "output": output, "start": start, "end": end, "duration": end - start, "subtitles": False}
        try:
            results = clips.make_clips(Path("C:/video/talk.mp4"),
                                       [{"n": 2, "start": 10.0, "end": 40.0, "headline": "First", "lines": ["A", "B"]},
                                        {"n": 5, "start": 60.0, "end": 90.0, "headline": "Second", "lines": []}],
                                       kicker="TUZLA", subtitles=True)
        finally:
            clips.make_clip = real
        self.assertEqual([(s, e, name) for s, e, name, _rest in made],
                         [(10.0, 40.0, clips.clip_name(2, "First")), (60.0, 90.0, clips.clip_name(5, "Second"))])
        self.assertEqual(made[0][3]["headline"], ["A", "B"])
        self.assertEqual(made[1][3]["headline"], ["Second"], "with no lines, the headline")
        self.assertEqual(made[0][3]["kicker"], "TUZLA")
        self.assertIn(clips.clip_name(5, "Second"), clips.report_many(results))


if __name__ == "__main__":
    unittest.main()
