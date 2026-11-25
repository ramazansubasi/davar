"""Tests finding repeated words, restarted sentences and talk about the recording."""

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import retakes  # noqa: E402
import roughcut  # noqa: E402


def spoken(text, gaps=None, start=0.0):
    """Words of `text` 0.4 s long, 0.05 s apart; `gaps` gives a longer pause before word n."""
    words, t = [], start
    for n, word in enumerate(text.split()):
        t += (gaps or {}).get(n, 0.05)
        words.append((word, t, t + 0.4))
        t += 0.4
    return words


def found(text, gaps=None):
    words = spoken(text, gaps)
    return [(" ".join(w[0] for w in words[first:last]), kind, confidence)
            for _s, _e, first, last, kind, confidence in retakes.find_retakes(words)]


class Repeats(unittest.TestCase):
    def test_words_said_twice_in_a_row(self):
        self.assertEqual(found("izleyicilerimize rahat konuşun rahat konuşun bizi beğenin"),
                         [("rahat konuşun", "repeat", "medium")])

    def test_a_word_broken_off_and_said_whole(self):
        self.assertEqual(found("bu haber yayın yayından kaldırılıyor"), [("yayın", "repeat", "medium")])

    def test_a_restart_after_a_pause(self):
        self.assertEqual(found("ve yirmi dört tane politika ve yirmi dört tane politika başkan yardımcısı"),
                         [("ve yirmi dört tane politika", "repeat", "medium")])
        restart = "bilgi sahibi olduğu veya ilgi sahibi olduğu noktalara yönlendirdik"
        self.assertEqual(found(restart, {4: 0.5}), [("bilgi sahibi olduğu veya", "repeat", "low")])

    def test_the_hesitation_between_goes_too(self):
        self.assertEqual(found("iski ııı iski yönetim kurulu"), [("iski ııı", "repeat", "medium")])

    def test_repeats_said_on_purpose_are_left(self):
        self.assertEqual(found("otuz iki yıldır kaybede kaybede büyüttüğümüz umut"), [])
        self.assertEqual(found("bunları tek tek anlattık"), [])
        self.assertEqual(found("bu bu konuda"), [], "a short common word")
        self.assertEqual(found("Her ikisi de kul hakkıdır. Her ikisi de ahlaksızlıktır."), [],
                         "a whole sentence said again with a new ending is rhetoric")

    def test_the_cut_ends_where_the_second_try_begins(self):
        words = spoken("rahat konuşun rahat konuşun bizi")
        start, end, *_rest = retakes.find_retakes(words)[0]
        self.assertEqual((start, end), (words[0][1], words[2][1]))


class RetakeTalk(unittest.TestCase):
    def test_talk_to_the_crew_with_its_sentence(self):
        self.assertEqual(found("Başlıyor musun? Kayıttayız başlayabiliriz. Hoş geldiniz efendim",
                               {4: 0.9}),
                         [("Başlıyor musun? Kayıttayız başlayabiliriz.", "retake", "medium")])
        self.assertEqual(found("Bu kısım bence yeter. Siz kesersiniz. Ben birkaç konuyu anlatayım."),
                         [("Siz kesersiniz.", "retake", "medium")])

    def test_the_new_take_after_starting_again_is_kept(self):
        self.assertEqual(found("izleyicilerimize merhaba baştan alıyorum can atalay kararı yayınlandı"),
                         [("izleyicilerimize merhaba baştan alıyorum", "retake", "medium")])

    def test_the_abandoned_take_is_offered_whole(self):
        text = ("geçtiğimiz günlerde Maltepe'de bir müdahale oldu ve bunu konuşacağız "
                "kamerayı kapatıyorum baştan alıyoruz geçtiğimiz günlerde Maltepe'de bir müdahale oldu")
        self.assertEqual(found(text), [(" ".join(text.split()[:13]), "retake", "medium")])

    def test_no_talk_in_another_language(self):
        self.assertEqual(retakes.find_retakes(spoken("baştan alıyorum"), "de"), [])


class Candidates(unittest.TestCase):
    def test_they_arrive_unticked_with_their_words_marked(self):
        words = spoken("izleyicilerimize rahat konuşun rahat konuşun bizi beğenin")
        db = np.full(int(4 / roughcut.WINDOW), -20.0)
        found = retakes.find_retakes(words)
        candidates = roughcut.build_candidates([], db, words, retakes=found)
        self.assertEqual(len(candidates), 1)
        c = candidates[0]
        self.assertEqual((c["kind"], c["selected"]), ("repeat", False))
        self.assertEqual([w for w, cut in c["parts"] if cut], ["rahat", "konuşun"])
        self.assertIn("(", roughcut.kind_name(c))


if __name__ == "__main__":
    unittest.main()
