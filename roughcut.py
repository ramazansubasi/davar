"""davar rough cut - finds silences, "uh / um" hesitations and filler words in a video
and writes the trimmed result as a timeline file (FCPXML) that DaVinci Resolve imports.

The original video is never modified.

    python roughcut.py "C:\\path\\video.mp4"
"""

import argparse
import bisect
import math
import re
import sys
from fractions import Fraction
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname
from xml.etree import ElementTree
from xml.sax.saxutils import quoteattr

import numpy as np

from common import (SAMPLE_RATE, WINDOW, DavarError, format_time, parse_ranges, parse_time, run,
                    two_microphones_note, video_info)
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


def _follow_tail(db, shape, voiced, mean, level, end, threshold):
    """Follow a hesitation past its steady core to where the sound really stops.

    An "uh" rarely ends abruptly: it fades for another 0.1-0.3 seconds, wavering as it
    goes, and while it fades its spectrum drifts, so the steady core ends early. Cutting
    only the core leaves an audible stub. From the end of the core this walks on while
    the sound stays no louder than the core, and stops where something new begins.
    """
    limit = min(len(db), end + int(0.6 / WINDOW))
    j = end
    while j < limit:
        if db[j] <= threshold:  # faded into silence
            return j
        if db[j] > level + 3:  # louder than the hesitation ever was: the next word
            a = max(end, j - 12)  # go back to the dip just before it
            return a + int(np.argmin(db[a:j])) + 1 if j > a else j
        if voiced[j] < 0.35 and db[j] > threshold + 6:  # audible but unvoiced: a consonant
            return j
        if db[j] > level - 10 and math.sqrt(float(np.mean((shape[j] - mean) ** 2))) > 2 * SHAPE_LIMIT:
            return j  # still loud and clearly a different sound
        if (j >= 3 and db[j] > threshold + 8
                and math.sqrt(float(np.mean((shape[j] - shape[j - 3]) ** 2))) > 1.4):
            return j  # the sound changes abruptly: speech, not a fading tail
        j += 1
    return j


def find_hesitations(features, threshold, min_duration):
    """Return sustained "uh / um" sounds as (start, end, kind) in seconds.

    Kind: "alone" = silence on both sides, "before_word" = follows a silence and
    runs into a word, "word_end" = glued to the end of a word (usually a real word
    being stretched; shown as a candidate but not cut by default), "between_words" =
    speech on both sides with no pause (a long vowel inside a word looks the same, so
    these only become candidates where the transcript heard an "uh / um").
    """
    db, shape, pitch, voiced = features
    n = len(db)
    usable = (db > threshold) & (voiced > VOICED_LIMIT)
    min_frames = int(round(min_duration / WINDOW))
    shift = FEATURE_WINDOW / 2 / SAMPLE_RATE - WINDOW / 2  # centre-of-window correction
    found = []  # (first frame, last frame, kind)
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
        level = float(np.median(db[i:end]))
        core = end - i
        end = _follow_tail(db, shape, voiced, mean, level, end, threshold)

        # what surrounds this stretch of sound: glued to a word, or standing alone?
        island_start, island_end = i, end
        while island_start > 0 and db[island_start - 1] > threshold:
            island_start -= 1
        while island_end < n and db[island_end] > threshold:
            island_end += 1
        before = (i - island_start) * WINDOW
        after = (island_end - end) * WINDOW
        # A slow onset is part of the sound: up to 0.2 s that never gets louder than the sound it
        # leads into. Only for a long steady sound; a short one after a quiet syllable is a word.
        if (0.08 < before <= 0.20 and core >= int(0.30 / WINDOW)
                and float(db[island_start:i].max()) <= level + 1):
            before = 0.0
        if before <= 0.08 and after <= 0.12:
            found.append((island_start, island_end, "alone"))
        elif before <= 0.08:
            found.append((island_start, end, "before_word"))
        elif after <= 0.12:
            found.append((i, island_end, "word_end"))
        else:
            found.append((i, end, "between_words"))
        i = max(end, i + 1)
    return [(a * WINDOW + shift, b * WINDOW + shift, kind) for a, b, kind in found]


# --- coughs and other non-speech sounds ---------------------------------------
NOISE_GAP = 0.12  # a non-speech sound must have at least this much silence on both sides
NOISE_MAX = 1.2  # longer stretches are speech, not a cough


def find_noises(features, threshold):
    """Return short sounds standing alone between silences as (start, end, voiced share, faint).

    `faint` marks a brief sound barely louder than the silence around it: a click, a lip
    smack, a breath.

    A cough, a throat being cleared, a loud breath or a click is a burst of sound with
    silence on both sides. So is a short word such as "yes", which is why the caller
    decides with the transcript: a burst no word was transcribed for is not speech.
    Without a transcript only the noisy ones, with little voicing, can be told apart.
    """
    db, _shape, _pitch, voiced = features
    n = len(db)
    loud = db > threshold
    # gaps shorter than 30 ms do not split a sound
    changes = np.flatnonzero(np.diff(loud.astype(np.int8)))
    bounds = np.concatenate(([0], changes + 1, [n]))
    for a, b in zip(bounds[:-1], bounds[1:]):
        if not loud[a] and b - a <= 3 and a > 0 and b < n:
            loud[a:b] = True
    changes = np.flatnonzero(np.diff(loud.astype(np.int8)))
    bounds = np.concatenate(([0], changes + 1, [n]))
    islands = [(a, b) for a, b in zip(bounds[:-1], bounds[1:]) if loud[a]]
    gap = int(NOISE_GAP / WINDOW)
    shift = FEATURE_WINDOW / 2 / SAMPLE_RATE - WINDOW / 2
    found = []
    for k, (a, b) in enumerate(islands):
        if not 0.06 <= (b - a) * WINDOW <= NOISE_MAX:
            continue
        before = a - islands[k - 1][1] if k else gap
        after = islands[k + 1][0] - b if k + 1 < len(islands) else gap
        if before < gap or after < gap:
            continue
        share = float(np.mean(voiced[a:b] > VOICED_LIMIT))
        faint = bool(db[a:b].max() < threshold + 10 and (b - a) * WINDOW < 0.25)
        found.append((a * WINDOW + shift, b * WINDOW + shift, share, faint))
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


def compute_cuts(intervals, info, pad_before, pad_after, audio_end=None):
    """Turn the intervals into cuts measured in frames, leaving padding around words.

    `pad_before` is kept before a word starts, `pad_after` after a word ends.
    `audio_end` is where the audio stops; it is often a few frames short of the video,
    and an interval reaching it must run to the very end of the video.
    """
    fps, total = info["fps"], info["frames"]
    last_moment = min(audio_end or info["duration"], info["duration"]) - 0.02
    cuts = []
    for start, end, starts_removed, ends_removed in intervals:
        # except at the very start and end of the video, keep padding on both sides of words;
        # at the edge of an "uh" glued to a word keep almost none, or its tail stays audible
        cut_start = start + (HESITATION_PAD if starts_removed else pad_after) if start > 0.02 else 0.0
        cut_end = (end - (HESITATION_PAD if ends_removed else pad_before)
                   if end < last_moment else info["duration"])
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


# --- framing the speaker -------------------------------------------------------------
# With one camera every cut makes the people jump. As an editor with two cameras would,
# the picture moves closer to whoever gives a long answer and stays on everyone during
# quick exchanges. The framing changes only where a cut already is, so it hides that
# cut's jump; inside a long answer it changes now and then, at the cut that jumps most.
CLOSE_UP = 1.25  # the closer framing, as a scale of the picture
CHANGE_EVERY = 30.0  # seconds; how often the framing changes inside a long answer
SHORT_TURN = 10.0  # seconds on the timeline; a shorter turn stays on the whole picture
SETTLE = 3.0  # seconds into a turn before moving closer: where a turn starts is known only roughly
TURN_END = 8.0  # seconds; no change this close to the end of a turn, the next speaker changes it anyway
WIDE = (1.0, 0.0, 0.0)  # (scale, x, y): the whole picture


def close_framing(zoom, place, width, height):
    """A closer framing toward a speaker sitting at `place` (left, centre, right or None):
    (scale, x, y) with x and y as FCPXML gives a position, in percent."""
    if place not in ("left", "right"):
        return (zoom, 0.0, 0.0)
    # Moved by (zoom - 1) / 2 of its width, the enlarged picture meets the edge of the frame. The
    # percentage is of the frame height according to Apple, of the width according to some other
    # programs; reckoned on the larger width, the picture moves at most to the edge, never past it.
    x = (zoom - 1) / 2 * 100 * (1 if place == "left" else -1)
    y = -(zoom - 1) / 4 * 100 * height / width  # a little down, to keep room above the heads
    return (zoom, round(x, 2), round(y, 2))


def framings(parts, fps, turns, places=(), zoom=CLOSE_UP, width=1920, height=1080, every=CHANGE_EVERY):
    """The framing (scale, x, y) of each part of the timeline.

    `turns` are (start, end, speaker) in seconds of the video, as speakers.find_turns gives
    them; `places` says where each speaker sits. A turn shorter than SHORT_TURN on the timeline
    stays on the whole picture. In a longer one the picture moves closer to the speaker at the
    first cut SETTLE seconds into it, and then changes between close and whole about every
    `every` seconds, at the cut where most was removed.
    """
    count = len(parts)
    if not count:
        return []

    def speaker_at(moment):
        nearest, distance = None, float("inf")
        for start, end, who in turns:
            if start <= moment < end:
                return who
            if min(abs(moment - start), abs(moment - end)) < distance:
                nearest, distance = who, min(abs(moment - start), abs(moment - end))
        return nearest

    who = [speaker_at((start + end) / 2 / fps) for start, end in parts]
    lengths = [(end - start) / fps for start, end in parts]
    gaps = [0.0] + [(parts[i][0] - parts[i - 1][1]) / fps for i in range(1, count)]
    result = [WIDE] * count
    first = 0
    while first < count:
        last = first
        while last + 1 < count and who[last + 1] == who[first]:
            last += 1
        total = sum(lengths[first:last + 1])
        if who[first] is not None and total >= SHORT_TURN:
            at, moment = {}, 0.0  # part -> seconds from the start of the turn to that part
            for k in range(first, last + 1):
                at[k], moment = moment, moment + lengths[k]
            usable = [k for k in range(first + 1, last + 1) if total - at[k] >= TURN_END]
            changes = [k for k in usable if at[k] >= SETTLE][:1]
            while changes:
                after = at[changes[-1]]
                window = [k for k in usable if after + every <= at[k] <= after + every * 1.5]
                window = window or [k for k in usable if at[k] >= after + every][:1]
                if not window:
                    break
                changes.append(max(window, key=lambda k: gaps[k]))
            place = places[who[first]] if who[first] < len(places) else None
            close = close_framing(zoom, place, width, height)
            for n, start in enumerate(changes):
                stop = changes[n + 1] if n + 1 < len(changes) else last + 1
                for k in range(start, stop):
                    result[k] = close if n % 2 == 0 else WIDE
        first = last + 1
    return result


def timeline_place(parts, frame):
    """Where a frame of the video lands on the timeline made of `parts`:
    (index of the part, the frame it is shown from, its frame on the timeline).
    A frame that was cut away moves to the start of the next part that was kept;
    None if nothing is kept after it."""
    position = 0
    for index, (start, end) in enumerate(parts):
        if frame < end:
            shown = max(frame, start)
            return index, shown, position + shown - start
        position += end - start
    return None


def timeline_words(words, parts, fps):
    """The transcript's words moved onto the timeline made of `parts`.

    A word stays when at least half of it, or a quarter of a second, is kept: the times of a
    transcript are approximate, and a hesitation cut out of a word's middle must not take
    the word with it. It runs on the timeline from the first to the last of its kept pieces.
    """
    bounds = [(start / fps, end / fps) for start, end in parts]
    offsets, position = [], 0.0
    for start, end in bounds:
        offsets.append(position)
        position += end - start
    ends = [end for _start, end in bounds]
    result = []
    for word in sorted(words, key=lambda w: w[1]):
        text, start, end = word[:3]  # anything after the times rides along
        end = max(end, start + 0.01)
        pieces = []
        index = bisect.bisect_right(ends, start)
        while index < len(bounds) and bounds[index][0] < end:
            first, last = bounds[index]
            low, high = max(start, first), min(end, last)
            if high > low:
                pieces.append((offsets[index] + low - first, offsets[index] + high - first))
            index += 1
        kept = sum(high - low for low, high in pieces)
        if pieces and (kept >= 0.5 * (end - start) or kept >= 0.25):
            result.append([text, round(pieces[0][0], 3), round(pieces[-1][1], 3), *word[3:]])
    return result


def write_cut_subtitles(path, words, parts, fps, language="tr"):
    """Write subtitles (.srt) that follow the timeline made of `parts`; return the number of lines."""
    import transcript  # imported here: transcript itself uses this module
    return transcript.write_srt({"words": timeline_words(words, parts, fps), "language": language}, path)


def cut_subtitles_path(timeline):
    """Where the subtitles of a timeline go: talk_cut.fcpxml -> talk_cut.srt."""
    return Path(timeline).with_suffix(".srt")


def write_fcpxml(output, video, info, parts, label="cut", overlays=(), framings=None, still=None):
    """Write the parts of the video one after the other as a timeline.

    `overlays` are clips for the track above, such as name titles: dicts with "path",
    "at" (the frame of the video they start on) and "frames" (their length). They must
    have the size and frame rate of the video. `framings` gives each part a (scale, x, y)
    as the framings function makes them; the whole picture when left out. `still` is a
    picture of the size of the video, such as a logo in a corner, shown on a track of its
    own above everything from the start of the timeline to its end.
    """
    fps = info["fps"]

    def t(frame):
        return f"{frame * fps.denominator}/{fps.numerator}s"

    name = video.stem
    zero = info.get("timecode", 0)  # the video's own start timecode: its source times count from there
    assets, above = {}, {}  # overlay path -> resource id; part index -> lines of the clips above it
    for overlay in sorted(overlays, key=lambda o: o["at"]):
        place = timeline_place(parts, overlay["at"])
        if place is None:
            continue
        path = Path(overlay["path"])
        assets.setdefault(path, (f"r{len(assets) + 3}", overlay["frames"]))
        above.setdefault(place[0], []).append(
            f'              <asset-clip name={quoteattr(path.stem)} lane="1" offset="{t(zero + place[1])}" start="0s" '
            f'duration="{t(overlay["frames"])}" tcFormat="NDF" ref="{assets[path][0]}"/>')
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<!DOCTYPE fcpxml>",
        '<fcpxml version="1.9">',
        "  <resources>",
        f'    <format id="r1" name="FFVideoFormatRateUndefined" frameDuration="{t(1)}" '
        f'width="{info["width"]}" height="{info["height"]}" colorSpace="1-1-1 (Rec. 709)"/>',
        f'    <asset id="r2" name={quoteattr(name)} start="{t(zero)}" hasVideo="1" format="r1" '
        f'hasAudio="1" audioSources="1" audioChannels="{info["audio_channels"]}" '
        f'duration="{t(info["frames"])}">',
        f'      <media-rep kind="original-media" src={quoteattr(video.resolve().as_uri())}/>',
        "    </asset>",
        *((f'    <asset id="rs" name={quoteattr(Path(still).stem)} start="0s" hasVideo="1" format="r1" '
           f'videoSources="1" duration="0s">',
           f'      <media-rep kind="original-media" src={quoteattr(Path(still).resolve().as_uri())}/>',
           "    </asset>") if still else ()),
        *(line for path, (resource, frames) in assets.items() for line in (
            f'    <asset id="{resource}" name={quoteattr(path.stem)} start="0s" hasVideo="1" format="r1" '
            f'videoSources="1" duration="{t(frames)}">',
            f'      <media-rep kind="original-media" src={quoteattr(path.resolve().as_uri())}/>',
            "    </asset>")),
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
    for index, (start, end) in enumerate(parts):
        clip = (f'            <asset-clip name={quoteattr(name)} offset="{t(position)}" '
                f'start="{t(zero + start)}" duration="{t(end - start)}" tcFormat="NDF" ref="r2"')
        inside = list(above.get(index, []))
        if still and index == 0:  # the picture rides on the first part and lasts the whole timeline
            inside.append(f'              <video name={quoteattr(Path(still).stem)} lane="2" offset="{t(zero + start)}" '
                          f'ref="rs" start="0s" duration="{t(sum(b - a for a, b in parts))}"/>')
        scale, x, y = framings[index] if framings else WIDE
        if (scale, x, y) != WIDE:  # the picture's own adjustments come before the clips above it
            moved = f'position="{x:g} {y:g}" ' if (x, y) != (0, 0) else ""
            inside.insert(0, f'              <adjust-transform {moved}scale="{scale:g} {scale:g}"/>')
        lines += [clip + ">", *inside, "            </asset-clip>"] if inside else [clip + "/>"]
        position += end - start
    lines += ["          </spine>", "        </sequence>", "      </project>",
              "    </event>", "  </library>", "</fcpxml>", ""]
    output.write_text("\n".join(lines), encoding="utf-8")


def read_timeline(path, video, info):
    """Read back a timeline written by write_fcpxml for this video: a dict with its "parts",
    "overlays", "framings" and "still" (as write_fcpxml takes them). None if the file is not there, is not
    such a timeline, or is of another video or frame rate."""
    fps = info["fps"]

    def frames(text):
        value = Fraction(text.rstrip("s")) * fps
        if value.denominator != 1:
            raise ValueError(text)
        return int(value)

    try:
        root = ElementTree.parse(path).getroot()
        sources = {asset.get("id"): asset.find("media-rep").get("src") for asset in root.iter("asset")}
        if sources.get("r2") != Path(video).resolve().as_uri() or frames(root.find(".//format").get("frameDuration")) != 1:
            return None
        zero = next(frames(a.get("start", "0s")) for a in root.iter("asset") if a.get("id") == "r2")
        parts, overlays, framed, still = [], [], [], None
        for clip in root.find(".//spine").findall("asset-clip"):
            start = frames(clip.get("start")) - zero
            parts.append((start, start + frames(clip.get("duration"))))
            transform = clip.find("adjust-transform")
            if transform is None:
                framed.append(WIDE)
            else:
                x, y = (float(v) for v in transform.get("position", "0 0").split())
                framed.append((float(transform.get("scale", "1").split()[0]), x, y))
            for upper in clip.findall("asset-clip"):
                overlays.append({"path": Path(url2pathname(unquote(urlparse(sources[upper.get("ref")]).path))),
                                 "at": frames(upper.get("offset")) - zero, "frames": frames(upper.get("duration"))})
            for picture in clip.findall("video"):
                still = Path(url2pathname(unquote(urlparse(sources[picture.get("ref")]).path)))
    except (OSError, ElementTree.ParseError, AttributeError, KeyError, TypeError, ValueError, ZeroDivisionError):
        return None
    return {"parts": parts, "overlays": overlays, "framings": framed, "still": still} if parts else None


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
             "word_end": _("stretch (end of a word)"), "between_words": _("uh / um (between words)"),
             "word": _("filler word"), "text_only": _("uh / um (transcript only)"),
             "noise": _("non-speech sound (cough, breath)"),
             "unknown": _("sound with no word (listen)"), "throat": _("throat clearing? (listen)"),
             "repeat": _("repeated words? (listen)"), "retake": _("talk about the recording? (listen)")}
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
                     short_hesitations=(), language="tr", noises=(), throats=(), retakes=()):
    """List the hesitations and filler words that may be cut, each with a confidence level.

    `words` is the transcript's list of (text, start, end). When given, hesitations
    found in the audio are checked against it and filler words are searched in it.
    `short_hesitations` are short sounds found with a loose measure: they become
    candidates only where the transcript also heard an "uh / um". `throats` are likely
    throat clearings found by the sound model (see sounds.py): suggestions, never ticked.
    `retakes` are repeated words and talk about the recording found in the transcript
    (see retakes.py), as (start, end, first word, last word, kind, confidence): never ticked.

    Every candidate carries its surrounding sentence twice: "context" as plain text and
    "parts" as [(word, is this the thing being cut)], so an interface can highlight it.
    """
    words = words or []
    plains = [plain(w[0]) for w in words]
    heard = [i for i, w in enumerate(words) if is_filler_sound(w[0], language)]

    def context(start, end, first=None, last=None):
        """The words around a candidate; words first..last-1 are the candidate itself."""
        parts = [(w[0], first is not None and first <= i < last)
                 for i, w in enumerate(words) if w[2] > start - 1.2 and w[1] < end + 1.2]
        return " ".join(f"«{text}»" if cut else text for text, cut in parts), parts

    def heard_near(start, end, margin=0.5):
        """Index of the transcribed "uh / um" closest to this stretch of audio, if any."""
        middle = (start + end) / 2
        near = [i for i in heard if words[i][1] < end + margin and words[i][2] > start - margin]
        return min(near, key=lambda i: abs((words[i][1] + words[i][2]) / 2 - middle)) if near else None

    def add(start, end, kind, confidence, selected, first=None, last=None, **extra):
        text, parts = context(start, end, first, last)
        candidates.append({"start": start, "end": end, "kind": kind, "confidence": confidence,
                           "selected": selected, "context": text, "parts": parts, **extra})

    candidates = []
    explained = set()  # transcribed "uh / um" sounds that already belong to a candidate
    for start, end, kind in hesitations:
        i = heard_near(start, end)
        if kind == "between_words":
            continue  # too easily a long vowel inside a word; handled below through the transcript
        if i is not None:
            explained.add(i)
        if kind == "alone":
            confidence = "high"
        elif kind == "before_word":
            # with a transcript we expect it to have heard the "uh" as well
            confidence = ("high" if i is not None else "low") if words else "medium"
        else:
            confidence = "medium" if i is not None else "low"
        # a long stretch at the end of a word is cut only when the transcript heard an "uh" there
        add(start, end, kind, confidence,
            confidence == "high" or (kind == "before_word" and confidence == "medium")
            or (kind == "word_end" and (include_word_ends or confidence == "medium")),
            i, None if i is None else i + 1)

    # A hesitation is often two steady stretches in a row: the voice steps up, or a second
    # speaker joins in. A stretch that starts right where a candidate ends continues it, unless
    # the transcript has a word there ("eee" followed by a word beginning with "e" sounds the same).
    if words:
        steady = sorted(h for h in list(hesitations) + list(short_hesitations)
                        if h[2] == "between_words" and h[1] - h[0] >= 0.20)
        for c in candidates:
            for start, end, _kind in steady:
                if -0.03 <= start - c["end"] <= 0.08 and c["selected"]:
                    spoken = any(start < (w[1] + w[2]) / 2 < end + 0.05 for w in words
                                 if not is_filler_sound(w[0], language))
                    if not spoken:
                        c["end"] = end

    def snap(t):  # word times are approximate: move to the quietest moment nearby
        mid = int(round(t / WINDOW))
        a, b = max(mid - 10, 0), min(mid + 11, len(db))
        return (a + int(np.argmin(db[a:b]))) * WINDOW if b > a else t

    def overlaps(start, end, margin=0.0):
        return any(c["start"] < end + margin and c["end"] > start - margin for c in candidates)

    # Hesitations the transcript heard but that were too short to be caught above.
    # Their timing comes from the steady sound at that spot, not from the transcript.
    between = [h for h in hesitations if h[2] == "between_words"]
    for i in heard:
        if i in explained:
            continue
        b, e = words[i][1], words[i][2]
        near = [h for h in list(short_hesitations) + between if h[0] < e + 0.35 and h[1] > b - 0.35
                and not overlaps(h[0], h[1])]
        if near:
            # prefer a sound that begins after a pause; among equals take the longest
            start, end, kind = max(near, key=lambda h: (h[2] in ("alone", "before_word"), h[1] - h[0]))
            # Heard by the transcript and found in the audio: after a pause it is cut by default,
            # and so is a longer one between two words. A short one in the middle of speech, or
            # one glued to the end of a word, is only a suggestion.
            clear = kind in ("alone", "before_word")
            long_enough = end - start >= 0.20
            add(start, end, kind, "medium" if clear or kind == "between_words" else "low",
                clear or (kind == "between_words" and long_enough), i, i + 1, short=end - start < 0.30)
        elif e - b >= SHORT_HESITATION and not overlaps(b, e, 0.2):
            start, end = snap(b), snap(e)
            if end - start >= SHORT_HESITATION and not overlaps(start, end):
                add(start, end, "text_only", "low", False, i, i + 1)

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
            add(start, end, "word", "medium", False, i, i + len(wanted))
    # Coughs, throat clearing, loud breaths: bursts of sound for which no word was transcribed.
    for start, end, voiced_share, faint in noises:
        if overlaps(start, end):
            continue  # already listed as a hesitation
        noisy = voiced_share < 0.5  # a cough or a breath is noise; a voice is mostly voiced
        if words:
            spoken = [w for w in words if not is_filler_sound(w[0], language)
                      and w[1] < end + 0.05 and w[2] > start - 0.05]
            middle_inside = any(start - 0.05 <= (w[1] + w[2]) / 2 <= end + 0.05 for w in spoken)
            covered = sum(min(w[2], end) - max(w[1], start) for w in spoken) / (end - start)
            if middle_inside or covered > 0.5:
                continue  # a word was said here
            if noisy or faint:
                add(start, end, "noise", "high" if not spoken else "medium", True)
            else:
                # A clear voice the transcript has no word for: a throat being cleared, a murmur
                # of agreement, or a word the speech model missed. Only a listener can tell.
                add(start, end, "unknown", "low", False)
        elif voiced_share < 0.35:
            # noisy and isolated, but without a transcript it could still be a short word
            add(start, end, "noise", "medium", True)
    # Throat clearing found by the sound model. Only a listener can tell, so nothing is ticked.
    # A place that a candidate already covers changes that candidate's name instead; a place
    # partly cut already keeps only the part that is left.
    for start, end, score in throats:
        over = [c for c in candidates if c["start"] < end and c["end"] > start]
        cut = [c for c in over if c["selected"]]
        confidence = "medium" if score >= 0.95 else "low"
        if cut:
            start = max(start, max(c["end"] for c in cut))
            if end - start >= 0.15 and not any(c["start"] < end and c["end"] > start for c in cut):
                add(start, end, "throat", confidence, False)
        elif over:
            c = over[0]
            c["start"], c["end"] = min(c["start"], start), max(c["end"], end)
            c["kind"], c["confidence"] = "throat", confidence
            c["context"], c["parts"] = context(c["start"], c["end"])
        else:
            add(start, end, "throat", confidence, False)
    # Repeats, restarts and talk about the recording. Only a listener can tell a slip from
    # a repeat said on purpose, so nothing is ticked. Edges move to the quietest moment nearby.
    for start, end, first, last, kind, confidence in retakes:
        add(snap(start), snap(end), kind, confidence, False, first, last)
    # Last check against the transcript: a sound candidate that swallows a transcribed word is
    # either a mistake of ours or a mistimed word. It stays in the list, unticked, for the listener.
    if words:
        for c in candidates:
            if c["kind"] in ("word", "noise", "unknown", "text_only", "throat") or not c["selected"]:
                continue
            for w in words:
                if (c["start"] + 0.05 < (w[1] + w[2]) / 2 < c["end"] - 0.05
                        and min(w[2], c["end"]) - max(w[1], c["start"]) > 0.6 * (w[2] - w[1])
                        and not is_filler_sound(w[0], language)):
                    c["selected"], c["confidence"] = False, "low"
                    break
    candidates.sort(key=lambda c: c["start"])
    return candidates


def analyze(video, silence=True, hesitations=True, min_silence=0.5, pad_before=0.10, pad_after=0.15,
            threshold=None, min_hesitation=0.30, include_word_ends=False, words=None,
            filler_words=(), language="tr", keep_from=None, keep_to=None, remove=(), noises=True,
            throat=False, retakes=False, progress=None):
    """Analyse the video and return a state holding the silence threshold and the cut candidates.

    Writes nothing. The result goes to `apply`; in between, the "selected" flags of
    the candidates may be changed.

    `keep_from` / `keep_to` trim everything before / after those seconds, and `remove`
    is a list of (start, end) ranges to drop from the middle, such as a repeated take.
    `noises` also looks for coughs and other non-speech sounds, `throat` for throat clearing
    with the sound model, and `retakes` for repeated words and talk about the recording.
    """
    def step(percent, text):
        if progress:
            progress(percent, text)

    video = Path(video)
    if not video.is_file():
        raise DavarError(_("file not found: {path}").format(path=video))
    trimming = keep_from is not None or keep_to is not None or bool(remove)
    if not silence and not hesitations and not filler_words and not trimming and not noises and not retakes:
        raise DavarError(_("nothing was selected to cut."))
    if keep_from is not None and keep_to is not None and keep_to <= keep_from:
        raise DavarError(_("the end of the programme must come after its start."))
    if filler_words and not words:
        raise DavarError(_("run Transcribe first to search for filler words."))

    step(5, _("Reading video information"))
    info = video_info(video)
    for moment in [keep_from, keep_to] + [start for start, _end in remove]:
        if moment is not None and moment >= info["duration"]:
            raise DavarError(_("the time {time} is past the end of the video ({length}). Write minute:second, "
                               "e.g. 16:40.5; three numbers such as 16:40:00 mean hours:minutes:seconds.").format(
                time=format_time(moment), length=format_time(info["duration"])))
    step(10, _("Extracting audio"))
    samples, db = audio_levels(video)
    auto, floor, speech = auto_threshold(db)
    used = threshold if threshold is not None else auto

    found, short, bursts = [], [], []
    if hesitations or noises:
        step(40, _("Looking for hesitations (uh / um)") if hesitations else _("Looking for non-speech sounds"))
        features = voice_features(samples)
        if hesitations:
            found = find_hesitations(features, used, min_hesitation)
            if words and min_hesitation > SHORT_HESITATION:
                step(70, _("Matching short hesitations with the transcript"))
                short = find_hesitations(features, used, SHORT_HESITATION)
        if noises:
            step(85, _("Looking for non-speech sounds"))
            bursts = find_noises(features, used)
    def usable(moment):  # a place that is trimmed away anyway is not offered
        return ((keep_from is None or moment >= keep_from) and (keep_to is None or moment < keep_to)
                and not any(start <= moment < end for start, end in remove))
    throats = []
    if throat:  # with the sound model; downloaded on first use
        import sounds
        throats = sounds.find_throat_clearing(samples, db, used, usable, lambda share, text: step(86 + 4 * share, text))
    repeats = []
    if retakes and words:
        import retakes as slips  # imported here: retakes itself uses this module
        repeats = [r for r in slips.find_retakes(words, language) if usable((r[0] + r[1]) / 2)]
    step(90, _("Preparing candidates"))
    candidates = build_candidates(found, db, words, filler_words, include_word_ends, short, language, bursts,
                                  throats, repeats)
    step(100, _("Analysis finished"))
    return {
        "video": video, "info": info, "fps": float(info["fps"]), "db": db, "samples": samples,
        "floor": floor, "speech": speech, "threshold": used, "manual_threshold": threshold is not None,
        "min_silence": min_silence if silence else float("inf"),
        "pad_before": pad_before, "pad_after": pad_after, "candidates": candidates,
        "has_transcript": bool(words), "words": words, "language": language,
        "keep_from": keep_from, "keep_to": keep_to, "remove": list(remove),
    }


def cut_plan(state):
    """Compute the cuts and the remaining parts from the silences and the ticked candidates."""
    db = state["db"]
    mask = np.zeros(len(db), bool)
    for c in state["candidates"]:
        if c["selected"]:
            mask[max(int(round(c["start"] / WINDOW)), 0): int(round(c["end"] / WINDOW))] = True
    # manual trimming goes into the same mask, so it merges with a neighbouring silence
    if state.get("keep_from") is not None:
        mask[: int(round(state["keep_from"] / WINDOW))] = True
    if state.get("keep_to") is not None:
        mask[int(round(state["keep_to"] / WINDOW)):] = True
    for start, end in state.get("remove", ()):
        mask[max(int(round(start / WINDOW)), 0): int(round(end / WINDOW))] = True
    intervals = silent_intervals(db, state["threshold"], state["min_silence"], mask)
    cuts = compute_cuts(intervals, state["info"], state["pad_before"], state["pad_after"], len(db) * WINDOW)
    return cuts, remaining_parts(cuts, state["info"]["frames"])


def apply(state, output=None, review=False, close_up=None, places=(), speakers=2, every=CHANGE_EVERY):
    """Write the timeline file(s) and return a summary of the result.

    With `close_up` (a scale such as 1.25) the picture moves closer to whoever gives a long
    answer (see framings). `places` says where each speaker sits, in the order they first
    speak; without it `speakers` people are assumed and the closer framing stays in the middle.
    Who speaks when is taken from state["turns"] or else worked out here from the transcript.
    """
    video, info, fps = state["video"], state["info"], state["fps"]
    cuts, parts = cut_plan(state)
    if not parts:
        raise DavarError(_("the whole video looks silent; try lowering the threshold."))
    output = Path(output) if output else video.with_name(video.stem + "_cut.fcpxml")
    # name titles that Titles placed on an earlier cut of this video stay on the new one
    earlier = read_timeline(output, video, info)
    titles = [o for o in earlier["overlays"] if o["path"].is_file()] if earlier else []
    still = earlier["still"] if earlier and earlier["still"] and earlier["still"].is_file() else None
    framed = None
    if close_up:
        turns = state.get("turns")
        if turns is None:
            if not state.get("words"):
                raise DavarError(_("run Transcribe first; the speakers are told apart with the help of the transcript."))
            import speakers as voices  # imported here: speakers itself uses this module
            turns = voices.find_turns(state["samples"], state["words"], len(places) or speakers,
                                      state.get("language", "tr"))
        framed = framings(parts, fps, turns, places, close_up, info["width"], info["height"], every)
    write_fcpxml(output, video, info, parts, overlays=titles, framings=framed, still=still)
    subtitles = None
    if state.get("words"):  # subtitles always follow the cut, never the uncut video
        subtitles = cut_subtitles_path(output)
        write_cut_subtitles(subtitles, state["words"], parts, fps, state.get("language", "tr"))

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
        "removed": sum(end - start for start, end in cuts) / fps, "titles": len(titles),
        "close_up": close_up, "every": every,
        "changes": sum(a != b for a, b in zip(framed, framed[1:])) if framed else 0,
        "close_share": (sum(end - start for (start, end), f in zip(parts, framed) if f != WIDE)
                        / sum(end - start for start, end in parts)) if framed else 0.0,
        "output": output, "review": review_file, "subtitles": subtitles,
        "keep_from": state.get("keep_from"), "keep_to": state.get("keep_to"),
        "remove": state.get("remove", []),
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
    trimmed = []
    if r.get("keep_from") is not None:
        trimmed.append(_("start up to {time}").format(time=format_time(r["keep_from"])))
    if r.get("keep_to") is not None:
        trimmed.append(_("end from {time}").format(time=format_time(r["keep_to"])))
    trimmed += [f"{format_time(a)}-{format_time(b)}" for a, b in r.get("remove", [])]
    if trimmed:
        lines.append(_("Trimmed      : {parts}").format(parts=", ".join(trimmed)))
    if r["speech"] - r["floor"] < 15:
        lines.append(_("WARNING: the background noise is close to the speech level; cuts may be wrong."))
    if info["variable_rate"]:
        lines.append(_("WARNING: the video seems to have a variable frame rate (phone or screen "
                       "recording); cut points may drift in Resolve."))
    if detailed and r["candidates"]:
        lines.append("\n" + _("Candidates (time in the original video; [x] = cut):"))
        for c in r["candidates"][:15]:
            lines.append(f"  [{'x' if c['selected'] else ' '}] {format_time(c['start'])}  "
                         f"{c['end'] - c['start']:.2f} {_('s')}  {kind_name(c)}, "
                         + _("confidence {level}").format(level=confidence_name(c["confidence"]))
                         + (f"  | {c['context']}" if c["context"] else ""))
        if len(r["candidates"]) > 15:
            lines.append("  " + _("... and {n} more candidates").format(n=len(r["candidates"]) - 15))
    lines.append("\n" + _("Timeline written: {path}").format(path=r["output"]))
    lines.append(two_microphones_note())
    if r.get("subtitles"):
        lines.append(_("Subtitles for this timeline: {path}").format(path=r["subtitles"]))
    if r.get("titles"):
        lines.append(_("Name titles kept on the timeline: {n}").format(n=r["titles"]))
    if r.get("close_up"):
        lines.append(_("Framing     : changes {changes} times, at speaker changes and about every {every:.0f} s "
                       "in long answers; closer framing ({percent:.0f}%) {share:.0f}% of the time").format(
            changes=r["changes"], every=r["every"], percent=r["close_up"] * 100, share=r["close_share"] * 100))
        lines.append(_("In Resolve, keep “Use sizing information” ticked when importing, or the "
                       "closer framings are lost."))
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
    p.add_argument("--no-noises", action="store_true",
                   help="leave coughs and other non-speech sounds alone")
    p.add_argument("--min-hesitation", type=float, default=0.30,
                   help="hesitations shorter than this are left alone (seconds, default 0.30)")
    p.add_argument("--word-ends", action="store_true",
                   help="also cut stretches glued to the end of a word (high risk of wrong cuts)")
    p.add_argument("--fillers", default="",
                   help='filler words to cut, comma separated (e.g. "you know, like"); '
                        "needs a transcript and cuts every match")
    p.add_argument("--from", dest="keep_from", default=None,
                   help="trim everything before this time (e.g. 0:07.5)")
    p.add_argument("--to", dest="keep_to", default=None, help="trim everything after this time (e.g. 51:19)")
    p.add_argument("--remove", default="",
                   help='ranges to drop from the middle, comma separated (e.g. "50:46-51:03")')
    p.add_argument("--review", action="store_true",
                   help="also write a timeline with only the cut hesitations, for checking (<name>_fillers.fcpxml)")
    p.add_argument("--close-up", type=float, default=None,
                   help="move closer to whoever gives a long answer; how close, in percent (e.g. 125). "
                        "Needs a transcript")
    p.add_argument("--places", default="",
                   help='where the speakers sit, in the order they first speak (e.g. "left, right")')
    p.add_argument("--speakers", type=int, default=2, help="number of speakers when --places is not given")
    p.add_argument("--every", type=float, default=CHANGE_EVERY,
                   help="seconds between framing changes inside a long answer (default 30)")
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
            language=saved["language"] if saved else "tr", noises=not a.no_noises,
            keep_from=parse_time(a.keep_from) if a.keep_from else None,
            keep_to=parse_time(a.keep_to) if a.keep_to else None, remove=parse_ranges(a.remove))
        for c in state["candidates"]:  # nobody to ask on the command line: requested words are cut
            if c["kind"] == "word":
                c["selected"] = True
        places = [p.strip().lower() for p in a.places.split(",") if p.strip()]
        result = apply(state, output=a.output, review=a.review, close_up=a.close_up / 100 if a.close_up else None,
                       places=places, speakers=a.speakers, every=a.every)
    except DavarError as e:
        sys.exit(_("ERROR: {message}").format(message=e))
    if saved:
        print(_("Transcript found: hesitations were checked against it."))
    print(report(result))


if __name__ == "__main__":
    main()
