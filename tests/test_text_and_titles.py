"""Tests the dictionary, transcript editing, lower-third drawing and the translations.
Needs neither ffmpeg nor a video."""

import ast
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import dictionary  # noqa: E402
import i18n  # noqa: E402
import lang_tr  # noqa: E402
import titles  # noqa: E402
import transcript  # noqa: E402
from common import VERSION, DavarError  # noqa: E402

WORDS = [["Hâlâ", 5.0, 5.2], ["top", 5.2, 5.5], ["sen", 5.5, 5.7], ["de", 5.7, 5.8],
         ["Tuzda", 6.0, 6.4], ["siyasetinde", 6.4, 7.0], ["Bülent", 7.1, 7.4],
         ["Akbörse'nin,", 7.4, 8.0]]


class Version(unittest.TestCase):
    def test_changelog_starts_with_the_current_version(self):
        text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        first = next(line for line in text.splitlines()
                     if line.startswith("## ") and "Unreleased" not in line)
        self.assertEqual(first.split()[1], VERSION, "add an entry to CHANGELOG.md when the version changes")


class Dictionary(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / "sub" / "dictionary.txt"

    def tearDown(self):
        self.folder.cleanup()

    def test_adding_and_reading(self):
        dictionary.add([("tuzda", "Tuzla"), ("top sen", "TÜPSAN")], self.path)
        dictionary.add([("Tuzda", "Tuzla'da")], self.path)  # the same key is updated
        self.assertEqual(dictionary.load(self.path), [(("top", "sen"), "TÜPSAN"), (("tuzda",), "Tuzla'da")])

    def test_missing_file_is_an_empty_dictionary(self):
        self.assertEqual(dictionary.load(self.path), [])
        self.assertEqual(dictionary.apply(WORDS, []), (WORDS, 0))

    def test_suffix_and_punctuation_are_kept_and_phrases_merge(self):
        entries = [(("top", "sen"), "TÜPSAN"), (("tuzda",), "Tuzla"), (("akbörse",), "Akköse")]
        new, count = dictionary.apply(WORDS, entries)
        self.assertEqual(count, 3)
        self.assertEqual([w[0] for w in new],
                         ["Hâlâ", "TÜPSAN", "de", "Tuzla", "siyasetinde", "Bülent", "Akköse'nin,"])
        self.assertEqual(new[1][1:], [5.2, 5.7])  # the two words' times were merged
        self.assertEqual(WORDS[1][0], "top", "the original list must not change")


class TranscriptEditing(unittest.TestCase):
    def test_same_word_count_keeps_the_times(self):
        group = transcript.line_groups(WORDS)[0]
        text = " ".join(WORDS[i][0] for i in group).replace("Tuzda", "Tuzla")
        new, corrections = transcript.edit_line(WORDS, group, text)
        self.assertEqual(corrections, [("Tuzda", "Tuzla")])
        self.assertEqual(new[4], ["Tuzla", 6.0, 6.4])
        self.assertEqual(WORDS[4][0], "Tuzda", "the original list must not change")

    def test_changed_word_count_shares_the_time_span(self):
        group = transcript.line_groups(WORDS)[0]
        new, corrections = transcript.edit_line(WORDS, group, "Hâlâ orada")
        self.assertEqual(corrections, [])
        self.assertEqual([w[0] for w in new], ["Hâlâ", "orada"])
        self.assertEqual((new[0][1], new[-1][2]), (5.0, 8.0))
        self.assertAlmostEqual(new[0][2], new[1][1])

    def test_hesitations_stay_out_of_lines_but_in_the_list(self):
        words = [["Evet.", 0.0, 0.4], ["ııı", 0.5, 1.0], ["Tamam", 1.1, 1.5]]
        groups = transcript.line_groups(words)
        self.assertEqual(groups, [[0], [2]])
        new, _corrections = transcript.edit_line(words, groups[1], "Tamam mı")
        self.assertEqual([w[0] for w in new], ["Evet.", "ııı", "Tamam", "mı"])

    def test_files_from_the_first_format_version_still_load(self):
        with tempfile.TemporaryDirectory() as folder:
            video = Path(folder) / "clip.mp4"
            video.write_bytes(b"not really a video")
            stat = video.stat()
            old = {"surum": 1, "dil": "tr", "model": "small", "sure": 3.3, "kelimeler": WORDS,
                   "video": {"ad": video.name, "boyut": stat.st_size, "degisim": int(stat.st_mtime)}}
            transcript.transcript_path(video).write_text(json.dumps(old), encoding="utf-8")
            record = transcript.load(video)
            self.assertIsNotNone(record)
            self.assertEqual((record["language"], record["duration"], len(record["words"])), ("tr", 3.3, 8))
            video.write_bytes(b"a different file altogether")  # a transcript of another video is ignored
            self.assertIsNone(transcript.load(video))


class LowerThird(unittest.TestCase):
    def test_colour_parsing(self):
        self.assertEqual(titles.parse_colour("#E30613"), (227, 6, 19))
        self.assertEqual(titles.parse_colour("0a0B0c"), (10, 11, 12))
        with self.assertRaises(DavarError):
            titles.parse_colour("red")

    def test_drawing_fits_the_screen_and_scales(self):
        for position in titles.POSITIONS:
            image, x, y, _stripe = titles.draw_lower_third(
                "A Very Long Speaker Name And Surname Example Right Here", "Title", 1920, 1080, position=position)
            self.assertGreaterEqual(x, 0)
            self.assertLessEqual(x + image.width, 1920)
            self.assertLess(y + image.height, 1080)
        large = titles.draw_lower_third("Jane Doe", "Title", 3840, 2160)[0]
        small = titles.draw_lower_third("Jane Doe", "Title", 1920, 1080)[0]
        self.assertAlmostEqual(large.height / small.height, 2.0, delta=0.1)

    def test_without_a_title_it_is_lower(self):
        full = titles.draw_lower_third("Jane Doe", "Title", 1920, 1080)[0]
        name_only = titles.draw_lower_third("Jane Doe", "", 1920, 1080)[0]
        self.assertLess(name_only.height, full.height)

    def test_soft_entrance_and_exit(self):
        full, _x, _y, stripe = titles.draw_lower_third("Jane Doe", "Title", 1920, 1080)
        solid = sum(full.getchannel("A").histogram()[1:])  # the area it covers when fully open

        def visible(time):  # share of that area visible at the given moment
            alpha = titles.lower_third_frame(full, stripe, time, 6.0).getchannel("A")
            return sum(alpha.histogram()[1:]) / solid

        def opacity(time):
            return titles.lower_third_frame(full, stripe, time, 6.0).getchannel("A").getextrema()[1]

        self.assertEqual(visible(0.0), 0.0)
        self.assertLess(visible(0.2), visible(0.4))
        self.assertAlmostEqual(visible(3.0), 1.0, delta=0.01)
        self.assertEqual(opacity(3.0), 255)
        self.assertLess(opacity(5.8), 255 * 0.6)
        self.assertEqual(opacity(6.0), 0)


class Translations(unittest.TestCase):
    SOURCES = ["common.py", "roughcut.py", "transcript.py", "dictionary.py", "audio.py", "picture.py",
               "clips.py", "titles.py", "speakers.py", "content.py", "davar_gui.pyw"]

    def source_strings(self):
        found = {}
        for name in self.SOURCES:
            tree = ast.parse((ROOT / name).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                        and node.func.id in ("_", "N_") and node.args
                        and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
                    found.setdefault(node.args[0].value, name)
        return found

    def test_every_string_in_the_code_has_a_turkish_translation(self):
        missing = {s: f for s, f in self.source_strings().items() if s not in lang_tr.TRANSLATIONS}
        self.assertEqual(missing, {})

    def test_no_translation_is_left_over_from_removed_code(self):
        unused = set(lang_tr.TRANSLATIONS) - set(self.source_strings())
        self.assertEqual(unused, set())

    def test_translations_keep_the_same_placeholders(self):
        import re
        for english, turkish in lang_tr.TRANSLATIONS.items():
            fields = sorted(re.findall(r"\{(\w+)", english))
            self.assertEqual(fields, sorted(re.findall(r"\{(\w+)", turkish)), english)

    def test_switching_language(self):
        before = i18n.language()
        try:
            i18n.set_language("tr")
            self.assertEqual(i18n._("Finished"), "Bitti")
            i18n.set_language("en")
            self.assertEqual(i18n._("Finished"), "Finished")
            i18n.set_language("xx")  # an unknown language falls back to English
            self.assertEqual(i18n.language(), "en")
        finally:
            i18n.set_language(before)


if __name__ == "__main__":
    unittest.main()
