# Davar

DaVinci Resolve için kurgu öncesi yardımcı. Konuşma videolarında elle yapılan sıkıcı işleri üstlenir: ses eşleme, sessizlikleri ve "ııı / eee" duraksamalarını kesme, yazıya dökme, KJ ve dikey klip üretme.

*English: [README.md](README.md)*

> **Durum: erken sürüm.** Henüz tek bir kullanıcının birkaç videosuyla denendi. Kesimleri yayınlamadan önce mutlaka izle; hata bulursan konu (issue) aç.

Adı iki yere selam veriyor: **Da**Vinci **R**esolve'a ve bu işin Türkiye'deki öncüsü, İlker Canikligil'in **Katır**'ına.

![Davar penceresi](docs/screenshot.png)

## İş akışları

On iş akışından altısı çalışıyor, dördü planlandı.

| No | İş akışı | Durum | Ne yapar |
|---|---|---|---|
| 01 | Ses | çalışıyor | Ayrı kaydedilmiş sesleri videodaki yerine oturtur, ses düzeyini YouTube'a göre ayarlar |
| 02 | Görüntü | çalışıyor | Videoyu 16:9 kadraja getirir ve sehpa çekimini sabitler; arka plan yerinden oynamaz |
| 03 | İlk Analiz | çalışıyor | Konuşmayı bir kez, kelime zamanlarıyla yazıya döker ve kaydeder; altyazı (`.srt`) ve metin (`.txt`) üretir |
| 04 | Kaba Kurgu | çalışıyor | Sessizlikleri, "ııı / eee" duraksamalarını ve dolgu kelimelerini bulur; adayları onayına sunar; Resolve çizelgesi (`.fcpxml`) yazar |
| 05 | Çok Kamera Kurgusu | planlandı | Kim konuşuyorsa onun kamerasını seçer |
| 06 | İçerik Analizi | planlandı | Konuları, bölüm zamanlarını ve öne çıkan yerleri çıkarır |
| 07 | Yazılar | çalışıyor | Konuşmacı adı ve unvanı için saydam zeminli, yumuşak giriş-çıkışlı KJ (alt bant) videosu üretir ve onu, o kişinin ilk konuştuğu yere zaman çizelgesine yerleştirir |
| 08 | Görsel Malzeme | planlandı | Araya girecek fotoğraf ve belgelerin yerleşimi |
| 09 | Sosyal Klipler | çalışıyor | Seçilen aralığı başlık, altyazı ve kapakla dikey Reels / Shorts olarak keser |
| 10 | Yayın | planlandı | YouTube açıklaması, bölüm zamanları, başlık önerileri |

Orijinal videoya hiçbir iş akışı dokunmaz. Resolve'un **ücretsiz sürümüyle** çalışır: Davar Resolve'u dışarıdan yönetmez, Resolve'un içe aktardığı dosyalar üretir.

Arayüz Türkçe ve İngilizce; dili pencerenin sol üstünden seçersin.

## Kurulum

Gerekenler:

- **Python 3.10** ya da daha yenisi
- **ffmpeg** (`ffmpeg` ve `ffprobe` komutları PATH'te olmalı)
- **numpy** ve **Pillow**
- **faster-whisper** (İlk Analiz ve otomatik altyazı için)
- **OpenCV** (`opencv-python`, Görüntü'de kadrajı sabitlemek için)

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

**Ayarlar hatırlanır.** Hiçbir şeyi iki kez girmen gerekmez; kaydedilecek ya da açılacak bir dosya da yoktur:

- Genel ayarlar (eşikler, paylar, dolgu kelimeleri, işaretli seçenekler, konuşmacı adları) her videoda son bıraktığın gibi gelir.
- Tek bir videoya ait ayarlar (kırpma zamanları, sosyal klibin aralığı, ayrı kaydedilmiş ses dosyaları, çıktı klasörü) o videoyla birlikte saklanır ve videoyu yeniden seçtiğinde geri gelir. Yeni bir videoda bu kutular boş başlar.
- Davar, son çalıştığın video ve sayfa ile açılır.
- Davar'ın başka bir videodan ürettiği video (`konusma.mp4`'ten `konusma_picture.mp4`), kaynağının ayarlarıyla başlar.
- Her sayfadaki **Varsayılanlara dön** düğmesi genel ayarları Davar'ın ilk hâline getirir.

Ayarlar kullanıcı klasöründeki `.davar/settings.json` dosyasında, yalnızca bu bilgisayarda tutulur; adı ya da yeri değişen video baştan başlar.

### Komut satırından

Her iş akışı aynı zamanda bir betiktir:

```bash
python audio.py "video.mp4" --audio "yaka_mikrofonu.wav"
```

```bash
python picture.py "video.mp4" --position 100
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

## 02 Görüntü

Telefonla çekilmiş görüntüler için. İki iş yapar; ikisi de ayrı ayrı kapatılabilir.

**16:9 kadraja getirme.** Çoğu telefon 16:9'dan geniş çeker; YouTube'da bu, görüntünün üstünde ve altında siyah bant demektir. Davar bunun yerine yanları keser. Konum, hangi yanın gideceğini söyler: 0 sol kenarı tutar, 50 iki yandan eşit alır, 100 sağ kenarı tutar (yani hepsi soldan kesilir). Yüksekliğe dokunulmaz, bu yüzden görüntü büyütülmez.

**Kadrajı sabitleme.** Sehpadaki telefon da görüntüyü oynatır. Odak ararken mercek hareket eder; görüntünün tamamı büyür, küçülür ve birkaç piksel zıplar. Uzun kayıtta kadraj ayrıca yavaş yavaş kayar. Birkaç saniyede bir kesilen videoda arka plan her kesimde sıçrar. Davar arka planı bütün video boyunca izler, her kareyi tek bir örnek kareye hizalar ve oynayan kenarlar görünmesin diye yaklaşık yüzde bir yakınlaştırır. Kameranın önünde hareket eden insanlar bunu bozmaz: arka plan tek bir konumda birleşir, gerisi dikkate alınmaz.

- Yalnızca hareket etmeyen kamera içindir. Görüntünün genişliğinin birkaç yüzdesinden fazla gezdiği videoyu Davar reddeder.
- Odağın kaçtığı andaki bulanıklık onarılamaz; yalnızca hareket giderilir.
- Sabitleme her kareyi iki kez okur ve videoyu baştan yazar. Videonun süresinin bir-iki katı kadar sürer.
- Değişken kare hızı sabit hıza çevrilir.

Ses olduğu gibi kopyalanır; sonuç `<video>_picture.mp4` olarak yazılır. Orijinal için yapılmış İlk Analiz yeni videoya taşınır, yeniden yazıya dökmek gerekmez. Sonraki adımları yeni videoyla yap.

## 03 İlk Analiz

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

## 04 Kaba Kurgu

| Ne bulur | Nasıl |
|---|---|
| Sessizlikler | Ses seviyesinden. Eşiği kayıttaki arka plan gürültüsüne göre kendisi seçer. Doğrudan kesilir. |
| "Iıı / eee" duraksamaları | Sesin kendisinden (düz perde, sabit ses). İlk Analiz varsa metinle karşılaştırılır. |
| Dolgu kelimeleri | Senin verdiğin listeden ("yani, şey, işte"), İlk Analiz'in metninde aranır. |
| Öksürük ve diğer konuşma dışı sesler | İki sessizlik arasında duran kısa sesler. İlk Analiz varsa, karşılığında kelime yazılmamış ses konuşma dışı sayılır. |

**Kırpma.** Programın başladığı ve bittiği zamanı, bir de aradan atılacak aralıkları (tekrar çekim, yayın dışı konuşma) verebilirsin: dışında kalan her şey atılır. Zamanları seçmene yardım etmek için sayfa, metnin ilk ve son satırlarını gösterebilir.

Duraksamalar ve dolgu kelimeleri **aday** olarak bir listede gelir: zaman, tür, güven derecesi ve çevresindeki cümle. Her adayı ve kesilmiş halini dinleyebilir, işaretini değiştirebilirsin. Emin olunanlar işaretli, şüpheliler işaretsiz gelir; dolgu kelimeleri her zaman işaretsiz gelir, çünkü hangisinin gereksiz olduğuna sen karar verirsin.

### Sessizlik ve duraksama nasıl bulunuyor

**Sessizlik.** Ses 10 milisaniyelik dilimlere bölünür ve her dilimin seviyesi ölçülür. Eşik, arka plan gürültüsü ile konuşma seviyesinin arasına otomatik yerleştirilir. Eşiğin altında yeterince uzun kalan aralıklar, kelimelerin iki yanında küçük bir pay bırakılarak kesilir.

**Duraksama.** "Iıı" sesi konuşmadan üç özelliğiyle ayrılır: ötümlüdür, perdesi düz kalır ve ağız şekli değişmez. Normal konuşmada bu üçü aynı anda 0,3 saniye sabit kalmaz. Davar bu kalıba uyan yerleri arar ve ayırır:

- iki yanı sessiz, tek başına duranlar,
- sessizlikten sonra gelip doğrudan kelimeye bağlananlar ("ııı şimdi…"),
- kelimenin *sonuna* yapışık olanlar. Bunlar çoğu zaman gerçek kelimenin parçasıdır; gösterilir ama varsayılan olarak kesilmez.

"Iıı" sesi çoğu zaman birden bitmez, 0,1-0,3 saniye daha kısılarak sürer. Kesim bu kuyruğu, sonraki sesin başladığı yere kadar izler; geride artık kalmaz.

Bunun için yapay zekâ modeli ya da internet bağlantısı gerekmez; sesin kendisinden hesaplanır. Bu yüzden Kaba Kurgu, yazıya dökülmemiş videolarda da çalışır.

## 07 Yazılar

Konuşmacı adı ve unvanı için KJ (alt bant) üretir: solda vurgu şeridi, üstte ad, altta unvan. Yarım saniyede soldan açılır, sonunda solarak çıkar. Çıktı saydam zeminli bir videodur (ProRes 4444, `lowerthird_<ad>.mov`); Resolve'da videonun üstündeki şeride sürüklersin, ayrıca efekt gerekmez.

Boyut ve kare hızı seçili videodan alınır; süre, yer (sol, orta, sağ) ve vurgu rengi ayarlanabilir.

Her satıra bir kişi yazılır: `Ad Soyad | Unvan`. Konuşmacılar farklı yanlarda oturuyorsa unvandan sonra o adın konumunu yaz; konum yazılmayan satırlar sayfada seçili yeri kullanır. Konum, izleyicinin ekranda gördüğü gibidir: görüntünün solunda oturan kişiye `sol` yazılır.

```
Ayşe Yılmaz | Gazeteci | sol
Ali Demir | Belediye Başkanı | sağ
```

### Adları zaman çizelgesine yerleştirme

**Zaman çizelgesine yerleştir** işaretliyken Davar her adı, o kişi ilk konuşmaya başladıktan birkaç saniye sonra videonun üstündeki şeride de koyar:

- Konuşmacıları **ilk konuştukları sırayla** yaz. Davar sesleri renginden ayırt eder; ilk satıra ilk duyulan sesi, ikinci satıra sonraki yeni sesi verir. Bunun için döküm gerekir.
- Adlar, varsa videonun Kaba Kurgu çizelgesine (`<video>_cut.fcpxml`) eklenir; çizelgeyi Resolve'a yeniden al. Yoksa videonun tamamını içeren bir çizelge yazılır (`<video>_titles.fcpxml`).
- Kayıt bölümü her ad için seçilen anı ve orada söylenen sözleri gösterir; adların yer değiştirdiği böylece hemen görülür. İkisi yer değiştirmişse satırların sırasını değiştir.
- Anı kendin seçmek için videodaki zamanı satıra ekle: `Ayşe Yılmaz | Gazeteci | 0:41`. Konum ve zaman birlikte, istediğin sırayla yazılabilir: `Ali Demir | Belediye Başkanı | sağ | 0:41`.
- Kaba Kurgu yeniden çalıştırıldığında adlar yerinde kalır.

Sesler bilgisayarında, ek bir indirme olmadan ayırt edilir. Sesleri birbirinden belirgin biçimde farklı birkaç kişi için yapılmıştır; konuşma sırasının değiştiği an ancak birkaç saniye yaklaşıklıkla bilinir, ad bu yüzden konuşmacı başladıktan biraz sonra gelir.

## 09 Sosyal Klipler

Yatay bir videodan verdiğin zaman aralığını 1080x1920 dikey video olarak keser: bulanık arka plan üstünde konuşmacı kadrajı, üstte kısa bir yazı ve iki satıra kadar başlık. İsteğe bağlı olarak altyazı ve 2,5 saniyelik bir giriş kapağı ekler. Ses yüksekliği sosyal medya düzeyine (-14 LUFS) getirilir.

Altyazı için İlk Analiz'in metni kullanılır; analiz yoksa seçilen aralık o an yazıya dökülür. Altyazı videoya gömülür ve sonradan düzeltilemez; önce metni düzelt.

## Sınırlar

- Varsayılan olarak yalnızca en az 0,3 saniye süren, net duraksamalar kesilir. Daha kısaları, metin de aynı yerde duymuşsa öneri olarak gelir.
- Dolgu kelimelerinin zamanı yazıya dökmeden gelir ve yaklaşıktır; kesmeden önce "Kesilmiş halini dinle" ile denetle.
- Arka planı gürültülü kayıtlarda (sokak, rüzgâr, müzik) sessizlik ayrımı zayıflar. Davar bu durumda uyarır.
- Kare hızı değişken kayıtlarda (bazı telefon ve ekran kayıtları) Resolve'da kesim yerleri kayabilir. Davar bu durumda uyarır.
- Konuşmacıları ayırt etme, birbirinden belirgin biçimde farklı seslerde çalışır. Benzer iki ses, aynı anda konuşan kişiler ya da konuşmanın altındaki müzik bir adı yanlış yere koyabilir; kayıt bölümü her yerdeki sözleri gösterir, oradan denetleyebilirsin.
- Kesimler otomatiktir; yayınlamadan önce izlemek senin işin.

## Geliştirme

Kod ve açıklamalar İngilizcedir. Hesap kısmı ve çevirilerin eksiksizliği yapay verilerle sınanır; ffmpeg ya da video gerekmez.

```bash
python -m unittest discover tests
```

Yeni iş akışı ya da yeni dil eklemek için [README.md](README.md) içindeki "Development" bölümüne bak.

## Değişiklikler

Her sürümde nelerin değiştiği [CHANGELOG.md](CHANGELOG.md) dosyasında (İngilizce).

## Lisans

[MIT](LICENSE)
