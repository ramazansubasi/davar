"""Tests the computational core with synthetic audio. Needs neither ffmpeg nor a video.

    python -m unittest discover tests
"""

import sys
import unittest
from fractions import Fraction
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import audio  # noqa: E402
import roughcut  # noqa: E402
import transcript  # noqa: E402
from common import SAMPLE_RATE, WINDOW  # noqa: E402


def tone(seconds, pitch, formant, rng, level=0.3, rate=SAMPLE_RATE):
    """A voiced sound with the given pitch and timbre (harmonics strongest around `formant`)."""
    t = np.arange(int(seconds * rate)) / rate
    x = np.zeros(len(t))
    for h in range(1, 25):
        f = pitch * h
        if f > rate / 2 - 200:
            break
        x += np.exp(-((f - formant) / 500.0) ** 2) * np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28))
    return (level * x / (np.abs(x).max() + 1e-9)).astype(np.float32)


def speech(seconds, rng, rate=SAMPLE_RATE):
    """Imitates speech: short syllables whose pitch and timbre keep changing."""
    parts, total = [], 0.0
    while total < seconds:
        d = rng.uniform(0.07, 0.13)
        syllable = tone(d, rng.uniform(100, 220), rng.uniform(400, 2600), rng, rng.uniform(0.15, 0.35), rate)
        syllable *= np.hanning(len(syllable)) ** 0.3
        parts += [syllable, np.zeros(int(rng.uniform(0.0, 0.02) * rate), np.float32)]
        total += d + 0.01
    return np.concatenate(parts)[: int(seconds * rate)]


def quiet(seconds, rng, rate=SAMPLE_RATE):
    return rng.normal(0, 0.0005, int(seconds * rate)).astype(np.float32)


def levels(x):
    step = int(SAMPLE_RATE * WINDOW)
    n = len(x) // step
    return 20 * np.log10(np.sqrt(np.mean(x[: n * step].reshape(n, step) ** 2, axis=1)) + 1e-10)


class Silence(unittest.TestCase):
    def test_silences_are_found_and_padding_is_kept(self):
        rng = np.random.default_rng(1)
        # 0-3 speech | 3-4.5 silent | 4.5-8 speech | 8-8.3 short silence | 8.3-10 speech
        x = np.concatenate((speech(3, rng), quiet(1.5, rng), speech(3.5, rng), quiet(0.3, rng), speech(1.7, rng)))
        db = levels(x)
        threshold, floor, top = roughcut.auto_threshold(db)
        self.assertLess(floor, -55)
        self.assertGreater(top, -25)
        intervals = roughcut.silent_intervals(db, threshold, 0.5)
        self.assertEqual(len(intervals), 1, "the 0.3 second silence must not be cut")
        start, end = intervals[0][:2]
        self.assertAlmostEqual(start, 3.0, delta=0.06)
        self.assertAlmostEqual(end, 4.5, delta=0.06)

        info = {"fps": Fraction(30), "duration": len(x) / SAMPLE_RATE, "frames": int(len(x) / SAMPLE_RATE * 30)}
        cuts = roughcut.compute_cuts(intervals, info, pad_before=0.10, pad_after=0.15)
        self.assertEqual(len(cuts), 1)
        self.assertAlmostEqual(cuts[0][0] / 30, 3.15, delta=0.08)  # padding after the word
        self.assertAlmostEqual(cuts[0][1] / 30, 4.40, delta=0.08)  # padding before the word
        parts = roughcut.remaining_parts(cuts, info["frames"])
        self.assertEqual(parts[0][0], 0)
        self.assertEqual(parts[-1][1], info["frames"])


class Hesitation(unittest.TestCase):
    def find(self, x, shortest=0.30):
        db = levels(x)
        threshold = roughcut.auto_threshold(db)[0]
        return roughcut.find_hesitations(roughcut.voice_features(x), threshold, shortest)

    def test_hesitation_standing_alone(self):
        rng = np.random.default_rng(2)
        x = np.concatenate((speech(3, rng), quiet(0.4, rng), tone(0.7, 120, 600, rng), quiet(0.4, rng), speech(3, rng)))
        found = self.find(x)
        self.assertEqual([f[2] for f in found], ["alone"])
        self.assertAlmostEqual(found[0][0], 3.4, delta=0.08)
        self.assertAlmostEqual(found[0][1], 4.1, delta=0.08)

    def test_hesitation_running_into_a_word(self):
        rng = np.random.default_rng(3)
        x = np.concatenate((speech(3, rng), quiet(0.4, rng), tone(0.6, 180, 700, rng), speech(3, rng)))
        found = self.find(x)
        self.assertEqual([f[2] for f in found], ["before_word"])
        self.assertAlmostEqual(found[0][0], 3.4, delta=0.08)
        self.assertAlmostEqual(found[0][1], 4.0, delta=0.10)

    def test_plain_speech_has_no_hesitation(self):
        self.assertEqual(self.find(speech(20, np.random.default_rng(4))), [])

    def test_octave_error_in_pitch_does_not_split_a_hesitation(self):
        # the pitch tracker jumping an octave midway must not break it (seen in a real recording)
        rng = np.random.default_rng(5)
        x = np.concatenate((quiet(0.5, rng), tone(0.8, 170, 600, rng), quiet(0.5, rng)))
        db, shape, pitch, voiced = roughcut.voice_features(x)
        pitch = pitch.copy()
        pitch[80:90] /= 2
        found = roughcut.find_hesitations((db, shape, pitch, voiced), -45, 0.30)
        self.assertEqual(len(found), 1)
        self.assertGreater(found[0][1] - found[0][0], 0.7)


class Candidates(unittest.TestCase):
    WORDS = [["Tabii", 0.0, 0.4], ["yani", 0.5, 0.8], ["ııı", 1.0, 1.6], ["bu", 1.7, 1.9],
             ["konu", 1.9, 2.3], ["şey,", 2.4, 2.7], ["önemli.", 2.8, 3.3]]

    def test_plain(self):
        self.assertEqual(roughcut.plain("Iıı,"), "ııı")
        self.assertEqual(roughcut.plain("İşte!"), "işte")
        self.assertEqual(roughcut.plain("Tuzla'da"), "tuzlada")

    def test_filler_sounds_depend_on_language(self):
        for word in ("ııı", "eee", "ee", "hmm", "ıh", "a"):
            self.assertTrue(roughcut.is_filler_sound(word, "tr"), word)
        for word in ("ve", "el", "anne", "iki"):
            self.assertFalse(roughcut.is_filler_sound(word, "tr"), word)
        for word in ("uh", "Um,", "uhm", "hmm", "er", "ah"):
            self.assertTrue(roughcut.is_filler_sound(word, "en"), word)
        for word in ("a", "I", "the", "am", "her", "him"):
            self.assertFalse(roughcut.is_filler_sound(word, "en"), word)

    def test_hesitation_confirmed_by_transcript_is_high_confidence(self):
        db = np.full(400, -20.0)
        found = roughcut.build_candidates([(1.05, 1.55, "before_word"), (2.85, 3.25, "before_word")], db, self.WORDS)
        self.assertEqual([(c["confidence"], c["selected"]) for c in found], [("high", True), ("low", False)])
        self.assertIn("ııı", found[0]["context"])

    def test_without_transcript_a_hesitation_before_a_word_is_medium(self):
        found = roughcut.build_candidates([(1.05, 1.55, "before_word"), (5.0, 5.4, "word_end")], np.full(700, -20.0))
        self.assertEqual([(c["confidence"], c["selected"]) for c in found], [("medium", True), ("low", False)])

    def test_filler_words_arrive_unticked(self):
        db = np.full(400, -20.0)
        found = roughcut.build_candidates([], db, self.WORDS, filler_words=["yani", "Şey"])
        # the "ııı" in the transcript also arrives, unticked, since no place was found for it in the audio
        self.assertEqual([c["kind"] for c in found], ["word", "text_only", "word"])
        self.assertTrue(all(not c["selected"] for c in found))
        self.assertIn("«yani»", found[0]["context"])
        self.assertAlmostEqual(found[2]["start"], 2.4, delta=0.11)

    def test_short_hesitation_needs_the_transcript_to_agree(self):
        db = np.full(400, -20.0)
        short = [(1.1, 1.3, "before_word"), (3.0, 3.2, "before_word")]  # the transcript heard no "ııı" at the second
        found = roughcut.build_candidates([], db, self.WORDS, short_hesitations=short)
        self.assertEqual(len(found), 1)
        self.assertTrue(found[0]["short"])
        self.assertFalse(found[0]["selected"])

    def test_names_are_available_for_every_kind(self):
        for kind in ("alone", "before_word", "word_end", "word", "text_only"):
            self.assertTrue(roughcut.kind_name({"kind": kind}))
            self.assertTrue(roughcut.kind_name({"kind": kind, "short": True}))
        for level in ("high", "medium", "low"):
            self.assertTrue(roughcut.confidence_name(level))


class Subtitles(unittest.TestCase):
    def test_srt_time(self):
        self.assertEqual(transcript.srt_time(0), "00:00:00,000")
        self.assertEqual(transcript.srt_time(3723.4567), "01:02:03,457")
        self.assertEqual(transcript.srt_time(59.9996), "00:01:00,000")

    def test_lines_skip_hesitations_and_break_at_sentence_ends(self):
        words = [["Merhaba.", 0.0, 0.5], ["ııı", 0.6, 1.0], ["Bugün", 1.1, 1.4], ["Tuzla'dayız.", 1.4, 2.0]]
        rows = transcript.lines(words)
        self.assertEqual([r[2] for r in rows], ["Merhaba.", "Bugün Tuzla'dayız."])
        self.assertEqual(rows[1][0], 1.1)

    def test_english_article_is_not_dropped_from_subtitles(self):
        words = [["This", 0.0, 0.2], ["is", 0.2, 0.3], ["um", 0.4, 0.7], ["a", 0.8, 0.9], ["test.", 0.9, 1.3]]
        self.assertEqual(transcript.lines(words, language="en")[0][2], "This is a test.")


class AudioMatching(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rng = np.random.default_rng(6)
        cls.rng = rng
        cls.video = np.concatenate([np.concatenate((speech(rng.uniform(1.5, 4), rng, audio.RATE),
                                                    quiet(rng.uniform(0.3, 1.2), rng, audio.RATE)))
                                    for _ in range(40)])

    def other_microphone(self, x):
        y = np.convolve(x, np.ones(5) / 5, mode="same") * 0.3
        return (y + self.rng.normal(0, 0.003, len(y))).astype(np.float32)

    def test_short_clip_is_located(self):
        start = 41.237
        clip = self.other_microphone(self.video[int(start * audio.RATE): int((start + 12) * audio.RATE)])
        position = audio.find_position(self.video, clip)
        self.assertAlmostEqual(position["offset"], start, delta=0.002)
        self.assertTrue(audio.is_match(position))

    def test_recording_that_starts_before_the_video(self):
        clip = np.concatenate((quiet(5.5, self.rng, audio.RATE), self.other_microphone(self.video)))
        position = audio.find_position(self.video, clip)
        self.assertAlmostEqual(position["offset"], -5.5, delta=0.002)
        self.assertTrue(audio.is_match(position))

    def test_unrelated_audio_does_not_match(self):
        other = np.random.default_rng(99)
        clip = np.concatenate([np.concatenate((speech(other.uniform(1.5, 4), other, audio.RATE),
                                               quiet(other.uniform(0.3, 1.2), other, audio.RATE)))
                               for _ in range(4)])
        self.assertFalse(audio.is_match(audio.find_position(self.video, clip)))


if __name__ == "__main__":
    unittest.main()
