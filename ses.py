"""davar ses - ayrı kaydedilmiş sesleri videodaki yerine oturtur ve ses düzeyini ayarlar.

Ayrı ses dosyasının videoda nereye denk geldiğini kendisi bulur (iki kayıttaki
konuşmanın ritmini karşılaştırarak), düzeyini videonun sesine eşitler ve videonun
o bölümdeki sesinin yerine koyar. Sonra bütün sesi YouTube düzeyine getirir.

Görüntü yeniden kodlanmaz; sonuç videonun yanına <video>_sesli.mp4 olarak yazılır.

    python ses.py "video.mp4" --ses "mikrofon.wav"
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

import davar
from davar import Hata

HIZ = 8000  # karşılaştırma için ses bu hıza indirilir
ZARF_ADIMI = 0.01  # konuşma ritmi 10 ms'lik adımlarla ölçülür
EN_AZ_AYIRT = 0.08  # en iyi konum ikinciden en az bu kadar önde olmalı
EN_AZ_DALGA = 0.25  # ya da dalga biçimi en az bu kadar benzemeli
HEDEF_TEPE = -1.5  # dBTP


def ses_oku(yol, hiz=HIZ):
    ham = davar.calistir(["ffmpeg", "-v", "error", "-i", str(yol), "-vn", "-ac", "1",
                          "-ar", str(hiz), "-f", "s16le", "-"])
    return np.frombuffer(ham, dtype=np.int16).astype(np.float32) / 32768.0


def zarf(x, hiz=HIZ):
    """Konuşmanın ritmi: 10 ms'lik dilimlerin seviyesi, yavaş değişimler atılmış hâliyle."""
    adim = int(hiz * ZARF_ADIMI)
    n = len(x) // adim
    if n < 20:
        return np.zeros(0, np.float32)
    rms = np.sqrt(np.mean(x[: n * adim].reshape(n, adim) ** 2, axis=1))
    db = 20 * np.log10(rms + 1e-4)
    cekirdek = np.ones(101, np.float32) / 101  # 1 saniyelik ortalamayı çıkar
    return (db - np.convolve(db, cekirdek, mode="same")).astype(np.float32)


def _capraz(uzun, kisa):
    """c[k] = toplam(uzun[t + k] * kisa[t]); negatif kaymalar dizinin sonundadır."""
    n = 1 << int(np.ceil(np.log2(len(uzun) + len(kisa))))
    return np.fft.irfft(np.fft.rfft(uzun, n) * np.conj(np.fft.rfft(kisa, n)), n)


def _benzerlik(a, b):
    if len(a) < 20:
        return 0.0
    a, b = a - a.mean(), b - b.mean()
    payda = float(np.sqrt((a * a).sum() * (b * b).sum()))
    return float((a * b).sum() / payda) if payda > 0 else 0.0


def _ince_kayma(video, klip, kaba, hiz, merkez, yaricap=0.08, pencere=6.0):
    """Klibin `merkez` saniyesi çevresindeki parçayla kaymayı örnek hassasiyetinde bulur.

    (kayma, dalga benzerliği) döndürür. Benzerlik, iki kayıt aynı mikrofondan
    geliyorsa 1'e yakındır; ayrı mikrofonlarda düşük çıkması olağandır.
    """
    yari = int(pencere / 2 * hiz)
    k0 = int(merkez * hiz) - yari
    k1 = k0 + 2 * yari
    r = int(yaricap * hiz)
    v0 = k0 + int(round(kaba * hiz)) - r
    v1 = k1 + int(round(kaba * hiz)) + r
    if k0 < 0 or k1 > len(klip) or v0 < 0 or v1 > len(video):
        return None
    parca, hedef = klip[k0:k1], video[v0:v1]
    if np.abs(parca).max() < 0.005:
        return None
    c = np.abs(_capraz(hedef, parca)[: 2 * r + 1])
    i = int(np.argmax(c))
    karsilik = hedef[i:i + len(parca)]
    payda = float(np.sqrt((parca ** 2).sum() * (karsilik ** 2).sum())) + 1e-9
    return kaba + (i - r) / hiz, float(c[i] / payda)


def _kaba_konumlar(zv, zk, kac=6):
    """Ritim benzerliğinin en yüksek olduğu, birbirinden ayrı konumları (zarf adımı, benzerlik) verir."""
    en_az = min(len(zk), len(zv), 300) // 2  # en az bu kadar üst üste binsin
    dolgu = len(zk) - en_az
    genis = np.concatenate((np.zeros(dolgu, np.float32), zv, np.zeros(dolgu, np.float32)))
    adet = len(genis) - len(zk) + 1
    c = _capraz(genis, zk)[:adet]
    enerji = np.convolve(genis ** 2, np.ones(len(zk), np.float32), mode="valid")[:adet]
    puan = c / np.sqrt(np.maximum(enerji, 0.05 * np.median(enerji) + 1e-9) * float((zk ** 2).sum()) + 1e-9)
    secilen = []
    for i in np.argsort(puan)[::-1][:4000]:
        if all(abs(int(i) - j) > 100 for j in secilen):  # tepeler en az 1 saniye ayrı olsun
            secilen.append(int(i))
            if len(secilen) == kac:
                break
    sonuc = []
    for i in secilen:
        k = i - dolgu
        a0, a1 = max(k, 0), min(k + len(zk), len(zv))
        sonuc.append((k, _benzerlik(zv[a0:a1], zk[a0 - k:a1 - k])))
    return sorted(sonuc, key=lambda x: -x[1])


def konum_bul(video, klip, hiz=HIZ):
    """Klibin videodaki yerini bulur.

    Döndürür:
      kayma      klibin başının videodaki saniyesi (klip videodan önce başlıyorsa negatif)
      guven      bulunan yerdeki ritim benzerliği (-1..1)
      ayirt      en iyi konumun ikinci en iyiden farkı; ilgisiz seslerde sıfıra yakındır
      dalga      dalga biçimi benzerliği (aynı kayıt videonun içindeyse 1'e yakın)
      hiz_farki  iki kayıt cihazının saat farkı; klibin süresinin çarpılacağı oran
    """
    zv, zk = zarf(video, hiz), zarf(klip, hiz)
    if len(zv) < 100 or len(zk) < 100:
        raise Hata("ses eşlemek için en az bir saniyelik kayıt gerekli.")
    konumlar = _kaba_konumlar(zv, zk)
    k, guven = konumlar[0]
    ayirt = guven - konumlar[1][1] if len(konumlar) > 1 else guven
    kaba = k * ZARF_ADIMI

    # örnek hassasiyetinde düzelt; uzun kayıtlarda baş ve sondan ölçüp saat farkını çıkar
    bas_t, son_t = max(-kaba, 0.0), min(len(klip) / hiz, len(video) / hiz - kaba)
    ortusme = son_t - bas_t
    noktalar = [bas_t + ortusme * o for o in ((0.15, 0.5, 0.85) if ortusme > 20 else (0.5,))]
    olcumler = [(t, _ince_kayma(video, klip, kaba, hiz, t, 0.3 if ortusme > 120 else 0.08))
                for t in noktalar]
    olcumler = [(t, o[0], o[1]) for t, o in olcumler if o is not None]
    kayma, hiz_farki, dalga = kaba, 1.0, 0.0
    if olcumler:
        kayma = float(np.median([o for _, o, _ in olcumler]))
        dalga = float(np.median([d for _, _, d in olcumler]))
        if ortusme > 120 and len(olcumler) >= 2:
            (t0, o0, _), (t1, o1, _) = olcumler[0], olcumler[-1]
            egim = (o1 - o0) / (t1 - t0)
            if abs(egim) * ortusme > 0.03 and abs(egim) < 0.002:  # 30 ms'den çok kayıyorsa
                hiz_farki = 1.0 + egim
                kayma = o0 - egim * t0
    return {"kayma": kayma, "guven": guven, "ayirt": ayirt, "dalga": dalga,
            "hiz_farki": hiz_farki, "sure": len(klip) / hiz}


def eslesti_mi(k):
    """Bulunan yer güvenilir mi? İlgisiz bir ses de bir yere benzer; önemli olan
    o yerin diğerlerinden açık farkla öne çıkması ya da dalga biçiminin tutmasıdır."""
    return k["ayirt"] >= EN_AZ_AYIRT or k["dalga"] >= EN_AZ_DALGA


# --- ffmpeg ile ölçme ve uygulama ------------------------------------------
def _ffmpeg(komut, cwd=None):
    gizli = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        sonuc = subprocess.run(komut, capture_output=True, creationflags=gizli, cwd=cwd)
    except FileNotFoundError:
        raise Hata("ffmpeg bulunamadı. ffmpeg kurulu ve PATH'te olmalı.")
    hata = sonuc.stderr.decode("utf-8", "replace")
    if sonuc.returncode != 0:
        raise Hata("ffmpeg sesi işleyemedi:\n" + hata.strip()[-600:])
    return hata


def duzey_olc(girdiler, zincir=None, cwd=None):
    """Sesin yüksekliğini (LUFS) ve tepe değerini ölçer; loudnorm'un ikinci geçiş değerlerini döndürür."""
    komut = ["ffmpeg", "-hide_banner", "-nostats", *girdiler]
    if zincir is None:
        komut += ["-vn", "-af", "loudnorm=print_format=json"]
    else:
        Path(cwd, "olcum.txt").write_text(zincir + ",loudnorm=print_format=json[a]", encoding="utf-8")
        komut += ["-/filter_complex", "olcum.txt", "-map", "[a]"]
    cikti = _ffmpeg(komut + ["-f", "null", "-"], cwd)
    bulunan = re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", cikti)
    if not bulunan:
        raise Hata("ses düzeyi ölçülemedi.")
    return {k: float(v) for k, v in json.loads(bulunan[-1]).items()
            if k.startswith(("input_", "target_")) and v not in ("inf", "-inf")}


def ses_isle(video, sesler=(), klasor=None, duzey=True, hedef=-14.0, dengele=False,
             gurultu=False, ilerleme=None):
    """Ayrı sesleri yerine oturtur, düzeyi ayarlar ve yeni videoyu yazar."""
    def adim(yuzde, metin):
        if ilerleme:
            ilerleme(yuzde, metin)

    video = Path(video)
    sesler = [Path(s) for s in sesler]
    for yol in [video, *sesler]:
        if not yol.is_file():
            raise Hata(f"dosya bulunamadı: {yol}")
    if not (sesler or duzey or dengele or gurultu):
        raise Hata("yapılacak bir işlem seçilmedi.")
    adim(2, "Video bilgileri okunuyor")
    bilgi = davar.video_bilgisi(video)
    uzanti = video.suffix.lower() if video.suffix.lower() in (".mp4", ".mov", ".mkv", ".m4v") else ".mp4"
    cikti = (Path(klasor) if klasor else video.parent) / (video.stem + "_sesli" + uzanti)

    # 1) ayrı seslerin yerini bul
    klipler = []
    if sesler:
        adim(5, "Videonun sesi okunuyor")
        video_sesi = ses_oku(video)
        for i, yol in enumerate(sesler):
            adim(8 + 22 * i / len(sesler), f"Yeri aranıyor: {yol.name}")
            k = konum_bul(video_sesi, ses_oku(yol))
            k["yol"] = yol
            k["yerlesti"] = eslesti_mi(k)
            klipler.append(k)
        del video_sesi
    yerlesen = [k for k in klipler if k["yerlesti"]]
    if sesler and not yerlesen and not (duzey or dengele or gurultu):
        raise Hata("ayrı seslerin hiçbiri videoyla eşleşmedi; yeni video yazılmadı.")

    with tempfile.TemporaryDirectory(prefix="davar_ses_") as gecici:
        girdiler = ["-i", str(video.resolve())]
        for k in yerlesen:
            girdiler += ["-i", str(k["yol"].resolve())]

        # 2) her klibin düzeyini videonun sesine eşitle
        if yerlesen:
            adim(32, "Ses düzeyleri ölçülüyor")
            asil = duzey_olc(["-i", str(video.resolve())])["input_i"]
            for k in yerlesen:
                olcum = duzey_olc(["-i", str(k["yol"].resolve())]).get("input_i", asil)
                k["kazanc"] = float(np.clip(asil - olcum, -20, 20))

        # 3) karışım: videonun sesi, kliplerin geldiği yerde susturulur
        zincir = "[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo"
        if yerlesen:
            araliklar = "+".join(
                f"between(t,{max(k['kayma'], 0):.3f},{k['kayma'] + k['sure'] * k['hiz_farki']:.3f})"
                for k in yerlesen)
            zincir += f",volume=0:enable='{araliklar}'[taban];"
            for i, k in enumerate(yerlesen, 1):
                z = f"[{i}:a]aresample=48000"
                if k["hiz_farki"] != 1.0:  # kayıt cihazlarının saat farkını gider
                    z += f",asetrate={48000 / k['hiz_farki']:.4f},aresample=48000"
                z += f",aformat=sample_fmts=fltp:channel_layouts=stereo,volume={k['kazanc']:.2f}dB"
                sure = k["sure"] * k["hiz_farki"]
                z += f",afade=t=in:d=0.02,afade=t=out:st={max(sure - 0.02, 0):.3f}:d=0.02"
                if k["kayma"] < 0:
                    z += f",atrim=start={-k['kayma']:.4f},asetpts=PTS-STARTPTS"
                elif k["kayma"] > 0:
                    z += f",adelay={k['kayma'] * 1000:.2f}:all=1"
                zincir += z + f"[k{i}];"
            zincir += "[taban]" + "".join(f"[k{i}]" for i in range(1, len(yerlesen) + 1))
            zincir += f"amix=inputs={len(yerlesen) + 1}:normalize=0:duration=first"
        if gurultu:
            zincir += ",highpass=f=80,afftdn=nr=8:nf=-45:tn=1"
        if dengele:
            zincir += ",dynaudnorm=f=400:g=31:p=0.9:m=6"

        onceki = None
        if duzey:
            adim(40, "Ses düzeyi ölçülüyor")
            o = duzey_olc(girdiler, zincir, gecici)
            onceki = o["input_i"]
            zincir += (f",loudnorm=I={hedef}:TP={HEDEF_TEPE}:LRA=11:measured_I={o['input_i']}"
                       f":measured_TP={o['input_tp']}:measured_LRA={o['input_lra']}"
                       f":measured_thresh={o['input_thresh']}:offset={o['target_offset']}:linear=true")
        Path(gecici, "filtre.txt").write_text(zincir + "[a]", encoding="utf-8")
        komut = ["ffmpeg", "-v", "error", "-y", *girdiler, "-/filter_complex", "filtre.txt",
                 "-map", "0:v?", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k",
                 "-ar", "48000", "-t", f"{bilgi['sure']:.3f}", "-movflags", "+faststart",
                 "-progress", "pipe:1", "-nostats", str(cikti.resolve())]
        adim(55, "Yeni video yazılıyor")
        gizli = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        surec = subprocess.Popen(komut, cwd=gecici, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 creationflags=gizli)
        for satir in surec.stdout:
            es = re.match(rb"out_time_us=(\d+)", satir)
            if es:
                adim(55 + 40 * min(int(es.group(1)) / 1e6 / bilgi["sure"], 1.0), "Yeni video yazılıyor")
        hata = surec.stderr.read().decode("utf-8", "replace").strip()
        if surec.wait() != 0:
            raise Hata("ffmpeg videoyu yazamadı:\n" + hata[-600:])

    adim(96, "Sonuç ölçülüyor")
    sonraki = duzey_olc(["-i", str(cikti.resolve())])
    adim(100, "Bitti")
    return {"cikti": cikti, "klipler": klipler, "onceki": onceki, "sonraki": sonraki["input_i"],
            "tepe": sonraki["input_tp"], "hedef": hedef if duzey else None,
            "dengele": dengele, "gurultu": gurultu}


def rapor(s):
    satir = []
    for k in s["klipler"]:
        if k["yerlesti"]:
            satir.append(
                f"Yerleşti : {k['yol'].name}  →  {davar.sure_yaz(max(k['kayma'], 0))}"
                f"  (benzerlik %{k['guven'] * 100:.0f}, ikinci adaydan %{k['ayirt'] * 100:.0f} önde, "
                f"düzey {k['kazanc']:+.1f} dB"
                + (f", saat farkı düzeltildi" if k["hiz_farki"] != 1.0 else "") + ")")
        else:
            satir.append(f"Yeri yok : {k['yol'].name}  (hiçbir yer öne çıkmadı; bu ses videoda "
                         "geçmiyor olabilir, yerleştirilmedi)")
    if s["onceki"] is not None:
        satir.append(f"Ses düzeyi : {s['onceki']:.1f} → {s['sonraki']:.1f} LUFS "
                     f"(hedef {s['hedef']:.0f}), tepe {s['tepe']:.1f} dBTP")
    else:
        satir.append(f"Ses düzeyi : {s['sonraki']:.1f} LUFS (ayarlanmadı)")
    ekler = [ad for ad, acik in (("konuşmacı dengeleme", s["dengele"]),
                                 ("gürültü azaltma", s["gurultu"])) if acik]
    if ekler:
        satir.append("Uygulandı  : " + ", ".join(ekler) + " (kulakla denetle)")
    satir.append(f"\nVideo yazıldı (görüntü yeniden kodlanmadı): {s['cikti']}")
    return "\n".join(satir)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Ayrı sesleri videoya oturtur ve ses düzeyini ayarlar.")
    p.add_argument("video", type=Path)
    p.add_argument("--ses", type=Path, action="append", default=[],
                   help="ayrı kaydedilmiş ses dosyası (birden çok kez yazılabilir)")
    p.add_argument("--klasor", type=Path, default=None, help="çıktı klasörü (varsayılan: videonun yanı)")
    p.add_argument("--duzey-yok", action="store_true", help="ses düzeyini ayarlama")
    p.add_argument("--hedef", type=float, default=-14.0, help="hedef yükseklik, LUFS (varsayılan -14)")
    p.add_argument("--dengele", action="store_true", help="konuşmacıların düzeyini birbirine yaklaştır")
    p.add_argument("--gurultu", action="store_true", help="dip gürültüsünü azalt")
    a = p.parse_args()
    try:
        sonuc = ses_isle(a.video, a.ses, klasor=a.klasor, duzey=not a.duzey_yok, hedef=a.hedef,
                         dengele=a.dengele, gurultu=a.gurultu,
                         ilerleme=lambda y, m: print(f"\r{y:5.1f}%  {m}        ", end="", file=sys.stderr))
    except Hata as h:
        sys.exit(f"\nHATA: {h}")
    print("\n" + rapor(sonuc))


if __name__ == "__main__":
    main()
