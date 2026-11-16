"""Tests the prompt for the YouTube texts and the reading of the AI chat's answer. No video,
no ffmpeg and no AI are needed."""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import content  # noqa: E402
from common import DavarError  # noqa: E402

# at 10 frames per second: 0-20 s kept, 20-30 s cut, 30-60 s kept
PARTS = [(0, 200), (300, 600)]
WORDS = [["Welcome.", 0.5, 1.0], ["uh", 1.2, 1.6], ["Thank", 2.0, 2.3], ["you.", 2.3, 2.6],
         ["Cut", 22.0, 23.0], ["Later", 31.0, 31.5], ["words.", 31.6, 32.0]]
TURNS = [(0.0, 1.8, 0), (1.8, 60.0, 1)]


class Prompt(unittest.TestCase):
    def test_lines_follow_the_cut_and_name_the_speakers(self):
        lines = content.transcript_lines(WORDS, PARTS, 10.0, TURNS, ["Host"], "en")
        self.assertEqual(lines, [(0.5, "Host", "Welcome."), (2.0, "Speaker 2", "Thank you."),
                                 (21.0, "Speaker 2", "Later words.")],
                         "the hesitation and the words cut away are gone; the guest has no name, so a number; "
                         "a sentence that ended long ago starts a new line")
        moved = content.transcript_lines(WORDS[5:], PARTS, 10.0, (), (), "en")
        self.assertEqual(moved, [(21.0, "", "Later words.")], "31 s in the video is 21 s on the timeline")

    def test_a_long_speech_is_split_into_lines(self):
        words = [[f"w{n}.", n * 1.0, n * 1.0 + 0.5] for n in range(50)]
        lines = content.transcript_lines(words, [(0, 600)], 10.0, (), (), "en")
        self.assertTrue(all(b[0] - a[0] <= content.LINE_SECONDS for a, b in zip(lines, lines[1:])))
        self.assertGreater(len(lines), 2)

    def test_the_prompt_holds_the_context_and_the_transcript(self):
        text = content.build_prompt([(0.0, "Host", "Welcome."), (75.0, "Guest", "Thanks.")], "tr", "Tuzla Meydanı",
                                    "Çağdaş Tuzla", [("Halil Özen", "Yayın Yönetmeni"), ("Bülent Akköse", "")],
                                    "", 2639.5)
        self.assertIn("Program: Tuzla Meydanı", text)
        self.assertIn("Konuşmacılar: Halil Özen (Yayın Yönetmeni), Bülent Akköse", text)
        self.assertIn("Süre: 43:59", text)
        self.assertIn("[0:00] Host: Welcome.\n[1:15] Guest: Thanks.", text)
        self.assertIn('"chapters": [{"time": "0:00"', text, "the example of the answer survives the formatting")
        self.assertNotIn("Notlar", text, "an empty field is left out")

    def test_clock(self):
        self.assertEqual(content.clock(65.9), "1:05")
        self.assertEqual(content.clock(3723), "1:02:03")


class Answer(unittest.TestCase):
    ANSWER = """Here it is:
```json
{"titles": ["One", "Two"], "summary": "Short.", "description": "About the talk.",
 "chapters": [{"time": "0:05", "title": "Opening"}, {"time": "0:08", "title": "Too soon"},
              {"time": "0:40", "title": "Main part"}, {"time": "9:00", "title": "Past the end"},
              {"time": "soon", "title": "Unreadable"}],
 "tags": "politics, local, Tuzla",
 "clips": [{"start": "0:30", "end": "0:50", "headline": "A strong answer", "why": "Clear."},
           {"start": "0:50", "end": "0:40", "headline": "Backwards"}]}
```"""

    def test_the_answer_is_read_and_put_in_order(self):
        answer = content.parse_answer(self.ANSWER, 50.0)
        self.assertEqual(answer["titles"], ["One", "Two"])
        self.assertEqual(answer["chapters"], [(0.0, "Opening"), (40.0, "Main part")],
                         "the first moves to 0:00; one 8 s after it, one past the end and one unreadable go")
        self.assertEqual(answer["tags"], ["politics", "local", "Tuzla"], "tags given as one text are split")
        self.assertEqual([c["headline"] for c in answer["clips"]], ["A strong answer"])

    def test_an_answer_that_is_not_one_is_refused(self):
        for text in ("", "Sorry, I cannot help with that.", "{not json}"):
            with self.assertRaises(DavarError):
                content.parse_answer(text, 50.0)

    def test_the_texts_give_clip_times_in_the_video_too(self):
        answer = content.parse_answer(self.ANSWER, 50.0)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "talk_youtube.txt"
            content.write_texts(path, answer, PARTS, 10.0, "en")
            text = path.read_text(encoding="utf-8")
        self.assertIn("Chapters:\n0:00 Opening\n0:40 Main part\n", text)
        self.assertIn("On the timeline: 0:30 - 0:50", text)
        self.assertIn("In the video (the times for Social Clips): 0:40.00 - 1:00.00", text,
                      "ten seconds were cut before the clip")

    def test_moments_of_the_timeline_are_found_in_the_video(self):
        self.assertEqual(content.video_moment(PARTS, 10.0, 5.0), 5.0)
        self.assertEqual(content.video_moment(PARTS, 10.0, 25.0), 35.0)
        self.assertEqual(content.video_moment(PARTS, 10.0, 99.0), 60.0, "past the end: the end")


if __name__ == "__main__":
    unittest.main()
