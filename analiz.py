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
            return kayit
    return None


def _satirlara_bol(kelimeler, en_cok=70, en_uzun=6.0):
    """Kelimeleri altyazı satırlarına böler; "ııı / eee" gibi sesleri atar."""
    satirlar, simdiki = [], []
    for metin, bas, son in kelimeler:
        if davar.DOLGU_SES.match(davar.sade(metin)):
            continue
        if simdiki:
            uzunluk = sum(len(k[0]) + 1 for k in simdiki) + len(metin)
            if (uzunluk > en_cok or bas - simdiki[-1][2] > 0.7 or son - simdiki[0][1] > en_uzun
                    or simdiki[-1][0][-1:] in ".?!"):
                satirlar.append(simdiki)
                simdiki = []
        simdiki.append((metin, bas, son))
    if simdiki:
        satirlar.append(simdiki)
    return [(s[0][1], s[-1][2], " ".join(k[0] for k in s)) for s in satirlar]


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
        kayit["yol"] = yol

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
        "Not      : otomatik yazıldı; özel adları ve sayıları yayınlamadan önce denetle", "",
    ]
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
