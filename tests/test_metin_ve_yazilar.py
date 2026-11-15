"""Sözlüğü, metin düzeltmeyi ve KJ çizimini sınar. ffmpeg ya da video gerekmez."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import analiz  # noqa: E402
import sozluk  # noqa: E402
import yazilar  # noqa: E402

KELIMELER = [["Hâlâ", 5.0, 5.2], ["top", 5.2, 5.5], ["sen", 5.5, 5.7], ["de", 5.7, 5.8],
             ["Tuzda", 6.0, 6.4], ["siyasetinde", 6.4, 7.0], ["Bülent", 7.1, 7.4],
             ["Akbörse'nin,", 7.4, 8.0]]


class Sozluk(unittest.TestCase):
    def setUp(self):
        self.klasor = tempfile.TemporaryDirectory()
        self.yol = Path(self.klasor.name) / "alt" / "sozluk.txt"

    def tearDown(self):
        self.klasor.cleanup()

    def test_ekleme_ve_okuma(self):
        sozluk.sozluge_ekle([("tuzda", "Tuzla"), ("top sen", "TÜPSAN")], self.yol)
        sozluk.sozluge_ekle([("Tuzda", "Tuzla'da")], self.yol)  # aynı anahtar güncellenir
        girdiler = sozluk.sozluk_yukle(self.yol)
        self.assertEqual(girdiler, [(("top", "sen"), "TÜPSAN"), (("tuzda",), "Tuzla'da")])

    def test_olmayan_dosya_bos_sozluk(self):
        self.assertEqual(sozluk.sozluk_yukle(self.yol), [])
        yeni, adet = sozluk.uygula(KELIMELER, [])
        self.assertEqual((yeni, adet), (KELIMELER, 0))

    def test_ek_ve_noktalama_korunur_ifadeler_birlesir(self):
        girdiler = [(("top", "sen"), "TÜPSAN"), (("tuzda",), "Tuzla"), (("akbörse",), "Akköse")]
        yeni, adet = sozluk.uygula(KELIMELER, girdiler)
        self.assertEqual(adet, 3)
        self.assertEqual([k[0] for k in yeni],
                         ["Hâlâ", "TÜPSAN", "de", "Tuzla", "siyasetinde", "Bülent", "Akköse'nin,"])
        self.assertEqual(yeni[1][1:], [5.2, 5.7])  # iki kelimenin süresi birleşti
        self.assertEqual(KELIMELER[1][0], "top", "asıl liste değişmemeli")


class MetinDuzeltme(unittest.TestCase):
    def test_ayni_sayida_kelime_zamanlari_korur(self):
        grup = analiz.satir_gruplari(KELIMELER)[0]
        metin = " ".join(KELIMELER[i][0] for i in grup).replace("Tuzda", "Tuzla")
        yeni, duzeltmeler = analiz.satiri_degistir(KELIMELER, grup, metin)
        self.assertEqual(duzeltmeler, [("Tuzda", "Tuzla")])
        self.assertEqual(yeni[4], ["Tuzla", 6.0, 6.4])
        self.assertEqual(KELIMELER[4][0], "Tuzda", "asıl liste değişmemeli")

    def test_kelime_sayisi_degisince_sure_paylastirilir(self):
        grup = analiz.satir_gruplari(KELIMELER)[0]
        yeni, duzeltmeler = analiz.satiri_degistir(KELIMELER, grup, "Hâlâ orada")
        self.assertEqual(duzeltmeler, [])
        self.assertEqual([k[0] for k in yeni], ["Hâlâ", "orada"])
        self.assertEqual((yeni[0][1], yeni[-1][2]), (5.0, 8.0))
        self.assertAlmostEqual(yeni[0][2], yeni[1][1])

    def test_duraksamalar_satira_girmez_ama_listede_kalir(self):
        kelimeler = [["Evet.", 0.0, 0.4], ["ııı", 0.5, 1.0], ["Tamam", 1.1, 1.5]]
        gruplar = analiz.satir_gruplari(kelimeler)
        self.assertEqual(gruplar, [[0], [2]])
        yeni, _ = analiz.satiri_degistir(kelimeler, gruplar[1], "Tamam mı")
        self.assertEqual([k[0] for k in yeni], ["Evet.", "ııı", "Tamam", "mı"])


class KJ(unittest.TestCase):
    def test_renk_okuma(self):
        self.assertEqual(yazilar.renk_oku("#E30613"), (227, 6, 19))
        self.assertEqual(yazilar.renk_oku("0a0B0c"), (10, 11, 12))
        with self.assertRaises(yazilar.Hata):
            yazilar.renk_oku("kırmızı")

    def test_cizim_ekrana_sigar_ve_olceklenir(self):
        for konum in yazilar.KONUMLAR:
            resim, x, y, serit = yazilar.kj_ciz("Çok Uzun Bir Konuşmacı Adı Soyadı Örneği Burada",
                                                "Unvan", 1920, 1080, konum=konum)
            self.assertGreaterEqual(x, 0)
            self.assertLessEqual(x + resim.width, 1920)
            self.assertLess(y + resim.height, 1080)
        buyuk = yazilar.kj_ciz("Ad Soyad", "Unvan", 3840, 2160)[0]
        kucuk = yazilar.kj_ciz("Ad Soyad", "Unvan", 1920, 1080)[0]
        self.assertAlmostEqual(buyuk.height / kucuk.height, 2.0, delta=0.1)

    def test_unvansiz_kj_daha_alcak(self):
        tam = yazilar.kj_ciz("Ad Soyad", "Unvan", 1920, 1080)[0]
        yalniz_ad = yazilar.kj_ciz("Ad Soyad", "", 1920, 1080)[0]
        self.assertLess(yalniz_ad.height, tam.height)

    def test_giris_ve_cikis_yumusak(self):
        tam, _, _, serit = yazilar.kj_ciz("Ad Soyad", "Unvan", 1920, 1080)

        dolu = sum(tam.getchannel("A").histogram()[1:])  # KJ'nin tam açıkken kapladığı alan

        def gorunurluk(zaman):  # o anda görünen alanın tam hâle oranı
            alfa = yazilar.kj_karesi(tam, serit, zaman, 6.0).getchannel("A")
            return sum(alfa.histogram()[1:]) / dolu

        self.assertEqual(gorunurluk(0.0), 0.0)
        self.assertLess(gorunurluk(0.2), gorunurluk(0.4))
        self.assertAlmostEqual(gorunurluk(3.0), 1.0, delta=0.01)
        orta = yazilar.kj_karesi(tam, serit, 3.0, 6.0).getchannel("A").getextrema()[1]
        cikis = yazilar.kj_karesi(tam, serit, 5.8, 6.0).getchannel("A").getextrema()[1]
        self.assertEqual(orta, 255)
        self.assertLess(cikis, 255 * 0.6)
        self.assertEqual(yazilar.kj_karesi(tam, serit, 6.0, 6.0).getchannel("A").getextrema()[1], 0)


if __name__ == "__main__":
    unittest.main()
