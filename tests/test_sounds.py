"""Tests finding throat clearing with the sound model, without the model: the classifier that
comes with Davar, how places are pinned and cut out, and how they join the candidates."""

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

    def speech_with_a_throat_cleared(self):
        """Six seconds: speech, a throat cleared from 3.0 to 3.38 s glued to it, speech again.
        The samples of the throat clearing are 0.9, the rest 0.3, so a stand-in model can hear it."""
        samples = np.full(6 * 16000, 0.3, np.float32)
        samples[int(3.0 * 16000):int(3.38 * 16000)] = 0.9
        db = np.full(600, -20.0)
        db[300:340] = -15.0
        for dip in (300, 340):  # the level drops briefly where one sound gives way to the other
            db[dip - 2:dip + 2] = -40.0
        db[100:120] = db[450:470] = -40.0  # and between syllables
        return samples, db

    def test_the_dips_of_the_level_are_where_sound_may_be_cut(self):
        _samples, db = self.speech_with_a_throat_cleared()
        found = sounds.edges(db, -48, 2.2, 3.8)
        self.assertIn(2.98, [round(e, 2) for e in found])
        self.assertIn(3.38, [round(e, 2) for e in found])

    def test_the_shortest_stretch_that_takes_the_throat_clearing_away_is_cut(self):
        samples, db = self.speech_with_a_throat_cleared()
        hears = lambda audio: 0.99 if (audio > 0.8).any() else 0.05
        start, end = sounds.narrow(samples, db, -48, 3.1, 3.2, hears)
        self.assertAlmostEqual(start, 2.98, delta=0.03)
        self.assertAlmostEqual(end, 3.38, delta=0.03)
        self.assertLess(end - start, 0.5, "none of the speech around it")

    def test_a_place_that_cannot_be_cut_out_cleanly_is_dropped(self):
        samples, db = self.speech_with_a_throat_cleared()
        self.assertIsNone(sounds.narrow(samples, db, -48, 3.1, 3.2, lambda audio: 0.9))


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
