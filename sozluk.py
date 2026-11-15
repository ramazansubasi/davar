"""davar sözlük - yazıya dökmenin hep yanlış yazdığı kelimeleri düzeltir.

Kişisel sözlük, kullanıcı klasöründeki .davar/sozluk.txt dosyasıdır. Her satır
"yanlış = doğru" biçimindedir:

    tuzda = Tuzla
    Akbörse = Akköse
    top sen = TÜPSAN

Düzeltme, kayıtlı analizi değiştirmeden her okunuşta uygulanır; sözlüğe sonradan
eklenen bir kelime eski analizleri de düzeltir.
"""

import re
from pathlib import Path

import davar

KESME = "'’"


def sozluk_yolu():
    return Path.home() / ".davar" / "sozluk.txt"


def sozluk_yukle(yol=None):
    """Sözlüğü [(yanlışın sade kelimeleri, doğrusu)] olarak okur; uzun ifadeler önce gelir."""
    yol = Path(yol) if yol else sozluk_yolu()
    try:
        satirlar = yol.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    girdiler = {}
    for satir in satirlar:
        satir = satir.split("#", 1)[0]
        if "=" not in satir:
            continue
        yanlis, dogru = (x.strip() for x in satir.split("=", 1))
        anahtar = tuple(davar.sade(k) for k in yanlis.split() if davar.sade(k))
        if anahtar and dogru:
            girdiler[anahtar] = dogru
    return sorted(girdiler.items(), key=lambda g: -len(g[0]))


def sozluge_ekle(ciftler, yol=None):
    """(yanlış, doğru) çiftlerini sözlük dosyasına ekler; var olan anahtarın doğrusunu günceller."""
    yol = Path(yol) if yol else sozluk_yolu()
    yol.parent.mkdir(parents=True, exist_ok=True)
    try:
        satirlar = yol.read_text(encoding="utf-8").splitlines()
    except OSError:
        satirlar = ["# Davar kişisel sözlüğü. Her satır: yanlış = doğru"]
    for yanlis, dogru in ciftler:
        anahtar = tuple(davar.sade(k) for k in yanlis.split())
        satirlar = [s for s in satirlar
                    if "=" not in s or tuple(davar.sade(k) for k in s.split("#")[0].split("=")[0].split()) != anahtar]
        satirlar.append(f"{yanlis.strip()} = {dogru.strip()}")
    yol.write_text("\n".join(satirlar) + "\n", encoding="utf-8")
    return yol


def _parcala(kelime):
    """ "Akbörse'nin," -> (kök "Akbörse", ek "'nin", noktalama ",")"""
    es = re.match(r"^(.*?)([^\w]*)$", kelime, re.S)
    govde, noktalama = es.group(1), es.group(2)
    for i, harf in enumerate(govde):
        if harf in KESME and i > 0:
            return govde[:i], govde[i:], noktalama
    return govde, "", noktalama


def uygula(kelimeler, girdiler=None):
    """Kelime listesine sözlüğü uygular; (yeni liste, düzeltme sayısı) döndürür.

    Kesme işaretinden sonraki ek ("'nin") ve sondaki noktalama korunur. Birden çok
    kelimelik bir yanlış tek kelimeye dönüşürse zamanları birleştirilir.
    """
    girdiler = sozluk_yukle() if girdiler is None else girdiler
    if not girdiler:
        return [list(k) for k in kelimeler], 0
    kokler = [davar.sade(_parcala(k[0])[0]) for k in kelimeler]
    yeni, adet, i = [], 0, 0
    while i < len(kelimeler):
        for anahtar, dogru in girdiler:
            n = len(anahtar)
            if tuple(kokler[i:i + n]) != anahtar:
                continue
            # ifadenin ortasındaki kelimeler eksiz olmalı ("top'un sen" eşleşmez)
            if any(_parcala(kelimeler[j][0])[1] for j in range(i, i + n - 1)):
                continue
            _, ek, noktalama = _parcala(kelimeler[i + n - 1][0])
            yeni.append([dogru + ek + noktalama, kelimeler[i][1], kelimeler[i + n - 1][2]])
            adet += 1
            i += n
            break
        else:
            yeni.append(list(kelimeler[i]))
            i += 1
    return yeni, adet
