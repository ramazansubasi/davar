"""davar transcribe - transcribes the speech in a video once, with a time for every word.

The result is saved next to the video as <video>.davar.json; the other workflows
(Rough Cut, Social Clips) read that file instead of transcribing again. It can also
write YouTube subtitles (.srt) and a time-stamped text file (.txt).

    python transcript.py "video.mp4" --srt --text
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

import dictionary
from common import DavarError, format_time, run
from i18n import _
from roughcut import FILLER_HINTS, is_filler_sound, plain

VERSION = 2


def transcript_path(video, folder=None):
    video = Path(video)
    return (Path(folder) if folder else video.parent) / (video.stem + ".davar.json")


def _identity(video):
    stat = Path(video).stat()
    return {"name": Path(video).name, "size": stat.st_size, "mtime": int(stat.st_mtime)}


def _upgrade(record):
    """Read files written by the first, Turkish-keyed version of the format."""
    if record.get("surum") == 1:
        old = record.get("video", {})
        return {"version": VERSION, "language": record.get("dil", "tr"), "model": record.get("model", ""),
                "duration": record.get("sure", 0.0), "words": record.get("kelimeler", []),
                "video": {"name": old.get("ad"), "size": old.get("boyut"), "mtime": old.get("degisim")}}
    return record


def load(video, folder=None):
    """Return the saved transcript, or None when there is none or it belongs to another video."""
    video = Path(video)
    if not video.is_file():
        return None
    for path in {transcript_path(video, folder), transcript_path(video)}:
        try:
            record = _upgrade(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
        if record.get("version") == VERSION and record.get("video") == _identity(video):
            record["path"] = path
            # the personal dictionary is applied on every read; the raw text on disk is untouched
            record["words"], record["corrections"] = dictionary.apply(record["words"])
            return record
    return None


def carry_over(source, target):
    """Give `target` the transcript of `source`. For a new video whose audio is the same as
    the original's (only the picture was changed). Returns whether there was one to carry."""
    source, target = Path(source), Path(target)
    for path in {transcript_path(source, target.parent), transcript_path(source)}:
        try:
            record = _upgrade(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
        if record.get("version") == VERSION and record.get("video") == _identity(source):
            record["video"] = _identity(target)
            transcript_path(target).write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
            return True
    return False


def save(record):
    """Write corrected words back to the transcript file."""
    stored = {k: v for k, v in record.items() if k not in ("path", "corrections")}
    Path(record["path"]).write_text(json.dumps(stored, ensure_ascii=False), encoding="utf-8")


def line_groups(words, max_chars=70, max_seconds=6.0, language="tr"):
    """Split the words into subtitle lines; each line is a list of word indexes.

    Hesitation sounds ("uh", "um") are left out of every line.
    """
    lines, current = [], []
    for i, (text, start, end) in enumerate(words):
        if is_filler_sound(text, language):
            continue
        if current:
            first, previous = words[current[0]], words[current[-1]]
            length = sum(len(words[j][0]) + 1 for j in current) + len(text)
            if (length > max_chars or start - previous[2] > 0.7 or end - first[1] > max_seconds
                    or previous[0][-1:] in ".?!"):
                lines.append(current)
                current = []
        current.append(i)
    if current:
        lines.append(current)
    return lines


def edit_line(words, indexes, new_text):
    """Change the text of one line; return (new word list, [(old, new)] single-word corrections).

    With the same number of words the times are kept. Otherwise the line's time span
    is shared among the new words in proportion to their length.
    """
    new = new_text.split()
    old = [words[i] for i in indexes]
    words = [list(w) for w in words]
    corrections = []
    if len(new) == len(old):
        for i, text in zip(indexes, new):
            if plain(words[i][0]) != plain(text) and plain(text):
                corrections.append((dictionary.split_word(words[i][0])[0], dictionary.split_word(text)[0]))
            words[i][0] = text
        return words, corrections
    start, end = old[0][1], old[-1][2]
    dropped = set(indexes)
    kept = [w for i, w in enumerate(words) if i not in dropped]
    total = sum(len(t) + 1 for t in new) or 1
    t = start
    for text in new:
        share = (end - start) * (len(text) + 1) / total
        kept.append([text, round(t, 2), round(t + share, 2)])
        t += share
    return sorted(kept, key=lambda w: w[1]), corrections


def lines(words, max_chars=70, max_seconds=6.0, language="tr"):
    """Subtitle lines as (start, end, text)."""
    return [(words[g[0]][1], words[g[-1]][2], " ".join(words[i][0] for i in g))
            for g in line_groups(words, max_chars, max_seconds, language)]


def srt_time(t):
    ms = int(round(max(t, 0) * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def write_srt(record, path):
    rows = lines(record["words"], language=record.get("language", "tr"))
    Path(path).write_text("".join(f"{i}\n{srt_time(b)} --> {srt_time(e)}\n{text}\n\n"
                                  for i, (b, e, text) in enumerate(rows, 1)), encoding="utf-8")
    return len(rows)


def write_text(record, path):
    rows = lines(record["words"], max_chars=110, max_seconds=12.0, language=record.get("language", "tr"))
    Path(path).write_text("".join(f"[{int(b // 60):02d}:{int(b % 60):02d}] {text}\n" for b, _e, text in rows),
                          encoding="utf-8")
    return len(rows)


def transcribe(video, folder=None, srt=False, text=False, language="tr", model="small",
               force=False, progress=None):
    """Transcribe the speech and save it. A valid saved transcript is reused unless `force`."""
    def step(percent, message):
        if progress:
            progress(percent, message)

    video = Path(video)
    if not video.is_file():
        raise DavarError(_("file not found: {path}").format(path=video))
    record = None if force else load(video, folder)
    reused = record is not None
    if record is None:
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise DavarError(_("transcription needs faster-whisper. Install it with: pip install faster-whisper"))
        step(2, _("Extracting audio"))
        raw = run(["ffmpeg", "-v", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"])
        audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        duration = len(audio) / 16000
        if duration < 1:
            raise DavarError(_("no audio was found in the video."))
        step(4, _("Loading the model (downloaded on first use)"))
        whisper = WhisperModel(model, device="cpu", compute_type="int8")
        # Whisper usually skips hesitations; the hint makes it write "uh / um" down too,
        # so hesitations found in the audio can be checked against the transcript
        segments, _info = whisper.transcribe(audio, language=language, vad_filter=True, beam_size=3,
                                             word_timestamps=True, hotwords=FILLER_HINTS.get(language))
        words = []
        for segment in segments:  # progress moves as segments arrive
            for w in segment.words or []:
                piece = w.word.strip()
                if not piece:
                    continue
                # join split pieces such as "10" + ".000" or "Tuzla" + "'da"
                if words and not piece[0].isalnum():
                    words[-1] = [words[-1][0] + piece, words[-1][1], round(w.end, 2)]
                else:
                    words.append([piece, round(w.start, 2), round(w.end, 2)])
            step(4 + 94 * min(segment.end / duration, 1.0),
                 _("Transcribing ({done} / {total})").format(done=format_time(segment.end),
                                                            total=format_time(duration)))
        if not words:
            raise DavarError(_("no speech was found."))
        record = {"version": VERSION, "video": _identity(video), "language": language, "model": model,
                  "duration": round(duration, 2), "words": words}
        transcript_path(video, folder).write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        record = load(video, folder)  # with the personal dictionary applied

    files = [record["path"]]
    target = Path(folder) if folder else video.parent
    if srt:
        write_srt(record, target / (video.stem + ".srt"))
        files.append(target / (video.stem + ".srt"))
    if text:
        write_text(record, target / (video.stem + "_transcript.txt"))
        files.append(target / (video.stem + "_transcript.txt"))
    step(100, _("Finished"))
    return {"output": files[-1], "files": files, "record": record, "reused": reused}


def report(r):
    record = r["record"]
    fillers = sum(1 for w in record["words"] if is_filler_sound(w[0], record.get("language", "tr")))
    out = [
        _("Speech   : {duration}, {words} words ({fillers} of them uh / um), model {model}").format(
            duration=format_time(record["duration"]), words=len(record["words"]), fillers=fillers,
            model=record["model"]) + ("  — " + _("saved transcript reused") if r["reused"] else ""),
        _("Note     : written automatically; check names and numbers before publishing"),
    ]
    if record.get("corrections"):
        out.append(_("Dictionary: {n} words corrected from your personal dictionary").format(
            n=record["corrections"]))
    out.append("")
    return "\n".join(out + [_("Written: {path}").format(path=f) for f in r["files"]])


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Transcribe the speech in a video with word-level timing.")
    p.add_argument("video", type=Path)
    p.add_argument("--folder", type=Path, default=None, help="output folder (default: next to the video)")
    p.add_argument("--srt", action="store_true", help="also write YouTube subtitles (.srt)")
    p.add_argument("--text", action="store_true", help="also write a time-stamped text file (.txt)")
    p.add_argument("--language", default="tr", help="spoken language code (default tr)")
    p.add_argument("--model", default="small", help="Whisper model: base, small, medium (default small)")
    p.add_argument("--force", action="store_true", help="transcribe again even if a transcript is saved")
    a = p.parse_args()
    try:
        result = transcribe(a.video, folder=a.folder, srt=a.srt, text=a.text, language=a.language,
                            model=a.model, force=a.force,
                            progress=lambda pct, msg: print(f"\r{pct:5.1f}%  {msg}      ", end="", file=sys.stderr))
    except DavarError as e:
        sys.exit("\n" + _("ERROR: {message}").format(message=e))
    print("\n" + report(result))


if __name__ == "__main__":
    main()
