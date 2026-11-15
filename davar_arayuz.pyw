"""davar arayüzü - soldan iş akışını seç, üstten videoyu göster, başlat.

Çift tıklayarak açılır (Davar.bat). Asıl iş davar.py, analiz.py, ses.py ve reels.py içindedir.

Yeni bir iş akışı eklemek için: Sayfa'dan türeyen bir sınıf yaz (ayarlari_kur,
eksik, ayarlari_oku, calistir, sonuc_metni) ve en alttaki SAYFALAR listesine ekle.
"""

import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
import wave
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analiz  # noqa: E402
import davar  # noqa: E402
import reels  # noqa: E402
import ses  # noqa: E402

try:
    import winsound  # aday dinletmek için; yalnızca Windows'ta var
except ImportError:
    winsound = None

ZEMIN = "#0F131A"
PANEL = "#161B24"
KART = "#1C2330"
CIZGI = "#2A3342"
KUTU = "#0F131A"
YAZI = "#E8ECF2"
SOLUK = "#8C97A8"
KIRMIZI = "#E30613"
KIRMIZI_KOYU = "#B80510"
VURGU = "#FF7880"
VIDEO_TURLERI = [("Video ve ses dosyaları", "*.mp4 *.mov *.mkv *.avi *.mts *.m4v *.webm *.wav *.mp3"),
                 ("Tüm dosyalar", "*.*")]


class Sayfa(ttk.Frame):
    """Bir iş akışının sayfası. Video, çıktı klasörü, ilerleme ve kayıt ortaktır
    (uygulamanın üst ve alt bölümünde durur); sayfa yalnızca kendi ayarlarını taşır.
    """

    ad = ""  # menüde görünen ad
    aciklama = ""
    hazir = True  # False ise henüz yazılmamış bir iş akışıdır

    def __init__(self, ust, uyg, sira):
        super().__init__(ust, style="Panel.TFrame", padding=(28, 22))
        self.uyg = uyg
        ust_satir = ttk.Frame(self, style="Panel.TFrame")
        ust_satir.pack(fill="x")
        sol = ttk.Frame(ust_satir, style="Panel.TFrame")
        sol.pack(side="left")
        ttk.Label(sol, text=f"İŞ AKIŞI  /  {sira:02d}", style="Etiket.TLabel").pack(anchor="w")
        ttk.Label(sol, text=self.ad, style="Baslik.TLabel").pack(anchor="w", pady=(4, 0))
        if self.hazir:  # düğme üstte durur: ayarlar uzasa da hep görünür
            self.baslat_dugmesi = ttk.Button(ust_satir, text="Başlat", style="Ana.TButton",
                                             command=self._baslat)
            self.baslat_dugmesi.pack(side="right")
            self.durum = ttk.Label(ust_satir, text="", style="PanelSoluk.TLabel")
            self.durum.pack(side="right", padx=14)
        ttk.Label(self, text=self.aciklama, style="PanelSoluk.TLabel", wraplength=760,
                  justify="left").pack(anchor="w", pady=(4, 14))
        self.ayarlari_kur(self._kaydirilan_alan())

    def _kaydirilan_alan(self):
        """Ayarların yerleştiği alan; pencereye sığmazsa fare tekerleğiyle kayar."""
        tuval = tk.Canvas(self, bg=PANEL, highlightthickness=0, bd=0)
        cubuk = ttk.Scrollbar(self, orient="vertical", command=tuval.yview)
        ic = ttk.Frame(tuval, style="Panel.TFrame")
        pencere = tuval.create_window((0, 0), window=ic, anchor="nw")
        tuval.configure(yscrollcommand=cubuk.set)
        tuval.pack(side="left", fill="both", expand=True)

        def sigiyor_mu():
            return ic.winfo_reqheight() <= tuval.winfo_height()

        def yenile(_=None):
            tuval.configure(scrollregion=(0, 0, ic.winfo_reqwidth(), ic.winfo_reqheight()))
            if sigiyor_mu():
                cubuk.pack_forget()
                tuval.yview_moveto(0)
            elif not cubuk.winfo_ismapped():
                cubuk.pack(side="right", fill="y", padx=(8, 0))

        def tekerlek(olay):
            if not sigiyor_mu():
                tuval.yview_scroll(-1 if olay.delta > 0 else 1, "units")

        ic.bind("<Configure>", yenile)
        tuval.bind("<Configure>", lambda o: (tuval.itemconfigure(pencere, width=o.width), yenile()))
        self.bind("<Enter>", lambda _: self.bind_all("<MouseWheel>", tekerlek))
        self.bind("<Leave>", lambda _: self.unbind_all("<MouseWheel>"))
        return ic

    # --- alt sınıfların dolduracakları ---------------------------------------
    def ayarlari_kur(self, ust):
        """Aracın kendi ayar kutularını `ust` içine yerleştirir."""

    def eksik(self):
        """Başlatmaya engel bir eksik varsa açıklamasını, yoksa "" döndürür."""
        return ""

    def ayarlari_oku(self):
        """Ayarları sözlük olarak döndürür; geçersiz değer varsa ValueError atar."""
        return {}

    def calistir(self, ayar, ilerleme):
        """İşi yapar (arka planda çağrılır); içinde "cikti" olan bir sözlük döndürür."""

    def sonuc_metni(self, sonuc):
        return ""

    def tamamla(self, sonuc):
        """İş bitince ana pencerede çağrılır; kullanıcıya bir şey sorup sonucu
        değiştirebilir. None döndürürse iş vazgeçilmiş sayılır."""
        return sonuc

    # --- ortak parçalar -----------------------------------------------------
    def kart(self, ust, degisken, baslik, aciklama=""):
        """Başlıklı bir kart. `degisken` verilirse başlık işaret kutusu olur ve
        kutu kapalıyken içindeki ayarlar soluklaşır."""
        kart = ttk.Frame(ust, style="Kart.TFrame", padding=(16, 12))
        kart.pack(fill="x", pady=(0, 10))
        if degisken is not None:
            ttk.Checkbutton(kart, text=baslik, variable=degisken,
                            style="KartBaslik.TCheckbutton").pack(anchor="w")
        else:
            ttk.Label(kart, text=baslik, style="KartBaslik.TLabel").pack(anchor="w")
        girinti = 26 if degisken is not None else 0
        if aciklama:
            ttk.Label(kart, text=aciklama, style="KartSoluk.TLabel", wraplength=700,
                      justify="left").pack(anchor="w", padx=(girinti, 0))
        govde = ttk.Frame(kart, style="Kart.TFrame")
        govde.pack(fill="x", padx=(girinti, 0))
        if degisken is not None:
            def ac_kapa(*_):
                for w in govde.winfo_children():
                    if isinstance(w, (ttk.Spinbox, ttk.Entry, ttk.Checkbutton, ttk.Scale)):
                        w.configure(state="normal" if degisken.get() else "disabled")
            degisken.trace_add("write", ac_kapa)
            degisken.trace_add("write", lambda *_: self.durumu_guncelle())
        return govde

    def sure_satiri(self, govde, sira, ad, degisken, en_az, en_cok, ipucu):
        ttk.Label(govde, text=ad, style="Kart.TLabel").grid(
            row=sira, column=0, sticky="w", padx=(0, 12), pady=(8, 0))
        ttk.Spinbox(govde, textvariable=degisken, from_=en_az, to=en_cok, increment=0.05,
                    width=6, format="%.2f").grid(row=sira, column=1, sticky="w", pady=(8, 0))
        ttk.Label(govde, text="sn", style="Kart.TLabel").grid(
            row=sira, column=2, sticky="w", padx=(6, 14), pady=(8, 0))
        ttk.Label(govde, text=ipucu, style="KartSoluk.TLabel").grid(
            row=sira, column=3, sticky="w", pady=(8, 0))
        govde.columnconfigure(3, weight=1)  # geniş satırların fazlası son sütuna gitsin

    def durumu_guncelle(self):
        if not self.hazir:
            return
        if self.uyg.calisiyor:
            self.baslat_dugmesi.configure(state="disabled")
            return
        neden = "Önce yukarıdan bir video seç" if not self.uyg.video.get().strip() else self.eksik()
        self.baslat_dugmesi.configure(state="disabled" if neden else "normal")
        self.durum.configure(text=neden)

    def _baslat(self):
        try:
            ayar = self.ayarlari_oku()
        except (tk.TclError, ValueError):
            self.uyg.kayit("Sayı kutularından birinde sayı olmayan bir değer var.", hata=True)
            return
        except davar.Hata as h:
            self.uyg.kayit("Olmadı: " + str(h), hata=True)
            return
        self.uyg.is_baslat(self, ayar)


class IlkAnaliz(Sayfa):
    ad = "İlk Analiz"
    aciklama = ("Konuşmayı bir kez, kelime kelime zamanlarıyla yazıya döker ve videonun yanına kaydeder. "
                "Sonraki iş akışları bu kaydı kullanır; aynı video yeniden yazıya dökülmez.")

    def ayarlari_kur(self, ust):
        self.srt = tk.BooleanVar(value=True)
        self.metin = tk.BooleanVar(value=True)
        self.model = tk.StringVar(value="small")
        self.yeniden = tk.BooleanVar(value=False)

        g = self.kart(ust, None, "Durum")
        self.kayit_durumu = ttk.Label(g, text="", style="Kart.TLabel", wraplength=700, justify="left")
        self.kayit_durumu.pack(anchor="w", pady=(6, 0))

        g = self.kart(ust, None, "Yazıya dökme",
                      "Bilgisayarında çalışır, internete bir şey gönderilmez. Videonun süresinin "
                      "yarısı kadar zaman alabilir; ilk kullanımda model indirilir.")
        ttk.Label(g, text="Doğruluk", style="Kart.TLabel").grid(row=0, column=0, sticky="w", pady=(10, 0))
        kutu = ttk.Frame(g, style="Kart.TFrame")
        kutu.grid(row=0, column=1, sticky="w", padx=(14, 0), pady=(10, 0))
        ttk.Combobox(kutu, textvariable=self.model, values=["base", "small", "medium"],
                     width=9, state="readonly").pack(side="left")
        ttk.Label(kutu, text="  base hızlı ama hatalı · small dengeli · medium en doğru, çok yavaş",
                  style="KartSoluk.TLabel").pack(side="left")
        ttk.Checkbutton(g, text="Kayıtlı analiz olsa da baştan yazıya dök", variable=self.yeniden,
                        style="Kart.TCheckbutton").grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 0))

        g = self.kart(ust, None, "Ek dosyalar", "Analizden üretilir; yazıya dökme yeniden yapılmaz.")
        ttk.Checkbutton(g, text="Altyazı dosyası (.srt)", variable=self.srt,
                        style="Kart.TCheckbutton").grid(row=0, column=0, sticky="w", pady=(8, 0))
        ttk.Label(g, text="YouTube Studio → Altyazılar bölümüne yüklenir",
                  style="KartSoluk.TLabel").grid(row=0, column=1, sticky="w", padx=(14, 0), pady=(8, 0))
        ttk.Checkbutton(g, text="Zaman damgalı metin (.txt)", variable=self.metin,
                        style="Kart.TCheckbutton").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Label(g, text="Her satırın başında [dakika:saniye]",
                  style="KartSoluk.TLabel").grid(row=1, column=1, sticky="w", padx=(14, 0), pady=(8, 0))

    def eksik(self):
        kayit = self.uyg.analiz()
        if kayit:
            self.kayit_durumu.configure(
                text=f"Bu video için kayıtlı analiz var: {len(kayit['kelimeler'])} kelime, "
                     f"model {kayit['model']}. Başlat'a basarsan yalnızca ek dosyalar yazılır.")
        else:
            self.kayit_durumu.configure(text="Bu video henüz yazıya dökülmedi.")
        return ""

    def ayarlari_oku(self):
        return dict(video=self.uyg.video_yolu(), klasor=self.uyg.cikti_klasoru(), srt=self.srt.get(),
                    metin=self.metin.get(), model=self.model.get(), yeniden=self.yeniden.get())

    def calistir(self, ayar, ilerleme):
        return analiz.ilk_analiz(ilerleme=ilerleme, **ayar)

    def sonuc_metni(self, sonuc):
        return analiz.rapor(sonuc)


class KabaKurgu(Sayfa):
    ad = "Kaba Kurgu"
    aciklama = ("Sessizlikleri, “ııı / eee” duraksamalarını ve istediğin dolgu kelimelerini bulur; "
                "DaVinci Resolve için kesilmiş zaman çizelgesi hazırlar. Orijinal videoya dokunmaz. "
                "Resolve'da: File → Import → Timeline…")

    def ayarlari_kur(self, ust):
        self.sessizlik = tk.BooleanVar(value=True)
        self.iii = tk.BooleanVar(value=True)
        self.kontrol = tk.BooleanVar(value=False)
        self.sor = tk.BooleanVar(value=True)
        self.min_sessizlik = tk.DoubleVar(value=0.5)
        self.pay_bas = tk.DoubleVar(value=0.10)
        self.pay_son = tk.DoubleVar(value=0.15)
        self.iii_min = tk.DoubleVar(value=0.30)
        self.dolgular = tk.StringVar()

        g = self.kart(ust, self.sessizlik, "Sessizlikleri kes", "Konuşma olmayan boşlukları atar.")
        self.sure_satiri(g, 0, "En kısa sessizlik", self.min_sessizlik, 0.2, 2.0,
                         "Bundan kısa boşluklara dokunulmaz")
        self.sure_satiri(g, 1, "Kelimeden önce pay", self.pay_bas, 0.0, 0.5,
                         "Kelime başı yeniyorsa artır")
        self.sure_satiri(g, 2, "Kelimeden sonra pay", self.pay_son, 0.0, 0.5,
                         "Kelime sonu yeniyorsa artır")

        g = self.kart(ust, self.iii, "“Iıı / eee” duraksamalarını bul",
                      "Uzatılmış düşünme seslerini sesin kendisinden bulur.")
        self.sure_satiri(g, 0, "En kısa duraksama", self.iii_min, 0.2, 1.0,
                         "Düşürürsen daha çok yakalar, yanlış aday artar")

        g = self.kart(ust, None, "Dolgu kelimeleri",
                      "Konuşmacının ağız alışkanlıkları. Virgülle ayır: yani, şey, işte, aslında")
        ttk.Entry(g, textvariable=self.dolgular).pack(fill="x", pady=(8, 0))
        self.analiz_durumu = ttk.Label(g, text="", style="KartSoluk.TLabel", wraplength=700, justify="left")
        self.analiz_durumu.pack(anchor="w", pady=(6, 0))

        g = self.kart(ust, None, "Uygulama")
        ttk.Checkbutton(g, text="Adayları kesmeden önce bana göster", variable=self.sor,
                        style="Kart.TCheckbutton").pack(anchor="w", pady=(8, 0))
        ttk.Label(g, text="Duraksamalar ve dolgu kelimeleri bir listede gelir; dinleyip işaretini "
                          "değiştirebilirsin. Kapalıysa yalnızca emin olunanlar kesilir.",
                  style="KartSoluk.TLabel", wraplength=680, justify="left").pack(anchor="w", padx=(26, 0))
        ttk.Checkbutton(g, text="Kontrol çizelgesi de hazırla", variable=self.kontrol,
                        style="Kart.TCheckbutton").pack(anchor="w", pady=(8, 0))
        ttk.Label(g, text="Kesilen adayları birer saniye öncesi ve sonrasıyla gösteren ikinci bir "
                          "çizelge; Resolve içinde denetlemek için.",
                  style="KartSoluk.TLabel", wraplength=680, justify="left").pack(anchor="w", padx=(26, 0))
        self.dolgular.trace_add("write", lambda *_: self.durumu_guncelle())

    def _dolgu_listesi(self):
        return [d.strip() for d in self.dolgular.get().split(",") if d.strip()]

    def eksik(self):
        kayit = self.uyg.analiz()
        if kayit:
            self.analiz_durumu.configure(
                text="İlk Analiz bulundu: duraksamalar metinle karşılaştırılacak, dolgu kelimeleri aranabilir.")
        else:
            self.analiz_durumu.configure(
                text="Bu video için İlk Analiz yok: duraksamalar yalnızca sesten bulunur, "
                     "dolgu kelimeleri aranamaz.")
        if self._dolgu_listesi() and not kayit:
            return "Dolgu kelimeleri için önce İlk Analiz'i çalıştır"
        if not (self.sessizlik.get() or self.iii.get() or self._dolgu_listesi()):
            return "Kesilecek en az bir şey işaretle"
        return ""

    def ayarlari_oku(self):
        video = self.uyg.video_yolu()
        kayit = self.uyg.analiz()
        return dict(
            cikti=self.uyg.cikti_klasoru() / (video.stem + "_kesik.fcpxml"),
            kontrol=self.kontrol.get(), sor=self.sor.get(),
            cozumleme=dict(
                video=video, sessizlik=self.sessizlik.get(), iii=self.iii.get(),
                min_sessizlik=float(self.min_sessizlik.get()), pay_bas=float(self.pay_bas.get()),
                pay_son=float(self.pay_son.get()), iii_min=float(self.iii_min.get()),
                kelimeler=kayit["kelimeler"] if kayit else None,
                dolgu_kelimeleri=self._dolgu_listesi()),
        )

    def calistir(self, ayar, ilerleme):
        return {"durum": davar.cozumle(ilerleme=ilerleme, **ayar["cozumleme"]), "ayar": ayar}

    def tamamla(self, sonuc):
        durum, ayar = sonuc["durum"], sonuc["ayar"]
        if ayar["sor"] and durum["adaylar"]:
            if not OnayPenceresi(self.uyg, durum).onaylandi:
                return None
        return davar.uygula(durum, cikti=ayar["cikti"], kontrol=ayar["kontrol"])

    def sonuc_metni(self, sonuc):
        return davar.rapor(sonuc, ayrinti=False)


class OnayPenceresi(tk.Toplevel):
    """Kesim adaylarının listesi: dinle, işaretini değiştir, uygula."""

    GUVEN_SIRASI = {"düşük": 0, "orta": 1, "yüksek": 2}

    def __init__(self, uyg, durum):
        super().__init__(uyg)
        self.durum = durum
        self.adaylar = durum["adaylar"]
        self.onerilen = [a["sec"] for a in self.adaylar]
        self.onaylandi = False
        self.gecici = tempfile.TemporaryDirectory(prefix="davar_dinle_")
        self.title("Davar — Kaba Kurgu adayları")
        self.configure(bg=PANEL)
        self.geometry("1200x680")
        self.minsize(1080, 460)
        self.transient(uyg)

        ust = ttk.Frame(self, style="Panel.TFrame", padding=(18, 14, 18, 8))
        ust.pack(fill="x")
        ttk.Label(ust, text="Kesim adaylarını gözden geçir", style="Baslik.TLabel").pack(anchor="w")
        ttk.Label(ust, text="İşaretli olanlar kesilecek. Satıra çift tıkla: dinle. İlk sütuna tıkla ya da "
                            "boşluk tuşu: işareti değiştir. Sessizlikler bu listede yok, doğrudan kesilir."
                            + ("" if durum["metinli"] else "  İlk Analiz olmadığı için bağlam metni yok."),
                  style="PanelSoluk.TLabel", wraplength=980, justify="left").pack(anchor="w", pady=(4, 0))
        self.supheli = tk.BooleanVar(value=False)
        ttk.Checkbutton(ust, text="Yalnızca emin olunmayanları göster", variable=self.supheli,
                        style="Panel.TCheckbutton", command=self._doldur).pack(anchor="w", pady=(8, 0))

        alt = ttk.Frame(self, style="Panel.TFrame", padding=(18, 8, 18, 14))
        alt.pack(side="bottom", fill="x")
        self.ozet = ttk.Label(alt, text="", style="Panel.TLabel")
        self.ozet.pack(anchor="w", pady=(0, 10))
        for metin, komut in (("Dinle", lambda: self._dinle(False)),
                             ("Kesilmiş halini dinle", lambda: self._dinle(True)),
                             ("Ortaları da işaretle", self._ortalari_isaretle),
                             ("Hepsini işaretle", lambda: self._toplu(True)),
                             ("Hiçbirini işaretleme", lambda: self._toplu(False)),
                             ("Önerilene dön", lambda: self._toplu(None))):
            ttk.Button(alt, text=metin, command=komut).pack(side="left", padx=(0, 8))
        ttk.Button(alt, text="Uygula", style="Ana.TButton", command=self._uygula).pack(side="right")
        ttk.Button(alt, text="Vazgeç", command=self._kapat).pack(side="right", padx=(0, 10))

        orta = ttk.Frame(self, style="Panel.TFrame", padding=(18, 4))
        orta.pack(fill="both", expand=True)
        sutunlar = (("sil", "Kes", 50, "center"), ("zaman", "Zaman", 90, "e"), ("sure", "Süre", 70, "e"),
                    ("tur", "Tür", 200, "w"), ("guven", "Güven", 80, "w"), ("metin", "Bağlam", 480, "w"))
        self.liste = ttk.Treeview(orta, columns=[x[0] for x in sutunlar], show="headings",
                                  selectmode="browse")
        for kod, ad, en, hiza in sutunlar:
            self.liste.heading(kod, text=ad, anchor=hiza if hiza != "center" else "center")
            self.liste.column(kod, width=en, anchor=hiza, stretch=kod == "metin")
        cubuk = ttk.Scrollbar(orta, orient="vertical", command=self.liste.yview)
        self.liste.configure(yscrollcommand=cubuk.set)
        self.liste.pack(side="left", fill="both", expand=True)
        cubuk.pack(side="right", fill="y", padx=(6, 0))
        self.liste.tag_configure("supheli", foreground=VURGU)
        self.liste.tag_configure("kesilmeyecek", foreground=SOLUK)
        self.liste.bind("<Button-1>", self._tikla)
        self.liste.bind("<Double-1>", lambda _: self._dinle(False))
        self.liste.bind("<space>", lambda _: self._degistir())
        self.liste.bind("<Return>", lambda _: self._dinle(False))

        self._doldur()
        self.protocol("WM_DELETE_WINDOW", self._kapat)
        self.grab_set()
        self.liste.focus_set()
        self.wait_window()

    # --- liste ------------------------------------------------------------
    def _satir(self, i):
        a = self.adaylar[i]
        return ("☑" if a["sec"] else "☐", davar.sure_yaz(a["bas"]), f"{a['son'] - a['bas']:.2f} sn",
                davar.tur_adi(a), a["guven"], a["metin"])

    def _etiket(self, i):
        a = self.adaylar[i]
        return ("supheli",) if a["guven"] == "düşük" else (() if a["sec"] else ("kesilmeyecek",))

    def _doldur(self):
        self.liste.delete(*self.liste.get_children())
        for i, a in enumerate(self.adaylar):
            if self.supheli.get() and a["guven"] == "yüksek":
                continue
            self.liste.insert("", "end", iid=str(i), values=self._satir(i), tags=self._etiket(i))
        ilk = self.liste.get_children()
        if ilk:
            self.liste.selection_set(ilk[0])
            self.liste.focus(ilk[0])
        self._ozetle()

    def _ozetle(self):
        kesimler, _ = davar.kesim_plani(self.durum)
        kisalma = sum(son - bas for bas, son in kesimler) / self.durum["fps"]
        secili = sum(a["sec"] for a in self.adaylar)
        self.ozet.configure(
            text=f"{len(self.adaylar)} adayın {secili} tanesi kesilecek "
                 f"({len(self.liste.get_children())} tanesi listede). "
                 f"Sessizliklerle birlikte çizelge {davar.sure_yaz(kisalma)} kısalacak.")

    def _secili(self):
        secim = self.liste.selection()
        return int(secim[0]) if secim else None

    def _degistir(self, i=None):
        i = self._secili() if i is None else i
        if i is None:
            return
        self.adaylar[i]["sec"] = not self.adaylar[i]["sec"]
        self.liste.item(str(i), values=self._satir(i), tags=self._etiket(i))
        self._ozetle()

    def _tikla(self, olay):
        satir = self.liste.identify_row(olay.y)
        if satir and self.liste.identify_column(olay.x) == "#1":
            self._degistir(int(satir))

    def _toplu(self, deger):
        for i, a in enumerate(self.adaylar):
            a["sec"] = self.onerilen[i] if deger is None else deger
        self._doldur()

    def _ortalari_isaretle(self):
        """Kısa duraksamalar gibi, işaretsiz gelen orta güvenli ses adaylarını da işaretler."""
        for a in self.adaylar:
            if a["guven"] == "orta" and a["tur"] in ("tek", "bas"):
                a["sec"] = True
        self._doldur()

    # --- dinleme ----------------------------------------------------------
    def _dinle(self, kesilmis):
        i = self._secili()
        if i is None:
            return
        if winsound is None:
            self.ozet.configure(text="Dinleme yalnızca Windows'ta çalışıyor.")
            return
        a, ses, hiz = self.adaylar[i], self.durum["ornekler"], davar.ORNEK_HIZI
        bas, son = int(max(a["bas"] - 1.5, 0) * hiz), int((a["son"] + 1.5) * hiz)
        if kesilmis:
            parca = davar.np.concatenate((ses[bas:int((a["bas"] + davar.III_PAY) * hiz)],
                                          ses[int((a["son"] - davar.III_PAY) * hiz):son]))
        else:
            parca = ses[bas:son]
        yol = Path(self.gecici.name) / f"aday_{i}_{int(kesilmis)}.wav"
        with wave.open(str(yol), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(hiz)
            w.writeframes((davar.np.clip(parca, -1, 1) * 32767).astype("<i2").tobytes())
        winsound.PlaySound(str(yol), winsound.SND_FILENAME | winsound.SND_ASYNC)

    # --- kapanış ----------------------------------------------------------
    def _uygula(self):
        self.onaylandi = True
        self._kapat()

    def _kapat(self):
        if winsound is not None:
            winsound.PlaySound(None, winsound.SND_PURGE)
        if not self.onaylandi:  # vazgeçilirse işaretler eski haline dönsün
            for i, a in enumerate(self.adaylar):
                a["sec"] = self.onerilen[i]
        try:
            self.gecici.cleanup()
        except OSError:
            pass
        self.grab_release()
        self.destroy()


class SosyalKlipler(Sayfa):
    ad = "Sosyal Klipler"
    aciklama = ("Yatay videodan seçtiğin aralığı dikey (9:16) Reels / Shorts videosu olarak keser. "
                "Bulanık arka plan üstüne konuşmacı kadrajı, başlık, altyazı ve giriş kapağı ekler.")

    def ayarlari_kur(self, ust):
        self.bas = tk.StringVar()
        self.son = tk.StringVar()
        self.yatay = tk.DoubleVar(value=50)
        self.ust_yazi = tk.StringVar()
        self.baslik1 = tk.StringVar()
        self.baslik2 = tk.StringVar()
        self.altyazi = tk.BooleanVar(value=True)
        self.kapak = tk.BooleanVar(value=False)

        g = self.kart(ust, None, "Aralık ve kadraj")
        ttk.Label(g, text="Başlangıç", style="Kart.TLabel").grid(row=0, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(g, textvariable=self.bas, width=10).grid(row=0, column=1, sticky="w", padx=(12, 20), pady=(8, 0))
        ttk.Label(g, text="Bitiş", style="Kart.TLabel").grid(row=0, column=2, sticky="w", pady=(8, 0))
        kutu = ttk.Frame(g, style="Kart.TFrame")
        kutu.grid(row=0, column=3, sticky="w", pady=(8, 0))
        ttk.Entry(kutu, textvariable=self.son, width=10).pack(side="left", padx=(12, 14))
        ttk.Label(kutu, text="dakika:saniye, örn. 13:06", style="KartSoluk.TLabel").pack(side="left")
        ttk.Label(g, text="Kadraj", style="Kart.TLabel").grid(row=1, column=0, sticky="w", pady=(12, 0))
        kutu = ttk.Frame(g, style="Kart.TFrame")
        kutu.grid(row=1, column=1, columnspan=3, sticky="w", padx=(12, 0), pady=(12, 0))
        ttk.Label(kutu, text="sol", style="KartSoluk.TLabel").pack(side="left")
        ttk.Scale(kutu, variable=self.yatay, from_=0, to=100, length=220).pack(side="left", padx=8)
        ttk.Label(kutu, text="sağ     konuşmacı ortada değilse kaydır", style="KartSoluk.TLabel").pack(side="left")

        g = self.kart(ust, None, "Yazılar", "Boş bıraktığın satır yazılmaz.")
        g.columnconfigure(1, weight=1)
        for sira, (ad, d) in enumerate((("Üst yazı", self.ust_yazi), ("Başlık 1. satır", self.baslik1),
                                        ("Başlık 2. satır", self.baslik2))):
            ttk.Label(g, text=ad, style="Kart.TLabel").grid(row=sira, column=0, sticky="w", pady=(8, 0))
            ttk.Entry(g, textvariable=d).grid(row=sira, column=1, sticky="ew", padx=(12, 0), pady=(8, 0))

        g = self.kart(ust, None, "Ekler")
        ttk.Checkbutton(g, text="Altyazı ekle", variable=self.altyazi,
                        style="Kart.TCheckbutton").grid(row=0, column=0, sticky="w", pady=(8, 0))
        ttk.Label(g, text="Konuşmayı videoya gömer (İlk Analiz varsa onu kullanır). Düzeltme imkânı yok; önce oku.",
                  style="KartSoluk.TLabel").grid(row=0, column=1, sticky="w", padx=(14, 0), pady=(8, 0))
        ttk.Checkbutton(g, text="Giriş kapağı ekle", variable=self.kapak,
                        style="Kart.TCheckbutton").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Label(g, text="Başa, üst yazı ve başlığı gösteren 2,5 saniyelik kapak koyar.",
                  style="KartSoluk.TLabel").grid(row=1, column=1, sticky="w", padx=(14, 0), pady=(8, 0))
        for d in (self.bas, self.son, self.ust_yazi, self.baslik1, self.baslik2, self.kapak):
            d.trace_add("write", lambda *_: self.durumu_guncelle())

    def eksik(self):
        if not self.bas.get().strip() or not self.son.get().strip():
            return "Başlangıç ve bitiş zamanını yaz"
        if self.kapak.get() and not (self.ust_yazi.get().strip() or self.baslik1.get().strip()
                                     or self.baslik2.get().strip()):
            return "Giriş kapağı için başlık ya da üst yazı yaz"
        return ""

    def ayarlari_oku(self):
        video = self.uyg.video_yolu()
        return dict(
            video=video, cikti=self.uyg.cikti_klasoru() / (video.stem + "_reels.mp4"),
            bas=self.bas.get(), son=self.son.get(), ust_yazi=self.ust_yazi.get(),
            baslik=[self.baslik1.get(), self.baslik2.get()], yatay=float(self.yatay.get()) / 100,
            altyazi=self.altyazi.get(), kapak=self.kapak.get(),
            kelimeler=(self.uyg.analiz() or {}).get("kelimeler"),
        )

    def calistir(self, ayar, ilerleme):
        return reels.reels_kes(ilerleme=ilerleme, **ayar)

    def sonuc_metni(self, sonuc):
        return reels.rapor(sonuc)


class Yakinda(Sayfa):
    """Henüz yazılmamış iş akışı: ne yapacağını ve neye ihtiyaç duyduğunu anlatır."""

    hazir = False
    yapacaklari = ()
    gereken = ""

    def ayarlari_kur(self, ust):
        self.kart(ust, None, "Henüz yazılmadı", "Bu iş akışı planlandı ama çalışmıyor.")
        g = self.kart(ust, None, "Ne yapacak")
        for satir in self.yapacaklari:
            ttk.Label(g, text="•  " + satir, style="Kart.TLabel", wraplength=700,
                      justify="left").pack(anchor="w", pady=(6, 0))
        if self.gereken:
            self.kart(ust, None, "Ne gerekiyor", self.gereken)


class SesSayfasi(Sayfa):
    ad = "Ses"
    aciklama = ("Ayrı kaydedilmiş sesleri videodaki yerine oturtur ve ses düzeyini ayarlar. Görüntü yeniden "
                "kodlanmaz; sonuç yeni bir video olarak yazılır ve sonraki adımlar onunla devam eder.")
    SES_TURLERI = [("Ses ve video dosyaları", "*.wav *.mp3 *.m4a *.aac *.ogg *.flac *.mp4 *.mov *.mkv"),
                   ("Tüm dosyalar", "*.*")]

    def ayarlari_kur(self, ust):
        self.duzey = tk.BooleanVar(value=True)
        self.dengele = tk.BooleanVar(value=False)
        self.gurultu = tk.BooleanVar(value=False)
        self.dosyalar = []

        g = self.kart(ust, None, "Ayrı kaydedilmiş sesler",
                      "Yaka mikrofonu, ses kayıt cihazı ya da sonradan kaydedilmiş bölümler. Davar her "
                      "birinin videoda nereye denk geldiğini kendisi bulur, düzeyini videonun sesine "
                      "eşitler ve videonun o bölümdeki sesinin yerine koyar. Videoda geçmeyen ses "
                      "yerleştirilmez.")
        satir = ttk.Frame(g, style="Kart.TFrame")
        satir.pack(fill="x", pady=(8, 0))
        self.liste = tk.Listbox(satir, height=4, bg=KUTU, fg=YAZI, bd=0, highlightthickness=1,
                                highlightbackground=CIZGI, selectbackground="#36415A",
                                selectforeground="white", activestyle="none", font=("Segoe UI", 10))
        self.liste.pack(side="left", fill="x", expand=True)
        dugmeler = ttk.Frame(satir, style="Kart.TFrame")
        dugmeler.pack(side="left", padx=(10, 0), anchor="n")
        ttk.Button(dugmeler, text="Ekle…", command=self._ekle).pack(fill="x")
        ttk.Button(dugmeler, text="Çıkar", command=self._cikar).pack(fill="x", pady=(6, 0))

        g = self.kart(ust, None, "Ses düzeyi")
        for sira, (d, ad, ipucu) in enumerate((
                (self.duzey, "YouTube düzeyine getir", "Sesi -14 LUFS'a ayarlar; kısık ya da patlayan sesi düzeltir"),
                (self.dengele, "Konuşmacıların düzeyini dengele", "Kısık konuşanı yükseltir; kulakla denetle"),
                (self.gurultu, "Dip gürültüsünü azalt", "Uğultu ve hışırtıyı kısar; kulakla denetle"))):
            ttk.Checkbutton(g, text=ad, variable=d, style="Kart.TCheckbutton").grid(
                row=sira, column=0, sticky="w", pady=(8, 0))
            ttk.Label(g, text=ipucu, style="KartSoluk.TLabel").grid(
                row=sira, column=1, sticky="w", padx=(14, 0), pady=(8, 0))
            d.trace_add("write", lambda *_: self.durumu_guncelle())

        self.kart(ust, None, "Sırada",
                  "Her konuşmacının ayrı mikrofonu olan kayıtlarda, konuşmayan kişinin mikrofonuna "
                  "sızan sesi kısmak.")

    def _ekle(self):
        ilk = self.uyg.video_yolu().parent if self.uyg.video.get().strip() else None
        for yol in filedialog.askopenfilenames(title="Ayrı ses dosyalarını seç", filetypes=self.SES_TURLERI,
                                               initialdir=ilk if ilk and ilk.is_dir() else None):
            self.ekle(yol)

    def ekle(self, yol):
        yol = Path(os.path.normpath(yol))
        if yol not in self.dosyalar:
            self.dosyalar.append(yol)
            self.liste.insert("end", yol.name)
        self.durumu_guncelle()

    def _cikar(self):
        for i in reversed(self.liste.curselection()):
            self.liste.delete(i)
            del self.dosyalar[i]
        self.durumu_guncelle()

    def eksik(self):
        if not (self.dosyalar or self.duzey.get() or self.dengele.get() or self.gurultu.get()):
            return "Bir ses ekle ya da bir işlem işaretle"
        return ""

    def ayarlari_oku(self):
        return dict(video=self.uyg.video_yolu(), sesler=list(self.dosyalar),
                    klasor=self.uyg.cikti_klasoru(), duzey=self.duzey.get(),
                    dengele=self.dengele.get(), gurultu=self.gurultu.get())

    def calistir(self, ayar, ilerleme):
        return ses.ses_isle(ilerleme=ilerleme, **ayar)

    def tamamla(self, sonuc):
        # sonraki adımlar yeni sesli videoyla çalışsın
        self.uyg.video.set(str(sonuc["cikti"]))
        return sonuc

    def sonuc_metni(self, sonuc):
        return ses.rapor(sonuc) + "\nVideo alanı bu yeni dosyaya çevrildi; sonraki adımlar onunla çalışır."


class CokKamera(Yakinda):
    ad = "Çok Kamera Kurgusu"
    aciklama = "Kim konuşuyorsa onun kamerasını seçer; arada genel plana dönerek kurguyu doğal tutar."
    yapacaklari = (
        "Her mikrofonu bir konuşmacıya ve o konuşurken gösterilecek kameraya bağlarsın.",
        "Konuşana göre kamera seçer; en kısa ve en uzun plan süresine uyar.",
        "Belirli aralıklarla genel plana (ikili ya da geniş çekim) döner.",
        "Sonucu Resolve için tek çizelge olarak yazar.",
    )
    gereken = ("Birbirine eşlenmiş (senkron) kamera dosyaları ve konuşmacı başına ayrı ses. "
               "Tek kameralı çekimlerde kullanılamaz.")


class IcerikAnalizi(Yakinda):
    ad = "İçerik Analizi"
    aciklama = "İlk Analiz'in metnini okuyup videonun konularını, bölümlerini ve öne çıkan yerlerini çıkarır."
    yapacaklari = (
        "Konu başlıklarını ve YouTube bölüm zamanlarını çıkarır.",
        "Videonun özetini ve öne çıkan cümlelerini listeler.",
        "Sosyal klip için aday aralıklar önerir (kanca, bağlam, sonuç).",
    )
    gereken = ("Metni anlayan bir dil modeli. İnternet üzerinden bir yapay zekâ servisi (anahtar ve küçük "
               "bir ücret gerekir, metin dışarı gider) ya da bilgisayarda çalışan bir model (ücretsiz, "
               "yavaş ve daha zayıf). Hangisinin kullanılacağı henüz kararlaştırılmadı.")


class Yazilar(Yakinda):
    ad = "Yazılar"
    aciklama = "Konuşmacı adı ve konu başlığı gibi ekran yazılarını (KJ / alt bant) hazırlar."
    yapacaklari = (
        "Konuşmacı adı ve unvanı için yumuşak giriş-çıkışlı alt bant üretir.",
        "Konu değiştikçe ekrana gelen konu başlıklarını hazırlar.",
        "Yazıları, zamanları belli saydam video ya da çizelge olarak Resolve'a verir.",
    )
    gereken = "Konu başlıklarının zamanı için İçerik Analizi'nin bölüm çıkarma adımı."


class GorselMalzeme(Yakinda):
    ad = "Görsel Malzeme"
    aciklama = "Konuşulan konulara göre araya girecek fotoğraf, belge ve görüntüleri düzenler."
    yapacaklari = (
        "Metinde adı geçen yer, kişi ve belgeleri listeler: nereye hangi görsel girmeli.",
        "Seçtiğin görselleri doğru zamana, yavaş yakınlaştırmayla yerleştirir.",
    )
    gereken = "Bu iş akışının kapsamı henüz netleşmedi; önce diğerleri bitecek."


class Yayin(Yakinda):
    ad = "Yayın"
    aciklama = "YouTube'a yüklemeden önce gereken metinleri ve dosyaları toplar."
    yapacaklari = (
        "Bölüm zamanlarıyla birlikte YouTube açıklaması taslağı çıkarır.",
        "Başlık önerileri ve etiketler hazırlar.",
        "Kapak görseli (thumbnail) için yazı ve kare önerir.",
    )
    gereken = "İçerik Analizi'nin bölüm çıkarma adımı."


SAYFALAR = [SesSayfasi, IlkAnaliz, KabaKurgu, CokKamera, IcerikAnalizi, Yazilar, GorselMalzeme,
            SosyalKlipler, Yayin]


class Arayuz(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Davar")
        self.configure(bg=ZEMIN)
        self.geometry("1180x900")
        self.minsize(1040, 800)
        self._stil()
        self.video = tk.StringVar()
        self.klasor = tk.StringVar()
        self.kuyruk = queue.Queue()
        self.calisiyor = False
        self.son_cikti = None

        self._ust_bolum()
        self._alt_bolum()
        orta = tk.Frame(self, bg=ZEMIN)
        orta.pack(fill="both", expand=True, padx=16)
        menu = tk.Frame(orta, bg=ZEMIN, width=250)
        menu.pack(side="left", fill="y", pady=(0, 12))
        menu.pack_propagate(False)
        govde = ttk.Frame(orta, style="Panel.TFrame")
        govde.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=(0, 12))

        self.sayfalar, self.dugmeler = [], []
        for sira, sinif in enumerate(SAYFALAR):
            sayfa = sinif(govde, self, sira + 1)
            sayfa.place(relx=0, rely=0, relwidth=1, relheight=1)
            dugme = tk.Label(menu, text=f"{sira + 1:02d}    {sinif.ad}", anchor="w", padx=18, pady=13,
                             font=("Segoe UI Semibold", 11), cursor="hand2")
            dugme.pack(fill="x", pady=(0, 2))
            dugme.bind("<Button-1>", lambda _, s=sira: self.goster(s))
            self.sayfalar.append(sayfa)
            self.dugmeler.append(dugme)
        self.goster(0)
        self.video.trace_add("write", lambda *_: self._durumlari_guncelle())
        self.klasor.trace_add("write", lambda *_: self._durumlari_guncelle())
        self._durumlari_guncelle()
        self.kayit("Davar hazır. Bir video seç, soldan iş akışını seç.")
        self.after(100, self._kuyrugu_isle)
        if len(sys.argv) > 1 and Path(sys.argv[1]).is_file():  # üstüne sürüklenen dosya
            self.video.set(sys.argv[1])

    # --- yerleşim -----------------------------------------------------------
    def _ust_bolum(self):
        ust = ttk.Frame(self, style="Panel.TFrame", padding=(22, 16))
        ust.pack(fill="x", padx=16, pady=(16, 12))
        sol = ttk.Frame(ust, style="Panel.TFrame")
        sol.pack(side="left")
        ttk.Label(sol, text="DAVAR", style="Logo.TLabel").pack(anchor="w")
        ttk.Label(sol, text="DaVinci Resolve için kurgu öncesi yardımcı",
                  style="PanelSoluk.TLabel").pack(anchor="w")
        sag = ttk.Frame(ust, style="Panel.TFrame")
        sag.pack(side="right")
        ttk.Label(sag, text="Video / ses dosyası", style="Panel.TLabel").grid(row=0, column=0, sticky="e", padx=(0, 10))
        ttk.Entry(sag, textvariable=self.video, width=56).grid(row=0, column=1, ipady=3)
        ttk.Button(sag, text="Seç", command=self._video_sec).grid(row=0, column=2, padx=(8, 0))
        ttk.Label(sag, text="Çıktı klasörü", style="Panel.TLabel").grid(row=1, column=0, sticky="e", padx=(0, 10), pady=(8, 0))
        ttk.Entry(sag, textvariable=self.klasor, width=56).grid(row=1, column=1, ipady=3, pady=(8, 0))
        ttk.Button(sag, text="Seç", command=self._klasor_sec).grid(row=1, column=2, padx=(8, 0), pady=(8, 0))
        ttk.Label(sag, text="Boş bırakırsan çıktılar videonun yanına yazılır",
                  style="PanelSoluk.TLabel", font=("Segoe UI", 8)).grid(row=2, column=1, sticky="w", pady=(2, 0))

    def _alt_bolum(self):
        alt = ttk.Frame(self, style="Panel.TFrame", padding=(18, 12))
        alt.pack(side="bottom", fill="x", padx=16, pady=(0, 16))
        satir = ttk.Frame(alt, style="Panel.TFrame")
        satir.pack(fill="x")
        ttk.Label(satir, text="İŞLEM", style="Etiket.TLabel").pack(side="left")
        self.klasor_dugmesi = ttk.Button(satir, text="Çıktıyı klasörde göster",
                                         command=self._klasoru_ac, state="disabled")
        self.klasor_dugmesi.pack(side="right")
        self.genel_durum = ttk.Label(satir, text="Hazır", style="Panel.TLabel")
        self.genel_durum.pack(side="right", padx=14)
        self.cubuk = ttk.Progressbar(alt, style="Kirmizi.Horizontal.TProgressbar", maximum=100)
        self.cubuk.pack(fill="x", pady=(8, 10))
        ttk.Label(alt, text="KAYIT", style="Etiket.TLabel").pack(anchor="w")
        self.kayit_kutusu = tk.Text(alt, height=6, wrap="word", bd=0, bg=KUTU, fg=YAZI,
                                    insertbackground=YAZI, font=("Consolas", 10), padx=12, pady=10,
                                    highlightthickness=1, highlightbackground=CIZGI, state="disabled")
        self.kayit_kutusu.pack(fill="x", pady=(6, 0))
        self.kayit_kutusu.tag_configure("hata", foreground=VURGU)
        self.kayit_kutusu.tag_configure("saat", foreground=SOLUK)

    def _stil(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(".", background=ZEMIN, foreground=YAZI, font=("Segoe UI", 10),
                    bordercolor=CIZGI, lightcolor=CIZGI, darkcolor=CIZGI)
        for ad, zemin in (("Panel", PANEL), ("Kart", KART)):
            s.configure(f"{ad}.TFrame", background=zemin)
            s.configure(f"{ad}.TLabel", background=zemin, foreground=YAZI)
            s.configure(f"{ad}Soluk.TLabel", background=zemin, foreground=SOLUK, font=("Segoe UI", 9))
        s.configure("PanelSoluk.TLabel", font=("Segoe UI", 10))
        s.configure("Logo.TLabel", background=PANEL, foreground="white", font=("Segoe UI", 22, "bold"))
        s.configure("Baslik.TLabel", background=PANEL, foreground="white", font=("Segoe UI Semibold", 20))
        s.configure("Etiket.TLabel", background=PANEL, foreground=VURGU, font=("Segoe UI Semibold", 9))
        s.configure("KartBaslik.TLabel", background=KART, foreground="white", font=("Segoe UI Semibold", 11))
        for ad, yazi_tipi in (("Kart.TCheckbutton", ("Segoe UI", 10)),
                              ("KartBaslik.TCheckbutton", ("Segoe UI Semibold", 11))):
            s.configure(ad, background=KART, foreground=YAZI, font=yazi_tipi, indicatorbackground=KUTU,
                        indicatorforeground="white", indicatormargin=(0, 0, 8, 0))
            s.map(ad, background=[("active", KART)], foreground=[("disabled", SOLUK)],
                  indicatorbackground=[("selected", KIRMIZI), ("active", KUTU)],
                  indicatorforeground=[("selected", "white")])
        for ad in ("TEntry", "TSpinbox", "TCombobox"):
            s.configure(ad, fieldbackground=KUTU, foreground=YAZI, insertcolor=YAZI, background=KART,
                        arrowcolor=YAZI, bordercolor=CIZGI, lightcolor=CIZGI, darkcolor=CIZGI, padding=4)
            s.map(ad, fieldbackground=[("disabled", KART), ("readonly", KUTU)],
                  foreground=[("disabled", SOLUK), ("readonly", YAZI)],
                  bordercolor=[("focus", VURGU)], lightcolor=[("focus", VURGU)],
                  selectbackground=[("readonly", KUTU)], selectforeground=[("readonly", YAZI)])
        self.option_add("*TCombobox*Listbox.background", KUTU)
        self.option_add("*TCombobox*Listbox.foreground", YAZI)
        self.option_add("*TCombobox*Listbox.selectBackground", KIRMIZI)
        s.configure("TButton", background="#2A3342", foreground=YAZI, padding=(14, 6), borderwidth=0,
                    font=("Segoe UI Semibold", 10))
        s.map("TButton", background=[("disabled", "#1F2632"), ("active", "#36415A")],
              foreground=[("disabled", "#566072")])
        s.configure("Ana.TButton", background=KIRMIZI, foreground="white", padding=(30, 10),
                    font=("Segoe UI Semibold", 12))
        s.map("Ana.TButton", background=[("disabled", "#3A2327"), ("active", KIRMIZI_KOYU)],
              foreground=[("disabled", "#8A6D70")])
        s.configure("Vertical.TScrollbar", background="#2A3342", troughcolor=PANEL, bordercolor=PANEL,
                    lightcolor="#2A3342", darkcolor="#2A3342", arrowcolor=SOLUK, gripcount=0)
        s.map("Vertical.TScrollbar", background=[("active", "#36415A")])
        s.configure("Panel.TCheckbutton", background=PANEL, foreground=YAZI, indicatorbackground=KUTU,
                    indicatorforeground="white")
        s.map("Panel.TCheckbutton", background=[("active", PANEL)],
              indicatorbackground=[("selected", KIRMIZI), ("active", KUTU)])
        s.configure("Treeview", background=KUTU, fieldbackground=KUTU, foreground=YAZI, rowheight=28,
                    bordercolor=CIZGI, lightcolor=CIZGI, darkcolor=CIZGI, font=("Segoe UI", 10))
        s.configure("Treeview.Heading", background=KART, foreground=YAZI, relief="flat",
                    font=("Segoe UI Semibold", 10), padding=(6, 6))
        s.map("Treeview", background=[("selected", "#36415A")], foreground=[("selected", "white")])
        s.map("Treeview.Heading", background=[("active", KART)])
        s.configure("Horizontal.TScale", background=KART, troughcolor=KUTU, bordercolor=CIZGI,
                    lightcolor=CIZGI, darkcolor=CIZGI)
        s.configure("Kirmizi.Horizontal.TProgressbar", background=KIRMIZI, troughcolor=KUTU,
                    bordercolor=CIZGI, lightcolor=KIRMIZI, darkcolor=KIRMIZI, thickness=10)

    # --- ortak davranış -----------------------------------------------------
    def goster(self, sira):
        self.sayfalar[sira].tkraise()
        for i, dugme in enumerate(self.dugmeler):
            if i == sira:
                dugme.configure(bg=KIRMIZI, fg="white")
            else:
                dugme.configure(bg=PANEL, fg=YAZI if SAYFALAR[i].hazir else "#66707F")

    def video_yolu(self):
        return Path(self.video.get().strip().strip('"'))

    def analiz(self):
        """Seçili video için kayıtlı İlk Analiz (yoksa None)."""
        video = self.video_yolu()
        if not self.video.get().strip() or not video.is_file():
            return None
        yol = self.klasor.get().strip().strip('"')
        return analiz.analiz_yukle(video, yol if yol and Path(yol).is_dir() else None)

    def cikti_klasoru(self):
        """Çıktı klasörü boşsa videonun bulunduğu klasör kullanılır."""
        yol = self.klasor.get().strip().strip('"')
        klasor = Path(yol) if yol else self.video_yolu().parent
        if not klasor.is_dir():
            raise davar.Hata(f"çıktı klasörü bulunamadı: {klasor}")
        return klasor

    def _video_sec(self):
        ilk = self.video_yolu().parent if self.video.get().strip() else None
        yol = filedialog.askopenfilename(title="Video seç", filetypes=VIDEO_TURLERI,
                                         initialdir=ilk if ilk and ilk.is_dir() else None)
        if yol:
            self.video.set(os.path.normpath(yol))

    def _klasor_sec(self):
        yol = filedialog.askdirectory(title="Çıktı klasörünü seç")
        if yol:
            self.klasor.set(os.path.normpath(yol))

    def _durumlari_guncelle(self):
        for sayfa in self.sayfalar:
            sayfa.durumu_guncelle()

    def kayit(self, metin, hata=False):
        self.kayit_kutusu.configure(state="normal")
        self.kayit_kutusu.insert("end", time.strftime("%H:%M:%S  "), "saat")
        self.kayit_kutusu.insert("end", metin.strip().replace("\n", "\n          ") + "\n",
                                 "hata" if hata else ())
        self.kayit_kutusu.see("end")
        self.kayit_kutusu.configure(state="disabled")

    def is_baslat(self, sayfa, ayar):
        self.calisiyor = True
        self.son_cikti = None
        self.klasor_dugmesi.configure(state="disabled")
        self.cubuk["value"] = 0
        self._durumlari_guncelle()
        self.kayit(f"{sayfa.ad} başladı.")

        def calis():
            try:
                sonuc = sayfa.calistir(ayar, lambda y, m: self.kuyruk.put(("ilerleme", y, m)))
                self.kuyruk.put(("bitti", sayfa, sonuc))
            except davar.Hata as h:
                self.kuyruk.put(("hata", str(h)))
            except Exception as h:  # beklenmeyen hata da kayıtta görünsün
                self.kuyruk.put(("hata", f"Beklenmeyen hata: {type(h).__name__}: {h}"))
        threading.Thread(target=calis, daemon=True).start()

    def _kuyrugu_isle(self):
        try:
            while True:
                olay = self.kuyruk.get_nowait()
                if olay[0] == "ilerleme":
                    self.cubuk["value"] = olay[1]
                    self.genel_durum.configure(text=olay[2] + "…")
                    continue
                self.calisiyor = False
                if olay[0] == "bitti":
                    try:
                        sonuc = olay[1].tamamla(olay[2])
                    except davar.Hata as h:
                        sonuc = None
                        self.kayit("Olmadı: " + str(h), hata=True)
                    if sonuc is None:
                        self.cubuk["value"] = 0
                        self.kayit(f"{olay[1].ad}: bir şey yazılmadı.")
                        self.genel_durum.configure(text="Hazır")
                    else:
                        self.son_cikti = sonuc["cikti"]
                        self.kayit(olay[1].sonuc_metni(sonuc))
                        self.genel_durum.configure(text="Bitti")
                        self.klasor_dugmesi.configure(state="normal")
                else:
                    self.cubuk["value"] = 0
                    self.kayit("Olmadı: " + olay[1], hata=True)
                    self.genel_durum.configure(text="Hazır")
                self._durumlari_guncelle()
        except queue.Empty:
            pass
        self.after(100, self._kuyrugu_isle)

    def _klasoru_ac(self):
        if self.son_cikti:
            # Explorer'da çıktı dosyasını seçili olarak göster
            subprocess.Popen(["explorer", "/select,", os.path.normpath(str(self.son_cikti))])


if __name__ == "__main__":
    Arayuz().mainloop()
