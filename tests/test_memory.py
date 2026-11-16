"""Tests what is remembered between sessions. Works on a dict and a temporary settings file;
no window is opened."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import i18n  # noqa: E402
import memory  # noqa: E402


class StoredValues(unittest.TestCase):
    def test_only_a_value_of_the_right_kind_is_taken(self):
        self.assertTrue(memory.fits(0.4, 0.5))
        self.assertTrue(memory.fits(1, 0.5), "a whole number is a number")
        self.assertFalse(memory.fits(True, 0.5), "a tick is not a number")
        self.assertFalse(memory.fits(1, True))
        self.assertFalse(memory.fits("0.4", 0.5))
        self.assertFalse(memory.fits(None, ""))
        self.assertTrue(memory.fits(["a.wav"], []))
        self.assertFalse(memory.fits(["a.wav", 3], []))
        self.assertFalse(memory.fits("a.wav", []))

    def test_stored_values_replace_the_start_values_where_they_fit(self):
        stored = {"rough_cut.min_silence": 0.8, "rough_cut.silence": "yes", "titles.colour": "#000000"}
        initial = {"min_silence": 0.5, "silence": True, "fillers": ""}
        self.assertEqual(memory.chosen(stored, "rough_cut.", initial),
                         {"min_silence": 0.8, "silence": True, "fillers": ""},
                         "the damaged tick and the missing text keep their start values; other pages are ignored")


class PerVideo(unittest.TestCase):
    def test_each_video_gets_its_own_values_back(self):
        settings = {}
        memory.store_video(settings, r"E:\shoot\talk.mp4", {"rough_cut.keep_from": "0:07.4"})
        memory.store_video(settings, r"E:\shoot\other.mp4", {"rough_cut.keep_from": "1:30"})
        self.assertEqual(memory.video_values(settings, r"E:\shoot\talk.mp4"), {"rough_cut.keep_from": "0:07.4"})
        self.assertEqual(memory.video_values(settings, r"E:\shoot\other.mp4"), {"rough_cut.keep_from": "1:30"})
        self.assertIsNone(memory.video_values(settings, r"E:\shoot\new.mp4"), "nothing is known about a new video")

    def test_a_later_store_adds_to_what_is_kept(self):
        settings = {}
        memory.store_video(settings, "talk.mp4", {"rough_cut.keep_from": "0:07", "rough_cut.remove": "1:00-2:00"})
        memory.store_video(settings, "talk.mp4", {"rough_cut.keep_from": "0:09"})  # the other box could not be read
        self.assertEqual(memory.video_values(settings, "talk.mp4"),
                         {"rough_cut.keep_from": "0:09", "rough_cut.remove": "1:00-2:00"})

    def test_a_video_made_by_davar_starts_with_the_values_of_its_source(self):
        settings = {}
        memory.store_video(settings, r"E:\shoot\talk.mp4",
                           {"rough_cut.keep_from": "0:07.4", "audio.clips": [r"E:\shoot\lav.wav"]})
        self.assertEqual(memory.video_values(settings, r"E:\shoot\talk_picture.mp4"), {"rough_cut.keep_from": "0:07.4"},
                         "the trim times carry over; the separate audio is already in the new video")
        self.assertEqual(memory.video_values(settings, r"E:\shoot\talk_audio_picture.mp4"),
                         {"rough_cut.keep_from": "0:07.4"})
        self.assertIsNone(memory.video_values(settings, r"E:\elsewhere\talk_picture.mp4"), "another folder: another video")
        self.assertIsNone(memory.video_values(settings, r"E:\shoot\talk_final.mp4"), "not a name Davar gives")

    def test_the_source_is_also_found_from_the_output_folder(self):
        settings = {}
        memory.store_video(settings, r"E:\camera\talk.mp4", {"folder": r"E:\work", "rough_cut.keep_to": "51:16"})
        found = memory.video_values(settings, r"E:\work\talk_picture.mp4")
        self.assertEqual(found["rough_cut.keep_to"], "51:16")

    def test_own_values_come_before_those_of_the_source(self):
        settings = {}
        memory.store_video(settings, r"E:\shoot\talk.mp4", {"rough_cut.keep_from": "0:07"})
        memory.store_video(settings, r"E:\shoot\talk_picture.mp4", {"rough_cut.keep_from": "0:10"})
        self.assertEqual(memory.video_values(settings, r"E:\shoot\talk_picture.mp4"), {"rough_cut.keep_from": "0:10"})

    def test_source_names(self):
        self.assertEqual(memory.sources("talk_audio_picture"), ["talk_audio", "talk"])
        self.assertEqual(memory.sources("talk"), [])
        self.assertEqual(memory.sources("_picture"), [], "a name that is nothing but the ending")

    def test_the_videos_used_longest_ago_are_forgotten(self):
        settings = {}
        for n in range(memory.KEPT_VIDEOS + 5):
            memory.store_video(settings, f"video{n}.mp4", {"folder": ""}, now=1000 + n)
        memory.store_video(settings, "video2.mp4", {"folder": ""}, touch=True, now=5000)  # used again
        memory.store_video(settings, "last.mp4", {"folder": ""}, now=5001)
        self.assertEqual(len(settings["videos"]), memory.KEPT_VIDEOS)
        self.assertIsNone(memory.video_values(settings, "video0.mp4"))
        self.assertIsNotNone(memory.video_values(settings, "video2.mp4"), "used recently, so kept")
        self.assertIsNotNone(memory.video_values(settings, "last.mp4"))

    def test_storing_again_without_using_does_not_make_a_video_recent(self):
        settings = {}
        memory.store_video(settings, "talk.mp4", {"folder": ""}, now=100)
        memory.store_video(settings, "talk.mp4", {"folder": "x"}, now=900)
        self.assertEqual(settings["videos"][memory.key("talk.mp4")]["used"], 100)

    def test_a_damaged_file_is_survived(self):
        for damaged in ({"videos": "nothing"}, {"videos": {"a.mp4": "nothing"}}, {"videos": {"a.mp4": {"values": 3}}}):
            self.assertIsNone(memory.video_values(damaged, "a.mp4"))
            memory.store_video(damaged, "a.mp4", {"folder": ""})
            self.assertEqual(memory.video_values(damaged, "a.mp4"), {"folder": ""})


class SettingsFile(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.original, i18n.settings_path = i18n.settings_path, lambda: Path(self.folder.name) / "davar" / "settings.json"

    def tearDown(self):
        i18n.settings_path = self.original
        self.folder.cleanup()

    def test_what_is_written_is_read_back_and_nothing_else_is_lost(self):
        i18n.save_setting("language", "tr")
        settings = i18n.load_settings()
        memory.store_video(settings, "Tuzla Meydanı.mp4", {"rough_cut.remove": "50:46.4-51:03.7"})
        i18n.save_settings(settings)
        i18n.save_setting("speech_language", "tr")
        read = i18n.load_settings()
        self.assertEqual(read["language"], "tr")
        self.assertEqual(memory.video_values(read, "Tuzla Meydanı.mp4"), {"rough_cut.remove": "50:46.4-51:03.7"})
        self.assertEqual([p.name for p in i18n.settings_path().parent.iterdir()], ["settings.json"], "no draft is left")

    def test_a_file_that_is_not_settings_reads_as_empty(self):
        i18n.settings_path().parent.mkdir(parents=True)
        for text in ("[1, 2]", "not json", json.dumps("text")):
            i18n.settings_path().write_text(text, encoding="utf-8")
            self.assertEqual(i18n.load_settings(), {})


if __name__ == "__main__":
    unittest.main()
