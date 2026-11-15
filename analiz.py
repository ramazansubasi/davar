"""davar ilk analiz - videodaki konuşmayı bir kez, kelime zamanlarıyla yazıya döker.

Sonuç videonun yanına <video>.davar.json olarak kaydedilir; diğer iş akışları
(Kaba Kurgu, Sosyal Klipler) yeniden yazıya dökmek yerine bu dosyayı okur.
İstenirse YouTube altyazısı (.srt) ve zaman damgalı metin (.txt) de yazar.

    python analiz.py "video.mp4" --srt --metin
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

import davar
import sozluk
from davar import Hata

SURUM = 1
# Whisper duraksamaları çoğu zaman yazmaz; bu ipucu "ııı / eee"yi de yazmasını sağlar.
# Böylece sesten bulunan duraksamalar metinle karşılaştırılabilir.
IPUCU = "ııı eee ıı ee hmm"


def analiz_yolu(video, klasor=None):
    video = Path(video)
    return (Path(klasor) if klasor else video.parent) / (video.stem + ".davar.json")


def _kimlik(video):
    bilgi = Path(video).stat()
    return {"ad": Path(video).name, "boyut": bilgi.st_size, "degisim": int(bilgi.st_mtime)}


def analiz_yukle(video, klasor=None):
    """Kayıtlı İlk Analiz'i döndürür; yoksa ya da başka bir videoya aitse None."""
    video = Path(video)
    if not video.is_file():
        return None
    for yol in {analiz_yolu(video, klasor), analiz_yolu(video)}:
        try:
            kayit = json.loads(yol.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if kayit.get("surum") == SURUM and kayit.get("video") == _kimlik(video):
            kayit["yol"] = yol
            # kişisel sözlük her okunuşta uygulanır; dosyadaki ham metin değişmez
            kayit["kelimeler"], kayit["duzeltme"] = sozluk.uygula(kayit["kelimeler"])
            return kayit
    return None


def analiz_kaydet(kayit):
    """Düzeltilmiş kelimeleri analiz dosyasına geri yazar."""
    yazilacak = {k: v for k, v in kayit.items() if k not in ("yol", "duzeltme")}
    Path(kayit["yol"]).write_text(json.dumps(yazilacak, ensure_ascii=False), encoding="utf-8")


def satir_gruplari(kelimeler, en_cok=70, en_uzun=6.0):
    """Kelimeleri altyazı satırlarına böler; her satır kelime sıra numaralarının listesidir.

    "ııı / eee" gibi sesler hiçbir satıra girmez.
    """
    satirlar, simdiki = [], []
    for i, (metin, bas, son) in enumerate(kelimeler):
        if davar.DOLGU_SES.match(davar.sade(metin)):
            continue
        if simdiki:
            ilk, onceki = kelimeler[simdiki[0]], kelimeler[simdiki[-1]]
            uzunluk = sum(len(kelimeler[j][0]) + 1 for j in simdiki) + len(metin)
            if (uzunluk > en_cok or bas - onceki[2] > 0.7 or son - ilk[1] > en_uzun
                    or onceki[0][-1:] in ".?!"):
                satirlar.append(simdiki)
                simdiki = []
        simdiki.append(i)
    if simdiki:
        satirlar.append(simdiki)
    return satirlar


def satiri_degistir(kelimeler, sira_listesi, yeni_metin):
    """Bir satırın metnini değiştirir; (yeni kelime listesi, [(eski, yeni)] tek kelimelik düzeltmeler).

    Kelime sayısı aynıysa zamanlar korunur. Değiştiyse satırın süresi yeni kelimelere
    uzunluklarıyla orantılı paylaştırılır.
    """
    yeni = yeni_metin.split()
    eski = [kelimeler[i] for i in sira_listesi]
    kelimeler = [list(k) for k in kelimeler]
    duzeltmeler = []
    if len(yeni) == len(eski):
        for i, y in zip(sira_listesi, yeni):
            if davar.sade(kelimeler[i][0]) != davar.sade(y) and davar.sade(y):
                duzeltmeler.append((sozluk._parcala(kelimeler[i][0])[0], sozluk._parcala(y)[0]))
            kelimeler[i][0] = y
        return kelimeler, duzeltmeler
    bas, son = eski[0][1], eski[-1][2]
    silinecek = set(sira_listesi)
    kalan = [k for i, k in enumerate(kelimeler) if i not in silinecek]
    toplam = sum(len(y) + 1 for y in yeni) or 1
    t = bas
    for y in yeni:
        sure = (son - bas) * (len(y) + 1) / toplam
        kalan.append([y, round(t, 2), round(t + sure, 2)])
        t += sure
    return sorted(kalan, key=lambda k: k[1]), duzeltmeler


def _satirlara_bol(kelimeler, en_cok=70, en_uzun=6.0):
    """Kelimeleri (başlangıç, bitiş, metin) altyazı satırlarına çevirir."""
    return [(kelimeler[g[0]][1], kelimeler[g[-1]][2], " ".join(kelimeler[i][0] for i in g))
            for g in satir_gruplari(kelimeler, en_cok, en_uzun)]


def _srt_zaman(t):
    ms = int(round(max(t, 0) * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def srt_yaz(kayit, yol):
    satirlar = _satirlara_bol(kayit["kelimeler"])
    Path(yol).write_text("".join(
        f"{i}\n{_srt_zaman(b)} --> {_srt_zaman(s)}\n{m}\n\n"
        for i, (b, s, m) in enumerate(satirlar, 1)), encoding="utf-8")
    return len(satirlar)


def metin_yaz(kayit, yol):
    satirlar = _satirlara_bol(kayit["kelimeler"], en_cok=110, en_uzun=12.0)
    Path(yol).write_text("".join(
        f"[{int(b // 60):02d}:{int(b % 60):02d}] {m}\n" for b, _, m in satirlar), encoding="utf-8")
    return len(satirlar)


def ilk_analiz(video, klasor=None, srt=False, metin=False, dil="tr", model="small",
               yeniden=False, ilerleme=None):
    """Konuşmayı yazıya döker ve kaydeder. Geçerli bir kayıt varsa onu kullanır."""
    def adim(yuzde, aciklama):
        if ilerleme:
            ilerleme(yuzde, aciklama)

    video = Path(video)
    if not video.is_file():
        raise Hata(f"dosya bulunamadı: {video}")
    kayit = None if yeniden else analiz_yukle(video, klasor)
    hazirdi = kayit is not None
    if kayit is None:
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise Hata("yazıya dökme için faster-whisper gerekli. Kurmak için: pip install faster-whisper")
        adim(2, "Ses çıkarılıyor")
        ham = davar.calistir(["ffmpeg", "-v", "error", "-i", str(video), "-vn", "-ac", "1",
                              "-ar", "16000", "-f", "s16le", "-"])
        ses = np.frombuffer(ham, dtype=np.int16).astype(np.float32) / 32768.0
        sure = len(ses) / 16000
        if sure < 1:
            raise Hata("videoda ses bulunamadı.")
        adim(4, "Model yükleniyor (ilk seferde internetten indirilir)")
        whisper = WhisperModel(model, device="cpu", compute_type="int8")
        parcalar, _ = whisper.transcribe(ses, language=dil, vad_filter=True, beam_size=3,
                                         word_timestamps=True, hotwords=IPUCU)
        kelimeler = []
        for parca in parcalar:  # parçalar geldikçe ilerleme güncellenir
            for k in parca.words or []:
                yazi = k.word.strip()
                if not yazi:
                    continue
                # "10" + ".000" ya da "Tuzla" + "'da" gibi bölünmüş parçaları birleştir
                if kelimeler and not yazi[0].isalnum():
                    kelimeler[-1] = [kelimeler[-1][0] + yazi, kelimeler[-1][1], round(k.end, 2)]
                else:
                    kelimeler.append([yazi, round(k.start, 2), round(k.end, 2)])
            adim(4 + 94 * min(parca.end / sure, 1.0),
                 f"Yazıya dökülüyor ({davar.sure_yaz(parca.end)} / {davar.sure_yaz(sure)})")
        if not kelimeler:
            raise Hata("konuşma bulunamadı.")
        kayit = {"surum": SURUM, "video": _kimlik(video), "dil": dil, "model": model,
                 "sure": round(sure, 2), "kelimeler": kelimeler}
        yol = analiz_yolu(video, klasor)
        yol.write_text(json.dumps(kayit, ensure_ascii=False), encoding="utf-8")
        kayit = analiz_yukle(video, klasor)  # kişisel sözlük uygulanmış hâliyle

    dosyalar = [kayit["yol"]]
    hedef = Path(klasor) if klasor else video.parent
    if srt:
        srt_yaz(kayit, hedef / (video.stem + ".srt"))
        dosyalar.append(hedef / (video.stem + ".srt"))
    if metin:
        metin_yaz(kayit, hedef / (video.stem + "_metin.txt"))
        dosyalar.append(hedef / (video.stem + "_metin.txt"))
    adim(100, "Bitti")
    return {"cikti": dosyalar[-1], "dosyalar": dosyalar, "kayit": kayit, "hazirdi": hazirdi}


def rapor(s):
    kayit = s["kayit"]
    dolgu = sum(1 for k in kayit["kelimeler"] if davar.DOLGU_SES.match(davar.sade(k[0])))
    satir = [
        f"Konuşma  : {davar.sure_yaz(kayit['sure'])}, {len(kayit['kelimeler'])} kelime "
        f"({dolgu} tanesi ııı / eee), model {kayit['model']}"
        + ("  — kayıtlı analiz kullanıldı" if s["hazirdi"] else ""),
        "Not      : otomatik yazıldı; özel adları ve sayıları yayınlamadan önce denetle",
    ]
    if kayit.get("duzeltme"):
        satir.append(f"Sözlük   : {kayit['duzeltme']} kelime kişisel sözlüğe göre düzeltildi")
    satir.append("")
    return "\n".join(satir + [f"Yazıldı: {d}" for d in s["dosyalar"]])


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Videodaki konuşmayı kelime zamanlarıyla yazıya döker.")
    p.add_argument("video", type=Path)
    p.add_argument("--klasor", type=Path, default=None, help="çıktı klasörü (varsayılan: videonun yanı)")
    p.add_argument("--srt", action="store_true", help="YouTube altyazısı (.srt) de yaz")
    p.add_argument("--metin", action="store_true", help="zaman damgalı metin (.txt) de yaz")
    p.add_argument("--dil", default="tr", help="konuşma dili (varsayılan tr)")
    p.add_argument("--model", default="small", help="Whisper modeli: base, small, medium (varsayılan small)")
    p.add_argument("--yeniden", action="store_true", help="kayıtlı analiz olsa da baştan yazıya dök")
    a = p.parse_args()
    try:
        sonuc = ilk_analiz(a.video, klasor=a.klasor, srt=a.srt, metin=a.metin, dil=a.dil,
                           model=a.model, yeniden=a.yeniden,
                           ilerleme=lambda y, m: print(f"\r{y:5.1f}%  {m}      ", end="", file=sys.stderr))
    except Hata as h:
        sys.exit(f"\nHATA: {h}")
    print("\n" + rapor(sonuc))


if __name__ == "__main__":
    main()
