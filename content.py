"""davar content - the YouTube texts of a video, written by an AI chat of your choice.

No key and no fee: Davar writes a prompt holding the transcript, with its times on the
Rough Cut timeline and who says what; you paste it into an AI chat (Claude, Gemini,
ChatGPT) and paste the answer back. Davar checks the answer and writes title suggestions,
a description with chapters, tags, a summary and candidate ranges for social clips.

    python content.py "talk.mp4"                 # writes talk_prompt.txt
    python content.py "talk.mp4" --answer a.txt  # writes talk_youtube.txt from the answer
"""

import argparse
import json
import re
import sys
from pathlib import Path

import roughcut
import speakers
from common import DavarError, format_time, parse_time, video_info
from i18n import _

LINE_SECONDS = 20.0  # a transcript line of the prompt spans at most this long
SHORTEST_CHAPTER = 10.0  # YouTube ignores the chapters when one is shorter
FEWEST_CHAPTERS = 3  # and when there are fewer

# The prompt and the texts are in the language of the speech, not of the interface.
WORDING = {
    "tr": {
        "speaker": "Konuşmacı",
        "prompt": """Aşağıda bir YouTube videosunun dökümü var. Her satırın başındaki [dakika:saniye] o satırın videodaki zamanıdır.
{context}
Bu dökümden YouTube'a yükleme için şunları hazırla. YALNIZCA aşağıdaki biçimde, tek bir JSON nesnesi olarak cevap ver; öncesine ya da sonrasına açıklama yazma.

{{
  "titles": ["beş başlık önerisi"],
  "summary": "videonun iki-üç cümlelik özeti",
  "description": "YouTube açıklaması",
  "chapters": [{{"time": "0:00", "title": "bölüm başlığı", "kj": "EKRAN YAZISI"}}],
  "tags": ["etiket"],
  "clips": [{{"start": "12:30", "end": "13:25", "headline": "klip başlığı", "why": "neden ilgi çeker"}}]
}}

Kurallar:
- Başlıklar: en çok 70 karakter; merak uyandırsın ama tıklama tuzağı olmasın.
- Açıklama: iki-üç kısa paragraf; bölüm listesini açıklamaya yazma.
- Bölümler: ilki 0:00; konu değiştikçe yeni bölüm; her biri en az bir dakika; toplam 5-12 bölüm. Zamanları dökümdeki satır zamanlarından seç.
- Her bölümün "kj" alanı, o bölüm başlarken ekranın altında gösterilecek yazıdır: sorulan soru ya da konunun kendisi, en çok 45 karakter, büyük harfle. Örnek: "TUZLA'NIN İMAR SORUNU NASIL ÇÖZÜLÜR?"
- Etiketler: 10-15 tane.
- Klipler: 3-5 tane; her biri 30-90 saniye; kendi başına anlaşılan ve güçlü bir sözle başlayan bir bölüm. Başlangıç ve bitişi dökümdeki satır zamanlarından seç.
- Dökümde yanlış yazılmış sözcükleri, özellikle özel adları, doğru yazımıyla kullan.
- Bilgi uydurma; yalnızca dökümde söylenenlere dayan.

Döküm:
""",
        "context": {"programme": "Program", "channel": "Kanal", "people": "Konuşmacılar", "length": "Süre",
                    "notes": "Notlar"},
        "texts": {"titles": "BAŞLIK ÖNERİLERİ", "description": "AÇIKLAMA", "chapters": "Bölümler:",
                  "tags": "ETİKETLER", "summary": "ÖZET", "clips": "SOSYAL KLİP ADAYLARI",
                  "on_timeline": "Çizelgede", "in_video": "Videoda (Sosyal Klipler'e yazılacak zamanlar)",
                  "timeline_note": "Zamanlar Kaba Kurgu çizelgesine göredir; bitmiş videoyla örtüşür."},
    },
    "en": {
        "speaker": "Speaker",
        "prompt": """Below is the transcript of a YouTube video. The [minute:second] at the start of each line is its time in the video.
{context}
From this transcript prepare the following for the upload. Answer ONLY in the form below, as one JSON object, with no explanation before or after it.

{{
  "titles": ["five title suggestions"],
  "summary": "a summary of the video in two or three sentences",
  "description": "the YouTube description",
  "chapters": [{{"time": "0:00", "title": "chapter title", "kj": "ON-SCREEN TITLE"}}],
  "tags": ["tag"],
  "clips": [{{"start": "12:30", "end": "13:25", "headline": "clip headline", "why": "why it draws attention"}}]
}}

Rules:
- Titles: at most 70 characters; make people curious, without clickbait.
- Description: two or three short paragraphs; do not put the chapter list in it.
- Chapters: the first at 0:00; a new one when the subject changes; each at least a minute; 5-12 in all. Take the times from the times of the transcript lines.
- The "kj" of each chapter is the line shown at the bottom of the screen as the chapter begins: the question asked or the subject itself, at most 45 characters, in capitals. Example: "HOW CAN THE ZONING PROBLEM BE SOLVED?"
- Tags: 10-15.
- Clips: 3-5; each 30-90 seconds; a passage that stands on its own and opens with a strong sentence. Take the start and end from the times of the transcript lines.
- Where the transcript misspells words, proper names above all, use the right spelling.
- Do not invent anything; rely only on what is said in the transcript.

Transcript:
""",
        "context": {"programme": "Programme", "channel": "Channel", "people": "Speakers", "length": "Length",
                    "notes": "Notes"},
        "texts": {"titles": "TITLE SUGGESTIONS", "description": "DESCRIPTION", "chapters": "Chapters:",
                  "tags": "TAGS", "summary": "SUMMARY", "clips": "SOCIAL CLIP CANDIDATES",
                  "on_timeline": "On the timeline", "in_video": "In the video (the times for Social Clips)",
                  "timeline_note": "Times are on the Rough Cut timeline; they match the finished video."},
    },
}


def wording(language):
    return WORDING.get(language, WORDING["en"])


def clock(seconds):
    """Whole seconds as YouTube writes them: 4:05, 1:02:03."""
    seconds = int(seconds)
    hours, rest = divmod(seconds, 3600)
    return f"{hours}:{rest // 60:02d}:{rest % 60:02d}" if hours else f"{rest // 60}:{rest % 60:02d}"


def timeline_of(video, folder=None, info=None):
    """The parts of the Rough Cut timeline of the video and whether there is one; without
    one, the whole video is a single part."""
    video = Path(video)
    info = info or video_info(video)
    target = Path(folder) if folder else video.parent
    known = roughcut.read_timeline(target / (video.stem + "_cut.fcpxml"), video, info)
    return (known["parts"], True) if known else ([(0, info["frames"])], False)


def video_moment(parts, fps, seconds):
    """Where a moment of the timeline is in the video."""
    position = 0.0
    for start, end in parts:
        length = (end - start) / fps
        if seconds < position + length:
            return start / fps + seconds - position
        position += length
    return parts[-1][1] / fps if parts else seconds


def transcript_lines(words, parts, fps, turns=(), names=(), language="tr"):
    """The transcript as it is heard on the timeline: (seconds, speaker, text) lines.

    A line ends where the speaker changes, at the end of a sentence once it is long enough,
    or after LINE_SECONDS. `turns` are (start, end, speaker) in seconds of the video; the
    speakers are called by `names`, in the order they first speak. Hesitation sounds are left out.
    """
    def speaker_at(moment):
        for start, end, who in turns:
            if start <= moment < end:
                return who
        return None

    labelled = [[text, start, end, speaker_at((start + end) / 2)] for text, start, end in words
                if not roughcut.is_filler_sound(text, language)]
    lines = []
    for text, start, _end, who in roughcut.timeline_words(labelled, parts, fps):
        name = "" if who is None else (names[who] if who < len(names) else f"{wording(language)['speaker']} {who + 1}")
        last = lines[-1] if lines else None
        if (last is None or last[1] != name or start - last[0] >= LINE_SECONDS
                or (start - last[0] >= LINE_SECONDS / 2 and last[2][-1:] in ".?!")):
            lines.append([start, name, text])
        else:
            last[2] += " " + text
    return [tuple(line) for line in lines]


def build_prompt(lines, language="tr", programme="", channel="", people=(), notes="", length=None):
    """The text to paste into the AI chat. `people` are (name, title) pairs."""
    words = wording(language)
    labels = words["context"]
    context = []
    if programme.strip():
        context.append(f"{labels['programme']}: {programme.strip()}")
    if channel.strip():
        context.append(f"{labels['channel']}: {channel.strip()}")
    if people:
        context.append(f"{labels['people']}: " + ", ".join(f"{name} ({title})" if title else name
                                                          for name, title in people))
    if length is not None:
        context.append(f"{labels['length']}: {clock(length)}")
    if notes.strip():
        context.append(f"{labels['notes']}: {notes.strip()}")
    body = "\n".join(f"[{clock(at)}] {name + ': ' if name else ''}{text}" for at, name, text in lines)
    return words["prompt"].format(context=("\n" + "\n".join(context) + "\n") if context else "") + body + "\n"


def _time(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str) and value.strip():
        return parse_time(value.strip())
    raise DavarError(_("could not read the time “{text}”. Example: 13:06 or 1:02:03").format(text=value))


def _texts(value):
    if isinstance(value, str):
        value = [part for part in re.split(r"[,\n]", value)]
    return [str(v).strip() for v in value if str(v).strip()] if isinstance(value, list) else []


def parse_answer(text, length):
    """Read the AI's answer: a dict with titles, summary, description, chapters, tags and clips,
    put in order and checked against the length of the timeline (in seconds)."""
    found = re.search(r"\{.*\}", text or "", re.S)
    try:
        answer = json.loads(found.group(0)) if found else None
    except ValueError:
        answer = None
    if not isinstance(answer, dict):
        raise DavarError(_("the answer could not be read. Paste the whole answer of the AI chat; it should be "
                           "one block that starts with {{ and ends with }}."))
    chapters, screen = [], {}
    for chapter in answer.get("chapters") or []:
        try:
            at, title = _time(chapter["time"]), str(chapter["title"]).strip()
        except (DavarError, KeyError, TypeError):
            continue
        if title and 0 <= at < length:
            chapters.append((at, title))
            screen[at] = str(chapter.get("kj") or "").strip() or title
    chapters.sort()
    if chapters:
        chapters[0] = (0.0, chapters[0][1])  # YouTube needs the first at 0:00
    kept = []
    for at, title in chapters:
        if not kept or at - kept[-1][0] >= SHORTEST_CHAPTER:
            kept.append((at, title))
    clips = []
    for clip in answer.get("clips") or []:
        try:
            start, end = _time(clip["start"]), _time(clip["end"])
        except (DavarError, KeyError, TypeError):
            continue
        if 0 <= start < end <= length + 1:
            clips.append({"start": start, "end": min(end, length), "headline": str(clip.get("headline", "")).strip(),
                          "why": str(clip.get("why", "")).strip()})
    # the on-screen titles of the chapters, for the topic titles; not the opening chapter
    topics = [(at, screen.get(at, title)) for at, title in kept[1:]]
    return {"titles": _texts(answer.get("titles"))[:10], "summary": str(answer.get("summary") or "").strip(),
            "description": str(answer.get("description") or "").strip(), "chapters": kept,
            "tags": _texts(answer.get("tags")), "clips": clips, "topics": topics}


def write_texts(path, answer, parts, fps, language="tr", on_timeline=True):
    """Write the texts ready to be copied into YouTube Studio."""
    labels = wording(language)["texts"]
    out = [labels["titles"]] + [f"{n}. {title}" for n, title in enumerate(answer["titles"], 1)] + [""]
    out += [labels["description"], answer["description"], ""]
    if answer["chapters"]:
        out += [labels["chapters"]] + [f"{clock(at)} {title}" for at, title in answer["chapters"]] + [""]
    out += [labels["tags"], ", ".join(answer["tags"]), "", labels["summary"], answer["summary"], ""]
    if answer["clips"]:
        out.append(labels["clips"])
        for n, clip in enumerate(answer["clips"], 1):
            start, end = video_moment(parts, fps, clip["start"]), video_moment(parts, fps, clip["end"])
            out += [f"{n}. {clip['headline']}",
                    f"   {labels['on_timeline']}: {clock(clip['start'])} - {clock(clip['end'])}",
                    f"   {labels['in_video']}: {format_time(start)} - {format_time(end)}"]
            if clip["why"]:
                out.append(f"   {clip['why']}")
        out.append("")
    if on_timeline:
        out.append(labels["timeline_note"])
    Path(path).write_text("\n".join(out) + "\n", encoding="utf-8")


def prepare(video, words, folder=None, language="tr", programme="", channel="", people=(), notes="",
            progress=None):
    """Write the prompt (<video>_prompt.txt) and return it with what it was made from.
    `people` are (name, title) pairs in the order the speakers first speak."""
    def step(percent, text):
        if progress:
            progress(percent, text)

    if not words:
        raise DavarError(_("run Transcribe first; the texts are written from the transcript."))
    video = Path(video)
    info = video_info(video)
    fps = float(info["fps"])
    parts, on_timeline = timeline_of(video, folder, info)
    turns = []
    if len(people) >= 2:  # who says what helps the chapters and the summary
        step(10, _("Extracting audio"))
        samples, _levels = roughcut.audio_levels(video)
        step(70, _("Listening for who speaks when"))
        turns = speakers.find_turns(samples, words, len(people), language)
    step(90, _("Writing the prompt"))
    lines = transcript_lines(words, parts, fps, turns, [name for name, _title in people], language)
    length = sum(end - start for start, end in parts) / fps
    prompt = build_prompt(lines, language, programme, channel, people, notes, length)
    target = Path(folder) if folder else video.parent
    output = target / (video.stem + "_prompt.txt")
    output.write_text(prompt, encoding="utf-8")
    step(100, _("Finished"))
    return {"output": output, "prompt": prompt, "lines": len(lines), "characters": len(prompt),
            "on_timeline": on_timeline, "speakers": bool(turns)}


def finish(video, answer_text, folder=None, language="tr"):
    """Read the pasted answer and write <video>_youtube.txt (and the answer as _content.json)."""
    video = Path(video)
    info = video_info(video)
    fps = float(info["fps"])
    parts, on_timeline = timeline_of(video, folder, info)
    length = sum(end - start for start, end in parts) / fps
    answer = parse_answer(answer_text, length)
    target = Path(folder) if folder else video.parent
    output = target / (video.stem + "_youtube.txt")
    write_texts(output, answer, parts, fps, language, on_timeline)
    saved = {**answer, "chapters": [[at, title] for at, title in answer["chapters"]],
             "topics": [[at, title] for at, title in answer["topics"]], "on_timeline": on_timeline}
    (target / (video.stem + "_content.json")).write_text(json.dumps(saved, ensure_ascii=False, indent=2),
                                                         encoding="utf-8")
    return {"output": output, "answer": answer, "on_timeline": on_timeline}


def report_prompt(r):
    lines = [_("Prompt written: {path} ({lines} lines, {characters} characters)").format(
        path=r["output"], lines=r["lines"], characters=r["characters"]),
        _("Times are on the Rough Cut timeline, so the chapters will match the finished video.") if r["on_timeline"]
        else _("There is no Rough Cut timeline yet: the times are those of the uncut video."),
        "",
        _("The prompt is copied. Open an AI chat (claude.ai, gemini.google.com or chatgpt.com), paste it and "
          "send it. Copy its whole answer and paste it into box 2 on this page.")]
    return "\n".join(lines)


def report_texts(r):
    answer = r["answer"]
    lines = [_("Texts written: {path}").format(path=r["output"]),
             _("{titles} titles, {chapters} chapters, {tags} tags, {clips} social clip candidates").format(
                 titles=len(answer["titles"]), chapters=len(answer["chapters"]), tags=len(answer["tags"]),
                 clips=len(answer["clips"]))]
    if 0 < len(answer["chapters"]) < FEWEST_CHAPTERS:
        lines.append(_("WARNING: YouTube shows chapters only when there are at least three."))
    return "\n".join(lines)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Write a prompt for the YouTube texts, or the texts from its answer.")
    p.add_argument("video", type=Path, help="path of the video file")
    p.add_argument("--answer", type=Path, default=None, help="a file holding the AI chat's answer")
    p.add_argument("--programme", default="", help="name of the programme")
    p.add_argument("--channel", default="", help="name of the channel")
    a = p.parse_args()
    try:
        import transcript
        saved = transcript.load(a.video)
        language = saved.get("language", "tr") if saved else "tr"
        if a.answer:
            print(report_texts(finish(a.video, a.answer.read_text(encoding="utf-8"), language=language)))
        else:
            print(report_prompt(prepare(a.video, saved["words"] if saved else None, language=language,
                                        programme=a.programme, channel=a.channel)))
    except DavarError as e:
        sys.exit(_("ERROR: {message}").format(message=e))


if __name__ == "__main__":
    main()
