"""davar - videodaki sessizlikleri ve "ııı / eee" duraksamalarını bulur,
kesilmiş hâlini DaVinci Resolve'a içe aktarılabilen bir zaman çizelgesi dosyası (FCPXML) olarak yazar.

Orijinal videoya dokunmaz. Kullanım:

    python davar.py "C:\\yol\\video.mp4"
"""

import argparse
import json
import math
import re
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from xml.sax.saxutils import quoteattr

import numpy as np

ORNEK_HIZI = 16000  # analiz için ses bu hıza indirilir
PENCERE = 0.01  # ses seviyesi 10 ms'lik dilimlerle ölçülür
STANDART_FPS = [
    Fraction(24000, 1001), Fraction(24), Fraction(25), Fraction(30000, 1001),
    Fraction(30), Fraction(50), Fraction(60000, 1001), Fraction(60),
]


class Hata(Exception):
    """Kullanıcıya gösterilecek, anlaşılır hata."""


def calistir(komut):
    # arayüzden çalışırken siyah komut penceresi açılmasın
    gizli = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        sonuc = subprocess.run(komut, capture_output=True, creationflags=gizli)
    except FileNotFoundError:
        raise Hata(f"{komut[0]} bulunamadı. ffmpeg kurulu ve PATH'te olmalı.")
    if sonuc.returncode != 0:
        hata = sonuc.stderr.decode("utf-8", "replace").strip()
        raise Hata(f"{komut[0]} çalışmadı:\n{hata}")
    return sonuc.stdout


def video_bilgisi(yol):
    """ffprobe ile kare hızı, boyut, süre ve ses bilgilerini okur."""
    ham = calistir([
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_streams", "-show_format", str(yol),
    ])
    veri = json.loads(ham)
    video = next((s for s in veri["streams"] if s["codec_type"] == "video"), None)
    ses = next((s for s in veri["streams"] if s["codec_type"] == "audio"), None)
    if video is None:
        raise Hata("dosyada görüntü yok.")
    if ses is None:
        raise Hata("dosyada ses yok, sessizlik analizi yapılamaz.")

    ortalama = Fraction(video.get("avg_frame_rate") or "0/1") if not video.get(
        "avg_frame_rate", "0/0").endswith("/0") else Fraction(0)
    if ortalama == 0:
        ortalama = Fraction(video["r_frame_rate"])
    # 29.97 gibi standart bir hıza çok yakınsa ona yuvarla
    fps = min(STANDART_FPS, key=lambda f: abs(f - ortalama))
    degisken_hiz = abs(fps - ortalama) / ortalama > 0.005
    if degisken_hiz:
        fps = ortalama.limit_denominator(1001)

    sure = float(video.get("duration") or veri["format"]["duration"])
    return {
        "fps": fps,
        "degisken_hiz": degisken_hiz,
        "genislik": int(video["width"]),
        "yukseklik": int(video["height"]),
        "sure": sure,
        "kare_sayisi": int(math.floor(sure * fps + 1e-6)),
        "ses_kanali": int(ses.get("channels", 2)),
        "ses_hizi": int(ses.get("sample_rate", 48000)),
    }


def ses_seviyeleri(yol):
    """Sesi tek kanala indirip her 10 ms için seviyeyi dB olarak döndürür."""
    ham = calistir([
        "ffmpeg", "-v", "error", "-i", str(yol), "-vn",
        "-ac", "1", "-ar", str(ORNEK_HIZI), "-f", "s16le", "-",
    ])
    ornekler = np.frombuffer(ham, dtype=np.int16).astype(np.float32) / 32768.0
    adim = int(ORNEK_HIZI * PENCERE)
    n = len(ornekler) // adim
    if n == 0:
        raise Hata("ses okunamadı.")
    dilimler = ornekler[: n * adim].reshape(n, adim)
    rms = np.sqrt(np.mean(dilimler ** 2, axis=1))
    return ornekler, 20 * np.log10(rms + 1e-10)


# --- "ııı / eee" bulma -------------------------------------------------------
# Duraksama sesi, konuşmadan şu üç özelliğiyle ayrılır: ötümlüdür (ses telleri
# titreşir), perdesi düz kalır ve ağız şekli değişmez. Normal konuşmada bu üçü
# aynı anda 0.3 saniye boyunca sabit kalmaz.
III_PENCERE = 512  # 32 ms
III_SEKIL_ESIK = 1.0  # ağız şekli (spektrum) en çok bu kadar oynayabilir
III_PERDE_TOL = 0.12  # perde en çok ~%12 oynayabilir
III_OTUMLU_ESIK = 0.45
III_PAY = 0.02  # kelimeye yapışık duraksamanın ucunda bırakılan pay (saniye)


def ses_ozellikleri(ornekler):
    """Her 10 ms için seviye, spektrum şekli, perde ve ötümlülük hesaplar."""
    adim = int(ORNEK_HIZI * PENCERE)
    n = max((len(ornekler) - III_PENCERE) // adim, 0)
    pencere = np.hanning(III_PENCERE).astype(np.float32)
    frek = np.fft.rfftfreq(III_PENCERE, 1 / ORNEK_HIZI)
    kenar = 700 * (10 ** np.linspace(np.log10(1 + 100 / 700), np.log10(1 + 6000 / 700), 26) - 1)
    banka = np.zeros((24, len(frek)), np.float32)
    for i in range(24):
        a, b, c = kenar[i], kenar[i + 1], kenar[i + 2]
        banka[i] = np.clip(np.minimum((frek - a) / (b - a), (c - frek) / (c - b)), 0, None)

    db = np.empty(n, np.float32)
    sekil = np.empty((n, 24), np.float32)
    perde = np.ones(n, np.float32)
    otumlu = np.zeros(n, np.float32)
    g_min, g_max = ORNEK_HIZI // 350, ORNEK_HIZI // 70  # 70-350 Hz arası perde
    duzeltme = (III_PENCERE / (III_PENCERE - np.arange(g_max + 1)))[None, :]
    for bas in range(0, n, 20000):
        son = min(n, bas + 20000)
        idx = (np.arange(bas, son) * adim)[:, None] + np.arange(III_PENCERE)[None, :]
        f = ornekler[idx]
        db[bas:son] = 10 * np.log10(np.mean(f ** 2, axis=1) + 1e-10)
        f = f - f.mean(axis=1, keepdims=True)
        s = np.fft.rfft(f * pencere, axis=1)
        m = np.log((s.real ** 2 + s.imag ** 2).astype(np.float32) @ banka.T + 1e-9)
        sekil[bas:son] = m - m.mean(axis=1, keepdims=True)
        s = np.fft.rfft(f, 2 * III_PENCERE, axis=1)
        ak = np.fft.irfft(s.real ** 2 + s.imag ** 2, axis=1)[:, : g_max + 1]
        ak = ak / (ak[:, :1] + 1e-9) * duzeltme
        k = np.argmax(ak[:, g_min:], axis=1) + g_min
        otumlu[bas:son] = ak[np.arange(son - bas), k]
        perde[bas:son] = ORNEK_HIZI / k
    return db, sekil, perde, otumlu


def duraksamalari_bul(ozellikler, esik, min_sure):
    """Uzatılmış "ııı / eee" seslerini (saniye, saniye, tür) olarak döndürür.

    Tür: "tek" = iki yanı sessiz, "bas" = sessizlikten sonra gelip kelimeye
    bağlanan, "son" = kelimenin sonuna yapışık (çoğu zaman uzatılmış gerçek
    kelimedir; aday olarak gösterilir ama varsayılan olarak kesilmez).
    """
    db, sekil, perde, otumlu = ozellikler
    n = len(db)
    uygun = (db > esik) & (otumlu > III_OTUMLU_ESIK)
    en_az = int(round(min_sure / PENCERE))
    kaydirma = III_PENCERE / 2 / ORNEK_HIZI - PENCERE / 2  # pencere ortası düzeltmesi
    bulunan = []
    i = 0
    while i < n:
        if not uygun[i]:
            i += 1
            continue
        ort, p0, j, bosluk = sekil[i].copy(), perde[i], i + 1, 0
        while j < n:
            fark = math.sqrt(float(np.mean((sekil[j] - ort) ** 2)))
            # perde ölçümü bazen bir oktav şaşar (176 Hz yerine 88 Hz); bunu sapma sayma
            sapma = abs(math.log(perde[j] / p0))
            oktav = abs(sapma - math.log(2)) < III_PERDE_TOL
            if uygun[j] and fark < III_SEKIL_ESIK and (sapma < III_PERDE_TOL or oktav):
                k = j - i
                ort = (ort * k + sekil[j]) / (k + 1)
                if not oktav:
                    p0 = p0 * 0.9 + perde[j] * 0.1
                bosluk = 0
            else:
                bosluk += 1
                if bosluk > 2:
                    break
            j += 1
        son = j - bosluk
        if son - i < en_az:
            i += 1
            continue
        # sesin bu parçasının çevresi: kelimeye mi yapışık, yoksa tek başına mı?
        ada_bas, ada_son = i, son
        while ada_bas > 0 and db[ada_bas - 1] > esik:
            ada_bas -= 1
        while ada_son < n and db[ada_son] > esik:
            ada_son += 1
        once = (i - ada_bas) * PENCERE
        sonra = (ada_son - son) * PENCERE
        if once <= 0.08 and sonra <= 0.12:
            bulunan.append((ada_bas * PENCERE + kaydirma, ada_son * PENCERE + kaydirma, "tek"))
        elif once <= 0.08:
            bulunan.append((ada_bas * PENCERE + kaydirma, son * PENCERE + kaydirma, "bas"))
        elif sonra <= 0.12:
            bulunan.append((i * PENCERE + kaydirma, ada_son * PENCERE + kaydirma, "son"))
        i = son
    return bulunan


def otomatik_esik(db):
    """Arka plan gürültüsü ile konuşma seviyesi arasında bir eşik seçer."""
    taban = max(float(np.percentile(db, 10)), -80.0)
    konusma = float(np.percentile(db, 95))
    return taban + 0.35 * (konusma - taban), taban, konusma


def sessiz_araliklar(db, esik, min_sessizlik, duraksama=None):
    """Atılacak aralıkları (saniye, saniye, başı duraksama mı, sonu duraksama mı)
    olarak döndürür. Duraksamalar sessizlik gibi sayılır; böylece bitişik
    sessizlikle tek kesimde birleşir.
    """
    if duraksama is None:
        duraksama = np.zeros(len(db), bool)
    sessiz = (db < esik) | duraksama
    # 30 ms'den kısa tıkırtılar sessizliği bölmesin
    kisa = int(0.03 / PENCERE)
    degisim = np.flatnonzero(np.diff(sessiz.astype(np.int8)))
    sinirlar = np.concatenate(([0], degisim + 1, [len(sessiz)]))
    for bas, son in zip(sinirlar[:-1], sinirlar[1:]):
        if not sessiz[bas] and son - bas <= kisa and bas > 0 and son < len(sessiz):
            sessiz[bas:son] = True

    degisim = np.flatnonzero(np.diff(sessiz.astype(np.int8)))
    sinirlar = np.concatenate(([0], degisim + 1, [len(sessiz)]))
    araliklar = []
    for bas, son in zip(sinirlar[:-1], sinirlar[1:]):
        if sessiz[bas] and ((son - bas) * PENCERE >= min_sessizlik
                            or duraksama[bas:son].any()):
            araliklar.append((bas * PENCERE, son * PENCERE,
                              bool(duraksama[bas]), bool(duraksama[son - 1])))
    return araliklar


def kesimleri_hesapla(araliklar, bilgi, pay_bas, pay_son):
    """Sessiz aralıklardan, payları düşerek kare cinsinden kesimler çıkarır."""
    fps = bilgi["fps"]
    toplam = bilgi["kare_sayisi"]
    kesimler = []
    for bas, son, bas_duraksama, son_duraksama in araliklar:
        # videonun en başı ve en sonu hariç, kelimelerin iki yanında pay bırak;
        # kelimeye yapışık bir "ııı"nın ucunda ise pay bırakma (yoksa ucu duyulur)
        k_bas = bas + (III_PAY if bas_duraksama else pay_son) if bas > 0.02 else 0.0
        k_son = (son - (III_PAY if son_duraksama else pay_bas)
                 if son < bilgi["sure"] - 0.02 else bilgi["sure"])
        kare_bas = math.ceil(k_bas * fps)
        kare_son = min(math.floor(k_son * fps), toplam)
        if kare_son - kare_bas >= 2:
            kesimler.append((kare_bas, kare_son))
    return kesimler


def kalan_parcalar(kesimler, toplam):
    parcalar, konum = [], 0
    for bas, son in kesimler:
        if bas > konum:
            parcalar.append((konum, bas))
        konum = son
    if konum < toplam:
        parcalar.append((konum, toplam))
    return parcalar


def fcpxml_yaz(cikti, video, bilgi, parcalar, ek="kesik"):
    fps = bilgi["fps"]

    def zaman(kare):
        return f"{kare * fps.denominator}/{fps.numerator}s"

    ad = video.stem
    proje = quoteattr(f"{ad} - {ek}")
    satirlar = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<!DOCTYPE fcpxml>",
        '<fcpxml version="1.9">',
        "  <resources>",
        f'    <format id="r1" name="FFVideoFormatRateUndefined" '
        f'frameDuration="{zaman(1)}" width="{bilgi["genislik"]}" '
        f'height="{bilgi["yukseklik"]}" colorSpace="1-1-1 (Rec. 709)"/>',
        f'    <asset id="r2" name={quoteattr(ad)} start="0s" hasVideo="1" format="r1" '
        f'hasAudio="1" audioSources="1" audioChannels="{bilgi["ses_kanali"]}" '
        f'duration="{zaman(bilgi["kare_sayisi"])}">',
        f'      <media-rep kind="original-media" src={quoteattr(video.resolve().as_uri())}/>',
        "    </asset>",
        "  </resources>",
        "  <library>",
        '    <event name="davar">',
        f"      <project name={proje}>",
        f'        <sequence format="r1" tcStart="0s" tcFormat="NDF" '
        f'audioLayout="{"mono" if bilgi["ses_kanali"] == 1 else "stereo"}" '
        f'audioRate="{"44.1k" if bilgi["ses_hizi"] == 44100 else "48k"}">',
        "          <spine>",
    ]
    konum = 0
    for bas, son in parcalar:
        satirlar.append(
            f'            <asset-clip name={quoteattr(ad)} offset="{zaman(konum)}" '
            f'start="{zaman(bas)}" duration="{zaman(son - bas)}" tcFormat="NDF" ref="r2"/>'
        )
        konum += son - bas
    satirlar += [
        "          </spine>", "        </sequence>", "      </project>",
        "    </event>", "  </library>", "</fcpxml>", "",
    ]
    cikti.write_text("\n".join(satirlar), encoding="utf-8")


def sure_yaz(saniye):
    dakika, sn = divmod(saniye, 60)
    return f"{int(dakika)}:{sn:05.2f}"


# --- adaylar ---------------------------------------------------------------
# Sessizlikler doğrudan kesilir. Duraksamalar ve dolgu kelimeleri ise "aday"dır:
# her birinin bir güven derecesi vardır, kullanıcı listeden işaretini değiştirebilir.
DOLGU_SES = re.compile(r"^(ı+h*|e+h*|a+h*|h*m+|ı+m+|e+m+)$")  # yazıya dökülmüş "ııı", "eee", "hmm"
TUR_ADI = {"tek": "ııı / eee (tek başına)", "bas": "ııı / eee (kelime önünde)",
           "son": "uzatma (kelime sonunda)", "kelime": "dolgu kelimesi",
           "metin": "ııı / eee (yalnızca metinde)"}
III_KISA = 0.15  # yazıya dökmenin duyduğu kısa duraksamalar seste en az bu kadar sürmeli


def tur_adi(aday):
    return ("kısa " if aday.get("kisa") else "") + TUR_ADI[aday["tur"]]


def sade(kelime):
    """Noktalamayı atar, Türkçe kurallarıyla küçük harfe çevirir."""
    return re.sub(r"[^\w]", "", kelime.replace("I", "ı").replace("İ", "i").lower())


def adaylari_cikar(duraksamalar, db, kelimeler=None, dolgu_kelimeleri=(), sondakiler=False,
                   kisalar=()):
    """Kesilebilecek duraksama ve dolgu kelimelerini güven dereceleriyle listeler.

    `kelimeler` İlk Analiz'den gelen (metin, başlangıç, bitiş) listesidir; varsa
    sesten bulunan duraksamalar metinle karşılaştırılır ve dolgu kelimeleri aranır.
    `kisalar`, sesten gevşek ölçüyle bulunan kısa duraksamalardır: yalnızca yazıya
    dökme de aynı yerde "ııı / eee" duymuşsa aday olurlar.
    """
    kelimeler = kelimeler or []
    sadeler = [sade(k[0]) for k in kelimeler]
    dolgu_zamanlari = [(k[1], k[2]) for k, sd in zip(kelimeler, sadeler) if DOLGU_SES.match(sd)]

    def baglam(bas, son, vurgu=None):
        parca = []
        for i, k in enumerate(kelimeler):
            if k[2] > bas - 1.2 and k[1] < son + 1.2:
                parca.append(f"«{k[0]}»" if vurgu and vurgu[0] <= i < vurgu[1] else k[0])
        return " ".join(parca)

    adaylar = []
    for bas, son, tur in duraksamalar:
        metinde = any(b < son + 0.5 and s > bas - 0.5 for b, s in dolgu_zamanlari)
        if tur == "tek":
            guven = "yüksek"
        elif tur == "bas":
            # yazıya dökme varsa onun da "ııı" duymuş olması beklenir
            guven = ("yüksek" if metinde else "düşük") if kelimeler else "orta"
        else:
            guven = "orta" if metinde else "düşük"
        adaylar.append({
            "bas": bas, "son": son, "tur": tur, "guven": guven, "metin": baglam(bas, son),
            "sec": guven == "yüksek" or (tur == "bas" and guven == "orta") or (tur == "son" and sondakiler),
        })

    def sinir(t):  # kelime zamanı yaklaşıktır: yakındaki en sessiz ana çek
        orta = int(round(t / PENCERE))
        a, b = max(orta - 10, 0), min(orta + 11, len(db))
        return (a + int(np.argmin(db[a:b]))) * PENCERE if b > a else t

    def cakisiyor(bas, son, pay=0.0):
        return any(a["bas"] < son + pay and a["son"] > bas - pay for a in adaylar)

    # Yazıya dökmenin duyduğu ama uzun olmadığı için yukarıda yakalanmayan duraksamalar.
    # Zamanı yazıya dökmeden değil, aynı yerdeki sabit sesten alınır.
    for b, s in dolgu_zamanlari:
        if cakisiyor(b, s, 0.5):
            continue
        yakin = [k for k in kisalar if k[0] < s + 0.35 and k[1] > b - 0.35
                 and not cakisiyor(k[0], k[1])]
        if yakin:
            bas, son, tur = max(yakin, key=lambda k: k[1] - k[0])
            guven = "düşük" if tur == "son" else "orta"
            # kısa kesimde hata payı az olduğu için öneri olarak gelir, işaretsiz
            adaylar.append({"bas": bas, "son": son, "tur": tur, "kisa": True, "guven": guven,
                            "sec": False, "metin": baglam(bas, son)})
        elif s - b >= III_KISA:
            bas, son = sinir(b), sinir(s)
            if son - bas >= III_KISA and not cakisiyor(bas, son):
                adaylar.append({"bas": bas, "son": son, "tur": "metin", "guven": "düşük",
                                "sec": False, "metin": baglam(bas, son)})

    for ifade in dolgu_kelimeleri:
        aranan = [sade(x) for x in ifade.split() if sade(x)]
        if not aranan:
            continue
        for i in range(len(sadeler) - len(aranan) + 1):
            if sadeler[i:i + len(aranan)] != aranan:
                continue
            bas, son = sinir(kelimeler[i][1]), sinir(kelimeler[i + len(aranan) - 1][2])
            if son - bas < 0.08 or cakisiyor(bas, son):
                continue
            adaylar.append({"bas": bas, "son": son, "tur": "kelime", "guven": "orta", "sec": False,
                            "metin": baglam(bas, son, (i, i + len(aranan)))})
    adaylar.sort(key=lambda a: a["bas"])
    return adaylar


def cozumle(video, sessizlik=True, iii=True, min_sessizlik=0.5, pay_bas=0.10, pay_son=0.15,
            esik=None, iii_min=0.30, iii_sondakiler=False, kelimeler=None, dolgu_kelimeleri=(),
            ilerleme=None):
    """Videoyu çözümler; sessizlik eşiğini ve kesim adaylarını içeren durumu döndürür.

    Dosya yazmaz. Sonuç `uygula`ya verilir; arada adayların "sec" işaretleri değiştirilebilir.
    """
    def adim(yuzde, metin):
        if ilerleme:
            ilerleme(yuzde, metin)

    video = Path(video)
    if not video.is_file():
        raise Hata(f"dosya bulunamadı: {video}")
    if not sessizlik and not iii and not dolgu_kelimeleri:
        raise Hata("kesilecek bir şey seçilmedi.")
    if dolgu_kelimeleri and not kelimeler:
        raise Hata("dolgu kelimelerini bulmak için önce İlk Analiz çalıştırılmalı.")

    adim(5, "Video bilgileri okunuyor")
    bilgi = video_bilgisi(video)
    adim(10, "Ses çıkarılıyor")
    ornekler, db = ses_seviyeleri(video)
    oto, taban, konusma = otomatik_esik(db)
    kullanilan_esik = esik if esik is not None else oto

    duraksamalar, kisalar = [], []
    if iii:
        adim(40, "Duraksamalar (ııı / eee) aranıyor")
        ozellikler = ses_ozellikleri(ornekler)
        duraksamalar = duraksamalari_bul(ozellikler, kullanilan_esik, iii_min)
        if kelimeler and iii_min > III_KISA:
            adim(70, "Kısa duraksamalar metinle eşleştiriliyor")
            kisalar = duraksamalari_bul(ozellikler, kullanilan_esik, III_KISA)
    adim(90, "Adaylar hazırlanıyor")
    adaylar = adaylari_cikar(duraksamalar, db, kelimeler, dolgu_kelimeleri, iii_sondakiler, kisalar)
    adim(100, "Çözümleme bitti")
    return {
        "video": video, "bilgi": bilgi, "fps": float(bilgi["fps"]), "db": db, "ornekler": ornekler,
        "taban": taban, "konusma": konusma, "esik": kullanilan_esik, "esik_elle": esik is not None,
        "min_sessizlik": min_sessizlik if sessizlik else float("inf"),
        "pay_bas": pay_bas, "pay_son": pay_son, "adaylar": adaylar, "metinli": bool(kelimeler),
    }


def kesim_plani(durum):
    """İşaretli adaylara ve sessizliklere göre kesimleri ve kalan parçaları hesaplar."""
    db = durum["db"]
    maske = np.zeros(len(db), bool)
    for a in durum["adaylar"]:
        if a["sec"]:
            maske[max(int(round(a["bas"] / PENCERE)), 0): int(round(a["son"] / PENCERE))] = True
    araliklar = sessiz_araliklar(db, durum["esik"], durum["min_sessizlik"], maske)
    kesimler = kesimleri_hesapla(araliklar, durum["bilgi"], durum["pay_bas"], durum["pay_son"])
    return kesimler, kalan_parcalar(kesimler, durum["bilgi"]["kare_sayisi"])


def uygula(durum, cikti=None, kontrol=False):
    """Zaman çizelgesi dosyalarını yazar ve sonuç özetini döndürür."""
    video, bilgi, fps = durum["video"], durum["bilgi"], durum["fps"]
    kesimler, parcalar = kesim_plani(durum)
    if not parcalar:
        raise Hata("videonun tamamı sessiz görünüyor; eşik değerini düşürmeyi dene.")
    cikti = Path(cikti) if cikti else video.with_name(video.stem + "_kesik.fcpxml")
    fcpxml_yaz(cikti, video, bilgi, parcalar)

    secilen = [a for a in durum["adaylar"] if a["sec"]]
    kontrol_dosyasi = None
    if kontrol and secilen:
        # kesilen her aday, öncesi ve sonrasındaki birer saniyeyle birlikte
        kontrol_dosyasi = cikti.with_name(video.stem + "_iii_kontrol.fcpxml")
        klipler = []
        for a in secilen:
            k_bas = max(int((a["bas"] - 1.0) * fps), 0)
            k_son = min(int(math.ceil((a["son"] + 1.0) * fps)), bilgi["kare_sayisi"])
            if klipler and k_bas <= klipler[-1][1]:
                klipler[-1] = (klipler[-1][0], k_son)
            else:
                klipler.append((k_bas, k_son))
        fcpxml_yaz(kontrol_dosyasi, video, bilgi, klipler, ek="ııı kontrol")

    return {
        "video": video, "bilgi": bilgi, "fps": fps, "taban": durum["taban"],
        "konusma": durum["konusma"], "esik": durum["esik"], "esik_elle": durum["esik_elle"],
        "kesimler": kesimler, "adaylar": durum["adaylar"], "secilen": secilen,
        "atilan": sum(son - bas for bas, son in kesimler) / fps,
        "cikti": cikti, "kontrol": kontrol_dosyasi,
    }


def isle(video, cikti=None, kontrol=False, ilerleme=None, **ayarlar):
    """Çözümler ve varsayılan işaretlerle doğrudan uygular (komut satırı için)."""
    return uygula(cozumle(video, ilerleme=ilerleme, **ayarlar), cikti=cikti, kontrol=kontrol)


def rapor(s, ayrinti=True):
    """uygula() sonucunu okunur bir metne çevirir."""
    bilgi, fps = s["bilgi"], s["fps"]
    satir = [
        f"Video        : {s['video'].name}  ({bilgi['genislik']}x{bilgi['yukseklik']}, {fps:.3f} kare/sn)",
        f"Ses seviyesi : arka plan {s['taban']:.0f} dB, konuşma {s['konusma']:.0f} dB, "
        f"eşik {s['esik']:.0f} dB" + (" (elle verildi)" if s["esik_elle"] else ""),
        f"Kesim        : {len(s['kesimler'])} yer atıldı"
        + (f"  ({len(s['secilen'])} tanesi duraksama ya da dolgu; "
           f"{len(s['adaylar']) - len(s['secilen'])} aday kesilmedi)" if s["adaylar"] else ""),
        f"Süre         : {sure_yaz(bilgi['sure'])} -> {sure_yaz(bilgi['sure'] - s['atilan'])}"
        f"  ({s['atilan']:.1f} sn kısaldı)",
    ]
    if s["konusma"] - s["taban"] < 15:
        satir.append("UYARI: arka plan gürültüsü ile konuşma seviyesi birbirine yakın; "
                     "kesimler hatalı olabilir.")
    if bilgi["degisken_hiz"]:
        satir.append("UYARI: videonun kare hızı değişken görünüyor (telefon/ekran kaydı); "
                     "Resolve'da kesim yerleri kayabilir.")
    if ayrinti and s["adaylar"]:
        satir.append("\nAdaylar (orijinal videodaki zaman; [x] kesildi):")
        for a in s["adaylar"][:15]:
            satir.append(f"  [{'x' if a['sec'] else ' '}] {sure_yaz(a['bas'])}  {a['son'] - a['bas']:.2f} sn  "
                         f"{tur_adi(a)}, güven {a['guven']}"
                         + (f"  | {a['metin']}" if a["metin"] else ""))
        if len(s["adaylar"]) > 15:
            satir.append(f"  ... ve {len(s['adaylar']) - 15} aday daha")
    satir.append(f"\nZaman çizelgesi yazıldı: {s['cikti']}")
    if s["kontrol"]:
        satir.append(f"Kontrol çizelgesi yazıldı: {s['kontrol']}")
    return "\n".join(satir)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(
        description="Videodaki sessizlikleri ve duraksamaları kesip Resolve zaman çizelgesi üretir.")
    p.add_argument("video", type=Path, help="video dosyasının yolu")
    p.add_argument("--min-sessizlik", type=float, default=0.5,
                   help="bundan kısa sessizliklere dokunulmaz (saniye, varsayılan 0.5)")
    p.add_argument("--pay-bas", type=float, default=0.10,
                   help="kelime başlamadan önce bırakılan pay (saniye, varsayılan 0.10)")
    p.add_argument("--pay-son", type=float, default=0.15,
                   help="kelime bittikten sonra bırakılan pay (saniye, varsayılan 0.15)")
    p.add_argument("--esik", type=float, default=None,
                   help="sessizlik eşiği (dB). Verilmezse otomatik seçilir")
    p.add_argument("--sessizlik-yok", action="store_true",
                   help="sessizliklere dokunma, yalnızca duraksamaları kes")
    p.add_argument("--iii-yok", action="store_true",
                   help='"ııı / eee" duraksamalarına dokunma, yalnızca sessizlikleri kes')
    p.add_argument("--iii-min", type=float, default=0.30,
                   help="bundan kısa duraksamalara dokunulmaz (saniye, varsayılan 0.30)")
    p.add_argument("--iii-sondakiler", action="store_true",
                   help="kelimenin sonuna yapışık uzatmaları da kes (yanlış kesim riski yüksek)")
    p.add_argument("--dolgu", default="",
                   help='kesilecek dolgu kelimeleri, virgülle ayrılmış (örn. "yani, şey"); '
                        "İlk Analiz gerektirir ve bulunanların hepsini keser")
    p.add_argument("--kontrol", action="store_true",
                   help="kesilen duraksamaları dinleyip denetlemek için ayrı bir "
                        "zaman çizelgesi de yaz (<ad>_iii_kontrol.fcpxml)")
    p.add_argument("--cikti", type=Path, default=None,
                   help="çıktı dosyası (varsayılan: videonun yanına <ad>_kesik.fcpxml)")
    a = p.parse_args()
    try:
        import analiz  # İlk Analiz daha önce yapıldıysa metni de kullan
        kayit = analiz.analiz_yukle(a.video)
        dolgular = [d.strip() for d in a.dolgu.split(",") if d.strip()]
        durum = cozumle(
            a.video, sessizlik=not a.sessizlik_yok, iii=not a.iii_yok,
            min_sessizlik=a.min_sessizlik, pay_bas=a.pay_bas, pay_son=a.pay_son,
            esik=a.esik, iii_min=a.iii_min, iii_sondakiler=a.iii_sondakiler,
            kelimeler=kayit["kelimeler"] if kayit else None, dolgu_kelimeleri=dolgular)
        for aday in durum["adaylar"]:  # komut satırında sorulamaz: istenen kelimeler kesilir
            if aday["tur"] == "kelime":
                aday["sec"] = True
        sonuc = uygula(durum, cikti=a.cikti, kontrol=a.kontrol)
    except Hata as h:
        sys.exit(f"HATA: {h}")
    if kayit:
        print("İlk Analiz bulundu: duraksamalar metinle karşılaştırıldı.")
    print(rapor(sonuc))


if __name__ == "__main__":
    main()
