"""davar rough cut - finds silences, "uh / um" hesitations and filler words in a video
and writes the trimmed result as a timeline file (FCPXML) that DaVinci Resolve imports.

The original video is never modified.

    python roughcut.py "C:\\path\\video.mp4"
"""

import argparse
import math
import re
import sys
from pathlib import Path
from xml.sax.saxutils import quoteattr

import numpy as np

from common import SAMPLE_RATE, WINDOW, DavarError, format_time, run, video_info
from i18n import _


def audio_levels(path):
    """Decode the audio to mono and return (samples, level in dB for every 10 ms)."""
    raw = run(["ffmpeg", "-v", "error", "-i", str(path), "-vn",
               "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "s16le", "-"])
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    step = int(SAMPLE_RATE * WINDOW)
    n = len(samples) // step
    if n == 0:
        raise DavarError(_("the audio could not be read."))
    rms = np.sqrt(np.mean(samples[: n * step].reshape(n, step) ** 2, axis=1))
    return samples, 20 * np.log10(rms + 1e-10)


# --- finding "uh / um" ---------------------------------------------------------
# A hesitation sound differs from speech in three ways: it is voiced (the vocal
# cords vibrate), its pitch stays flat and the mouth shape does not change. In
# normal speech these three never hold together for 0.3 seconds.
FEATURE_WINDOW = 512  # 32 ms
SHAPE_LIMIT = 1.0  # the mouth shape (spectrum) may move at most this much
PITCH_TOLERANCE = 0.12  # the pitch may move by about 12% at most
VOICED_LIMIT = 0.45
HESITATION_PAD = 0.02  # padding left at the edge of a hesitation glued to a word (seconds)
SHORT_HESITATION = 0.15  # short hesitations heard by the transcript must last this long in the audio


def voice_features(samples):
    """Compute level, spectral shape, pitch and voicing for every 10 ms."""
    step = int(SAMPLE_RATE * WINDOW)
    n = max((len(samples) - FEATURE_WINDOW) // step, 0)
    window = np.hanning(FEATURE_WINDOW).astype(np.float32)
    freqs = np.fft.rfftfreq(FEATURE_WINDOW, 1 / SAMPLE_RATE)
    edges = 700 * (10 ** np.linspace(np.log10(1 + 100 / 700), np.log10(1 + 6000 / 700), 26) - 1)
    bank = np.zeros((24, len(freqs)), np.float32)
    for i in range(24):
        a, b, c = edges[i], edges[i + 1], edges[i + 2]
        bank[i] = np.clip(np.minimum((freqs - a) / (b - a), (c - freqs) / (c - b)), 0, None)

    db = np.empty(n, np.float32)
    shape = np.empty((n, 24), np.float32)
    pitch = np.ones(n, np.float32)
    voiced = np.zeros(n, np.float32)
    lag_min, lag_max = SAMPLE_RATE // 350, SAMPLE_RATE // 70  # pitch between 70 and 350 Hz
    correction = (FEATURE_WINDOW / (FEATURE_WINDOW - np.arange(lag_max + 1)))[None, :]
    for start in range(0, n, 20000):
        end = min(n, start + 20000)
        idx = (np.arange(start, end) * step)[:, None] + np.arange(FEATURE_WINDOW)[None, :]
        f = samples[idx]
        db[start:end] = 10 * np.log10(np.mean(f ** 2, axis=1) + 1e-10)
        f = f - f.mean(axis=1, keepdims=True)
        s = np.fft.rfft(f * window, axis=1)
        m = np.log((s.real ** 2 + s.imag ** 2).astype(np.float32) @ bank.T + 1e-9)
        shape[start:end] = m - m.mean(axis=1, keepdims=True)
        s = np.fft.rfft(f, 2 * FEATURE_WINDOW, axis=1)
        ac = np.fft.irfft(s.real ** 2 + s.imag ** 2, axis=1)[:, : lag_max + 1]
        ac = ac / (ac[:, :1] + 1e-9) * correction
        k = np.argmax(ac[:, lag_min:], axis=1) + lag_min
        voiced[start:end] = ac[np.arange(end - start), k]
        pitch[start:end] = SAMPLE_RATE / k
    return db, shape, pitch, voiced


def find_hesitations(features, threshold, min_duration):
    """Return sustained "uh / um" sounds as (start, end, kind) in seconds.

    Kind: "alone" = silence on both sides, "before_word" = follows a silence and
    runs into a word, "word_end" = glued to the end of a word (usually a real word
    being stretched; shown as a candidate but not cut by default).
    """
    db, shape, pitch, voiced = features
    n = len(db)
    usable = (db > threshold) & (voiced > VOICED_LIMIT)
    min_frames = int(round(min_duration / WINDOW))
    shift = FEATURE_WINDOW / 2 / SAMPLE_RATE - WINDOW / 2  # centre-of-window correction
    found = []
    i = 0
    while i < n:
        if not usable[i]:
            i += 1
            continue
        mean, p0, j, gap = shape[i].copy(), pitch[i], i + 1, 0
        while j < n:
            distance = math.sqrt(float(np.mean((shape[j] - mean) ** 2)))
            # the pitch tracker sometimes jumps an octave (88 Hz instead of 176 Hz); not a real change
            drift = abs(math.log(pitch[j] / p0))
            octave = abs(drift - math.log(2)) < PITCH_TOLERANCE
            if usable[j] and distance < SHAPE_LIMIT and (drift < PITCH_TOLERANCE or octave):
                k = j - i
                mean = (mean * k + shape[j]) / (k + 1)
                if not octave:
                    p0 = p0 * 0.9 + pitch[j] * 0.1
                gap = 0
            else:
                gap += 1
                if gap > 2:
                    break
            j += 1
        end = j - gap
        if end - i < min_frames:
            i += 1
            continue
        # what surrounds this stretch of sound: glued to a word, or standing alone?
        island_start, island_end = i, end
        while island_start > 0 and db[island_start - 1] > threshold:
            island_start -= 1
        while island_end < n and db[island_end] > threshold:
            island_end += 1
        before = (i - island_start) * WINDOW
        after = (island_end - end) * WINDOW
        if before <= 0.08 and after <= 0.12:
            found.append((island_start * WINDOW + shift, island_end * WINDOW + shift, "alone"))
        elif before <= 0.08:
            found.append((island_start * WINDOW + shift, end * WINDOW + shift, "before_word"))
        elif after <= 0.12:
            found.append((i * WINDOW + shift, island_end * WINDOW + shift, "word_end"))
        i = end
    return found


# --- silence ------------------------------------------------------------------
def auto_threshold(db):
    """Pick a threshold between the background noise and the speech level."""
    floor = max(float(np.percentile(db, 10)), -80.0)
    speech = float(np.percentile(db, 95))
    return floor + 0.35 * (speech - floor), floor, speech


def silent_intervals(db, threshold, min_silence, removed=None):
    """Return the intervals to drop as (start, end, starts with a candidate, ends with a candidate).

    Selected hesitations (`removed`, a boolean mask) count as silence, so they merge
    with an adjacent silence into a single cut.
    """
    if removed is None:
        removed = np.zeros(len(db), bool)
    silent = (db < threshold) | removed
    # clicks shorter than 30 ms must not split a silence
    short = int(0.03 / WINDOW)
    changes = np.flatnonzero(np.diff(silent.astype(np.int8)))
    bounds = np.concatenate(([0], changes + 1, [len(silent)]))
    for start, end in zip(bounds[:-1], bounds[1:]):
        if not silent[start] and end - start <= short and start > 0 and end < len(silent):
            silent[start:end] = True

    changes = np.flatnonzero(np.diff(silent.astype(np.int8)))
    bounds = np.concatenate(([0], changes + 1, [len(silent)]))
    intervals = []
    for start, end in zip(bounds[:-1], bounds[1:]):
        if silent[start] and ((end - start) * WINDOW >= min_silence or removed[start:end].any()):
            intervals.append((start * WINDOW, end * WINDOW, bool(removed[start]), bool(removed[end - 1])))
    return intervals


def compute_cuts(intervals, info, pad_before, pad_after):
    """Turn the intervals into cuts measured in frames, leaving padding around words.

    `pad_before` is kept before a word starts, `pad_after` after a word ends.
    """
    fps, total = info["fps"], info["frames"]
    cuts = []
    for start, end, starts_removed, ends_removed in intervals:
        # except at the very start and end of the video, keep padding on both sides of words;
        # at the edge of an "uh" glued to a word keep almost none, or its tail stays audible
        cut_start = start + (HESITATION_PAD if starts_removed else pad_after) if start > 0.02 else 0.0
        cut_end = (end - (HESITATION_PAD if ends_removed else pad_before)
                   if end < info["duration"] - 0.02 else info["duration"])
        first = math.ceil(cut_start * fps)
        last = min(math.floor(cut_end * fps), total)
        if last - first >= 2:
            cuts.append((first, last))
    return cuts


def remaining_parts(cuts, total):
    parts, position = [], 0
    for start, end in cuts:
        if start > position:
            parts.append((position, start))
        position = end
    if position < total:
        parts.append((position, total))
    return parts


def write_fcpxml(output, video, info, parts, label="cut"):
    fps = info["fps"]

    def t(frame):
        return f"{frame * fps.denominator}/{fps.numerator}s"

    name = video.stem
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<!DOCTYPE fcpxml>",
        '<fcpxml version="1.9">',
        "  <resources>",
        f'    <format id="r1" name="FFVideoFormatRateUndefined" frameDuration="{t(1)}" '
        f'width="{info["width"]}" height="{info["height"]}" colorSpace="1-1-1 (Rec. 709)"/>',
        f'    <asset id="r2" name={quoteattr(name)} start="0s" hasVideo="1" format="r1" '
        f'hasAudio="1" audioSources="1" audioChannels="{info["audio_channels"]}" '
        f'duration="{t(info["frames"])}">',
        f'      <media-rep kind="original-media" src={quoteattr(video.resolve().as_uri())}/>',
        "    </asset>",
        "  </resources>",
        "  <library>",
        '    <event name="davar">',
        f"      <project name={quoteattr(f'{name} - {label}')}>",
        f'        <sequence format="r1" tcStart="0s" tcFormat="NDF" '
        f'audioLayout="{"mono" if info["audio_channels"] == 1 else "stereo"}" '
        f'audioRate="{"44.1k" if info["audio_rate"] == 44100 else "48k"}">',
        "          <spine>",
    ]
    position = 0
    for start, end in parts:
        lines.append(f'            <asset-clip name={quoteattr(name)} offset="{t(position)}" '
                     f'start="{t(start)}" duration="{t(end - start)}" tcFormat="NDF" ref="r2"/>')
        position += end - start
    lines += ["          </spine>", "        </sequence>", "      </project>",
              "    </event>", "  </library>", "</fcpxml>", ""]
    output.write_text("\n".join(lines), encoding="utf-8")


# --- candidates ---------------------------------------------------------------
# Silences are cut directly. Hesitations and filler words are "candidates": each
# has a confidence level and the user can change its tick in the review list.

# How a hesitation sound looks once transcribed. It depends on the language: "a" and
# "e" are hesitations in Turkish but ordinary words in English.
FILLER_SOUNDS = {
    "tr": re.compile(r"^(ı+h*|e+h*|a+h*|h*m+|ı+m+|e+m+)$"),
    "en": re.compile(r"^(u+h+|u+m+|h*m{2,}|h+m+|e+r+m*|a+h+|u+h+m+)$"),
}
# what to hint to the speech model so that it writes hesitations down instead of skipping them
FILLER_HINTS = {"tr": "ııı eee ıı ee hmm", "en": "uh um er hmm"}


def kind_name(candidate):
    names = {"alone": _("uh / um (alone)"), "before_word": _("uh / um (before a word)"),
             "word_end": _("stretch (end of a word)"), "word": _("filler word"),
             "text_only": _("uh / um (transcript only)")}
    return (_("short") + " " if candidate.get("short") else "") + names[candidate["kind"]]


def confidence_name(level):
    return {"high": _("high"), "medium": _("medium"), "low": _("low")}[level]


def plain(word):
    """Strip punctuation and lowercase, following Turkish casing rules for I and İ."""
    return re.sub(r"[^\w]", "", word.replace("I", "ı").replace("İ", "i").lower())


def is_filler_sound(word, language="tr"):
    """Is this transcribed word a hesitation sound ("ııı", "uh") rather than a real word?"""
    pattern = FILLER_SOUNDS.get(language or "tr", FILLER_SOUNDS["en"])
    return bool(pattern.match(plain(word)))


def build_candidates(hesitations, db, words=None, filler_words=(), include_word_ends=False,
                     short_hesitations=(), language="tr"):
    """List the hesitations and filler words that may be cut, each with a confidence level.

    `words` is the transcript's list of (text, start, end). When given, hesitations
    found in the audio are checked against it and filler words are searched in it.
    `short_hesitations` are short sounds found with a loose measure: they become
    candidates only where the transcript also heard an "uh / um".
    """
    words = words or []
    plains = [plain(w[0]) for w in words]
    heard = [(w[1], w[2]) for w in words if is_filler_sound(w[0], language)]

    def context(start, end, mark=None):
        parts = []
        for i, w in enumerate(words):
            if w[2] > start - 1.2 and w[1] < end + 1.2:
                parts.append(f"«{w[0]}»" if mark and mark[0] <= i < mark[1] else w[0])
        return " ".join(parts)

    candidates = []
    for start, end, kind in hesitations:
        in_text = any(b < end + 0.5 and e > start - 0.5 for b, e in heard)
        if kind == "alone":
            confidence = "high"
        elif kind == "before_word":
            # with a transcript we expect it to have heard the "uh" as well
            confidence = ("high" if in_text else "low") if words else "medium"
        else:
            confidence = "medium" if in_text else "low"
        candidates.append({
            "start": start, "end": end, "kind": kind, "confidence": confidence,
            "context": context(start, end),
            "selected": (confidence == "high" or (kind == "before_word" and confidence == "medium")
                         or (kind == "word_end" and include_word_ends)),
        })

    def snap(t):  # word times are approximate: move to the quietest moment nearby
        mid = int(round(t / WINDOW))
        a, b = max(mid - 10, 0), min(mid + 11, len(db))
        return (a + int(np.argmin(db[a:b]))) * WINDOW if b > a else t

    def overlaps(start, end, margin=0.0):
        return any(c["start"] < end + margin and c["end"] > start - margin for c in candidates)

    # Hesitations the transcript heard but that were too short to be caught above.
    # Their timing comes from the steady sound at that spot, not from the transcript.
    for b, e in heard:
        if overlaps(b, e, 0.5):
            continue
        near = [h for h in short_hesitations if h[0] < e + 0.35 and h[1] > b - 0.35
                and not overlaps(h[0], h[1])]
        if near:
            start, end, kind = max(near, key=lambda h: h[1] - h[0])
            # a short cut leaves little room for error, so it arrives as a suggestion, unticked
            candidates.append({"start": start, "end": end, "kind": kind, "short": True,
                               "confidence": "low" if kind == "word_end" else "medium",
                               "selected": False, "context": context(start, end)})
        elif e - b >= SHORT_HESITATION:
            start, end = snap(b), snap(e)
            if end - start >= SHORT_HESITATION and not overlaps(start, end):
                candidates.append({"start": start, "end": end, "kind": "text_only", "confidence": "low",
                                   "selected": False, "context": context(start, end)})

    for phrase in filler_words:
        wanted = [plain(x) for x in phrase.split() if plain(x)]
        if not wanted:
            continue
        for i in range(len(plains) - len(wanted) + 1):
            if plains[i:i + len(wanted)] != wanted:
                continue
            start, end = snap(words[i][1]), snap(words[i + len(wanted) - 1][2])
            if end - start < 0.08 or overlaps(start, end):
                continue
            candidates.append({"start": start, "end": end, "kind": "word", "confidence": "medium",
                               "selected": False, "context": context(start, end, (i, i + len(wanted)))})
    candidates.sort(key=lambda c: c["start"])
    return candidates


def analyze(video, silence=True, hesitations=True, min_silence=0.5, pad_before=0.10, pad_after=0.15,
            threshold=None, min_hesitation=0.30, include_word_ends=False, words=None,
            filler_words=(), language="tr", progress=None):
    """Analyse the video and return a state holding the silence threshold and the cut candidates.

    Writes nothing. The result goes to `apply`; in between, the "selected" flags of
    the candidates may be changed.
    """
    def step(percent, text):
        if progress:
            progress(percent, text)

    video = Path(video)
    if not video.is_file():
        raise DavarError(_("file not found: {path}").format(path=video))
    if not silence and not hesitations and not filler_words:
        raise DavarError(_("nothing was selected to cut."))
    if filler_words and not words:
        raise DavarError(_("run Transcribe first to search for filler words."))

    step(5, _("Reading video information"))
    info = video_info(video)
    step(10, _("Extracting audio"))
    samples, db = audio_levels(video)
    auto, floor, speech = auto_threshold(db)
    used = threshold if threshold is not None else auto

    found, short = [], []
    if hesitations:
        step(40, _("Looking for hesitations (uh / um)"))
        features = voice_features(samples)
        found = find_hesitations(features, used, min_hesitation)
        if words and min_hesitation > SHORT_HESITATION:
            step(70, _("Matching short hesitations with the transcript"))
            short = find_hesitations(features, used, SHORT_HESITATION)
    step(90, _("Preparing candidates"))
    candidates = build_candidates(found, db, words, filler_words, include_word_ends, short, language)
    step(100, _("Analysis finished"))
    return {
        "video": video, "info": info, "fps": float(info["fps"]), "db": db, "samples": samples,
        "floor": floor, "speech": speech, "threshold": used, "manual_threshold": threshold is not None,
        "min_silence": min_silence if silence else float("inf"),
        "pad_before": pad_before, "pad_after": pad_after, "candidates": candidates,
        "has_transcript": bool(words),
    }


def cut_plan(state):
    """Compute the cuts and the remaining parts from the silences and the ticked candidates."""
    db = state["db"]
    mask = np.zeros(len(db), bool)
    for c in state["candidates"]:
        if c["selected"]:
            mask[max(int(round(c["start"] / WINDOW)), 0): int(round(c["end"] / WINDOW))] = True
    intervals = silent_intervals(db, state["threshold"], state["min_silence"], mask)
    cuts = compute_cuts(intervals, state["info"], state["pad_before"], state["pad_after"])
    return cuts, remaining_parts(cuts, state["info"]["frames"])


def apply(state, output=None, review=False):
    """Write the timeline file(s) and return a summary of the result."""
    video, info, fps = state["video"], state["info"], state["fps"]
    cuts, parts = cut_plan(state)
    if not parts:
        raise DavarError(_("the whole video looks silent; try lowering the threshold."))
    output = Path(output) if output else video.with_name(video.stem + "_cut.fcpxml")
    write_fcpxml(output, video, info, parts)

    selected = [c for c in state["candidates"] if c["selected"]]
    review_file = None
    if review and selected:
        # every cut candidate with one second before and after it
        review_file = output.with_name(video.stem + "_fillers.fcpxml")
        clips = []
        for c in selected:
            first = max(int((c["start"] - 1.0) * fps), 0)
            last = min(int(math.ceil((c["end"] + 1.0) * fps)), info["frames"])
            if clips and first <= clips[-1][1]:
                clips[-1] = (clips[-1][0], last)
            else:
                clips.append((first, last))
        write_fcpxml(review_file, video, info, clips, label="fillers")

    return {
        "video": video, "info": info, "fps": fps, "floor": state["floor"], "speech": state["speech"],
        "threshold": state["threshold"], "manual_threshold": state["manual_threshold"],
        "cuts": cuts, "candidates": state["candidates"], "selected": selected,
        "removed": sum(end - start for start, end in cuts) / fps,
        "output": output, "review": review_file,
    }


def process(video, output=None, review=False, progress=None, **settings):
    """Analyse and apply straight away with the default ticks (for the command line)."""
    return apply(analyze(video, progress=progress, **settings), output=output, review=review)


def report(r, detailed=True):
    """Turn the result of apply() into readable text."""
    info, fps = r["info"], r["fps"]
    lines = [
        _("Video        : {name}  ({width}x{height}, {fps:.3f} fps)").format(
            name=r["video"].name, width=info["width"], height=info["height"], fps=fps),
        _("Audio level  : background {floor:.0f} dB, speech {speech:.0f} dB, threshold {threshold:.0f} dB").format(
            floor=r["floor"], speech=r["speech"], threshold=r["threshold"])
        + (" " + _("(set manually)") if r["manual_threshold"] else ""),
        _("Cuts         : {n} places removed").format(n=len(r["cuts"]))
        + ("  " + _("({cut} of them hesitations or fillers; {kept} candidates left uncut)").format(
            cut=len(r["selected"]), kept=len(r["candidates"]) - len(r["selected"])) if r["candidates"] else ""),
        _("Duration     : {before} -> {after}  ({seconds:.1f} s shorter)").format(
            before=format_time(info["duration"]), after=format_time(info["duration"] - r["removed"]),
            seconds=r["removed"]),
    ]
    if r["speech"] - r["floor"] < 15:
        lines.append(_("WARNING: the background noise is close to the speech level; cuts may be wrong."))
    if info["variable_rate"]:
        lines.append(_("WARNING: the video seems to have a variable frame rate (phone or screen "
                       "recording); cut points may drift in Resolve."))
    if detailed and r["candidates"]:
        lines.append("\n" + _("Candidates (time in the original video; [x] = cut):"))
        for c in r["candidates"][:15]:
            lines.append(f"  [{'x' if c['selected'] else ' '}] {format_time(c['start'])}  "
                         f"{c['end'] - c['start']:.2f} s  {kind_name(c)}, "
                         + _("confidence {level}").format(level=confidence_name(c["confidence"]))
                         + (f"  | {c['context']}" if c["context"] else ""))
        if len(r["candidates"]) > 15:
            lines.append("  " + _("... and {n} more candidates").format(n=len(r["candidates"]) - 15))
    lines.append("\n" + _("Timeline written: {path}").format(path=r["output"]))
    if r["review"]:
        lines.append(_("Review timeline written: {path}").format(path=r["review"]))
    return "\n".join(lines)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Cut silences and hesitations and write a Resolve timeline.")
    p.add_argument("video", type=Path, help="path of the video file")
    p.add_argument("--min-silence", type=float, default=0.5,
                   help="silences shorter than this are left alone (seconds, default 0.5)")
    p.add_argument("--pad-before", type=float, default=0.10,
                   help="padding kept before a word starts (seconds, default 0.10)")
    p.add_argument("--pad-after", type=float, default=0.15,
                   help="padding kept after a word ends (seconds, default 0.15)")
    p.add_argument("--threshold", type=float, default=None,
                   help="silence threshold in dB; chosen automatically when omitted")
    p.add_argument("--no-silence", action="store_true", help="leave silences alone, cut hesitations only")
    p.add_argument("--no-hesitations", action="store_true", help="leave hesitations alone, cut silences only")
    p.add_argument("--min-hesitation", type=float, default=0.30,
                   help="hesitations shorter than this are left alone (seconds, default 0.30)")
    p.add_argument("--word-ends", action="store_true",
                   help="also cut stretches glued to the end of a word (high risk of wrong cuts)")
    p.add_argument("--fillers", default="",
                   help='filler words to cut, comma separated (e.g. "you know, like"); '
                        "needs a transcript and cuts every match")
    p.add_argument("--review", action="store_true",
                   help="also write a timeline with only the cut hesitations, for checking (<name>_fillers.fcpxml)")
    p.add_argument("--output", type=Path, default=None,
                   help="output file (default: <name>_cut.fcpxml next to the video)")
    a = p.parse_args()
    try:
        import transcript  # use the transcript too when one has been made
        saved = transcript.load(a.video)
        fillers = [f.strip() for f in a.fillers.split(",") if f.strip()]
        state = analyze(
            a.video, silence=not a.no_silence, hesitations=not a.no_hesitations,
            min_silence=a.min_silence, pad_before=a.pad_before, pad_after=a.pad_after,
            threshold=a.threshold, min_hesitation=a.min_hesitation, include_word_ends=a.word_ends,
            words=saved["words"] if saved else None, filler_words=fillers,
            language=saved["language"] if saved else "tr")
        for c in state["candidates"]:  # nobody to ask on the command line: requested words are cut
            if c["kind"] == "word":
                c["selected"] = True
        result = apply(state, output=a.output, review=a.review)
    except DavarError as e:
        sys.exit(_("ERROR: {message}").format(message=e))
    if saved:
        print(_("Transcript found: hesitations were checked against it."))
    print(report(result))


if __name__ == "__main__":
    main()
