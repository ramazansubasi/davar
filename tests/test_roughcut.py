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


class Trimming(unittest.TestCase):
    def state(self, **trim):
        rng = np.random.default_rng(7)
        x = speech(20, rng)  # twenty seconds of speech with no silence to cut
        db = levels(x)
        info = {"fps": Fraction(30), "duration": 20.0, "frames": 600}
        return {"db": db, "threshold": roughcut.auto_threshold(db)[0], "min_silence": 0.5, "info": info,
                "pad_before": 0.10, "pad_after": 0.15, "candidates": [],
                "keep_from": None, "keep_to": None, "remove": [], **trim}

    def test_nothing_is_cut_without_trimming(self):
        cuts, parts = roughcut.cut_plan(self.state())
        self.assertEqual((cuts, parts), ([], [(0, 600)]))

    def test_start_end_and_a_middle_range_are_removed(self):
        cuts, parts = roughcut.cut_plan(self.state(keep_from=2.0, keep_to=18.0, remove=[(9.0, 11.0)]))
        self.assertEqual(len(parts), 2)
        (a0, a1), (b0, b1) = parts
        # a trim edge may keep the usual padding after the word before it, never more
        for frame, second in ((a0, 2.0), (a1, 9.0), (b0, 11.0), (b1, 18.0)):
            self.assertAlmostEqual(frame / 30, second, delta=0.2)
        self.assertEqual(cuts[0][0], 0)
        self.assertEqual(cuts[-1][1], 600, "nothing may be left after the end trim")

    def test_end_trim_reaches_the_last_frame_even_when_the_audio_is_shorter(self):
        state = self.state(keep_to=18.0)
        state["info"] = dict(state["info"], duration=20.07, frames=602)  # video two frames longer than audio
        cuts, parts = roughcut.cut_plan(state)
        self.assertEqual(cuts[-1][1], 602)
        self.assertLess(parts[-1][1] / 30, 18.2)

    def test_range_parsing(self):
        from common import DavarError, parse_ranges, parse_time
        self.assertEqual(parse_time("1:02:03.5"), 3723.5)
        self.assertEqual(parse_ranges("50:46-51:03, 12:00 – 12:30"), [(3046.0, 3063.0), (720.0, 750.0)])
        self.assertEqual(parse_ranges("  "), [])
        for bad in ("12:00", "12:30-12:00", "abc-def"):
            with self.assertRaises(DavarError):
                parse_ranges(bad)


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

    def test_fading_tail_is_cut_with_the_hesitation(self):
        # the "uh" holds for half a second, then fades for a quarter second while its timbre drifts
        open_sound = tone(0.75, 180, 700, np.random.default_rng(8))
        closed_sound = tone(0.75, 180, 350, np.random.default_rng(8))  # same phases, darker timbre
        n, tail = len(open_sound), int(0.25 * SAMPLE_RATE)
        drift = np.concatenate((np.zeros(n - tail), np.linspace(0, 1, tail))).astype(np.float32)
        fade = np.concatenate((np.ones(n - tail), 10 ** (np.linspace(0, -20, tail) / 20))).astype(np.float32)
        sound = ((1 - drift) * open_sound + drift * closed_sound) * fade
        rng = np.random.default_rng(9)
        x = np.concatenate((speech(3, rng), quiet(0.4, rng), sound, speech(3, rng)))
        core_only = roughcut.find_hesitations.__globals__["_follow_tail"]
        self.assertTrue(callable(core_only))
        found = self.find(x)
        self.assertEqual(len(found), 1)
        self.assertGreater(found[0][1], 3.9 + 0.15, "the cut must reach into the fading tail")
        self.assertLess(found[0][1], 4.15 + 0.08, "but must stop before the next word")

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


class Noises(unittest.TestCase):
    def burst(self, seconds, rng):
        """A cough-like sound: a burst of noise that dies away."""
        n = int(seconds * SAMPLE_RATE)
        return (rng.normal(0, 0.2, n) * np.exp(-np.linspace(0, 4, n))).astype(np.float32)

    def test_cough_between_silences_is_found_and_speech_is_not(self):
        rng = np.random.default_rng(11)
        # 0-3 speech | silence | 3.5-3.8 cough | silence | 4.3-7.3 speech
        x = np.concatenate((speech(3, rng), quiet(0.5, rng), self.burst(0.3, rng), quiet(0.5, rng), speech(3, rng)))
        db = levels(x)
        found = roughcut.find_noises(roughcut.voice_features(x), roughcut.auto_threshold(db)[0])
        self.assertEqual(len(found), 1)
        start, end, voiced_share, _faint = found[0]
        self.assertAlmostEqual(start, 3.5, delta=0.06)
        self.assertLess(end, 3.95)
        self.assertLess(voiced_share, 0.35, "a cough is noise, not a voiced sound")

    def test_transcript_decides_between_a_cough_and_a_short_word(self):
        db = np.full(900, -20.0)
        words = [["Evet", 1.0, 1.4], ["tamam.", 5.0, 5.5]]
        bursts = [(1.02, 1.38, 0.9, False),  # the word "Evet": speech
                  (3.0, 3.3, 0.1, False),    # noise with nothing transcribed: a cough
                  (3.8, 3.9, 0.8, True),     # a faint click
                  (4.2, 4.5, 0.9, False),    # a clear voice with no word: nobody can tell without listening
                  (4.7, 4.98, 0.2, False)]   # noise just before a word, brushing its edge
        found = roughcut.build_candidates([], db, words, noises=bursts)
        self.assertEqual([(round(c["start"], 1), c["kind"], c["confidence"], c["selected"]) for c in found],
                         [(3.0, "noise", "high", True), (3.8, "noise", "high", True),
                          (4.2, "unknown", "low", False), (4.7, "noise", "medium", True)])

    def test_without_a_transcript_only_noisy_sounds_are_candidates(self):
        db = np.full(900, -20.0)
        found = roughcut.build_candidates([], db, None, noises=[(1.0, 1.3, 0.9, False), (3.0, 3.3, 0.1, False)])
        self.assertEqual([(round(c["start"], 1), c["confidence"]) for c in found], [(3.0, "medium")])


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
        # the transcribed "ııı" is marked as the thing being cut; the sentence around it is not
        self.assertEqual([w for w, cut in found[0]["parts"] if cut], ["ııı"])
        self.assertIn(("bu", False), found[0]["parts"])
        self.assertEqual([w for w, cut in found[1]["parts"] if cut], [], "nothing heard there: nothing marked")

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
        self.assertEqual([w for w, cut in found[0]["parts"] if cut], ["yani"])
        self.assertEqual([w for w, cut in found[1]["parts"] if cut], ["ııı"])
        self.assertAlmostEqual(found[2]["start"], 2.4, delta=0.11)

    def test_short_hesitation_needs_the_transcript_to_agree(self):
        db = np.full(400, -20.0)
        short = [(1.1, 1.3, "before_word"), (3.0, 3.2, "before_word")]  # the transcript heard no "ııı" at the second
        found = roughcut.build_candidates([], db, self.WORDS, short_hesitations=short)
        self.assertEqual(len(found), 1)
        self.assertTrue(found[0]["short"])
        self.assertTrue(found[0]["selected"], "heard by the transcript and found after a pause: cut by default")

    def test_sound_between_words_is_only_a_suggestion(self):
        db = np.full(400, -20.0)
        found = roughcut.build_candidates([(1.1, 1.5, "between_words"), (2.0, 2.4, "between_words")], db, self.WORDS)
        self.assertEqual([(c["kind"], c["selected"]) for c in found], [("between_words", False)],
                         "only the one the transcript heard becomes a candidate, and it arrives unticked")

    def test_a_neighbouring_candidate_does_not_hide_another_hesitation(self):
        words = [["ııı", 1.0, 1.9], ["evet", 2.0, 2.3], ["ııı", 2.4, 3.2], ["tamam", 3.3, 3.7]]
        db = np.full(500, -20.0)
        found = roughcut.build_candidates([(1.2, 1.7, "before_word")], db, words,
                                          short_hesitations=[(2.6, 2.85, "before_word")])
        self.assertEqual([round(c["start"], 1) for c in found], [1.2, 2.6])

    def test_names_are_available_for_every_kind(self):
        for kind in ("alone", "before_word", "word_end", "between_words", "word", "text_only", "noise", "unknown"):
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
