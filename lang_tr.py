"""Turkish translations. Keys are the English source strings exactly as written in the code.

tests/test_i18n.py fails if a string used in the code is missing here.
"""

TRANSLATIONS = {
    # --- common ---------------------------------------------------------------
    "the file has no video stream.": "dosyada görüntü yok.",
    "the file has no audio, so silence cannot be analysed.": "dosyada ses yok, sessizlik analizi yapılamaz.",
    "{tool} was not found. ffmpeg must be installed and on PATH.":
        "{tool} bulunamadı. ffmpeg kurulu ve PATH'te olmalı.",
    "{tool} failed:": "{tool} çalışmadı:",
    "file not found: {path}": "dosya bulunamadı: {path}",
    "output folder not found: {path}": "çıktı klasörü bulunamadı: {path}",
    "ERROR: {message}": "HATA: {message}",
    "Failed: {message}": "Olmadı: {message}",
    "Unexpected error: {kind}: {message}": "Beklenmeyen hata: {kind}: {message}",
    "Finished": "Bitti",
    "Ready": "Hazır",
    "Written: {path}": "Yazıldı: {path}",
    "Reading video information": "Video bilgileri okunuyor",
    "Extracting audio": "Ses çıkarılıyor",
    "this needs Pillow. Install it with: pip install pillow":
        "bunun için Pillow gerekli. Kurmak için: pip install pillow",
    "s": "sn",
    "If two microphones were recorded on the video's two channels, tick “Import multi-channel "
    "audio tracks as linked groups” when importing: each microphone then comes on a track of its own.":
        "Videonun iki kanalına iki ayrı mikrofon kaydedildiyse içeri alırken “Import multi-channel audio "
        "tracks as linked groups” kutusunu işaretle; her mikrofon kendi kanalına gelir.",

    # --- rough cut ------------------------------------------------------------
    "uh / um (alone)": "ııı / eee (tek başına)",
    "uh / um (before a word)": "ııı / eee (kelime önünde)",
    "stretch (end of a word)": "uzatma (kelime sonunda)",
    "uh / um (between words)": "ııı / eee (kelimeler arasında)",
    "non-speech sound (cough, breath)": "konuşma dışı ses (öksürük, nefes)",
    "sound with no word (listen)": "kelimesi olmayan ses (dinle)",
    "Looking for non-speech sounds": "Konuşma dışı sesler aranıyor",
    "filler word": "dolgu kelimesi",
    "uh / um (transcript only)": "ııı / eee (yalnızca metinde)",
    "short": "kısa",
    "high": "yüksek",
    "medium": "orta",
    "low": "düşük",
    "the audio could not be read.": "ses okunamadı.",
    "nothing was selected to cut.": "kesilecek bir şey seçilmedi.",
    "run Transcribe first to search for filler words.":
        "dolgu kelimelerini bulmak için önce İlk Analiz çalıştırılmalı.",
    "Looking for hesitations (uh / um)": "Duraksamalar (ııı / eee) aranıyor",
    "Matching short hesitations with the transcript": "Kısa duraksamalar metinle eşleştiriliyor",
    "Preparing candidates": "Adaylar hazırlanıyor",
    "Analysis finished": "Çözümleme bitti",
    "the whole video looks silent; try lowering the threshold.":
        "videonun tamamı sessiz görünüyor; eşik değerini düşürmeyi dene.",
    "Video        : {name}  ({width}x{height}, {fps:.3f} fps)":
        "Video        : {name}  ({width}x{height}, {fps:.3f} kare/sn)",
    "Audio level  : background {floor:.0f} dB, speech {speech:.0f} dB, threshold {threshold:.0f} dB":
        "Ses seviyesi : arka plan {floor:.0f} dB, konuşma {speech:.0f} dB, eşik {threshold:.0f} dB",
    "(set manually)": "(elle verildi)",
    "Cuts         : {n} places removed": "Kesim        : {n} yer atıldı",
    "({cut} of them hesitations or fillers; {kept} candidates left uncut)":
        "({cut} tanesi duraksama ya da dolgu; {kept} aday kesilmedi)",
    "Duration     : {before} -> {after}  ({seconds:.1f} s shorter)":
        "Süre         : {before} -> {after}  ({seconds:.1f} sn kısaldı)",
    "WARNING: the background noise is close to the speech level; cuts may be wrong.":
        "UYARI: arka plan gürültüsü ile konuşma seviyesi birbirine yakın; kesimler hatalı olabilir.",
    "WARNING: the video seems to have a variable frame rate (phone or screen recording); "
    "cut points may drift in Resolve.":
        "UYARI: videonun kare hızı değişken görünüyor (telefon/ekran kaydı); "
        "Resolve'da kesim yerleri kayabilir.",
    "Candidates (time in the original video; [x] = cut):":
        "Adaylar (orijinal videodaki zaman; [x] kesildi):",
    "confidence {level}": "güven {level}",
    "... and {n} more candidates": "... ve {n} aday daha",
    "... and {n} more": "... ve {n} tane daha",
    "Timeline written: {path}": "Zaman çizelgesi yazıldı: {path}",
    "Review timeline written: {path}": "Kontrol çizelgesi yazıldı: {path}",
    "the end of the programme must come after its start.": "program bitişi başlangıcından sonra olmalı.",
    "start up to {time}": "baştan {time} anına kadar",
    "end from {time}": "{time} anından sona kadar",
    "Trimmed      : {parts}": "Kırpıldı     : {parts}",
    "could not read the range “{text}”. Example: 50:46-51:03":
        "aralık anlaşılmadı: “{text}”. Örnek: 50:46-51:03",
    "the range “{text}” ends before it starts.": "“{text}” aralığının bitişi başlangıcından önce.",
    "Transcript found: hesitations were checked against it.":
        "İlk Analiz bulundu: duraksamalar metinle karşılaştırıldı.",

    # --- transcript -----------------------------------------------------------
    "transcription needs faster-whisper. Install it with: pip install faster-whisper":
        "yazıya dökme için faster-whisper gerekli. Kurmak için: pip install faster-whisper",
    "Loading the model": "Model yükleniyor",
    "Loading the model (downloaded on first use)": "Model yükleniyor (ilk seferde internetten indirilir)",
    "no audio was found in the video.": "videoda ses bulunamadı.",
    "no speech was found.": "konuşma bulunamadı.",
    "Transcribing ({done} / {total})": "Yazıya dökülüyor ({done} / {total})",
    "Speech   : {duration}, {words} words ({fillers} of them uh / um), model {model}":
        "Konuşma  : {duration}, {words} kelime ({fillers} tanesi ııı / eee), model {model}",
    "saved transcript reused": "kayıtlı analiz kullanıldı",
    "Note     : written automatically; check names and numbers before publishing":
        "Not      : otomatik yazıldı; özel adları ve sayıları yayınlamadan önce denetle",
    "Dictionary: {n} words corrected from your personal dictionary":
        "Sözlük   : {n} kelime kişisel sözlüğe göre düzeltildi",

    # --- audio ----------------------------------------------------------------
    "matching audio needs at least one second of recording.":
        "ses eşlemek için en az bir saniyelik kayıt gerekli.",
    "ffmpeg could not process the audio:": "ffmpeg sesi işleyemedi:",
    "ffmpeg could not write the video:": "ffmpeg videoyu yazamadı:",
    "the loudness could not be measured.": "ses düzeyi ölçülemedi.",
    "no operation was selected.": "yapılacak bir işlem seçilmedi.",
    "Reading the video's audio": "Videonun sesi okunuyor",
    "Looking for the place of {name}": "Yeri aranıyor: {name}",
    "none of the separate recordings matched the video; no new video was written.":
        "ayrı seslerin hiçbiri videoyla eşleşmedi; yeni video yazılmadı.",
    "Measuring audio levels": "Ses düzeyleri ölçülüyor",
    "Measuring loudness": "Ses düzeyi ölçülüyor",
    "Writing the new video": "Yeni video yazılıyor",
    "Measuring the result": "Sonuç ölçülüyor",
    "Placed   : {name}  ->  {time}  (similarity {similarity:.0f}%, {margin:.0f}% ahead of "
    "the runner-up, level {gain:+.1f} dB":
        "Yerleşti : {name}  ->  {time}  (benzerlik %{similarity:.0f}, ikinci adaydan %{margin:.0f} önde, "
        "düzey {gain:+.1f} dB",
    "clock difference corrected": "saat farkı düzeltildi",
    "No place : {name}  (no position stood out; this audio may not occur in "
    "the video, so it was not placed)":
        "Yeri yok : {name}  (hiçbir yer öne çıkmadı; bu ses videoda geçmiyor olabilir, yerleştirilmedi)",
    "Loudness : {before:.1f} -> {after:.1f} LUFS (target {target:.0f}), peak {peak:.1f} dBTP":
        "Ses düzeyi : {before:.1f} -> {after:.1f} LUFS (hedef {target:.0f}), tepe {peak:.1f} dBTP",
    "Loudness : {after:.1f} LUFS (not adjusted)": "Ses düzeyi : {after:.1f} LUFS (ayarlanmadı)",
    "speaker balancing": "konuşmacı dengeleme",
    "noise reduction": "gürültü azaltma",
    "Applied  : {what} (check by ear)": "Uygulandı  : {what} (kulakla denetle)",
    "Video written (picture not re-encoded): {path}":
        "Video yazıldı (görüntü yeniden kodlanmadı): {path}",

    # --- social clips ---------------------------------------------------------
    "could not read the time “{text}”. Example: 13:06 or 1:02:03":
        "zaman anlaşılmadı: “{text}”. Örnek: 13:06 ya da 1:02:03",
    "subtitles need faster-whisper. Install it with: pip install faster-whisper":
        "altyazı için faster-whisper gerekli. Kurmak için: pip install faster-whisper",
    "the end time must be at least 1 second after the start.":
        "bitiş zamanı başlangıçtan en az 1 saniye sonra olmalı.",
    "the intro cover needs a headline or a kicker.": "giriş kapağı için başlık ya da üst yazı gerekli.",
    "Transcribing the speech (the model is downloaded on first use)":
        "Konuşma yazıya dökülüyor (ilk seferde model indirilir)",
    "Rendering the video": "Video hazırlanıyor",
    "Range    : {start} - {end}": "Aralık   : {start} - {end}",
    "Video    : {width}x{height}, {seconds:.1f} s": "Video    : {width}x{height}, {seconds:.1f} sn",
    "(including the intro cover)": "(giriş kapağı dahil)",
    "Subtitles: {n} lines (automatic; read them before publishing)":
        "Altyazı  : {n} satır (otomatik; yayınlamadan önce oku)",
    "Subtitles: no speech found, none added": "Altyazı  : konuşma bulunamadı, eklenmedi",
    "Video written: {path}": "Video yazıldı: {path}",

    # --- titles ---------------------------------------------------------------
    "could not read the colour “{text}”. Example: #E30613": "renk anlaşılmadı: “{text}”. Örnek: #E30613",
    "a lower third needs at least a name.": "KJ için en az bir ad yazılmalı.",
    "the position can be: {choices}": "yer şunlardan biri olabilir: {choices}",
    "the lower third must last between 2 and 60 seconds.": "KJ süresi 2 ile 60 saniye arasında olmalı.",
    "Drawing the lower third: {name}": "KJ çiziliyor: {name}",
    "Lower thirds: {n}, {width}x{height}, {seconds:.0f} s, transparent background (ProRes 4444)":
        "KJ       : {n} adet, {width}x{height}, {seconds:.0f} sn, saydam zeminli (ProRes 4444)",
    "How to use : in Resolve drag it onto the track above the video; the entrance and exit are built in":
        "Kullanım : Resolve'da videonun üstündeki şeride sürükle; giriş ve çıkış hazır gelir",
    "too many “|” in the line “{line}”. It reads: Name | Title | place | time":
        "“{line}” satırında fazla “|” var. Biçimi şöyle: Ad Soyad | Unvan | konum | zaman",
    "could not read “{field}” in the line “{line}”. After the title comes a place "
    "(left, centre, right) or a time (0:41), each once.":
        "“{line}” satırındaki “{field}” okunamadı. Unvandan sonra konum (sol, orta, sağ) ya da zaman "
        "(0:41) gelir; her biri bir kez yazılır.",
    "the time given for {name} is outside the video.": "{name} için verilen zaman videonun dışında.",
    "run Transcribe first, or give each name its time: Name | Title | 0:41":
        "önce İlk Analiz'i çalıştır ya da her ada zamanını ver: Ad Soyad | Unvan | 0:41",
    "Listening for who speaks when": "Kimin ne zaman konuştuğu dinleniyor",
    "Writing the timeline": "Zaman çizelgesi yazılıyor",
    "Placed on the Rough Cut timeline, on the track above the video:":
        "Kaba Kurgu çizelgesine, videonun üstündeki şeride yerleştirildi:",
    "No Rough Cut timeline was found for this video, so a timeline of the whole video "
    "was written:":
        "Bu video için Kaba Kurgu çizelgesi bulunamadı; videonun tamamını içeren bir çizelge yazıldı:",
    "{name}: at {video} in the video, {timeline} on the timeline":
        "{name}: videoda {video}, çizelgede {timeline}",
    "{name}: could not tell where this person first speaks. Give the time "
    "yourself: Name | Title | 12:30":
        "{name}: bu kişinin ilk nerede konuştuğu bulunamadı. Zamanı kendin ver: Ad Soyad | Unvan | 12:30",
    "Check that each name stands over that person's own words; if two are swapped, "
    "change the order of the lines.":
        "Her adın o kişinin kendi sözlerinin üstünde durduğunu denetle; ikisi yer değiştirmişse "
        "satırların sırasını değiştir.",
    "In Resolve: File → Import → Timeline…": "Resolve'da: File → Import → Timeline…",
    "run Transcribe first; the speakers are told apart with the help of the transcript.":
        "önce İlk Analiz'i çalıştır; konuşmacılar dökümün yardımıyla ayırt edilir.",
    "there is too little speech to tell the speakers apart.":
        "konuşmacıları ayırt etmek için konuşma çok az.",
    "Name titles kept on the timeline: {n}": "Çizelgede korunan KJ: {n}",
    "Subtitles for this timeline: {path}": "Bu çizelgenin altyazısı: {path}",
    "the time {time} is past the end of the video ({length}). Write minute:second, "
    "e.g. 16:40.5; three numbers such as 16:40:00 mean hours:minutes:seconds.":
        "{time} zamanı videonun sonundan ({length}) sonra geliyor. Dakika:saniye biçiminde yaz, örneğin "
        "16:40.5; 16:40:00 gibi üç sayı saat:dakika:saniye demektir.",
    "Framing     : changes {changes} times, at speaker changes and about every {every:.0f} s "
    "in long answers; closer framing ({percent:.0f}%) {share:.0f}% of the time":
        "Kadraj      : {changes} kez değişiyor; konuşmacı değişince ve uzun cevaplarda yaklaşık {every:.0f} "
        "sn'de bir. Yakın kadraj (%{percent:.0f}) sürenin %{share:.0f} kadarı",
    "In Resolve, keep “Use sizing information” ticked when importing, or the "
    "closer framings are lost.":
        "Resolve'da içeri alırken “Use sizing information” işaretli kalsın; yoksa yakın kadrajlar kaybolur.",
    "Move closer to the speaker (hides jump cuts)": "Konuşana yaklaş (sıçramaları gizler)",
    "As with a second camera: during a long answer the picture moves closer to the speaker, "
    "in quick exchanges it stays on everyone. Inside a long answer the framing changes now "
    "and then, at the cut that jumps most; other cuts keep their framing. Who speaks is "
    "found from the transcript; who sits where is taken from the Titles page.":
        "İkinci bir kamera varmış gibi: uzun bir cevapta görüntü konuşana yaklaşır, kısa atışmalarda "
        "herkesi gösterir. Uzun cevabın içinde kadraj arada bir, en çok sıçrayan kesimde değişir; öteki "
        "kesimler kadrajını korur. Kimin konuştuğu dökümden bulunur; kimin nerede oturduğu Yazılar "
        "sayfasından alınır.",
    "Closer framing": "Yakın kadraj",
    "percent of the picture; above 130 the picture grows soft":
        "görüntünün yüzdesi; 130'un üstünde görüntü yumuşar",
    "Change inside a long answer every": "Uzun cevapta kadraj değişimi",
    "seconds": "saniyede bir",
    "Run Transcribe first to move closer to the speaker": "Konuşana yaklaşmak için önce İlk Analiz'i çalıştır",
    "No speakers are written on the Titles page: two are assumed, and the closer framing "
    "stays in the middle. Write them there as Name | Title | left to move toward the speaker.":
        "Yazılar sayfasında konuşmacı yazılı değil: iki kişi varsayılır ve yakın kadraj ortada kalır. "
        "Konuşana doğru kaymak için onları orada Ad Soyad | Unvan | sol biçiminde yaz.",
    "Speakers from the Titles page: {list}": "Yazılar sayfasındaki konuşmacılar: {list}",
    "middle": "orta",

    # --- interface: frame -----------------------------------------------------
    "Pre-edit helper for DaVinci Resolve": "DaVinci Resolve için kurgu öncesi yardımcı",
    "Interface": "Arayüz",
    "Video / audio file": "Video / ses dosyası",
    "Choose": "Seç",
    "Output folder": "Çıktı klasörü",
    "Leave empty to write the outputs next to the video": "Boş bırakırsan çıktılar videonun yanına yazılır",
    "PROCESS": "İŞLEM",
    "LOG": "KAYIT",
    "WORKFLOW": "İŞ AKIŞI",
    "Start": "Başlat",
    "Back to defaults": "Varsayılanlara dön",
    "The settings last used for this video were brought back.":
        "Bu video için son kullanılan ayarlar geri getirildi.",
    "Show the output in its folder": "Çıktıyı klasörde göster",
    "Davar is ready. Choose a video, then a workflow on the left.":
        "Davar hazır. Bir video seç, soldan iş akışını seç.",
    "Choose a video at the top first": "Önce yukarıdan bir video seç",
    "Choose a video": "Video seç",
    "Choose the output folder": "Çıktı klasörünü seç",
    "Video and audio files": "Video ve ses dosyaları",
    "Audio and video files": "Ses ve video dosyaları",
    "All files": "Tüm dosyalar",
    "One of the number boxes holds something that is not a number.":
        "Sayı kutularından birinde sayı olmayan bir değer var.",
    "{workflow} started.": "{workflow} başladı.",
    "{workflow}: nothing was written.": "{workflow}: bir şey yazılmadı.",
    "The language can be changed once the running job has finished.":
        "Dil, süren iş bittikten sonra değiştirilebilir.",
    "Coming next": "Sırada",
    "Listening only works on Windows.": "Dinleme yalnızca Windows'ta çalışıyor.",
    "Listen": "Dinle",
    "Apply": "Uygula",
    "Cancel": "Vazgeç",
    "Save": "Kaydet",
    "Time": "Zaman",

    # --- interface: audio -----------------------------------------------------
    "Audio": "Ses",
    "Puts separately recorded audio in its place in the video and sets the loudness. "
    "The picture is not re-encoded; the result is written as a new video and the next "
    "steps continue with it.":
        "Ayrı kaydedilmiş sesleri videodaki yerine oturtur ve ses düzeyini ayarlar. Görüntü yeniden "
        "kodlanmaz; sonuç yeni bir video olarak yazılır ve sonraki adımlar onunla devam eder.",
    "Separately recorded audio": "Ayrı kaydedilmiş sesler",
    "A lavalier microphone, an audio recorder or parts recorded afterwards. Davar finds "
    "by itself where each one belongs in the video, matches its level to the video's "
    "audio and replaces the video's audio there. Audio that does not occur in the "
    "video is not placed.":
        "Yaka mikrofonu, ses kayıt cihazı ya da sonradan kaydedilmiş bölümler. Davar her "
        "birinin videoda nereye denk geldiğini kendisi bulur, düzeyini videonun sesine "
        "eşitler ve videonun o bölümdeki sesinin yerine koyar. Videoda geçmeyen ses yerleştirilmez.",
    "Add…": "Ekle…",
    "Remove": "Çıkar",
    "Choose the separate audio files": "Ayrı ses dosyalarını seç",
    "Loudness": "Ses düzeyi",
    "Bring to YouTube loudness": "YouTube düzeyine getir",
    "Sets the audio to -14 LUFS; fixes audio that is too quiet or too loud":
        "Sesi -14 LUFS'a ayarlar; kısık ya da patlayan sesi düzeltir",
    "Balance the speakers' levels": "Konuşmacıların düzeyini dengele",
    "Raises the quiet speaker; check by ear": "Kısık konuşanı yükseltir; kulakla denetle",
    "Reduce background noise": "Dip gürültüsünü azalt",
    "Lowers hum and hiss; check by ear": "Uğultu ve hışırtıyı kısar; kulakla denetle",
    "For recordings where each speaker has their own microphone: lowering the bleed "
    "that reaches the microphone of the person who is not speaking.":
        "Her konuşmacının ayrı mikrofonu olan kayıtlarda, konuşmayan kişinin mikrofonuna "
        "sızan sesi kısmak.",
    "Add an audio file or tick an operation": "Bir ses ekle ya da bir işlem işaretle",
    "The video field now points to this new file; the next steps work on it.":
        "Video alanı bu yeni dosyaya çevrildi; sonraki adımlar onunla çalışır.",

    # --- interface: transcribe ------------------------------------------------
    "Transcribe": "İlk Analiz",
    "Transcribes the speech once, word by word with timing, and saves it next to the "
    "video. The later workflows use this; the same video is not transcribed again.":
        "Konuşmayı bir kez, kelime kelime zamanlarıyla yazıya döker ve videonun yanına kaydeder. "
        "Sonraki iş akışları bu kaydı kullanır; aynı video yeniden yazıya dökülmez.",
    "Status": "Durum",
    "Edit the text…": "Metni düzelt…",
    "Open the dictionary": "Sözlüğü aç",
    "Dictionary: teach a word that is always misspelt once, then it fixes itself":
        "Sözlük: hep yanlış yazılan kelimeler bir kez öğretilir, sonra kendiliğinden düzelir",
    "Transcription": "Yazıya dökme",
    "Runs on your computer; nothing is sent to the internet. It can take about half "
    "the length of the video; the model is downloaded on first use.":
        "Bilgisayarında çalışır, internete bir şey gönderilmez. Videonun süresinin "
        "yarısı kadar zaman alabilir; ilk kullanımda model indirilir.",
    "Speech language": "Konuşma dili",
    "language code of the speech: tr, en, de …": "konuşmanın dil kodu: tr, en, de …",
    "Accuracy": "Doğruluk",
    "base is fast but error-prone · small is balanced · medium is the "
    "most accurate and very slow":
        "base hızlı ama hatalı · small dengeli · medium en doğru, çok yavaş",
    "Transcribe again even if a transcript is saved": "Kayıtlı analiz olsa da baştan yazıya dök",
    "Extra files": "Ek dosyalar",
    "Made from the transcript; nothing is transcribed again.":
        "Analizden üretilir; yazıya dökme yeniden yapılmaz.",
    "Subtitle file (.srt)": "Altyazı dosyası (.srt)",
    "Uploaded in YouTube Studio → Subtitles": "YouTube Studio → Altyazılar bölümüne yüklenir",
    "Time-stamped text (.txt)": "Zaman damgalı metin (.txt)",
    "Each line starts with [minute:second]": "Her satırın başında [dakika:saniye]",
    "A transcript is saved for this video: {words} words, model {model}. "
    "Start will only write the extra files.":
        "Bu video için kayıtlı analiz var: {words} kelime, model {model}. "
        "Başlat'a basarsan yalnızca ek dosyalar yazılır.",
    "This video has not been transcribed yet.": "Bu video henüz yazıya dökülmedi.",
    "Dictionary file: {path}": "Sözlük dosyası: {path}",
    "Each line: wrong = right. Once saved it applies to every transcript, new and old.":
        "Her satır: yanlış = doğru. Kaydettiğinde yeni ve eski analizlerin hepsine uygulanır.",

    # --- interface: transcript editor ----------------------------------------
    "edit the text": "metni düzelt",
    "Edit the text": "Metni düzelt",
    "Select a line, correct it in the box below and press Enter: the correction "
    "is applied and the next line is selected. Saving also rewrites the subtitle "
    "and text files.":
        "Bir satır seç, alttaki kutuda düzelt, Enter'a bas: düzeltme uygulanır ve sonraki "
        "satıra geçilir. Kaydedince altyazı ve metin dosyaları da yenilenir.",
    "Apply and next (Enter)": "Uygula ve sonraki (Enter)",
    "Text": "Metin",
    "{lines} lines, {edited} corrected": "{lines} satır, {edited} tanesi düzeltildi",
    "Text corrected: {n} lines saved.": "Metin düzeltildi: {n} satır kaydedildi.",
    "Files rewritten: {files}.": "Yenilenen dosyalar: {files}.",
    "Add to the dictionary?": "Sözlüğe eklensin mi?",
    "Add these corrections to your personal dictionary? They will then be fixed "
    "automatically in every video from now on.":
        "Bu düzeltmeler kişisel sözlüğe eklensin mi? Eklenirse bundan sonraki bütün "
        "videolarda kendiliğinden düzeltilir.",
    "… and {n} more": "… ve {n} tane daha",
    "{n} words added to the dictionary.": "{n} kelime sözlüğe eklendi.",

    # --- interface: rough cut -------------------------------------------------
    "Rough Cut": "Kaba Kurgu",
    "Finds silences, “uh / um” hesitations and the filler words you choose, and prepares "
    "a trimmed timeline for DaVinci Resolve. The original video is not touched. "
    "In Resolve: File → Import → Timeline…":
        "Sessizlikleri, “ııı / eee” duraksamalarını ve istediğin dolgu kelimelerini bulur; "
        "DaVinci Resolve için kesilmiş zaman çizelgesi hazırlar. Orijinal videoya dokunmaz. "
        "Resolve'da: File → Import → Timeline…",
    "Cut silences": "Sessizlikleri kes",
    "Removes the gaps where nobody speaks.": "Konuşma olmayan boşlukları atar.",
    "Shortest silence": "En kısa sessizlik",
    "Shorter gaps are left alone": "Bundan kısa boşluklara dokunulmaz",
    "Padding before a word": "Kelimeden önce pay",
    "Raise it if word starts are clipped": "Kelime başı yeniyorsa artır",
    "Padding after a word": "Kelimeden sonra pay",
    "Raise it if word ends are clipped": "Kelime sonu yeniyorsa artır",
    "Find “uh / um” hesitations": "“Iıı / eee” duraksamalarını bul",
    "Finds drawn-out thinking sounds from the audio itself.":
        "Uzatılmış düşünme seslerini sesin kendisinden bulur.",
    "Shortest hesitation": "En kısa duraksama",
    "Lower it to catch more; wrong candidates increase": "Düşürürsen daha çok yakalar, yanlış aday artar",
    "Find coughs and other non-speech sounds": "Öksürük ve diğer konuşma dışı sesleri bul",
    "Coughs, throat clearing, loud breaths and clicks standing between silences. With a "
    "transcript, a sound no word was written for is taken as non-speech; without one only "
    "the noisy ones can be told apart.":
        "İki sessizlik arasında duran öksürük, boğaz temizleme, yüksek nefes ve tıkırtılar. İlk Analiz "
        "varsa, karşılığında kelime yazılmamış ses konuşma dışı sayılır; yoksa yalnızca hışırtılı "
        "olanlar ayırt edilebilir.",
    "Filler words": "Dolgu kelimeleri",
    "The speaker's verbal habits. Separate with commas: you know, like, I mean":
        "Konuşmacının ağız alışkanlıkları. Virgülle ayır: yani, şey, işte, aslında",
    "Applying": "Uygulama",
    "Show me the candidates before cutting": "Adayları kesmeden önce bana göster",
    "Hesitations and filler words arrive in a list; you can listen and change "
    "their ticks. When off, only the confident ones are cut.":
        "Duraksamalar ve dolgu kelimeleri bir listede gelir; dinleyip işaretini "
        "değiştirebilirsin. Kapalıysa yalnızca emin olunanlar kesilir.",
    "Also write a review timeline": "Kontrol çizelgesi de hazırla",
    "A second timeline showing the cut candidates with one second before and "
    "after each, for checking inside Resolve.":
        "Kesilen adayları birer saniye öncesi ve sonrasıyla gösteren ikinci bir "
        "çizelge; Resolve içinde denetlemek için.",
    "Transcript found: hesitations will be checked against it and filler words can be searched.":
        "İlk Analiz bulundu: duraksamalar metinle karşılaştırılacak, dolgu kelimeleri aranabilir.",
    "No transcript for this video: hesitations are found from the audio only and "
    "filler words cannot be searched.":
        "Bu video için İlk Analiz yok: duraksamalar yalnızca sesten bulunur, "
        "dolgu kelimeleri aranamaz.",
    "Run Transcribe first to use filler words": "Dolgu kelimeleri için önce İlk Analiz'i çalıştır",
    "Tick at least one thing to cut": "Kesilecek en az bir şey işaretle",

    "Trim the start, the end and takes in between": "Başı, sonu ve aradaki tekrarları kırp",
    "Drops what was recorded before the programme starts and after it ends, and any "
    "range in the middle such as a repeated take. Leave a box empty to trim nothing there.":
        "Program başlamadan önce ve bittikten sonra kaydedilenleri, bir de aradaki tekrar çekim gibi "
        "aralıkları atar. Boş bıraktığın kutu için kırpma yapılmaz.",
    "Programme starts at": "Program başlangıcı",
    "Programme ends at": "Program bitişi",
    "Also remove": "Ayrıca at",
    "Show the start and end of the transcript": "Metnin başını ve sonunu göster",
    "ranges as start-end, separated by commas: 50:46-51:03, 12:00-12:30":
        "aralıklar başlangıç-bitiş biçiminde, virgülle ayrılır: 50:46-51:03, 12:00-12:30",
    "Start of the transcript:": "Metnin başı:",
    "End of the transcript:": "Metnin sonu:",

    # --- interface: review window ---------------------------------------------
    "Rough Cut candidates": "Kaba Kurgu adayları",
    "Review the cut candidates": "Kesim adaylarını gözden geçir",
    "Ticked ones will be cut. Double-click a row: listen. Click the first column "
    "or press space: change the tick. Silences are not in this list; they are "
    "cut directly.":
        "İşaretli olanlar kesilecek. Satıra çift tıkla: dinle. İlk sütuna tıkla ya da "
        "boşluk tuşu: işareti değiştir. Sessizlikler bu listede yok, doğrudan kesilir.",
    "There is no transcript, so no context text.": "İlk Analiz olmadığı için bağlam metni yok.",
    "Show": "Göster",
    "Apply the Rough Cut's cuts": "Kaba Kurgu kesimlerini uygula",
    "Leaves out the silences and hesitations it cut; the times above stay those of the video.":
        "Kaba Kurgu'nun kestiği sessizlik ve duraksamaları klipten çıkarır; yukarıdaki zamanlar videonun zamanları olarak kalır.",
    "the Rough Cut leaves nothing of this range.": "Kaba Kurgu bu aralıktan hiçbir şey bırakmıyor.",
    "the Rough Cut leaves less than a second of this range.": "Kaba Kurgu bu aralıktan bir saniyeden az bırakıyor.",
    "run Transcribe first; subtitles for a clip with the Rough Cut's cuts are made from the transcript.":
        "önce İlk Analiz'i çalıştır; Kaba Kurgu kesimleri uygulanmış bir klibin altyazısı dökümden yapılır.",
    "Cuts     : the Rough Cut's {n} cuts applied, {seconds:.1f} s shorter":
        "Kesimler : Kaba Kurgu'nun {n} kesimi uygulandı, {seconds:.1f} sn kısaldı",
    "throat clearing? (listen)": "boğaz temizleme? (dinle)",
    "Find throat clearing with the sound model": "Boğaz temizlemeyi ses modeliyle bul",
    "repeated words? (listen)": "tekrarlanan söz? (dinle)",
    "talk about the recording? (listen)": "çekimle ilgili konuşma? (dinle)",
    "Find repeated words and talk about the recording": "Tekrarlanan sözleri ve çekimle ilgili konuşmaları bul",
    "From the transcript: a word or a few said twice in a row, a sentence begun again after "
    "a pause, and what is said to the crew (“baştan alıyorum”, “bunu keseriz”). They arrive "
    "unticked as “repeated words? (listen)” and “talk about the recording? (listen)”, and "
    "Show → Repeats and retakes lists them. Speech also repeats on purpose; only you can tell.":
        "Dökümden: art arda iki kez söylenen bir ya da birkaç kelime, duraksayıp yeniden başlanan cümle ve "
        "ekibe söylenenler (“baştan alıyorum”, “bunu keseriz”). İşaretsiz olarak “tekrarlanan söz? (dinle)” "
        "ve “çekimle ilgili konuşma? (dinle)” diye gelir; Göster → Tekrarlar ve çekim konuşmaları onları "
        "listeler. Konuşmada bilerek yapılan tekrarlar da olur; ayırt etmek size kalır.",
    "Repeats and retakes": "Tekrarlar ve çekim konuşmaları",
    "Davar: listen to this join ({word})": "Davar: bu birleşimi dinle ({word})",
    "Joins to listen to: {n}, where a cut goes through a word with sound at the join. "
    "Each has a marker on the timeline.":
        "Dinlenecek birleşimler: {n}; kesimin bir kelimenin içinden geçtiği ve birleşimde ses olan yerler. "
        "Her birinde çizelgede bir işaret var.",
    "Joins to listen to: {n}, where a cut goes through a word with sound at the join.":
        "Dinlenecek birleşimler: {n}; kesimin bir kelimenin içinden geçtiği ve birleşimde ses olan yerler.",
    "{timeline} on the timeline ({video} in the video)  «{word}»": "çizelgede {timeline} (videoda {video})  «{word}»",
    "Mark the joins to listen to": "Dinlenecek birleşimleri işaretle",
    "The same markers for Resolve: {path}": "Aynı işaretler Resolve için: {path}",
    "In Resolve, right-click the timeline in the Media Pool and choose Timelines > Import > "
    "Timeline Markers from EDL.":
        "Resolve'da Media Pool'daki çizelgeye sağ tıklayıp Timelines > Import > "
        "Timeline Markers from EDL'i seçin.",
    "Take the rhythm of finished episodes…": "Bitmiş bölümlerin ritmini al…",
    "measures their pauses and sets the three boxes above": "duraklamalarını ölçer, yukarıdaki üç kutuyu ayarlar",
    "Choose finished episodes": "Bitmiş bölümleri seç",
    "Measuring the rhythm of {n} episodes…": "{n} bölümün ritmi ölçülüyor…",
    "too few pauses to measure a rhythm ({n}); choose longer or more episodes.":
        "ritim ölçmek için duraklama çok az ({n}); daha uzun ya da daha çok bölüm seç.",
    "choose at least one finished episode.": "en az bir bitmiş bölüm seç.",
    "Rhythm of finished episodes:": "Bitmiş bölümlerin ritmi:",
    "{name}: {minutes:.0f} min, {pauses} pauses; between phrases {phrase}, longest kept {longest}":
        "{name}: {minutes:.0f} dk, {pauses} duraklama; cümle arası {phrase}, bırakılan en uzun {longest}",
    "A pause between phrases lasts {phrase:.2f} s; 95 in 100 pauses are shorter than {longest:.2f} s.":
        "Cümle arası duraklama {phrase:.2f} sn sürüyor; duraklamaların 100'de 95'i {longest:.2f} sn'den kısa.",
    "Set: shortest silence {min:.2f} s, padding before a word {before:.2f} s, after a word "
    "{after:.2f} s. A longer silence is cut down to about {kept:.2f} s.":
        "Ayarlandı: en kısa sessizlik {min:.2f} sn, kelimeden önce pay {before:.2f} sn, kelimeden sonra "
        "{after:.2f} sn. Daha uzun bir sessizlik yaklaşık {kept:.2f} sn'ye kısaltılır.",
    "({n} of the times moved to the nearest pause)": "(zamanlardan {n} tanesi en yakın duraklamaya kaydırıldı)",
    "Looking for the pauses at the start and the end": "Başta ve sondaki duraklamalar aranıyor",
    "(moved to the nearest pauses)": "(en yakın duraklamalara kaydırıldı)",
    "A marker on the timeline wherever a cut goes through a word of the transcript "
    "with sound at the join, where a word may be clipped. The log lists them too.":
        "Kesimin dökümdeki bir kelimenin içinden geçtiği ve birleşimde ses olan her yere, yani bir kelimenin "
        "kırpılmış olabileceği yerlere çizelgede bir işaret konur. Kayıt penceresi de bunları listeler.",
    "Also the throat clearing that runs into speech, which the rule above misses. A sound "
    "model picks about 25 likely places an hour; they arrive unticked as “throat clearing? "
    "(listen)”, and Show → Non-speech sounds lists them. The model (16 MB) is downloaded "
    "once, on first use. It was trained on one programme; it may miss some or pick others.":
        "Yukarıdaki kuralın kaçırdığı, konuşmaya yapışık boğaz temizlemeleri de bulur. Bir ses modeli "
        "saatte yaklaşık 25 olası yer seçer; bunlar işaretsiz olarak “boğaz temizleme? (dinle)” diye gelir, "
        "Göster → Konuşma dışı sesler onları listeler. Model (16 MB) ilk kullanımda bir kez indirilir. "
        "Tek bir programla eğitildi; bazılarını kaçırabilir, başka sesleri seçebilir.",
    "the sound model could not be downloaded: {message}": "ses modeli indirilemedi: {message}",
    "the downloaded sound model is not the expected file, so it was not used.":
        "indirilen ses modeli beklenen dosya değil; bu yüzden kullanılmadı.",
    "the sound model needs onnxruntime. Install it with: pip install onnxruntime":
        "ses modeli için onnxruntime gerekir. Kurmak için: pip install onnxruntime",
    "Downloading the sound model (16 MB, only once)": "Ses modeli indiriliyor (16 MB, yalnızca bir kez)",
    "Listening for throat clearing": "Boğaz temizleme sesleri dinleniyor",
    "Finding where each throat clearing begins and ends": "Her boğaz temizlemenin başı ve sonu aranıyor",
    "Has an AI chat of your choice write the YouTube texts: title suggestions, a description "
    "with chapters, tags, a summary and social clip candidates. No key and no fee: you paste "
    "Davar's prompt into the chat and its answer back here.":
        "YouTube metinlerini seçtiğin bir yapay zekâ sohbetine yazdırır: başlık önerileri, bölüm zamanlı "
        "açıklama, etiketler, özet ve sosyal klip adayları. Anahtar ve ücret gerekmez: Davar'ın istemini "
        "sohbete, cevabını buraya yapıştırırsın.",
    "1. Prepare the prompt": "1. İstemi hazırla",
    "Start writes the transcript with its times on the Rough Cut timeline and who says "
    "what, and copies it. The speakers and their titles are taken from the Titles page. "
    "The text goes to the AI service you paste it into.":
        "Başlat, dökümü Kaba Kurgu çizelgesindeki zamanlarıyla ve kimin ne dediğiyle yazar ve kopyalar. "
        "Konuşmacılar ve unvanları Yazılar sayfasından alınır. Metin, onu yapıştırdığın yapay zekâ "
        "hizmetine gider.",
    "Programme": "Program",
    "e.g. the name of the series": "örneğin programın adı",
    "Channel": "Kanal",
    "Notes": "Notlar",
    "anything the AI should know: the date, the subject, a spelling":
        "yapay zekânın bilmesi gerekenler: tarih, konu, bir yazım",
    "Copy the prompt again": "İstemi yeniden kopyala",
    "2. Paste the answer": "2. Cevabı yapıştır",
    "Copy the AI chat's whole answer, paste it here and press Write the texts. The texts are "
    "written next to the video, ready for YouTube Studio.":
        "Yapay zekâ sohbetinin cevabının tamamını kopyala, buraya yapıştır ve Metinleri yaz'a bas. "
        "Metinler videonun yanına, YouTube Studio'ya hazır olarak yazılır.",
    "Write the texts": "Metinleri yaz",
    "Clear": "Temizle",
    "No speakers are written on the Titles page; the lines will not say who speaks.":
        "Yazılar sayfasında konuşmacı yazılı değil; satırlarda kimin konuştuğu yazmayacak.",
    "Run Transcribe first": "Önce İlk Analiz'i çalıştır",
    "The prompt is copied again: {path}": "İstem yeniden kopyalandı: {path}",
    "run Transcribe first; the texts are written from the transcript.":
        "önce İlk Analiz'i çalıştır; metinler dökümden yazılır.",
    "Writing the prompt": "İstem yazılıyor",
    "the answer could not be read. Paste the whole answer of the AI chat; it should be "
    "one block that starts with {{ and ends with }}.":
        "cevap okunamadı. Yapay zekâ sohbetinin cevabının tamamını yapıştır; {{ ile başlayıp }} ile "
        "biten tek bir blok olmalı.",
    "Prompt written: {path} ({lines} lines, {characters} characters)":
        "İstem yazıldı: {path} ({lines} satır, {characters} karakter)",
    "Times are on the Rough Cut timeline, so the chapters will match the finished video.":
        "Zamanlar Kaba Kurgu çizelgesine göre; bölümler bitmiş videoyla örtüşecek.",
    "There is no Rough Cut timeline yet: the times are those of the uncut video.":
        "Henüz Kaba Kurgu çizelgesi yok: zamanlar kesilmemiş videonunkiler.",
    "The prompt is copied. Open an AI chat (claude.ai, gemini.google.com or chatgpt.com), paste it and "
    "send it. Copy its whole answer and paste it into box 2 on this page.":
        "İstem kopyalandı. Bir yapay zekâ sohbeti aç (claude.ai, gemini.google.com ya da chatgpt.com), "
        "yapıştır ve gönder. Cevabın tamamını kopyalayıp bu sayfadaki 2. kutuya yapıştır.",
    "Texts written: {path}": "Metinler yazıldı: {path}",
    "{titles} titles, {chapters} chapters, {tags} tags, {clips} social clip candidates":
        "{titles} başlık, {chapters} bölüm, {tags} etiket, {clips} sosyal klip adayı",
    "WARNING: YouTube shows chapters only when there are at least three.":
        "UYARI: YouTube bölümleri ancak en az üç tane olduğunda gösterir.",
    "All": "Hepsi",
    "To be cut": "Kesilecekler",
    "Not to be cut": "Kesilmeyecekler",
    "Uncertain ones": "Emin olunmayanlar",
    "Non-speech sounds": "Konuşma dışı sesler",
    "A row whose tick you change stays in the list until you choose again.":
        "İşaretini değiştirdiğin satır, yeniden seçim yapana kadar listede kalır.",
    "Listen with the cut": "Kesilmiş halini dinle",
    "Tick the medium ones too": "Ortaları da işaretle",
    "Tick all": "Hepsini işaretle",
    "Tick none": "Hiçbirini işaretleme",
    "Back to suggested": "Önerilene dön",
    "Cut": "Kes",
    "Length": "Süre",
    "Kind": "Tür",
    "Confidence": "Güven",
    "Context": "Bağlam",
    "{selected} of {total} candidates will be cut ({shown} in the list). With the silences "
    "the timeline gets {time} shorter.":
        "{total} adayın {selected} tanesi kesilecek ({shown} tanesi listede). "
        "Sessizliklerle birlikte çizelge {time} kısalacak.",

    # --- interface: titles ----------------------------------------------------
    "Titles": "Yazılar",
    "Makes lower thirds: a speaker's name and title, and the topic being talked about. "
    "Ready videos with a transparent background and a soft entrance and exit; Davar puts "
    "them on the timeline, or drag them onto the track above the video in Resolve.":
        "KJ (alt bant) üretir: konuşmacının adı ve unvanı, bir de konuşulan gündem. Saydam zeminli, girişi "
        "ve çıkışı yumuşak hazır videolar; Davar onları zaman çizelgesine koyar, istersen Resolve'da "
        "videonun üstündeki şeride kendin sürüklersin.",
    "Speakers": "Konuşmacılar",
    "One person per line: Name | Title. The title is optional. "
    "A separate file is written for each person. To put one name elsewhere than "
    "the others, add its place on the screen, as the viewer sees it (left, centre, "
    "right): Name | Title | right":
        "Her satıra bir kişi: Ad Soyad | Unvan. Unvan yazmak zorunlu değil. "
        "Her kişi için ayrı bir dosya yazılır. Bir adı diğerlerinden farklı bir yere koymak için "
        "ekrandaki konumunu, izleyicinin gördüğü gibi ekle (sol, orta, sağ): Ad Soyad | Unvan | sağ. "
        "Ekranın solunda oturan kişi kendi sağında otursa da “sol” yazılır.",
    "Look": "Görünüm",
    "Time on screen": "Ekranda kalma",
    "Opens in half a second, fades out at the end": "Yarım saniyede açılır, sonunda solarak çıkar",
    "Place": "Yer",
    "Bottom left": "Sol alt",
    "Bottom centre": "Orta alt",
    "Bottom right": "Sağ alt",
    "Accent colour": "Vurgu rengi",
    "Colour of the stripe and the title band; example #E30613":
        "Şerit ve unvan bandının rengi; örnek #E30613",
    "Topic titles": "Gündem KJ'leri",
    "A title for the question or the subject, at the bottom of the picture with the logo "
    "on the right. One per line: time | headline. The time is on the Rough Cut timeline; "
    "each title opens a few seconds later, and waits if a name is on screen. A line of "
    "its own under the headline can be added: time | headline | line.":
        "Soru ya da gündem için, görüntünün altında, sağında logo olan bir KJ. Her satıra bir tane: "
        "zaman | başlık. Zaman Kaba Kurgu çizelgesindeki zamandır; KJ birkaç saniye sonra açılır, ekranda "
        "isim KJ'si varsa onun bitmesini bekler. Başlığın altına o KJ'ye özel bir satır da eklenebilir: "
        "zaman | başlık | alt satır.",
    "Take the chapters of Content Analysis": "İçerik Analizi'nin bölümlerini al",
    "Tab": "Sekme",
    "the name of the programme; empty: the one written on Content Analysis":
        "programın adı; boş bırakılırsa İçerik Analizi'ne yazılan",
    "Line under it": "Alt satır",
    "e.g. GUEST: NAME · TITLE; the same on every title": "örneğin KONUK: AD SOYAD · UNVAN; her KJ'de aynı",
    "Logo": "Logo",
    "The logo shown on the topic titles, and if you like in a corner of the picture from the "
    "start to the end.":
        "Gündem KJ'lerinde görünen logo; istersen videonun başından sonuna kadar görüntünün bir köşesinde de durur.",
    "Logo file": "Logo dosyası",
    "Put it in a corner of the picture, from the start to the end": "Baştan sona görüntünün bir köşesine koy",
    "Corner": "Köşe",
    "Top right": "Sağ üst",
    "Top left": "Sol üst",
    "Bottom right": "Sağ alt",
    "Bottom left": "Sol alt",
    "Width": "Genişlik",
    "percent of the picture's width": "görüntü genişliğinin yüzdesi",
    "Choose the logo file": "Logo dosyasını seç",
    "the corner can be: {choices}": "köşe şunlardan biri olabilir: {choices}",
    "the logo's width must be between 3 and 40 percent of the picture.":
        "logonun genişliği görüntünün yüzde 3 ile 40'ı arasında olmalı.",
    "choose the logo file first.": "önce logo dosyasını seç.",
    "top right": "sağ üst",
    "top left": "sol üst",
    "bottom right": "sağ alt",
    "bottom left": "sol alt",
    "Logo         : {corner} corner, {width} pixels wide, from the start to the end":
        "Logo         : {corner} köşede, {width} piksel genişlikte, baştan sona",
    "Placed on the Rough Cut timeline, on a track of its own above the titles.":
        "Kaba Kurgu çizelgesine, KJ'lerin üstünde kendi şeridine yerleştirildi.",
    "No Rough Cut timeline was found for this video, so a timeline of the whole video was written.":
        "Bu video için Kaba Kurgu çizelgesi bulunamadı; videonun tamamını içeren bir çizelge yazıldı.",
    "Choose the logo": "Logoyu seç",
    "Pictures": "Resimler",
    "No chapters yet: write the texts on the Content Analysis page first.":
        "Henüz bölüm yok: önce İçerik Analizi sayfasında metinleri yaz.",
    "The logo file was not found.": "Logo dosyası bulunamadı.",
    "Montserrat is not in {folder}; a common bold font will be used.":
        "Montserrat {folder} içinde yok; yaygın bir kalın yazı tipi kullanılacak.",
    "Write at least one name or one topic": "En az bir ad ya da bir gündem başlığı yaz",
    "the logo could not be opened: {path}": "logo açılamadı: {path}",
    "a topic title needs a headline.": "gündem KJ'si için bir başlık gerekir.",
    "a topic title must last between 3 and 60 seconds.": "gündem KJ'si 3 ile 60 saniye arasında kalmalı.",
    "could not read the line “{line}”. It reads: time | headline | line under it":
        "“{line}” satırı okunamadı. Biçimi şöyle: zaman | başlık | alt satır",
    "write at least one topic: time | headline": "en az bir gündem başlığı yaz: zaman | başlık",
    "Drawing the topic title {n} of {count}": "Gündem KJ'si çiziliyor: {n} / {count}",
    "Topic titles: {n}, {seconds:.0f} s each, transparent background (ProRes 4444)":
        "Gündem KJ'leri: {n} adet, her biri {seconds:.0f} sn, saydam zeminli (ProRes 4444)",
    "Montserrat was not found in {folder}; {font} was used.":
        "Montserrat {folder} içinde bulunamadı; {font} kullanıldı.",
    "{headline}: {timeline} on the timeline": "{headline}: çizelgede {timeline}",
    "{headline}: no room left before the end; not placed": "{headline}: sona kadar yer kalmadı; yerleştirilmedi",
    "Place them on the timeline": "Zaman çizelgesine yerleştir",
    "Write the speakers in the order they first speak. Davar listens for who speaks when "
    "and puts each name on the track above the video, a few seconds after that person "
    "first speaks. It needs the transcript. To choose the moment yourself, add the time "
    "in the video to the line: Name | Title | 0:41":
        "Konuşmacıları ilk konuştukları sırayla yaz. Davar kimin ne zaman konuştuğunu sesten bulur ve her "
        "adı, o kişi ilk konuşmaya başladıktan birkaç saniye sonra videonun üstündeki şeride koyar. "
        "Bunun için döküm gerekir. Anı kendin seçmek istersen videodaki zamanı satıra ekle: "
        "Ad Soyad | Unvan | 0:41",
    "For the names whose line gives no place of its own": "Satırında konum yazmayan adlar için",
    "No video selected: the names are made but not placed.":
        "Video seçili değil: KJ'ler üretilir ama yerleştirilmez.",
    "They will be added to the Rough Cut timeline of this video: {name}":
        "Bu videonun Kaba Kurgu çizelgesine eklenecek: {name}",
    "This video has no Rough Cut timeline yet, so a timeline of the whole video will be "
    "written. Run Rough Cut first to get the names on the cut.":
        "Bu videonun henüz Kaba Kurgu çizelgesi yok; videonun tamamını içeren bir çizelge yazılacak. "
        "Adların kesilmiş çizelgeye gelmesi için önce Kaba Kurgu'yu çalıştır.",
    "Run Transcribe first, or give each name a time": "Önce İlk Analiz'i çalıştır ya da her ada zaman ver",
    "The size and frame rate are taken from the selected video.":
        "Boyut ve kare hızı seçili videodan alınır.",
    "No video selected: made at 1920x1080, 30 frames per second.":
        "Video seçilmedi: 1920x1080, saniyede 30 kare olarak üretilir.",
    "Choose an output folder to make one without a video": "Video seçmeden üretmek için çıktı klasörü seç",

    # --- interface: social clips ----------------------------------------------
    "Social Clips": "Sosyal Klipler",
    "Cuts the range you choose from a landscape video into a vertical (9:16) Reels / Shorts "
    "video. Puts the speaker's frame over a blurred background and adds a headline, "
    "subtitles and an intro cover.":
        "Yatay videodan seçtiğin aralığı dikey (9:16) Reels / Shorts videosu olarak keser. "
        "Bulanık arka plan üstüne konuşmacı kadrajı, başlık, altyazı ve giriş kapağı ekler.",
    "Range and framing": "Aralık ve kadraj",
    "From": "Başlangıç",
    "To": "Bitiş",
    "minute:second, e.g. 13:06": "dakika:saniye, örn. 13:06",
    "Framing": "Kadraj",
    "left": "sol",
    "right": "sağ",
    "move it if the speaker is not in the centre": "konuşmacı ortada değilse kaydır",
    "Texts": "Yazılar",
    "A line left empty is not written.": "Boş bıraktığın satır yazılmaz.",
    "Kicker": "Üst yazı",
    "Headline line 1": "Başlık 1. satır",
    "Headline line 2": "Başlık 2. satır",
    "Extras": "Ekler",
    "Add subtitles": "Altyazı ekle",
    "Burns the speech into the video (uses the transcript when there is one). "
    "They cannot be corrected afterwards; read them first.":
        "Konuşmayı videoya gömer (İlk Analiz varsa onu kullanır). Sonradan düzeltilemez; önce oku.",
    "Add an intro cover": "Giriş kapağı ekle",
    "Puts a 2.5 second cover showing the kicker and headline at the start.":
        "Başa, üst yazı ve başlığı gösteren 2,5 saniyelik kapak koyar.",
    "Write the start and end time": "Başlangıç ve bitiş zamanını yaz",
    "Write a headline or a kicker for the intro cover": "Giriş kapağı için başlık ya da üst yazı yaz",

    # --- interface: planned workflows ----------------------------------------
    "Not written yet": "Henüz yazılmadı",
    "This workflow is planned but does not work.": "Bu iş akışı planlandı ama çalışmıyor.",
    "What it will do": "Ne yapacak",
    "What it needs": "Ne gerekiyor",
    "Multicam Edit": "Çok Kamera Kurgusu",
    "Picks the camera of whoever is speaking and returns to the wide shot now and then "
    "to keep the edit natural.":
        "Kim konuşuyorsa onun kamerasını seçer; arada genel plana dönerek kurguyu doğal tutar.",
    "You link each microphone to a speaker and to the camera to show while they speak.":
        "Her mikrofonu bir konuşmacıya ve o konuşurken gösterilecek kameraya bağlarsın.",
    "It picks the camera by speaker, respecting the shortest and longest shot length.":
        "Konuşana göre kamera seçer; en kısa ve en uzun plan süresine uyar.",
    "At intervals it returns to the wide shot (two-shot or wide).":
        "Belirli aralıklarla genel plana (ikili ya da geniş çekim) döner.",
    "It writes the result as one timeline for Resolve.": "Sonucu Resolve için tek çizelge olarak yazar.",
    "Synchronised camera files and separate audio per speaker. Cannot be used on single-camera shoots.":
        "Birbirine eşlenmiş (senkron) kamera dosyaları ve konuşmacı başına ayrı ses. "
        "Tek kameralı çekimlerde kullanılamaz.",
    "Content Analysis": "İçerik Analizi",
    "Visual Assets": "Görsel Malzeme",
    "Arranges the photos, documents and footage to cut in, according to what is being said.":
        "Konuşulan konulara göre araya girecek fotoğraf, belge ve görüntüleri düzenler.",
    "Lists the places, people and documents named in the text: which visual should go where.":
        "Metinde adı geçen yer, kişi ve belgeleri listeler: nereye hangi görsel girmeli.",
    "Places the visuals you choose at the right time, with a slow zoom.":
        "Seçtiğin görselleri doğru zamana, yavaş yakınlaştırmayla yerleştirir.",
    "The scope of this workflow is not settled yet; the others come first.":
        "Bu iş akışının kapsamı henüz netleşmedi; önce diğerleri bitecek.",
    "Publish": "Yayın",
    "Gathers the texts and files needed before uploading to YouTube. The description, "
    "chapters, titles and tags are already written by Content Analysis.":
        "YouTube'a yüklemeden önce gereken metinleri ve dosyaları toplar. Açıklama, bölümler, başlıklar "
        "ve etiketler zaten İçerik Analizi'nde yazılıyor.",
    "Suggests text and a frame for the thumbnail.": "Kapak görseli (thumbnail) için yazı ve kare önerir.",
    "Makes the thumbnail picture.": "Kapak görselini hazırlar.",
    "The texts of Content Analysis.": "İçerik Analizi'nin metinleri.",
    # picture
    "Picture": "Görüntü",
    "Reframes the video to 16:9 and holds a tripod shot still. The picture is re-encoded and "
    "written as a new video; the audio is not touched, so a transcript already made stays "
    "valid. The next steps continue with the new video.":
        "Videoyu 16:9 kadraja getirir ve sehpa çekimini yerinde sabitler. Görüntü yeniden kodlanıp yeni bir "
        "video olarak yazılır; sese dokunulmaz, bu yüzden önceden yapılmış İlk Analiz geçerli kalır. Sonraki "
        "adımlar yeni videoyla devam eder.",
    "Reframe to 16:9": "16:9 kadraja getir",
    "Cuts the sides of a picture wider than 16:9 (most phones), or the top and bottom of "
    "a narrower one, so that it fills the YouTube frame with no black bars.":
        "16:9'dan geniş görüntünün (çoğu telefon) yanlarını, dar olanın üstünü ve altını keser; görüntü "
        "YouTube çerçevesini siyah bant kalmadan doldurur.",
    "Position of the frame": "Kadrajın konumu",
    "0 = keep the left (or top) edge, 50 = middle, 100 = keep the right (or bottom) edge":
        "0 = sol (ya da üst) kenar kalır, 50 = orta, 100 = sağ (ya da alt) kenar kalır",
    "Lock the frame (tripod shots)": "Kadrajı sabitle (sehpa çekimleri)",
    "A phone on a tripod still makes the picture pump and hop while it hunts for focus, and "
    "the frame creeps over a long recording. Every frame is lined up with one reference "
    "frame, so the background stands perfectly still and cuts show less. The blur of the "
    "moment the focus slips stays. Only for a camera that does not move. Needs OpenCV.\n"
    "It takes one to two times the length of the video; the time left is shown at the bottom.":
        "Sehpadaki telefon odak ararken görüntüyü büyütüp küçültür ve zıplatır; uzun kayıtta kadraj da yavaş "
        "yavaş kayar. Her kare tek bir örnek kareye hizalanır: arka plan yerinden hiç oynamaz, kesim yerleri "
        "daha az belli olur. Odağın kaçtığı andaki bulanıklık kalır. Yalnızca hareket etmeyen kamera "
        "içindir. OpenCV gerekir.\n"
        "Videonun süresinin bir-iki katı kadar sürer; kalan süre altta görünür.",
    "Tick an operation": "Bir işlem işaretle",
    "could not read the frame shape “{text}”. Example: 16:9": "kadraj biçimi “{text}” okunamadı. Örnek: 16:9",
    "the frame position must be between 0 and 100.": "kadraj konumu 0 ile 100 arasında olmalı.",
    "the picture could not be followed in any frame.": "görüntü hiçbir karede izlenemedi.",
    "OpenCV is needed to lock the frame. Install it with: pip install opencv-python":
        "Kadrajı sabitlemek için OpenCV gerekir. Kurmak için: pip install opencv-python",
    "the picture has too little detail to follow (a plain wall, or too dark).":
        "görüntüde izlenecek kadar ayrıntı yok (düz bir duvar ya da fazla karanlık).",
    "about {minutes} min left": "yaklaşık {minutes} dk kaldı",
    "no frame could be read from the video.": "videodan kare okunamadı.",
    "Following the picture": "Görüntü izleniyor",
    "the picture already has this shape and locking is off: there is nothing to do.":
        "görüntü zaten bu biçimde ve sabitleme kapalı: yapılacak bir şey yok.",
    "the new video would overwrite the original.": "yeni video orijinalin üzerine yazılacaktı.",
    "the picture could not be followed in {share:.0f}% of the frames. Locking "
    "only works for a camera that does not move.":
        "görüntü karelerin %{share:.0f} kadarında izlenemedi. Sabitleme yalnızca hareket etmeyen kamerada "
        "çalışır.",
    "the camera moves too much in this video (up to {pixels:.0f} pixels). "
    "Locking only works for a camera that does not move.":
        "bu videoda kamera fazla hareket ediyor ({pixels:.0f} piksele kadar). Sabitleme yalnızca hareket "
        "etmeyen kamerada çalışır.",
    "Frame    : {width}x{height} -> {w}x{h}  (cut: left {left}, right {right}, top {top}, "
    "bottom {bottom} pixels)":
        "Kadraj   : {width}x{height} -> {w}x{h}  (kesilen: sol {left}, sağ {right}, üst {top}, "
        "alt {bottom} piksel)",
    "Locked   : the picture wandered by up to {pixels:.1f} pixels and {scale:.2f}% in size; "
    "every frame now lines up with one reference frame":
        "Sabitlendi: görüntü {pixels:.1f} piksele kadar kayıyor, boyutu %{scale:.2f} oynuyordu; "
        "artık her kare tek bir örnek kareye hizalı",
    "Zoom     : {percent:.1f}% closer, so the moving edges stay out of sight":
        "Yakınlık : %{percent:.1f} yakınlaştırıldı; oynayan kenarlar görünmüyor",
    "Lost     : {count} of {frames} frames could not be followed and took the position "
    "of their neighbours":
        "İzlenemedi: {frames} karenin {count} tanesi izlenemedi, komşularının konumunu aldı",
    "Rate     : the variable frame rate was turned into a constant one":
        "Kare hızı: değişken kare hızı sabit hıza çevrildi",
    "Text     : the transcript was carried over to the new video (the audio is unchanged)":
        "Metin    : İlk Analiz yeni videoya taşındı (ses değişmedi)",
    "Time     : {minutes:.0f} min": "Süre     : {minutes:.0f} dk",
    "Video written (audio not touched): {path}": "Video yazıldı (sese dokunulmadı): {path}",
}
