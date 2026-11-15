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

    # --- rough cut ------------------------------------------------------------
    "uh / um (alone)": "ııı / eee (tek başına)",
    "uh / um (before a word)": "ııı / eee (kelime önünde)",
    "stretch (end of a word)": "uzatma (kelime sonunda)",
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
    "Show only the uncertain ones": "Yalnızca emin olunmayanları göster",
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
    "Makes a lower third for a speaker's name and title: a ready video with a transparent "
    "background and a soft entrance and exit. In Resolve it is dragged onto the track "
    "above the video.":
        "Konuşmacı adı ve unvanı için KJ (alt bant) üretir: saydam zeminli, girişi ve çıkışı "
        "yumuşak hazır bir video. Resolve'da videonun üstündeki şeride sürüklenir.",
    "Speakers": "Konuşmacılar",
    "One person per line: Name | Title. The title is optional. "
    "A separate file is written for each person.":
        "Her satıra bir kişi: Ad Soyad | Unvan. Unvan yazmak zorunlu değil. "
        "Her kişi için ayrı bir dosya yazılır.",
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
    "Topic titles that appear as the subject changes, and placing lower thirds on the "
    "timeline automatically.":
        "Konu değiştikçe ekrana gelen konu başlıkları ve KJ'lerin çizelgeye kendiliğinden yerleştirilmesi.",
    "The size and frame rate are taken from the selected video.":
        "Boyut ve kare hızı seçili videodan alınır.",
    "No video selected: made at 1920x1080, 30 frames per second.":
        "Video seçilmedi: 1920x1080, saniyede 30 kare olarak üretilir.",
    "Write at least one name": "En az bir ad yaz",
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
    "Reads the transcript and extracts the video's topics, chapters and highlights.":
        "İlk Analiz'in metnini okuyup videonun konularını, bölümlerini ve öne çıkan yerlerini çıkarır.",
    "Extracts topic titles and YouTube chapter times.":
        "Konu başlıklarını ve YouTube bölüm zamanlarını çıkarır.",
    "Lists a summary of the video and its standout sentences.":
        "Videonun özetini ve öne çıkan cümlelerini listeler.",
    "Suggests candidate ranges for social clips (hook, context, payoff).":
        "Sosyal klip için aday aralıklar önerir (kanca, bağlam, sonuç).",
    "A language model that understands the text: either an online AI service (needs a key and a "
    "small fee, and the text leaves your computer) or a model running on your computer (free, "
    "slow and weaker). Which one will be used is not decided yet.":
        "Metni anlayan bir dil modeli. İnternet üzerinden bir yapay zekâ servisi (anahtar ve küçük "
        "bir ücret gerekir, metin dışarı gider) ya da bilgisayarda çalışan bir model (ücretsiz, "
        "yavaş ve daha zayıf). Hangisinin kullanılacağı henüz kararlaştırılmadı.",
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
    "Gathers the texts and files needed before uploading to YouTube.":
        "YouTube'a yüklemeden önce gereken metinleri ve dosyaları toplar.",
    "Drafts a YouTube description with chapter times.":
        "Bölüm zamanlarıyla birlikte YouTube açıklaması taslağı çıkarır.",
    "Prepares title suggestions and tags.": "Başlık önerileri ve etiketler hazırlar.",
    "Suggests text and a frame for the thumbnail.": "Kapak görseli (thumbnail) için yazı ve kare önerir.",
    "The chapter extraction step of Content Analysis.": "İçerik Analizi'nin bölüm çıkarma adımı.",
}
