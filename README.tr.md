# Davar

DaVinci Resolve için kurgu öncesi yardımcı. Konuşma videolarında elle yapılan sıkıcı işleri üstlenir: ses eşleme, sessizlikleri ve "ııı / eee" duraksamalarını kesme, yazıya dökme, KJ ve dikey klip üretme.

*English: [README.md](README.md)*

> **Durum: erken sürüm.** Henüz tek bir kullanıcının birkaç videosuyla denendi. Kesimleri yayınlamadan önce mutlaka izle; hata bulursan konu (issue) aç.

Adı iki yere selam veriyor: **Da**Vinci **R**esolve'a ve bu işin Türkiye'deki öncüsü, İlker Canikligil'in **Katır**'ına.

![Davar penceresi](docs/screenshot.png)

## İş akışları

Dokuz iş akışından beşi çalışıyor, dördü planlandı.

| No | İş akışı | Durum | Ne yapar |
|---|---|---|---|
| 01 | Ses | çalışıyor | Ayrı kaydedilmiş sesleri videodaki yerine oturtur, ses düzeyini YouTube'a göre ayarlar |
| 02 | İlk Analiz | çalışıyor | Konuşmayı bir kez, kelime zamanlarıyla yazıya döker ve kaydeder; altyazı (`.srt`) ve metin (`.txt`) üretir |
| 03 | Kaba Kurgu | çalışıyor | Sessizlikleri, "ııı / eee" duraksamalarını ve dolgu kelimelerini bulur; adayları onayına sunar; Resolve çizelgesi (`.fcpxml`) yazar |
| 04 | Çok Kamera Kurgusu | planlandı | Kim konuşuyorsa onun kamerasını seçer |
| 05 | İçerik Analizi | planlandı | Konuları, bölüm zamanlarını ve öne çıkan yerleri çıkarır |
| 06 | Yazılar | çalışıyor | Konuşmacı adı ve unvanı için saydam zeminli, yumuşak giriş-çıkışlı KJ (alt bant) videosu üretir |
| 07 | Görsel Malzeme | planlandı | Araya girecek fotoğraf ve belgelerin yerleşimi |
| 08 | Sosyal Klipler | çalışıyor | Seçilen aralığı başlık, altyazı ve kapakla dikey Reels / Shorts olarak keser |
| 09 | Yayın | planlandı | YouTube açıklaması, bölüm zamanları, başlık önerileri |

Orijinal videoya hiçbir iş akışı dokunmaz. Resolve'un **ücretsiz sürümüyle** çalışır: Davar Resolve'u dışarıdan yönetmez, Resolve'un içe aktardığı dosyalar üretir.

Arayüz Türkçe ve İngilizce; dili pencerenin sol üstünden seçersin.

## Kurulum

Gerekenler:

- **Python 3.10** ya da daha yenisi
- **ffmpeg** (`ffmpeg` ve `ffprobe` komutları PATH'te olmalı)
- **numpy** ve **Pillow**
- **faster-whisper** (İlk Analiz ve otomatik altyazı için)

```bash
pip install -r requirements.txt
```

Windows'ta ffmpeg kurmanın kolay yolu:

```bash
winget install Gyan.FFmpeg
```

## Kullanım

### Pencereyle

`Davar.bat` dosyasına çift tıkla. Üstten videoyu (istersen çıktı klasörünü) seç, soldan iş akışını seç, ayarları işaretle, **Başlat**'a bas. İlerleme ve sonuçlar alttaki kayıt bölümünde görünür. Bir videoyu `Davar.bat`'ın üstüne sürükleyip bırakırsan pencere o video seçili açılır.

### Komut satırından

Her iş akışı aynı zamanda bir betiktir:

```bash
python audio.py "video.mp4" --audio "yaka_mikrofonu.wav"
```

```bash
python transcript.py "video.mp4" --srt --text
```

```bash
python roughcut.py "video.mp4" --from 0:07 --to 51:19 --remove "50:46-51:03" --fillers "yani, şey"
```

```bash
python titles.py "Halil Özen" "Gazeteci" --video "video.mp4"
```

```bash
python clips.py "video.mp4" 13:06 13:56 --headline "TUZLA'DA TRAFİK" --subtitles --cover
```

Bütün seçenekler için herhangi birini `--help` ile çalıştır.

### Resolve'a aktarma

1. Resolve'da bir proje aç.
2. **File → Import → Timeline…** ile videonun yanında oluşan `<video>_cut.fcpxml` dosyasını seç.
3. Çıkan pencerede **OK** de. Edit sayfasında kesilmiş zaman çizelgesi açılır.

## 01 Ses

Ayrı kaydedilmiş sesleri (yaka mikrofonu, ses kayıt cihazı, sonradan kaydedilmiş bölümler) videodaki yerine oturtur. Yeri kendisi bulur: iki kayıttaki konuşmanın ritmini karşılaştırır, sonra örnek hassasiyetinde hizalar. Uzun kayıtlarda iki cihazın saat farkından doğan kaymayı da ölçüp giderir.

- Her sesin düzeyi videonun sesine eşitlenir ve videonun o bölümdeki sesinin yerine konur.
- Videoda geçmeyen bir ses verilirse yerleştirilmez; hangi sesin reddedildiği raporda yazar.
- Bütün ses YouTube düzeyine (-14 LUFS) getirilir. İstenirse konuşmacı düzeyleri dengelenir ve dip gürültüsü azaltılır.

Görüntü yeniden kodlanmaz; sonuç `<video>_audio.mp4` olarak yazılır. Sonraki adımları bu yeni videoyla yap.

## 02 İlk Analiz

Konuşmayı kelime kelime zamanlarıyla yazıya döker ve videonun yanına `<video>.davar.json` olarak kaydeder. Diğer iş akışları bu kaydı okur; aynı video yeniden yazıya dökülmez. İstenirse YouTube Studio'ya yüklenebilen altyazı (`.srt`) ve zaman damgalı metin (`_transcript.txt`) de yazar.

Yazıya dökme bilgisayarında, Whisper modeliyle yapılır; internete bir şey gönderilmez (model ilk kullanımda bir kez indirilir). Özel adlarda ve sayılarda hata yapar; yayınlamadan önce denetle.

### Metni düzeltme ve kişisel sözlük

**Metni düzelt** penceresinde metin satır satır gelir; satırı dinleyip düzeltir, Enter ile sonrakine geçersin. Kaydedince altyazı ve metin dosyaları da yenilenir.

Tek kelimelik düzeltmeleri Davar **kişisel sözlüğe** eklemeyi önerir. Sözlük, kullanıcı klasöründeki `.davar/dictionary.txt` dosyasıdır; her satırı `yanlış = doğru` biçimindedir:

```
tuzda = Tuzla
Akbörse = Akköse
top sen = TÜPSAN
```

Sözlük her okunuşta uygulanır: bir kez öğrettiğin kelime sonraki videolarda da, daha önce analiz ettiklerinde de kendiliğinden düzelir. Kesme işaretinden sonraki ekler korunur (`Akbörse'nin` → `Akköse'nin`).

## 03 Kaba Kurgu

| Ne bulur | Nasıl |
|---|---|
| Sessizlikler | Ses seviyesinden. Eşiği kayıttaki arka plan gürültüsüne göre kendisi seçer. Doğrudan kesilir. |
| "Iıı / eee" duraksamaları | Sesin kendisinden (düz perde, sabit ses). İlk Analiz varsa metinle karşılaştırılır. |
| Dolgu kelimeleri | Senin verdiğin listeden ("yani, şey, işte"), İlk Analiz'in metninde aranır. |

**Kırpma.** Programın başladığı ve bittiği zamanı, bir de aradan atılacak aralıkları (tekrar çekim, yayın dışı konuşma) verebilirsin: dışında kalan her şey atılır. Zamanları seçmene yardım etmek için sayfa, metnin ilk ve son satırlarını gösterebilir.

Duraksamalar ve dolgu kelimeleri **aday** olarak bir listede gelir: zaman, tür, güven derecesi ve çevresindeki cümle. Her adayı ve kesilmiş halini dinleyebilir, işaretini değiştirebilirsin. Emin olunanlar işaretli, şüpheliler işaretsiz gelir; dolgu kelimeleri her zaman işaretsiz gelir, çünkü hangisinin gereksiz olduğuna sen karar verirsin.

### Sessizlik ve duraksama nasıl bulunuyor

**Sessizlik.** Ses 10 milisaniyelik dilimlere bölünür ve her dilimin seviyesi ölçülür. Eşik, arka plan gürültüsü ile konuşma seviyesinin arasına otomatik yerleştirilir. Eşiğin altında yeterince uzun kalan aralıklar, kelimelerin iki yanında küçük bir pay bırakılarak kesilir.

**Duraksama.** "Iıı" sesi konuşmadan üç özelliğiyle ayrılır: ötümlüdür, perdesi düz kalır ve ağız şekli değişmez. Normal konuşmada bu üçü aynı anda 0,3 saniye sabit kalmaz. Davar bu kalıba uyan yerleri arar ve ayırır:

- iki yanı sessiz, tek başına duranlar,
- sessizlikten sonra gelip doğrudan kelimeye bağlananlar ("ııı şimdi…"),
- kelimenin *sonuna* yapışık olanlar. Bunlar çoğu zaman gerçek kelimenin parçasıdır; gösterilir ama varsayılan olarak kesilmez.

Bunun için yapay zekâ modeli ya da internet bağlantısı gerekmez; sesin kendisinden hesaplanır. Bu yüzden Kaba Kurgu, yazıya dökülmemiş videolarda da çalışır.

## 06 Yazılar

Konuşmacı adı ve unvanı için KJ (alt bant) üretir: solda vurgu şeridi, üstte ad, altta unvan. Yarım saniyede soldan açılır, sonunda solarak çıkar. Çıktı saydam zeminli bir videodur (ProRes 4444, `lowerthird_<ad>.mov`); Resolve'da videonun üstündeki şeride sürüklersin, ayrıca efekt gerekmez.

Boyut ve kare hızı seçili videodan alınır; süre, yer (sol, orta, sağ) ve vurgu rengi ayarlanabilir.

## 08 Sosyal Klipler

Yatay bir videodan verdiğin zaman aralığını 1080x1920 dikey video olarak keser: bulanık arka plan üstünde konuşmacı kadrajı, üstte kısa bir yazı ve iki satıra kadar başlık. İsteğe bağlı olarak altyazı ve 2,5 saniyelik bir giriş kapağı ekler. Ses yüksekliği sosyal medya düzeyine (-14 LUFS) getirilir.

Altyazı için İlk Analiz'in metni kullanılır; analiz yoksa seçilen aralık o an yazıya dökülür. Altyazı videoya gömülür ve sonradan düzeltilemez; önce metni düzelt.

## Sınırlar

- Varsayılan olarak yalnızca en az 0,3 saniye süren, net duraksamalar kesilir. Daha kısaları, metin de aynı yerde duymuşsa öneri olarak gelir.
- Dolgu kelimelerinin zamanı yazıya dökmeden gelir ve yaklaşıktır; kesmeden önce "Kesilmiş halini dinle" ile denetle.
- Arka planı gürültülü kayıtlarda (sokak, rüzgâr, müzik) sessizlik ayrımı zayıflar. Davar bu durumda uyarır.
- Kare hızı değişken kayıtlarda (bazı telefon ve ekran kayıtları) Resolve'da kesim yerleri kayabilir. Davar bu durumda uyarır.
- Kesimler otomatiktir; yayınlamadan önce izlemek senin işin.

## Geliştirme

Kod ve açıklamalar İngilizcedir. Hesap kısmı ve çevirilerin eksiksizliği yapay verilerle sınanır; ffmpeg ya da video gerekmez.

```bash
python -m unittest discover tests
```

Yeni iş akışı ya da yeni dil eklemek için [README.md](README.md) içindeki "Development" bölümüne bak.

## Lisans

[MIT](LICENSE)
