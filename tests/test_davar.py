"""Davar'ın hesap kısmını yapay seslerle sınar. ffmpeg ya da video gerekmez.

    python -m unittest discover tests
"""

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import analiz  # noqa: E402
import davar  # noqa: E402
import ses  # noqa: E402

HIZ = davar.ORNEK_HIZI


def _ton(sure, perde, bicim, rng, genlik=0.3, hiz=HIZ):
    """Perdesi ve tınısı verilen ötümlü ses (harmonikler `bicim` çevresinde güçlü)."""
    t = np.arange(int(sure * hiz)) / hiz
    x = np.zeros(len(t))
    for h in range(1, 25):
        f = perde * h
        if f > hiz / 2 - 200:
            break
        x += np.exp(-((f - bicim) / 500.0) ** 2) * np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28))
    return (genlik * x / (np.abs(x).max() + 1e-9)).astype(np.float32)


def konusma(sure, rng, hiz=HIZ):
    """Konuşmayı taklit eder: perdesi ve tınısı sürekli değişen kısa heceler."""
    parcalar, toplam = [], 0.0
    while toplam < sure:
        d = rng.uniform(0.07, 0.13)
        hece = _ton(d, rng.uniform(100, 220), rng.uniform(400, 2600), rng, rng.uniform(0.15, 0.35), hiz)
        hece *= np.hanning(len(hece)) ** 0.3
        parcalar += [hece, np.zeros(int(rng.uniform(0.0, 0.02) * hiz), np.float32)]
        toplam += d + 0.01
    return np.concatenate(parcalar)[: int(sure * hiz)]


def sessizlik(sure, rng, hiz=HIZ):
    return rng.normal(0, 0.0005, int(sure * hiz)).astype(np.float32)


def seviyeler(x):
    adim = int(HIZ * davar.PENCERE)
    n = len(x) // adim
    return 20 * np.log10(np.sqrt(np.mean(x[: n * adim].reshape(n, adim) ** 2, axis=1)) + 1e-10)


BILGI = {"fps": __import__("fractions").Fraction(30), "sure": 0.0, "kare_sayisi": 0}


class Sessizlik(unittest.TestCase):
    def test_sessizlikler_bulunur_ve_paylar_birakilir(self):
        rng = np.random.default_rng(1)
        # 0-3 konuşma | 3-4.5 sessiz | 4.5-8 konuşma | 8-8.3 kısa sessiz | 8.3-10 konuşma
        x = np.concatenate((konusma(3, rng), sessizlik(1.5, rng), konusma(3.5, rng),
                            sessizlik(0.3, rng), konusma(1.7, rng)))
        db = seviyeler(x)
        esik, taban, ust = davar.otomatik_esik(db)
        self.assertLess(taban, -55)
        self.assertGreater(ust, -25)
        araliklar = davar.sessiz_araliklar(db, esik, 0.5)
        self.assertEqual(len(araliklar), 1, "0.3 saniyelik sessizlik kesilmemeli")
        bas, son = araliklar[0][:2]
        self.assertAlmostEqual(bas, 3.0, delta=0.06)
        self.assertAlmostEqual(son, 4.5, delta=0.06)

        bilgi = dict(BILGI, sure=len(x) / HIZ, kare_sayisi=int(len(x) / HIZ * 30))
        kesimler = davar.kesimleri_hesapla(araliklar, bilgi, pay_bas=0.10, pay_son=0.15)
        self.assertEqual(len(kesimler), 1)
        self.assertAlmostEqual(kesimler[0][0] / 30, 3.15, delta=0.08)  # kelimeden sonra pay
        self.assertAlmostEqual(kesimler[0][1] / 30, 4.40, delta=0.08)  # kelimeden önce pay
        parcalar = davar.kalan_parcalar(kesimler, bilgi["kare_sayisi"])
        self.assertEqual(parcalar[0][0], 0)
        self.assertEqual(parcalar[-1][1], bilgi["kare_sayisi"])


class Duraksama(unittest.TestCase):
    def _bul(self, x, en_kisa=0.30):
        db = seviyeler(x)
        esik = davar.otomatik_esik(db)[0]
        return davar.duraksamalari_bul(davar.ses_ozellikleri(x), esik, en_kisa)

    def test_tek_basina_duraksama_bulunur(self):
        rng = np.random.default_rng(2)
        x = np.concatenate((konusma(3, rng), sessizlik(0.4, rng), _ton(0.7, 120, 600, rng),
                            sessizlik(0.4, rng), konusma(3, rng)))
        bulunan = self._bul(x)
        self.assertEqual([b[2] for b in bulunan], ["tek"])
        self.assertAlmostEqual(bulunan[0][0], 3.4, delta=0.08)
        self.assertAlmostEqual(bulunan[0][1], 4.1, delta=0.08)

    def test_kelimeye_bitisik_duraksama_bulunur(self):
        rng = np.random.default_rng(3)
        x = np.concatenate((konusma(3, rng), sessizlik(0.4, rng), _ton(0.6, 180, 700, rng),
                            konusma(3, rng)))
        bulunan = self._bul(x)
        self.assertEqual([b[2] for b in bulunan], ["bas"])
        self.assertAlmostEqual(bulunan[0][0], 3.4, delta=0.08)
        self.assertAlmostEqual(bulunan[0][1], 4.0, delta=0.10)

    def test_duz_konusmada_duraksama_cikmaz(self):
        rng = np.random.default_rng(4)
        self.assertEqual(self._bul(konusma(20, rng)), [])

    def test_perdedeki_oktav_hatasi_duraksamayi_bolmez(self):
        # perde ölçümü ortada bir oktav şaşsa da tek parça sayılmalı (gerçek kayıtta görülen hata)
        rng = np.random.default_rng(5)
        x = np.concatenate((sessizlik(0.5, rng), _ton(0.8, 170, 600, rng), sessizlik(0.5, rng)))
        db, sekil, perde, otumlu = davar.ses_ozellikleri(x)
        perde = perde.copy()
        perde[80:90] /= 2
        bulunan = davar.duraksamalari_bul((db, sekil, perde, otumlu), -45, 0.30)
        self.assertEqual(len(bulunan), 1)
        self.assertGreater(bulunan[0][1] - bulunan[0][0], 0.7)


class Adaylar(unittest.TestCase):
    KELIMELER = [["Tabii", 0.0, 0.4], ["yani", 0.5, 0.8], ["ııı", 1.0, 1.6], ["bu", 1.7, 1.9],
                 ["konu", 1.9, 2.3], ["şey,", 2.4, 2.7], ["önemli.", 2.8, 3.3]]

    def test_sade(self):
        self.assertEqual(davar.sade("Iıı,"), "ııı")
        self.assertEqual(davar.sade("İşte!"), "işte")
        self.assertEqual(davar.sade("Tuzla'da"), "tuzlada")

    def test_dolgu_sesi_tanima(self):
        for k in ("ııı", "eee", "ee", "hmm", "ıh"):
            self.assertTrue(davar.DOLGU_SES.match(k), k)
        for k in ("ve", "el", "anne", "iki"):
            self.assertFalse(davar.DOLGU_SES.match(k), k)

    def test_metinle_dogrulanan_duraksama_yuksek_guvenli(self):
        db = np.full(400, -20.0)
        adaylar = davar.adaylari_cikar([(1.05, 1.55, "bas"), (2.85, 3.25, "bas")], db, self.KELIMELER)
        self.assertEqual([(a["guven"], a["sec"]) for a in adaylar], [("yüksek", True), ("düşük", False)])
        self.assertIn("ııı", adaylar[0]["metin"])

    def test_metin_yoksa_kelime_onundeki_duraksama_orta_guvenli(self):
        adaylar = davar.adaylari_cikar([(1.05, 1.55, "bas"), (5.0, 5.4, "son")], np.full(700, -20.0))
        self.assertEqual([(a["guven"], a["sec"]) for a in adaylar], [("orta", True), ("düşük", False)])

    def test_dolgu_kelimeleri_isaretsiz_gelir(self):
        db = np.full(400, -20.0)
        adaylar = davar.adaylari_cikar([], db, self.KELIMELER, dolgu_kelimeleri=["yani", "Şey"])
        # metindeki "ııı" da (seste yeri bulunamadığı için) işaretsiz bir aday olarak gelir
        self.assertEqual([a["tur"] for a in adaylar], ["kelime", "metin", "kelime"])
        self.assertTrue(all(not a["sec"] for a in adaylar))
        self.assertIn("«yani»", adaylar[0]["metin"])
        self.assertAlmostEqual(adaylar[2]["bas"], 2.4, delta=0.11)

    def test_kisa_duraksama_yalnizca_metin_de_duyduysa_aday_olur(self):
        db = np.full(400, -20.0)
        kisalar = [(1.1, 1.3, "bas"), (3.0, 3.2, "bas")]  # ikincisinin yerinde metin "ııı" duymadı
        adaylar = davar.adaylari_cikar([], db, self.KELIMELER, kisalar=kisalar)
        self.assertEqual(len(adaylar), 1)
        self.assertTrue(adaylar[0]["kisa"])
        self.assertFalse(adaylar[0]["sec"])


class Altyazi(unittest.TestCase):
    def test_srt_zamani(self):
        self.assertEqual(analiz._srt_zaman(0), "00:00:00,000")
        self.assertEqual(analiz._srt_zaman(3723.4567), "01:02:03,457")
        self.assertEqual(analiz._srt_zaman(59.9996), "00:01:00,000")

    def test_satirlar_duraksamasiz_ve_cumle_sonunda_bolunur(self):
        kelimeler = [["Merhaba.", 0.0, 0.5], ["ııı", 0.6, 1.0], ["Bugün", 1.1, 1.4], ["Tuzla'dayız.", 1.4, 2.0]]
        satirlar = analiz._satirlara_bol(kelimeler)
        self.assertEqual([s[2] for s in satirlar], ["Merhaba.", "Bugün Tuzla'dayız."])
        self.assertEqual(satirlar[1][0], 1.1)


class SesEsleme(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rng = np.random.default_rng(6)
        cls.rng = rng
        cls.video = np.concatenate([np.concatenate((konusma(rng.uniform(1.5, 4), rng, ses.HIZ),
                                                    sessizlik(rng.uniform(0.3, 1.2), rng, ses.HIZ)))
                                    for _ in range(40)])

    def _baska_mikrofon(self, x):
        y = np.convolve(x, np.ones(5) / 5, mode="same") * 0.3
        return (y + self.rng.normal(0, 0.003, len(y))).astype(np.float32)

    def test_kisa_klibin_yeri_bulunur(self):
        bas = 41.237
        klip = self._baska_mikrofon(self.video[int(bas * ses.HIZ): int((bas + 12) * ses.HIZ)])
        k = ses.konum_bul(self.video, klip)
        self.assertAlmostEqual(k["kayma"], bas, delta=0.002)
        self.assertTrue(ses.eslesti_mi(k))

    def test_videodan_once_baslayan_kayit(self):
        klip = np.concatenate((sessizlik(5.5, self.rng, ses.HIZ), self._baska_mikrofon(self.video)))
        k = ses.konum_bul(self.video, klip)
        self.assertAlmostEqual(k["kayma"], -5.5, delta=0.002)
        self.assertTrue(ses.eslesti_mi(k))

    def test_ilgisiz_ses_eslesmez(self):
        baska = np.random.default_rng(99)
        klip = np.concatenate([np.concatenate((konusma(baska.uniform(1.5, 4), baska, ses.HIZ),
                                               sessizlik(baska.uniform(0.3, 1.2), baska, ses.HIZ)))
                               for _ in range(4)])
        self.assertFalse(ses.eslesti_mi(ses.konum_bul(self.video, klip)))


if __name__ == "__main__":
    unittest.main()
