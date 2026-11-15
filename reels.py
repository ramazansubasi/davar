"""davar reels - yatay bir videodan, seçilen zaman aralığını dikey (9:16)
Reels / Shorts videosu olarak keser.

Bulanık arka plan üstüne konuşmacı kadrajı, üstte kısa bir yazı ve başlık,
isteğe bağlı altyazı (konuşmadan otomatik) ve giriş kapağı ekler.

    python reels.py "video.mp4" 13:06 13:56 --baslik "TUZLA'DA TRAFİK" --altyazi
"""

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

import davar
from davar import Hata

EN, BOY = 1080, 1920
KADRAJ_Y, KADRAJ_BOY = 340, 1440  # konuşmacı penceresinin dikey yeri ve boyu
KAPAK_SURESI = 2.5
VURGU = (227, 6, 19)  # üst yazı rengi
KAPAK_ZEMIN = (92, 6, 16)
KAPAK_UST = (255, 120, 128)
YAZI_TIPLERI = [
    "C:/Windows/Fonts/arialbd.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
]


def zaman_oku(metin):
    """ "13:06", "1:02:03.5" ya da "786.4" biçimindeki zamanı saniyeye çevirir."""
    metin = str(metin).strip().replace(",", ".")
    if not re.fullmatch(r"\d+(\.\d+)?(:\d+(\.\d+)?){0,2}", metin):
        raise Hata(f"zaman anlaşılmadı: “{metin}”. Örnek: 13:06 ya da 1:02:03")
    saniye = 0.0
    for parca in metin.split(":"):
        saniye = saniye * 60 + float(parca)
    return saniye


def _yazi_tipi(boyut):
    from PIL import ImageFont
    for yol in YAZI_TIPLERI:
        if Path(yol).is_file():
            return ImageFont.truetype(yol, boyut)
    return ImageFont.load_default(boyut)


def _ortala(ciz, y, metin, boyut, renk, en_cok=EN - 80):
    """Metni yatayda ortalayarak yazar; sığmıyorsa küçültür. Alt kenarın y'sini döndürür."""
    while True:
        tip = _yazi_tipi(boyut)
        sol, ust, sag, alt = ciz.textbbox((0, 0), metin, font=tip)
        if sag - sol <= en_cok or boyut <= 20:
            break
        boyut -= 2
    ciz.text(((EN - (sag - sol)) / 2 - sol, y), metin, font=tip, fill=renk)
    return y + int(boyut * 1.22)


def _yazi_katmani(yol, ust_yazi, baslik):
    """Videonun üstüne binen saydam katman: üst yazı ve başlık."""
    from PIL import Image, ImageDraw
    resim = Image.new("RGBA", (EN, BOY), (0, 0, 0, 0))
    ciz = ImageDraw.Draw(resim)
    y = 96
    if ust_yazi:
        y = _ortala(ciz, y, ust_yazi, 34, VURGU + (255,)) + 18
    for satir in baslik[:2]:
        y = _ortala(ciz, y, satir, 70, (255, 255, 255, 255))
    resim.save(yol)


def _kapak(yol, ust_yazi, baslik):
    """Videonun başına eklenen duyuru kapağı."""
    from PIL import Image, ImageDraw
    resim = Image.new("RGB", (EN, BOY), KAPAK_ZEMIN)
    ciz = ImageDraw.Draw(resim)
    ciz.rectangle((0, 0, EN, 14), fill=VURGU)
    satirlar = [s for s in baslik[:2] if s]
    y = BOY // 2 - (len(satirlar) * 130 + (114 if ust_yazi else 0)) // 2
    if ust_yazi:
        y = _ortala(ciz, y, ust_yazi, 44, KAPAK_UST) + 60
    ciz.rectangle((EN // 2 - 60, y - 34, EN // 2 + 60, y - 28), fill=VURGU)
    for satir in satirlar:
        y = _ortala(ciz, y, satir, 104, (255, 255, 255))
    resim.save(yol)


def _ass_zaman(t):
    saat, kalan = divmod(max(t, 0), 3600)
    dakika, saniye = divmod(kalan, 60)
    return f"{int(saat)}:{int(dakika):02d}:{saniye:05.2f}"


def _altyazi_yaz(yol, kelimeler):
    """Kelimeleri (metin, başlangıç, bitiş) kısa satırlara böler ve ASS dosyası yazar."""
    satirlar, simdiki = [], []
    for metin, bas, son in kelimeler:
        if simdiki:
            uzunluk = sum(len(k[0]) + 1 for k in simdiki) + len(metin)
            if (uzunluk > 36 or bas - simdiki[-1][2] > 0.6 or son - simdiki[0][1] > 3.5
                    or simdiki[-1][0][-1:] in ".?!"):
                satirlar.append(simdiki)
                simdiki = []
        simdiki.append((metin, bas, son))
    if simdiki:
        satirlar.append(simdiki)

    cikti = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {EN}", f"PlayResY: {BOY}",
        "WrapStyle: 0", "", "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Alt,Arial,54,&H00FFFFFF,&H00FFFFFF,&H00100C0C,&H00100C0C,-1,0,0,0,100,100,"
        "0,0,3,14,0,2,80,80,470,1",
        "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for i, satir in enumerate(satirlar):
        bas, son = satir[0][1], satir[-1][2]
        if i + 1 < len(satirlar):  # sonraki satıra taşmasın
            son = min(max(son, bas + 0.8), satirlar[i + 1][0][1])
        metin = " ".join(k[0] for k in satir).replace("{", "(").replace("}", ")")
        cikti.append(f"Dialogue: 0,{_ass_zaman(bas)},{_ass_zaman(son)},Alt,,0,0,0,,{metin}")
    Path(yol).write_text("\n".join(cikti) + "\n", encoding="utf-8")
    return len(satirlar)


def _yaziya_dok(video, bas, sure, dil):
    """Seçilen aralıktaki konuşmayı kelime zamanlarıyla yazıya döker."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise Hata("altyazı için faster-whisper gerekli. Kurmak için: pip install faster-whisper")
    ham = davar.calistir([
        "ffmpeg", "-v", "error", "-ss", f"{bas:.3f}", "-t", f"{sure:.3f}", "-i", str(video),
        "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-",
    ])
    ses = np.frombuffer(ham, dtype=np.int16).astype(np.float32) / 32768.0
    model = WhisperModel("small", device="cpu", compute_type="int8")
    parcalar, _ = model.transcribe(ses, language=dil, word_timestamps=True,
                                   vad_filter=True, beam_size=3)
    kelimeler = []
    for parca in parcalar:
        for k in parca.words:
            metin = k.word.strip()
            if not metin:
                continue
            # "10" + ".000" ya da "Tuzla" + "'da" gibi bölünmüş parçaları birleştir
            if kelimeler and not metin[0].isalnum():
                onceki = kelimeler[-1]
                kelimeler[-1] = (onceki[0] + metin, onceki[1], k.end)
            else:
                kelimeler.append((metin, k.start, k.end))
    return kelimeler


def reels_kes(video, bas, son, cikti=None, ust_yazi="", baslik=(), yatay=0.5,
              altyazi=False, kapak=False, dil="tr", kelimeler=None, ilerleme=None):
    """Aralığı dikey video olarak keser; çıktı dosyasının bilgilerini döndürür.

    `yatay`: konuşmacı kadrajının yatay yeri, 0 (sol) - 1 (sağ).
    `kelimeler`: İlk Analiz'in (metin, başlangıç, bitiş) listesi; verilirse altyazı
    için yeniden yazıya dökülmez.
    """
    def adim(yuzde, metin):
        if ilerleme:
            ilerleme(yuzde, metin)

    try:
        import PIL  # noqa: F401
    except ImportError:
        raise Hata("Reels kesici için Pillow gerekli. Kurmak için: pip install pillow")

    video = Path(video)
    if not video.is_file():
        raise Hata(f"dosya bulunamadı: {video}")
    bas, son = zaman_oku(bas), zaman_oku(son)
    adim(2, "Video bilgileri okunuyor")
    bilgi = davar.video_bilgisi(video)
    son = min(son, bilgi["sure"])
    sure = son - bas
    if sure < 1:
        raise Hata("bitiş zamanı başlangıçtan en az 1 saniye sonra olmalı.")
    baslik = [s.strip() for s in baslik if s and s.strip()]
    ust_yazi = ust_yazi.strip()
    if kapak and not (baslik or ust_yazi):
        raise Hata("giriş kapağı için başlık ya da üst yazı gerekli.")
    cikti = Path(cikti) if cikti else video.with_name(video.stem + "_reels.mp4")

    # konuşmacı kadrajı: kaynaktan alınabilecek en büyük 3:4 parça
    g, y = bilgi["genislik"], bilgi["yukseklik"]
    k_en = min(g, int(y * 3 / 4)) // 2 * 2
    k_boy = min(y, int(k_en * 4 / 3)) // 2 * 2
    k_x = int((g - k_en) * min(max(yatay, 0.0), 1.0))
    k_y = (y - k_boy) // 2

    with tempfile.TemporaryDirectory(prefix="davar_") as gecici:
        gecici = Path(gecici)
        girdiler = ["-ss", f"{bas:.3f}", "-t", f"{sure:.3f}", "-i", str(video.resolve())]
        zincir = (
            "[0:v]split[a][b];"
            f"[a]scale={EN}:{BOY}:force_original_aspect_ratio=increase,crop={EN}:{BOY},"
            "boxblur=24:4,eq=brightness=-0.22[bg];"
            f"[b]crop={k_en}:{k_boy}:{k_x}:{k_y},scale={EN}:{KADRAJ_BOY}[fg];"
            f"[bg][fg]overlay=0:{KADRAJ_Y}"
        )
        sira = 1
        if baslik or ust_yazi:
            _yazi_katmani(gecici / "yazi.png", ust_yazi, baslik)
            girdiler += ["-i", "yazi.png"]
            zincir += f"[k];[k][{sira}:v]overlay=0:0"
            sira += 1
        satir_sayisi = 0
        if altyazi:
            if kelimeler:  # videonun tamamına ait zamanları bu aralığa taşı
                kelimeler = [(k[0], k[1] - bas, k[2] - bas) for k in kelimeler
                             if k[1] >= bas - 0.05 and k[2] <= son + 0.05
                             and not davar.DOLGU_SES.match(davar.sade(k[0]))]
            else:
                adim(5, "Konuşma yazıya dökülüyor (ilk seferde model indirilir)")
                kelimeler = _yaziya_dok(video, bas, sure, dil)
            if kelimeler:
                satir_sayisi = _altyazi_yaz(gecici / "alt.ass", kelimeler)
                zincir += ",subtitles=alt.ass"
        zincir += ",fps=30,format=yuv420p,setsar=1[v0];"
        ses = (f"[0:a]loudnorm=I=-14:TP=-1.5:LRA=11,afade=t=in:d=0.05,"
               f"afade=t=out:st={sure - 0.15:.3f}:d=0.1")
        toplam = sure
        if kapak:
            _kapak(gecici / "kapak.png", ust_yazi, baslik)
            girdiler += ["-loop", "1", "-framerate", "30", "-t", str(KAPAK_SURESI), "-i", "kapak.png"]
            zincir += (f"[{sira}:v]fps=30,format=yuv420p,setsar=1[v1];"
                       "[v1][v0]concat=n=2:v=1:a=0[v];")
            ses += f",adelay={int(KAPAK_SURESI * 1000)}:all=1"
            toplam += KAPAK_SURESI
        else:
            zincir += "[v0]null[v];"
        zincir += ses + "[au]"
        (gecici / "filtre.txt").write_text(zincir, encoding="utf-8")

        komut = ["ffmpeg", "-v", "error", "-y", *girdiler, "-/filter_complex", "filtre.txt",
                 "-map", "[v]", "-map", "[au]", "-c:v", "libx264", "-preset", "medium",
                 "-crf", "20", "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
                 "-movflags", "+faststart", "-progress", "pipe:1", "-nostats",
                 str(cikti.resolve())]
        adim(30 if altyazi else 5, "Video hazırlanıyor")
        gizli = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        try:
            surec = subprocess.Popen(komut, cwd=gecici, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, creationflags=gizli)
        except FileNotFoundError:
            raise Hata("ffmpeg bulunamadı. ffmpeg kurulu ve PATH'te olmalı.")
        taban = 30 if altyazi else 5
        for satir in surec.stdout:
            es = re.match(rb"out_time_us=(\d+)", satir)
            if es:
                oran = min(int(es.group(1)) / 1e6 / toplam, 1.0)
                adim(taban + (99 - taban) * oran, "Video hazırlanıyor")
        hata = surec.stderr.read().decode("utf-8", "replace").strip()
        if surec.wait() != 0:
            raise Hata("ffmpeg videoyu hazırlayamadı:\n" + hata[-600:])

    adim(100, "Bitti")
    return {"cikti": cikti, "sure": toplam, "bas": bas, "son": son,
            "altyazi_satiri": satir_sayisi, "altyazi": altyazi, "kapak": kapak}


def rapor(s):
    satir = [
        f"Aralık   : {davar.sure_yaz(s['bas'])} - {davar.sure_yaz(s['son'])}",
        f"Video    : {EN}x{BOY}, {s['sure']:.1f} sn" + ("  (giriş kapağı dahil)" if s["kapak"] else ""),
    ]
    if s["altyazi"]:
        satir.append(f"Altyazı  : {s['altyazi_satiri']} satır (otomatik; yayınlamadan önce oku)"
                     if s["altyazi_satiri"] else "Altyazı  : konuşma bulunamadı, eklenmedi")
    satir.append(f"\nVideo yazıldı: {s['cikti']}")
    return "\n".join(satir)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Videodan dikey Reels / Shorts keser.")
    p.add_argument("video", type=Path)
    p.add_argument("bas", help="başlangıç zamanı (örn. 13:06)")
    p.add_argument("son", help="bitiş zamanı (örn. 13:56)")
    p.add_argument("--ust-yazi", default="", help="başlığın üstündeki kısa yazı")
    p.add_argument("--baslik", action="append", default=[],
                   help="başlık satırı (iki satır için iki kez yaz)")
    p.add_argument("--yatay", type=float, default=0.5,
                   help="kadrajın yatay yeri: 0 sol, 0.5 orta, 1 sağ (varsayılan 0.5)")
    p.add_argument("--altyazi", action="store_true", help="konuşmadan otomatik altyazı ekle")
    p.add_argument("--kapak", action="store_true", help="başa 2.5 saniyelik giriş kapağı ekle")
    p.add_argument("--dil", default="tr", help="konuşma dili (varsayılan tr)")
    p.add_argument("--cikti", type=Path, default=None,
                   help="çıktı dosyası (varsayılan: videonun yanına <ad>_reels.mp4)")
    a = p.parse_args()
    try:
        sonuc = reels_kes(a.video, a.bas, a.son, cikti=a.cikti, ust_yazi=a.ust_yazi,
                          baslik=a.baslik, yatay=a.yatay, altyazi=a.altyazi, kapak=a.kapak,
                          dil=a.dil)
    except Hata as h:
        sys.exit(f"HATA: {h}")
    print(rapor(sonuc))


if __name__ == "__main__":
    main()
