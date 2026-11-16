"""Tests finding throat clearing with the sound model, without the model: the classifier that
comes with Davar, how places are pinned and widened, and how they join the candidates."""

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import roughcut  # noqa: E402
import sounds  # noqa: E402
from common import DavarError  # noqa: E402


class Classifier(unittest.TestCase):
    def test_the_classifier_comes_with_davar(self):
        weights, bias = sounds.classifier()
        self.assertEqual(weights.shape, (1024,), "one weight for each number of a YAMNet description")
        self.assertTrue(np.isfinite(weights).all() and np.isfinite(bias))
        scores = sounds.score(np.zeros((2, 1024), np.float32), weights, bias)
        self.assertTrue(((scores > 0) & (scores < 1)).all())


class Places(unittest.TestCase):
    def descriptions_every(self, seconds, step=0.12):
        return np.arange(0, seconds, step)

    def test_a_sound_is_pinned_where_the_strong_descriptions_overlap(self):
        starts = self.descriptions_every(30)
        scores = np.full(len(starts), 0.01)
        sound = 12.30  # each description hears a second; those that hear the sound score high
        scores[(starts <= sound) & (starts + sounds.LISTEN >= sound + 0.2)] = 0.99
        (start, end, best), = sounds.places(starts, scores, 1)
        self.assertLessEqual(start, sound + 0.05)
        self.assertGreaterEqual(end, sound + 0.15)
        self.assertLess(end - start, 0.5, "pinned much closer than the second each description hears")
        self.assertEqual(best, 0.99)

    def test_places_are_apart_and_trimmed_parts_are_skipped(self):
        starts = self.descriptions_every(60)
        scores = np.full(len(starts), 0.01)
        for moment, value in ((10.0, 0.9), (10.8, 0.95), (30.0, 0.8), (50.0, 0.7)):
            scores[np.argmin(np.abs(starts + sounds.LISTEN / 2 - moment))] = value
        found = sounds.places(starts, scores, 5, usable=lambda moment: moment < 45)
        self.assertEqual([round(start) for start, _end, _best in found], [10, 30],
                         "10.0 and 10.8 are one place; 50 is trimmed away")

    def test_a_place_grows_to_the_whole_sound_but_not_into_words(self):
        db = np.full(1000, -70.0)
        db[300:345] = -20  # a sound from 3.00 to 3.45 s
        db[365:420] = -25  # speech goes on after a short pause
        db[310:315] = -60  # a dip too short to end the sound
        words = [["before", 2.0, 2.9], ["uh", 3.0, 3.3], ["after", 3.65, 4.2]]
        start, end = sounds.widen(3.1, 3.2, db, -48, words, lambda text: text == "uh")
        self.assertEqual((start, end), (3.0, 3.45), "out to the silence on both sides, across the short dip")
        start, end = sounds.widen(3.1, 3.2, db, -48, [["after", 3.4, 4.2]])
        self.assertEqual(end, 3.4, "never into a word")

    def test_a_place_never_reaches_far(self):
        db = np.full(1000, -20.0)  # loud everywhere
        start, end = sounds.widen(5.0, 5.1, db, -48)
        self.assertEqual((start, end), (round(5.0 - sounds.REACH, 2), round(5.1 + sounds.REACH, 2)))


class Candidates(unittest.TestCase):
    DB = np.full(2000, -20.0)

    def build(self, throats, noises=(), hesitations=()):
        words = [["Hello", 0.5, 1.0], ["there.", 1.0, 1.5], ["Next", 6.0, 6.5]]
        return roughcut.build_candidates(hesitations, self.DB, words, language="en", noises=noises, throats=throats)

    def test_a_new_place_arrives_unticked(self):
        found = self.build([(2.0, 2.4, 0.99)])
        self.assertEqual([(c["kind"], c["selected"], c["confidence"]) for c in found], [("throat", False, "medium")])
        self.assertIn("there.", found[0]["context"], "the words around it are shown, to help the listener")

    def test_a_sound_already_listed_gets_the_new_name(self):
        found = self.build([(3.0, 3.4, 0.5)], noises=[(3.1, 3.5, 0.9, False)])
        self.assertEqual(len(found), 1)
        self.assertEqual((found[0]["kind"], found[0]["start"], found[0]["end"]), ("throat", 3.0, 3.5))

    def test_only_what_is_not_cut_already_is_offered(self):
        words = [["Hello", 0.5, 1.0], ["uh", 3.0, 3.2], ["Next", 6.0, 6.5]]
        found = roughcut.build_candidates([(3.0, 3.2, "alone")], self.DB, words, language="en",
                                          throats=[(3.0, 3.6, 0.99)])
        self.assertEqual([(c["kind"], c["selected"], c["start"], c["end"]) for c in found],
                         [("alone", True, 3.0, 3.2), ("throat", False, 3.2, 3.6)],
                         "the uh is cut as before; the rest of the sound is offered to the listener")


class Model(unittest.TestCase):
    def test_a_model_already_there_is_used_as_it_is(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "yamnet.onnx"
            path.write_bytes(b"x" * 10)
            original, size = sounds.model_path, sounds.MODEL_SIZE
            sounds.model_path, sounds.MODEL_SIZE = (lambda: path), 10
            try:
                self.assertEqual(sounds.ensure_model(), path, "no download when the file is there")
            finally:
                sounds.model_path, sounds.MODEL_SIZE = original, size

    def test_a_failed_download_leaves_nothing_behind(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "models" / "yamnet.onnx"
            original, url = sounds.model_path, sounds.MODEL_URL
            sounds.model_path, sounds.MODEL_URL = (lambda: path), "http://127.0.0.1:9/none.onnx"
            try:
                with self.assertRaises(DavarError):
                    sounds.ensure_model()
            finally:
                sounds.model_path, sounds.MODEL_URL = original, url
            self.assertEqual(list(path.parent.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
