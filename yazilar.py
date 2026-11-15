"""davar yazılar - konuşmacı adı ve unvanı için KJ (alt bant) üretir.

Sonuç saydam zeminli, girişi ve çıkışı yumuşak bir videodur (ProRes 4444).
DaVinci Resolve'da videonun üstündeki şeride sürüklenir; ayrıca efekt gerekmez.

    python yazilar.py "Halil Özen" "Gazeteci" --video "bolum.mp4"
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

import davar
from davar import Hata

YAZI_TIPLERI = {
    "kalin": ["C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf",
              "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    "duz": ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
}
KONUMLAR = ("sol", "orta", "sag")
ZEMIN = (14, 18, 26, 225)  # ad bandının rengi (hafif saydam koyu)
GIRIS, CIKIS = 0.5, 0.4  # saniye


def renk_oku(metin):
    """ "#E30613" ya da "E30613" biçimindeki rengi (r, g, b) yapar."""
    es = re.fullmatch(r"#?([0-9a-fA-F]{6})", metin.strip())
    if not es:
        raise Hata(f"renk anlaşılmadı: “{metin}”. Örnek: #E30613")
    return tuple(int(es.group(1)[i:i + 2], 16) for i in (0, 2, 4))


def _yazi_tipi(tur, boyut):
    from PIL import ImageFont
    for yol in YAZI_TIPLERI[tur]:
        if Path(yol).is_file():
            return ImageFont.truetype(yol, boyut)
    return ImageFont.load_default(boyut)


def kj_ciz(ad, unvan, genislik, yukseklik, renk=(227, 6, 19), konum="sol"):
    """KJ'nin tam görünür hâlini ve yerini döndürür: (resim, x, y, şerit eni).

    Resim yalnızca KJ'nin kapladığı alan kadardır; solunda vurgu şeridi,
    üstte ad bandı, altında (varsa) unvan bandı bulunur.
    """
    from PIL import Image, ImageDraw
    o = yukseklik / 1080  # bütün ölçüler 1080 satıra göre verilir
    ad_tipi, unvan_tipi = _yazi_tipi("kalin", round(50 * o)), _yazi_tipi("duz", round(30 * o))
    olc = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    ic, serit = round(26 * o), round(10 * o)
    en_cok = int(genislik * 0.7)

    def sigdir(metin, tip, tur, boyut):
        while olc.textlength(metin, font=tip) > en_cok and boyut > 14:
            boyut -= 2
            tip = _yazi_tipi(tur, boyut)
        return tip

    ad_tipi = sigdir(ad, ad_tipi, "kalin", round(50 * o))
    ad_boy = round(ad_tipi.size * 1.62)
    ad_en = round(olc.textlength(ad, font=ad_tipi)) + 2 * ic
    unvan_boy = unvan_en = 0
    if unvan:
        unvan_tipi = sigdir(unvan, unvan_tipi, "duz", round(30 * o))
        unvan_boy = round(unvan_tipi.size * 1.75)
        unvan_en = round(olc.textlength(unvan, font=unvan_tipi)) + 2 * ic

    en, boy = serit + max(ad_en, unvan_en), ad_boy + unvan_boy
    resim = Image.new("RGBA", (en, boy), (0, 0, 0, 0))
    ciz = ImageDraw.Draw(resim)
    ciz.rectangle((0, 0, serit - 1, boy - 1), fill=renk + (255,))
    ciz.rectangle((serit, 0, serit + ad_en - 1, ad_boy - 1), fill=ZEMIN)
    ciz.text((serit + ic, ad_boy / 2), ad, font=ad_tipi, fill=(255, 255, 255, 255), anchor="lm")
    if unvan:
        ciz.rectangle((serit, ad_boy, serit + unvan_en - 1, boy - 1), fill=renk + (255,))
        ciz.text((serit + ic, ad_boy + unvan_boy / 2), unvan, font=unvan_tipi,
                 fill=(255, 255, 255, 255), anchor="lm")

    kenar = round(genislik * 0.06)
    x = {"sol": kenar, "orta": (genislik - en) // 2, "sag": genislik - en - kenar}[konum]
    return resim, x, yukseklik - boy - round(yukseklik * 0.12), serit


def _yumusak(t):
    """0-1 arası ilerlemeyi yavaşlayarak biten harekete çevirir."""
    t = min(max(t, 0.0), 1.0)
    return 1 - (1 - t) ** 3


def kj_karesi(tam, serit, zaman, sure):
    """KJ'nin verilen andaki görünümü: soldan açılarak girer, solarak çıkar."""
    from PIL import Image
    en, boy = tam.size
    acilma = _yumusak((zaman - 0.12) / (GIRIS - 0.12))  # önce şerit, sonra bantlar açılır
    serit_boyu = _yumusak(zaman / 0.22)
    kare = Image.new("RGBA", (en, boy), (0, 0, 0, 0))
    s = round(boy * serit_boyu)
    if s > 0:
        kare.paste(tam.crop((0, boy - s, serit, boy)), (0, boy - s))
    g = round((en - serit) * acilma)
    if g > 0:
        kare.paste(tam.crop((serit, 0, serit + g, boy)), (serit, 0))
    kalan = sure - zaman
    if kalan < CIKIS:  # çıkışta bütünüyle solar
        saydamlik = kare.getchannel("A").point(lambda a: int(a * max(kalan, 0) / CIKIS))
        kare.putalpha(saydamlik)
    return kare


def kj_uret(ad, unvan="", video=None, klasor=None, sure=6.0, renk="#E30613", konum="sol",
            genislik=1920, yukseklik=1080, fps=30.0, ilerleme=None):
    """Saydam zeminli KJ videosunu yazar. Video verilirse boyutu ve kare hızı ondan alınır."""
    try:
        from PIL import Image
    except ImportError:
        raise Hata("KJ üretmek için Pillow gerekli. Kurmak için: pip install pillow")
    ad, unvan = ad.strip(), unvan.strip()
    if not ad:
        raise Hata("KJ için en az bir ad yazılmalı.")
    if konum not in KONUMLAR:
        raise Hata(f"konum {', '.join(KONUMLAR)} olabilir.")
    if not 2.0 <= sure <= 60.0:
        raise Hata("KJ süresi 2 ile 60 saniye arasında olmalı.")
    rgb = renk_oku(renk) if isinstance(renk, str) else tuple(renk)
    hiz = f"{fps:.3f}"
    if video:
        bilgi = davar.video_bilgisi(video)
        genislik, yukseklik, fps = bilgi["genislik"], bilgi["yukseklik"], float(bilgi["fps"])
        hiz = f"{bilgi['fps'].numerator}/{bilgi['fps'].denominator}"
    hedef = Path(klasor) if klasor else (Path(video).parent if video else Path.cwd())
    if not hedef.is_dir():
        raise Hata(f"çıktı klasörü bulunamadı: {hedef}")
    # dosya adı yalnızca ASCII: her programda sorunsuz açılsın
    dosya_adi = davar.sade(ad.replace(" ", "_")).translate(str.maketrans("çğıöşü", "cgiosu"))
    dosya_adi = re.sub(r"[^a-z0-9]+", "_", dosya_adi).strip("_") or "kj"
    cikti = hedef / f"kj_{dosya_adi}.mov"

    tam, x, y, serit = kj_ciz(ad, unvan, genislik, yukseklik, rgb, konum)
    kare_sayisi = round(sure * fps)
    komut = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba",
             "-s", f"{genislik}x{yukseklik}", "-r", hiz, "-i", "-",
             "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le",
             "-vendor", "apl0", "-an", str(cikti.resolve())]
    gizli = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        surec = subprocess.Popen(komut, stdin=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=gizli)
    except FileNotFoundError:
        raise Hata("ffmpeg bulunamadı. ffmpeg kurulu ve PATH'te olmalı.")
    bos = Image.new("RGBA", (genislik, yukseklik), (0, 0, 0, 0))
    try:
        for i in range(kare_sayisi):
            tuval = bos.copy()
            tuval.paste(kj_karesi(tam, serit, i / fps, sure), (x, y))
            surec.stdin.write(tuval.tobytes())
            if ilerleme and i % 10 == 0:
                ilerleme(100 * i / kare_sayisi, f"KJ çiziliyor: {ad}")
        surec.stdin.close()
    except (BrokenPipeError, OSError):
        pass
    hata = surec.stderr.read().decode("utf-8", "replace").strip()
    if surec.wait() != 0:
        raise Hata("ffmpeg KJ videosunu yazamadı:\n" + hata[-600:])
    if ilerleme:
        ilerleme(100, "Bitti")
    return {"cikti": cikti, "ad": ad, "unvan": unvan, "sure": sure,
            "boyut": (genislik, yukseklik), "fps": fps}


def kjleri_uret(satirlar, ilerleme=None, **ayarlar):
    """Her satırı "Ad Soyad | Unvan" olan metinden birden çok KJ üretir."""
    kisiler = []
    for satir in satirlar:
        if satir.strip():
            ad, _, unvan = satir.partition("|")
            kisiler.append((ad.strip(), unvan.strip()))
    if not kisiler:
        raise Hata("KJ için en az bir ad yazılmalı.")
    sonuclar = []
    for i, (ad, unvan) in enumerate(kisiler):
        def adim(yuzde, metin, i=i):
            if ilerleme:
                ilerleme((i * 100 + yuzde) / len(kisiler), metin)
        sonuclar.append(kj_uret(ad, unvan, ilerleme=adim, **ayarlar))
    return {"cikti": sonuclar[0]["cikti"], "kjler": sonuclar}


def rapor(s):
    ilk = s["kjler"][0]
    satir = [f"KJ       : {len(s['kjler'])} adet, {ilk['boyut'][0]}x{ilk['boyut'][1]}, "
             f"{ilk['sure']:.0f} sn, saydam zeminli (ProRes 4444)",
             "Kullanım : Resolve'da videonun üstündeki şeride sürükle; giriş ve çıkış hazır gelir", ""]
    return "\n".join(satir + [f"Yazıldı: {k['cikti']}" for k in s["kjler"]])


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Konuşmacı adı için saydam zeminli KJ (alt bant) videosu üretir.")
    p.add_argument("ad", help="konuşmacının adı")
    p.add_argument("unvan", nargs="?", default="", help="unvanı (isteğe bağlı)")
    p.add_argument("--video", type=Path, default=None, help="boyut ve kare hızı bu videodan alınır")
    p.add_argument("--klasor", type=Path, default=None, help="çıktı klasörü")
    p.add_argument("--sure", type=float, default=6.0, help="ekranda kalma süresi, saniye (varsayılan 6)")
    p.add_argument("--renk", default="#E30613", help="vurgu rengi (varsayılan #E30613)")
    p.add_argument("--konum", default="sol", choices=KONUMLAR, help="yatay yer (varsayılan sol)")
    a = p.parse_args()
    try:
        sonuc = kjleri_uret([f"{a.ad} | {a.unvan}"], video=a.video, klasor=a.klasor, sure=a.sure,
                            renk=a.renk, konum=a.konum)
    except Hata as h:
        sys.exit(f"HATA: {h}")
    print(rapor(sonuc))


if __name__ == "__main__":
    main()
