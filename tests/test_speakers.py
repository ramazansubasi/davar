"""Tests telling the speakers apart and placing their names on the timeline, with made-up
voices and timelines. Needs neither ffmpeg nor a video."""

import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import roughcut  # noqa: E402
import speakers  # noqa: E402
import titles  # noqa: E402
from common import SAMPLE_RATE, DavarError  # noqa: E402

INFO = {"fps": Fraction(30), "width": 1920, "height": 1080, "frames": 3000, "duration": 100.0,
        "audio_channels": 2, "audio_rate": 48000, "variable_rate": False}


def voice(seconds, pitch, formants, seed):
    """Something like a voice: a buzz at `pitch` shaped by resonances, with syllables."""
    rng = np.random.default_rng(seed)
    n = int(seconds * SAMPLE_RATE)
    t = np.arange(n) / SAMPLE_RATE
    wobble = 1 + 0.03 * np.sin(2 * np.pi * 3 * t + rng.uniform(0, 6))
    buzz = np.sign(np.sin(2 * np.pi * np.cumsum(pitch * wobble) / SAMPLE_RATE)) + 0.3 * rng.normal(0, 1, n)
    spectrum = np.fft.rfft(buzz)
    freqs = np.fft.rfftfreq(n, 1 / SAMPLE_RATE)
    shape = sum(np.exp(-((freqs - f) / 180) ** 2) for f in formants) + 0.02
    syllables = 0.55 + 0.45 * np.sin(2 * np.pi * 4 * t + rng.uniform(0, 6)) ** 2
    out = np.fft.irfft(spectrum * shape, n) * syllables
    return (0.3 * out / np.abs(out).max()).astype(np.float32)


def conversation(plan):
    """Audio and "words" for a list of (speaker, seconds); half a second of quiet between turns."""
    voices = {0: (110, (500, 1500, 2500)), 1: (190, (800, 1200, 3100)), 2: (150, (350, 2100, 2900))}
    samples, words, moment = [], [], 0.0
    for n, (who, seconds) in enumerate(plan):
        samples.append(voice(seconds, *voices[who], seed=n))
        words += [[f"word{n}", moment + k * 0.5, moment + k * 0.5 + 0.45] for k in range(int(seconds * 2))]
        samples.append(np.zeros(SAMPLE_RATE // 2, np.float32))
        moment += seconds + 0.5
    return np.concatenate(samples), words


class TellingApart(unittest.TestCase):
    def test_two_voices_are_followed_through_their_turns(self):
        plan = [(0, 20), (1, 45), (0, 12), (1, 30), (0, 25), (1, 16)]
        samples, words = conversation(plan)
        turns = speakers.find_turns(samples, words, 2)
        self.assertEqual([who for _s, _e, who in turns], [0, 1, 0, 1, 0, 1], "numbered in the order they first speak")
        moment = 0.0
        for (start, end, _who), (_speaker, seconds) in zip(turns, plan):
            self.assertAlmostEqual(start, moment, delta=3.0, msg="a turn is found to within a few seconds")
            moment += seconds + 0.5

    def test_three_voices(self):
        samples, words = conversation([(0, 25), (1, 30), (2, 28), (0, 20), (2, 22), (1, 24)])
        self.assertEqual([who for _s, _e, who in speakers.find_turns(samples, words, 3)], [0, 1, 2, 0, 2, 1])

    def test_one_speaker_needs_no_listening(self):
        self.assertEqual(speakers.find_turns(np.zeros(10, np.float32), [["a", 1.0, 1.5], ["b", 9.0, 9.4]], 1),
                         [(1.0, 9.4, 0)])

    def test_too_little_speech_is_refused(self):
        samples, words = conversation([(0, 6), (1, 6)])
        with self.assertRaises(DavarError):
            speakers.find_turns(samples, words, 2)
        with self.assertRaises(DavarError):
            speakers.find_turns(samples, [], 2)

    def test_a_short_turn_joins_its_longer_neighbour(self):
        turns = [(0, 30, 0), (30, 32, 1), (32, 50, 0), (50, 80, 1), (80, 83, 0)]
        self.assertEqual(speakers.join_short_turns(turns), [(0, 50, 0), (50, 83, 1)])
        self.assertEqual(speakers.join_short_turns([(0, 2, 0)]), [(0, 2, 0)], "a lone turn stays")


class Placing(unittest.TestCase):
    TURNS = [(1.6, 40.0, 0), (38.0, 300.0, 1), (298.0, 350.0, 0)]

    def people(self, *rows):
        return titles.parse_people(rows)

    def test_lines_are_read_with_or_without_title_place_and_time(self):
        self.assertEqual(self.people("Jane Doe | Host", "John Roe", "Ann Poe | | 1:05", "  "),
                         [{"name": "Jane Doe", "title": "Host", "position": None, "time": None},
                          {"name": "John Roe", "title": "", "position": None, "time": None},
                          {"name": "Ann Poe", "title": "", "position": None, "time": 65.0}])
        self.assertEqual([(p["position"], p["time"]) for p in self.people(
            "A | Host | sol", "B | Guest | Sağ | 0:41", "C | | 12:30 | ORTA", "D | x | RIGHT", "E | x | center |")],
            [("left", None), ("right", 41.0), ("centre", 750.0), ("right", None), ("centre", None)],
            "a word is a place and a number is a time, in either order and in either language")
        self.assertEqual(self.people("Sol Kaya | Sağ Görüş")[0]["position"], None,
                         "the second field is always the title, whatever it says")
        for bad in (["a | b | left | 0:41 | x"], ["Jane | Host | soon"], ["Jane | Host | left | right"],
                    ["Jane | Host | 0:41 | 0:50"], ["Jane | Host | 0:4x"], ["  "]):
            with self.assertRaises(DavarError, msg=bad):
                titles.parse_people(bad)

    def test_each_name_goes_where_its_speaker_first_speaks(self):
        places = titles.plan_places(self.people("Host", "Guest"), self.TURNS, 7.4, 3076.0)
        self.assertEqual(places, [7.4 + titles.OPENING, 38.0 + titles.PLACE_AFTER],
                         "the programme opens with the host; the guest's name waits for the guest")

    def test_a_first_turn_that_is_cut_away_does_not_count(self):
        turns = [(0.0, 9.0, 0), (9.0, 60.0, 1), (60.0, 90.0, 0)]  # chatter before the programme, then the guest
        places = titles.plan_places(self.people("Guest", "Host"), turns, 8.0, 100.0)
        self.assertEqual(places, [9.0 + titles.PLACE_AFTER, 60.0 + titles.PLACE_AFTER],
                         "one second of the host is left after trimming: too short to carry a name")

    def test_a_time_of_ones_own_is_kept_and_claims_its_voice(self):
        places = titles.plan_places(self.people("Guest | | 2:00", "Host"), self.TURNS, 7.4, 3076.0)
        self.assertEqual(places, [120.0, 7.4 + titles.OPENING], "the voice at 2:00 is the guest's; the other is the host")

    def test_more_names_than_voices(self):
        places = titles.plan_places(self.people("Host", "Guest", "Nobody"), self.TURNS, 7.4, 3076.0)
        self.assertIsNone(places[2])
        self.assertEqual(titles.plan_places(self.people("Host"), [], 0.0, 100.0), [None])


class Timeline(unittest.TestCase):
    PARTS = [(221, 327), (334, 395), (1156, 1343)]

    def test_a_frame_of_the_video_is_found_on_the_timeline(self):
        self.assertEqual(roughcut.timeline_place(self.PARTS, 281), (0, 281, 60))
        self.assertEqual(roughcut.timeline_place(self.PARTS, 340), (1, 340, 106 + 6))
        self.assertEqual(roughcut.timeline_place(self.PARTS, 500), (2, 1156, 106 + 61), "cut away: the next part kept")
        self.assertEqual(roughcut.timeline_place(self.PARTS, 0), (0, 221, 0))
        self.assertIsNone(roughcut.timeline_place(self.PARTS, 1343))

    def test_titles_are_written_above_the_video_and_read_back(self):
        with tempfile.TemporaryDirectory() as folder:
            video, title, timeline = (Path(folder) / name for name in ("Tuzla Meydanı.mp4", "lowerthird_host.mov", "cut.fcpxml"))
            overlays = [{"path": title, "at": 281, "frames": 180}, {"path": title, "at": 500, "frames": 180},
                        {"path": title, "at": 2000, "frames": 180}]
            roughcut.write_fcpxml(timeline, video, INFO, self.PARTS, overlays=overlays)
            text = timeline.read_text(encoding="utf-8")
            self.assertEqual(text.count("<asset id="), 2, "the video and one title file, however often it is used")
            self.assertEqual(text.count('lane="1"'), 2, "the one after the end of the timeline is left out")
            self.assertIn('lane="1" offset="281/30s" start="0s" duration="180/30s"', text)
            back = roughcut.read_timeline(timeline, video, INFO)
            self.assertEqual(back["parts"], self.PARTS)
            self.assertEqual(back["overlays"], [{"path": title.resolve(), "at": 281, "frames": 180},
                                                {"path": title.resolve(), "at": 1156, "frames": 180}])

    def test_a_timeline_without_titles_is_written_as_before(self):
        with tempfile.TemporaryDirectory() as folder:
            video, timeline = Path(folder) / "talk.mp4", Path(folder) / "cut.fcpxml"
            roughcut.write_fcpxml(timeline, video, INFO, self.PARTS)
            self.assertNotIn("lane", timeline.read_text(encoding="utf-8"))
            wide = roughcut.WIDE
            self.assertEqual(roughcut.read_timeline(timeline, video, INFO),
                             {"parts": self.PARTS, "overlays": [], "framings": [wide, wide, wide], "still": None})

    def test_closer_framings_are_written_before_the_titles_and_read_back(self):
        with tempfile.TemporaryDirectory() as folder:
            video, title, timeline = (Path(folder) / name for name in ("talk.mp4", "lowerthird_a.mov", "cut.fcpxml"))
            left, middle = (1.25, 12.5, -3.52), (1.15, 0.0, 0.0)
            roughcut.write_fcpxml(timeline, video, INFO, self.PARTS, framings=[middle, left, left],
                                  overlays=[{"path": title, "at": 1200, "frames": 180}])
            text = timeline.read_text(encoding="utf-8")
            self.assertEqual(text.count('<adjust-transform position="12.5 -3.52" scale="1.25 1.25"/>'), 2)
            self.assertEqual(text.count('<adjust-transform scale="1.15 1.15"/>'), 1, "no position when centred")
            self.assertLess(text.index("adjust-transform", text.index('start="1156/30s"')), text.index('lane="1"'),
                            "the picture's own adjustment comes before the clip above it")
            back = roughcut.read_timeline(timeline, video, INFO)
            self.assertEqual(back["framings"], [middle, left, left])
            self.assertEqual(len(back["overlays"]), 1)

    def test_a_still_picture_lasts_the_whole_timeline_and_is_read_back(self):
        with tempfile.TemporaryDirectory() as folder:
            video, logo, timeline = (Path(folder) / name for name in ("talk.mp4", "talk_logo.png", "cut.fcpxml"))
            roughcut.write_fcpxml(timeline, video, INFO, self.PARTS, still=logo,
                                  overlays=[{"path": Path(folder) / "lowerthird_a.mov", "at": 230, "frames": 60}])
            text = timeline.read_text(encoding="utf-8")
            self.assertIn('<video name="talk_logo" lane="2" offset="221/30s" ref="rs" start="0s" duration="354/30s"/>',
                          text, "on its own track above the titles, from the start to the end of the cut")
            self.assertEqual(text.count('lane="2"'), 1)
            back = roughcut.read_timeline(timeline, video, INFO)
            self.assertEqual(back["still"], logo.resolve())
            self.assertEqual(len(back["overlays"]), 1)

    def test_a_cameras_start_timecode_is_kept_so_editors_find_the_file(self):
        with tempfile.TemporaryDirectory() as folder:
            video, logo, title, timeline = (Path(folder) / name for name in
                                            ("C0017.MP4", "C0017_logo.png", "lowerthird_a.mov", "cut.fcpxml"))
            info = {**INFO, "timecode": 1000}
            overlays = [{"path": title, "at": 281, "frames": 180}]
            roughcut.write_fcpxml(timeline, video, info, self.PARTS, still=logo, overlays=overlays)
            text = timeline.read_text(encoding="utf-8")
            self.assertIn('<asset id="r2" name="C0017" start="1000/30s"', text)
            self.assertIn('start="1221/30s"', text, "the first part, from the timecode on")
            self.assertIn('lane="1" offset="1281/30s"', text)
            self.assertIn('lane="2" offset="1221/30s"', text)
            back = roughcut.read_timeline(timeline, video, info)
            self.assertEqual(back["parts"], self.PARTS)
            self.assertEqual(back["overlays"][0]["at"], 281)

    def test_start_timecodes_are_read_from_the_file(self):
        from common import start_timecode
        data = {"streams": [{"codec_type": "data", "tags": {"timecode": "00:03:34:28"}}], "format": {}}
        self.assertEqual(start_timecode(data, Fraction(50)), (3 * 60 + 34) * 50 + 28)
        self.assertEqual(start_timecode({"streams": [], "format": {}}, Fraction(25)), 0)
        self.assertEqual(start_timecode({"streams": [], "format": {"tags": {"timecode": "00:01:00;02"}}},
                                        Fraction(30000, 1001)), 1800, "drop frame: 00:01:00;02 is frame 1800")

    def test_another_videos_timeline_is_not_taken(self):
        with tempfile.TemporaryDirectory() as folder:
            video, other, timeline = (Path(folder) / name for name in ("talk.mp4", "other.mp4", "cut.fcpxml"))
            roughcut.write_fcpxml(timeline, video, INFO, self.PARTS)
            self.assertIsNone(roughcut.read_timeline(timeline, other, INFO))
            self.assertIsNone(roughcut.read_timeline(timeline, video, {**INFO, "fps": Fraction(25)}), "another frame rate")
            self.assertIsNone(roughcut.read_timeline(Path(folder) / "none.fcpxml", video, INFO))
            timeline.write_text("not a timeline", encoding="utf-8")
            self.assertIsNone(roughcut.read_timeline(timeline, video, INFO))


class Framings(unittest.TestCase):
    WIDE = roughcut.WIDE

    def parts(self, count, gaps=None):
        """`count` parts of two seconds at 30 frames per second, half a second cut between them
        unless `gaps` says otherwise (part index -> seconds cut before it). Also their start times."""
        parts, frame = [], 0
        for n in range(count):
            frame += round((gaps or {}).get(n, 0.5 if n else 0) * 30)
            parts.append((frame, frame + 60))
            frame += 60
        return parts, [start / 30 for start, _end in parts]

    def test_a_long_answer_is_framed_closer_and_changes_at_the_biggest_jump(self):
        parts, starts = self.parts(43, gaps={23: 1.5})  # three short parts of the host, then 80 s of the guest
        turns = [(0.0, starts[3], 0), (starts[3], starts[-1] + 2, 1)]
        found = roughcut.framings(parts, 30.0, turns, ["left", "right"], 1.25)
        close = roughcut.close_framing(1.25, "right", 1920, 1080)
        self.assertEqual(found[:5], [self.WIDE] * 5, "the host's 6 s stay on everyone; the guest's start too")
        self.assertEqual(found[5:23], [close] * 18, "4 s into the answer the picture moves to the guest")
        self.assertEqual(found[23:38], [self.WIDE] * 15, "after half a minute, at the cut where most was removed")
        self.assertEqual(found[38:], [close] * 5, "and back; nothing changes in the last 8 s")

    def test_quick_exchanges_stay_on_everyone(self):
        parts, starts = self.parts(30)
        turns = [(starts[n], starts[n] + 7.5, (n // 3) % 2) for n in range(0, 30, 3)]  # 6 s each
        self.assertEqual(roughcut.framings(parts, 30.0, turns, ["left", "right"]), [self.WIDE] * 30)

    def test_closer_framing_moves_toward_the_speaker_and_never_past_the_edge(self):
        self.assertEqual(roughcut.close_framing(1.25, "left", 1920, 1080), (1.25, 12.5, -3.52))
        self.assertEqual(roughcut.close_framing(1.25, "right", 1920, 1080), (1.25, -12.5, -3.52))
        self.assertEqual(roughcut.close_framing(1.25, "centre", 1920, 1080), (1.25, 0.0, 0.0))
        self.assertEqual(roughcut.close_framing(1.25, None, 1920, 1080), (1.25, 0.0, 0.0))

    def test_nothing_to_frame(self):
        self.assertEqual(roughcut.framings([], 30.0, []), [])
        parts, _starts = self.parts(10)
        self.assertEqual(roughcut.framings(parts, 30.0, []), [self.WIDE] * 10, "no speaker known")


if __name__ == "__main__":
    unittest.main()
