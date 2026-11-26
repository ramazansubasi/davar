"""davar social clips - cuts a time range of a landscape video into a vertical (9:16)
Reels / Shorts video.

Puts the speaker's frame over a blurred background, with a short kicker and a
headline on top, optional subtitles (from the speech) and an intro cover. When the
video has a Rough Cut timeline, its cuts are applied inside the range: the silences,
hesitations and trimmed parts are left out of the clip, and the subtitles follow.

The social clip candidates of Content Analysis can be made one after the other
(make_clips); their ranges are first fitted to whole sentences of the transcript.

The frame can follow whoever speaks, for two people filmed together in one wide shot:
who speaks when is known from the transcript (and the two microphones, when each has
one), and where each of them sits from the picture, since whoever speaks moves more
than whoever listens. The frame cuts to the speaker at each change of turn.

    python clips.py "video.mp4" 13:06 13:56 --headline "TRAFFIC IN TUZLA" --subtitles
"""

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

import roughcut
import speakers
import transcript
from common import NO_WINDOW, DavarError, format_time, parse_time, run, video_info
from i18n import _
from roughcut import is_filler_sound

WIDTH, HEIGHT = 1080, 1920
FRAME_Y, FRAME_HEIGHT = 340, 1440  # vertical place and height of the speaker's frame
COVER_SECONDS = 2.5
JOIN_FADE = 0.008  # seconds of fade at each join of the pieces, so a cut in a sound does not click
ACCENT = (227, 6, 19)  # colour of the kicker
COVER_BACKGROUND = (92, 6, 16)
COVER_KICKER = (255, 120, 128)
FONTS = [
    "C:/Windows/Fonts/arialbd.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
]


def _font(size):
    from PIL import ImageFont
    for path in FONTS:
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def _centred(draw, y, text, size, colour, max_width=WIDTH - 80):
    """Write text centred horizontally, shrinking it to fit. Returns the y of its bottom edge."""
    while True:
        font = _font(size)
        left, _top, right, _bottom = draw.textbbox((0, 0), text, font=font)
        if right - left <= max_width or size <= 20:
            break
        size -= 2
    draw.text(((WIDTH - (right - left)) / 2 - left, y), text, font=font, fill=colour)
    return y + int(size * 1.22)


def _text_layer(path, kicker, headline):
    """The transparent layer drawn over the video: kicker and headline."""
    from PIL import Image, ImageDraw
    image = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    y = 96
    if kicker:
        y = _centred(draw, y, kicker, 34, ACCENT + (255,)) + 18
    for line in headline[:2]:
        y = _centred(draw, y, line, 70, (255, 255, 255, 255))
    image.save(path)


def _cover(path, kicker, headline):
    """The announcement cover placed before the video."""
    from PIL import Image, ImageDraw
    image = Image.new("RGB", (WIDTH, HEIGHT), COVER_BACKGROUND)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, WIDTH, 14), fill=ACCENT)
    rows = [line for line in headline[:2] if line]
    y = HEIGHT // 2 - (len(rows) * 130 + (114 if kicker else 0)) // 2
    if kicker:
        y = _centred(draw, y, kicker, 44, COVER_KICKER) + 60
    draw.rectangle((WIDTH // 2 - 60, y - 34, WIDTH // 2 + 60, y - 28), fill=ACCENT)
    for line in rows:
        y = _centred(draw, y, line, 104, (255, 255, 255))
    image.save(path)


def _ass_time(t):
    hours, rest = divmod(max(t, 0), 3600)
    minutes, seconds = divmod(rest, 60)
    return f"{int(hours)}:{int(minutes):02d}:{seconds:05.2f}"


def _write_subtitles(path, words):
    """Split (text, start, end) words into short lines and write an ASS subtitle file."""
    rows, current = [], []
    for text, start, end in words:
        if current:
            length = sum(len(w[0]) + 1 for w in current) + len(text)
            if (length > 36 or start - current[-1][2] > 0.6 or end - current[0][1] > 3.5
                    or current[-1][0][-1:] in ".?!"):
                rows.append(current)
                current = []
        current.append((text, start, end))
    if current:
        rows.append(current)

    out = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {WIDTH}", f"PlayResY: {HEIGHT}",
        "WrapStyle: 0", "", "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Sub,Arial,54,&H00FFFFFF,&H00FFFFFF,&H00100C0C,&H00100C0C,-1,0,0,0,100,100,"
        "0,0,3,14,0,2,80,80,470,1",
        "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for i, row in enumerate(rows):
        start, end = row[0][1], row[-1][2]
        if i + 1 < len(rows):  # do not run into the next line
            end = min(max(end, start + 0.8), rows[i + 1][0][1])
        text = " ".join(w[0] for w in row).replace("{", "(").replace("}", ")")
        out.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Sub,,0,0,0,,{text}")
    Path(path).write_text("\n".join(out) + "\n", encoding="utf-8")
    return len(rows)


def _transcribe_range(video, start, duration, language):
    """Transcribe the speech in the chosen range with word timing."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise DavarError(_("subtitles need faster-whisper. Install it with: pip install faster-whisper"))
    raw = run(["ffmpeg", "-v", "error", "-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", str(video),
               "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"])
    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    model = WhisperModel("small", device="cpu", compute_type="int8")
    segments, _info = model.transcribe(audio, language=language, word_timestamps=True,
                                       vad_filter=True, beam_size=3)
    words = []
    for segment in segments:
        for w in segment.words:
            piece = w.word.strip()
            if not piece:
                continue
            # join split pieces such as "10" + ".000" or "Tuzla" + "'da"
            if words and not piece[0].isalnum():
                words[-1] = (words[-1][0] + piece, words[-1][1], w.end)
            else:
                words.append((piece, w.start, w.end))
    return words


# An AI picks a clip's range from transcript lines of about 20 seconds, so it seldom starts
# or ends with a sentence. It is moved to the sentences around it.
SENTENCE_BACK = 4.0  # seconds a start may move back to the beginning of its sentence
SENTENCE_AHEAD = 4.0  # or ahead to the beginning of the next one
SENTENCE_LATER = 6.0  # seconds an end may move on to the end of its sentence
SENTENCE_EARLIER = 6.0  # or back to the end of the sentence before
ENDS = ".?!…"


def _sentence_end(text):
    return str(text).rstrip("\"'”’»)]").endswith(tuple(ENDS))


def fit_to_sentences(words, start, end):
    """(start, end) in seconds moved to whole sentences of the transcript `words`
    ((text, start, end), in order): the start to the beginning of a sentence and the end to
    the end of one, each to the nearer one within reach; a time with none near stays."""
    words = list(words or ())
    if not words:
        return start, end
    begins = [w[1] for n, w in enumerate(words) if n == 0 or _sentence_end(words[n - 1][0])]
    finishes = [w[2] for w in words if _sentence_end(w[0])]
    back = [t for t in begins if start - SENTENCE_BACK <= t <= start + 0.05]
    ahead = [t for t in begins if start < t <= start + SENTENCE_AHEAD]
    new_start = max(back) if back else min(ahead) if ahead else start
    later = [t for t in finishes if end - 0.05 <= t <= end + SENTENCE_LATER]
    earlier = [t for t in finishes if end - SENTENCE_EARLIER <= t < end - 0.05]
    new_end = min(later) if later else max(earlier) if earlier else end
    if new_end - new_start < 5:  # a clip is not shortened to a few words
        return start, end
    return new_start, new_end


def clip_name(n, headline):
    """The file name of the n-th clip: "Clip 1 - <headline>.mp4", without characters a file name cannot hold."""
    words = re.sub(r'[\\/:*?"<>|“”‘’«»\n\r\t]', " ", str(headline)).split()
    text = ""
    for word in words:  # whole words, up to about 60 characters
        if text and len(text) + 1 + len(word) > 60:
            break
        text = f"{text} {word}".strip()
    text = text[:60].strip(" .")
    return _("Clip {n}").format(n=n) + (f" - {text}" if text else "") + ".mp4"


def make_clips(video, candidates, folder=None, kicker="", horizontal=0.5, subtitles=False, cover=False,
               language="tr", words=None, parts=None, follow=False, progress=None):
    """Make each of `candidates` (dicts with start, end, lines and headline, as
    content.clip_candidates gives them) with make_clip, one after the other, into
    `folder` (next to the video by default) as "Clip 1 - <headline>.mp4" and so on.
    Returns the results of make_clip, each with its "n" and "headline"."""
    video = Path(video)
    target = Path(folder) if folder else video.parent
    turns = None
    if follow:  # who speaks when is found once for all the clips
        if not words:
            raise DavarError(_("run Transcribe first; following the speaker needs the transcript."))
        if progress:
            progress(0, _("Listening for who speaks when"))
        turns = speakers.who_speaks(video, words, 2, language)
    made = []
    for n, clip in enumerate(candidates, 1):
        def step(percent, text, n=n):
            if progress:
                progress((len(made) + percent / 100) / len(candidates) * 100,
                         _("Clip {n} of {count}").format(n=n, count=len(candidates)) + ": " + text)
        result = make_clip(video, clip["start"], clip["end"], output=target / clip_name(clip.get("n", n), clip["headline"]),
                           kicker=kicker, headline=clip.get("lines") or [clip["headline"]], horizontal=horizontal,
                           subtitles=subtitles, cover=cover, language=language, words=words, parts=parts,
                           follow=follow, turns=turns, progress=step)
        made.append({**result, "n": clip.get("n", n), "headline": clip["headline"]})
    return made


def kept_in_range(parts, fps, start, end):
    """The pieces of the range [start, end] (seconds of the video) that the Rough Cut keeps,
    in frames counted from the start of the range. Pieces shorter than three frames are dropped."""
    first, last = round(start * fps), round(end * fps)
    pieces = []
    for a, b in parts:
        a, b = max(a, first), min(b, last)
        if b - a >= 3:
            pieces.append((a - first, b - first))
    return pieces


def snap_range(video, start, end, length):
    """Move the start and the end of a range to the nearest pause, so that no word is clipped:
    (start, end, whether either moved). The range is left as it is when its audio cannot be read."""
    first, last = max(start - 1.0, 0.0), min(end + 1.0, length)
    try:
        _samples, db = roughcut.audio_levels(video, first, last - first)
    except DavarError:
        return start, end, False
    threshold = roughcut.auto_threshold(db)[0]
    new_start = first + roughcut.snap_to_pause(db, start - first, threshold)
    new_end = first + roughcut.snap_to_pause(db, end - first, threshold)
    if new_end - new_start < 1:
        return start, end, False
    return new_start, new_end, abs(new_start - start) > 0.02 or abs(new_end - end) > 0.02


# Following the speaker. Whoever speaks moves more than whoever listens (the mouth, the head,
# the hands), so the place of each speaker is where the picture moves more during their turns
# than during the other's.
MOTION_RATE, MOTION_WIDTH = 5, 192  # frames per second and width in pixels the picture is watched at
WATCHED = 180.0  # seconds of the video watched around a clip
WATCHED_MORE = 4  # further stretches of 60 s across the video, when that is not enough
SURE_PLACE = 1.2  # how far the place of a speaker must stand out of the rest of the picture
FEWEST_FRAMES = 40  # watched frames of each speaker's turns
CUT_BEFORE = 0.25  # seconds before a turn begins that the frame cuts to the new speaker
SHORTEST_SHOT = 1.5  # seconds; a shot at the start or end of a clip shorter than this is not made


def watch_motion(video, start, duration, info):
    """How much the picture moves in each column, between frames watched MOTION_RATE times a
    second: (times in seconds of the video, array of shape (frames, MOTION_WIDTH))."""
    height = max(round(info["height"] * MOTION_WIDTH / info["width"] / 2) * 2, 2)
    raw = run(["ffmpeg", "-v", "error", "-ss", f"{max(start, 0):.3f}", "-t", f"{duration:.3f}", "-i", str(video),
               "-vf", f"fps={MOTION_RATE},scale={MOTION_WIDTH}:{height},format=gray", "-f", "rawvideo", "-"])
    frames = np.frombuffer(raw, np.uint8)[:len(raw) // (MOTION_WIDTH * height) * MOTION_WIDTH * height]
    frames = frames.reshape(-1, height, MOTION_WIDTH).astype(np.int16)
    if len(frames) < 2:
        return np.zeros(0), np.zeros((0, MOTION_WIDTH))
    columns = np.abs(frames[1:] - frames[:-1]).mean(1)
    times = max(start, 0) + (np.arange(1, len(frames)) + 0.5) / MOTION_RATE
    return times, columns


def speaker_places(turns, times, columns):
    """Where the two speakers of `turns` ((start, end, speaker), speakers 0 and 1) sit, from the
    motion of the picture (see watch_motion): {speaker: centre as a share of the width, 0 left
    to 1 right}, or None when the picture does not tell."""
    who = np.full(len(times), -1)
    for start, end, speaker in turns:  # the first half second of a turn may still show the other
        who[(times >= start + 0.5) & (times < end)] = speaker
    if len(times) == 0 or min((who == 0).sum(), (who == 1).sum()) < FEWEST_FRAMES:
        return None
    contrast = columns[who == 0].mean(0) - columns[who == 1].mean(0)
    smooth = max(len(contrast) // 12, 1)
    contrast = np.convolve(contrast, np.ones(smooth) / smooth, "same")
    spread = contrast.std()
    if spread == 0 or min(contrast.max(), -contrast.min()) < SURE_PLACE * spread:
        return None
    width = len(contrast)
    places = {0: (contrast.argmax() + 0.5) / width, 1: (contrast.argmin() + 0.5) / width}
    if abs(places[0] - places[1]) < 0.25:  # two people side by side are further apart
        return None
    return places


def find_places(video, turns, start, end, info):
    """speaker_places from the picture around the range [start, end] of the video, and when that is
    not enough, from stretches across the whole video too. None when the picture does not tell."""
    length = info["duration"]
    first = max(min((start + end) / 2 - WATCHED / 2, length - WATCHED), 0)
    times, columns = watch_motion(video, first, min(WATCHED, length), info)
    places = speaker_places(turns, times, columns)
    if places is None and length > WATCHED * 2:
        more = [watch_motion(video, at, 60.0, info)
                for at in np.linspace(0, length - 60, WATCHED_MORE + 2)[1:-1]]
        places = speaker_places(turns, np.concatenate([times] + [m[0] for m in more]),
                                np.concatenate([columns] + [m[1] for m in more]))
    return places


def clip_moment(moment, start, pieces, fps):
    """A moment of the video (seconds) on the clip that starts at `start`; with the Rough Cut's
    `pieces` (see kept_in_range), a moment that was cut away goes to the start of the next piece."""
    if pieces is None:
        return moment - start
    frame, before = (moment - start) * fps, 0
    for a, b in pieces:
        if frame < b:
            return (before + max(frame - a, 0)) / fps
        before += b - a
    return before / fps


def follow_shots(turns, places, start, end, pieces=None, fps=30.0):
    """The shots of a clip that follows whoever speaks: [(from second of the clip, speaker), ...].
    The frame cuts to the new speaker a moment before each turn; a short shot at either end of the
    clip is not made, and a speaker whose place is not known is not cut to."""
    length = clip_moment(end, start, pieces, fps)
    shots = []
    for turn_start, turn_end, speaker in turns:
        if speaker not in places or turn_end <= start or turn_start >= end:
            continue
        if shots and shots[-1][1] == speaker:
            continue
        at = max(clip_moment(turn_start - CUT_BEFORE, start, pieces, fps), 0.0) if shots else 0.0
        if shots and at - shots[-1][0] < SHORTEST_SHOT:  # the shot before is too short: this one takes its place
            at = shots.pop()[0]
            if shots and shots[-1][1] == speaker:
                continue
        shots.append((at, speaker))
    if len(shots) > 1 and length - shots[-1][0] < SHORTEST_SHOT:
        shots.pop()
    return shots


def crop_x_expression(shots, xs):
    """The x of the crop filter for `shots` (see follow_shots), with `xs` the x of each speaker:
    a number for one shot, otherwise a formula of the time t."""
    text = str(xs[shots[-1][1]])
    for n in range(len(shots) - 2, -1, -1):
        text = f"if(lt(t,{shots[n + 1][0]:.3f}),{xs[shots[n][1]]},{text})"
    return text


def make_clip(video, start, end, output=None, kicker="", headline=(), horizontal=0.5,
              subtitles=False, cover=False, language="tr", words=None, parts=None, follow=False,
              turns=None, progress=None):
    """Cut the range as a vertical video; returns information about the output file.

    `horizontal`: where the speaker's frame is taken from, 0 (left) to 1 (right).
    `words`: the transcript's list of (text, start, end); when given, the range is
    not transcribed again for the subtitles.
    `parts`: the parts of the Rough Cut timeline (frames of the video); when given, only
    what they keep of the range goes into the clip.
    `follow`: the frame follows whichever of two people speaks (see find_places); `horizontal`
    is used when the picture does not tell where they sit. `turns` are who speaks when, as
    speakers.who_speaks gives them; without them they are found from `words`.
    The start and the end move to the nearest pause (see roughcut.snap_to_pause).
    """
    def step(percent, text):
        if progress:
            progress(percent, text)

    try:
        import PIL  # noqa: F401
    except ImportError:
        raise DavarError(_("this needs Pillow. Install it with: pip install pillow"))

    video = Path(video)
    if not video.is_file():
        raise DavarError(_("file not found: {path}").format(path=video))
    start, end = parse_time(start), parse_time(end)
    step(2, _("Reading video information"))
    info = video_info(video)
    end = min(end, info["duration"])
    duration = end - start
    if duration < 1:
        raise DavarError(_("the end time must be at least 1 second after the start."))
    step(3, _("Looking for the pauses at the start and the end"))
    start, end, moved = snap_range(video, start, end, info["duration"])
    duration = end - start
    fps = float(info["fps"])
    pieces = kept_in_range(parts, fps, start, end) if parts else None
    if pieces is not None:
        if not pieces:
            raise DavarError(_("the Rough Cut leaves nothing of this range."))
        if len(pieces) == 1 and pieces[0][1] - pieces[0][0] >= round(duration * fps) - 1:
            pieces = None  # nothing is cut inside the range
    span = duration  # of the source read
    if pieces is not None:
        duration = sum(b - a for a, b in pieces) / fps
        if duration < 1:
            raise DavarError(_("the Rough Cut leaves less than a second of this range."))
    headline = [line.strip() for line in headline if line and line.strip()]
    kicker = kicker.strip()
    if cover and not (headline or kicker):
        raise DavarError(_("the intro cover needs a headline or a kicker."))
    output = Path(output) if output else video.with_name(video.stem + "_vertical.mp4")

    # the speaker's frame: the largest 3:4 piece the source allows
    w, h = info["width"], info["height"]
    crop_w = min(w, int(h * 3 / 4)) // 2 * 2
    crop_h = min(h, int(crop_w * 4 / 3)) // 2 * 2
    crop_x = int((w - crop_w) * min(max(horizontal, 0.0), 1.0))
    crop_y = (h - crop_h) // 2
    shots, places = [], None
    if follow:
        if turns is None:
            if not words:
                raise DavarError(_("run Transcribe first; following the speaker needs the transcript."))
            step(4, _("Listening for who speaks when"))
            turns = speakers.who_speaks(video, words, 2, language)
        step(5, _("Watching where the speakers sit"))
        places = find_places(video, turns, start, end, info)
        if places:
            xs = {who: min(max(int(place * w - crop_w / 2), 0), w - crop_w) for who, place in places.items()}
            shots = follow_shots(turns, places, start, end, pieces, fps)
            if shots:
                crop_x = f"'{crop_x_expression(shots, xs)}'"

    with tempfile.TemporaryDirectory(prefix="davar_") as temp:
        temp = Path(temp)
        inputs = ["-ss", f"{start:.3f}", "-t", f"{span:.3f}", "-i", str(video.resolve())]
        chain, picture, sound = "", "[0:v]", "[0:a]"
        if pieces is not None:  # the Rough Cut's pieces, each trimmed exactly and joined
            n = len(pieces)
            chain += f"[0:v]split={n}" + "".join(f"[vs{i}]" for i in range(n)) + ";"
            chain += f"[0:a]asplit={n}" + "".join(f"[as{i}]" for i in range(n)) + ";"
            for i, (a, b) in enumerate(pieces):
                # a very short fade at both ends of each piece, so the joins do not click
                length = (b - a) / fps
                fade = (f",afade=t=in:d={JOIN_FADE},afade=t=out:st={length - JOIN_FADE:.6f}:d={JOIN_FADE}"
                        if n > 1 and length > 4 * JOIN_FADE else "")
                chain += (f"[vs{i}]trim=start_frame={a}:end_frame={b},setpts=PTS-STARTPTS[vp{i}];"
                          f"[as{i}]atrim=start={a / fps:.6f}:end={b / fps:.6f},asetpts=PTS-STARTPTS{fade}[ap{i}];")
            chain += "".join(f"[vp{i}][ap{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[cv][ca];"
            picture, sound = "[cv]", "[ca]"
        chain += (
            f"{picture}split[a][b];"
            f"[a]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,crop={WIDTH}:{HEIGHT},"
            "boxblur=24:4,eq=brightness=-0.22[bg];"
            f"[b]crop={crop_w}:{crop_h}:{crop_x}:{crop_y},scale={WIDTH}:{FRAME_HEIGHT}[fg];"
            f"[bg][fg]overlay=0:{FRAME_Y}"
        )
        index = 1
        if headline or kicker:
            _text_layer(temp / "text.png", kicker, headline)
            inputs += ["-i", "text.png"]
            chain += f"[k];[k][{index}:v]overlay=0:0"
            index += 1
        subtitle_lines = 0
        if subtitles:
            if words and pieces is not None:  # times on the clip, as the Rough Cut leaves them
                shifted = [(x[0], x[1] - start, x[2] - start) for x in words if not is_filler_sound(x[0], language)]
                words = [tuple(x[:3]) for x in roughcut.timeline_words(shifted, pieces, fps)]
            elif words:  # move times of the whole video into this range
                words = [(x[0], x[1] - start, x[2] - start) for x in words
                         if x[1] >= start - 0.05 and x[2] <= end + 0.05
                         and not is_filler_sound(x[0], language)]
            elif pieces is None:
                step(5, _("Transcribing the speech (the model is downloaded on first use)"))
                words = _transcribe_range(video, start, duration, language)
            else:
                raise DavarError(_("run Transcribe first; subtitles for a clip with the Rough Cut's cuts "
                                   "are made from the transcript."))
            if words:
                subtitle_lines = _write_subtitles(temp / "sub.ass", words)
                chain += ",subtitles=sub.ass"
        chain += ",fps=30,format=yuv420p,setsar=1[v0];"
        audio = (f"{sound}loudnorm=I=-14:TP=-1.5:LRA=11,afade=t=in:d=0.05,"
                 f"afade=t=out:st={duration - 0.15:.3f}:d=0.1")
        total = duration
        if cover:
            _cover(temp / "cover.png", kicker, headline)
            inputs += ["-loop", "1", "-framerate", "30", "-t", str(COVER_SECONDS), "-i", "cover.png"]
            chain += (f"[{index}:v]fps=30,format=yuv420p,setsar=1[v1];"
                      "[v1][v0]concat=n=2:v=1:a=0[v];")
            audio += f",adelay={int(COVER_SECONDS * 1000)}:all=1"
            total += COVER_SECONDS
        else:
            chain += "[v0]null[v];"
        chain += audio + "[au]"
        (temp / "filter.txt").write_text(chain, encoding="utf-8")

        command = ["ffmpeg", "-v", "error", "-y", *inputs, "-/filter_complex", "filter.txt",
                   "-map", "[v]", "-map", "[au]", "-c:v", "libx264", "-preset", "medium",
                   "-crf", "20", "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
                   "-movflags", "+faststart", "-progress", "pipe:1", "-nostats",
                   str(output.resolve())]
        base = 30 if subtitles else 5
        step(base, _("Rendering the video"))
        try:
            proc = subprocess.Popen(command, cwd=temp, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, creationflags=NO_WINDOW)
        except FileNotFoundError:
            raise DavarError(_("{tool} was not found. ffmpeg must be installed and on PATH.").format(tool="ffmpeg"))
        for line in proc.stdout:
            match = re.match(rb"out_time_us=(\d+)", line)
            if match:
                done = min(int(match.group(1)) / 1e6 / total, 1.0)
                step(base + (99 - base) * done, _("Rendering the video"))
        log = proc.stderr.read().decode("utf-8", "replace").strip()
        if proc.wait() != 0:
            raise DavarError(_("ffmpeg could not write the video:") + "\n" + log[-600:])

    step(100, _("Finished"))
    return {"output": output, "duration": total, "start": start, "end": end, "moved": moved,
            "subtitle_lines": subtitle_lines, "subtitles": subtitles, "cover": cover,
            "follow": follow, "shots": len(shots), "places": places,
            "cuts": len(pieces) - 1 + (pieces[0][0] > 0) + (pieces[-1][1] < round(span * fps)) if pieces else 0,
            "shorter": span - duration}


def report(r):
    lines = [
        _("Range    : {start} - {end}").format(start=format_time(r["start"]), end=format_time(r["end"]))
        + ("  " + _("(moved to the nearest pauses)") if r.get("moved") else ""),
        _("Video    : {width}x{height}, {seconds:.1f} s").format(width=WIDTH, height=HEIGHT, seconds=r["duration"])
        + ("  " + _("(including the intro cover)") if r["cover"] else ""),
    ]
    if r.get("follow"):
        lines.append(_("Framing  : follows whoever speaks, {n} shots").format(n=r["shots"]) if r.get("shots")
                     else _("Framing  : the picture did not tell where the speakers sit; the fixed framing was used"))
    if r.get("cuts"):
        lines.append(_("Cuts     : the Rough Cut's {n} cuts applied, {seconds:.1f} s shorter").format(
            n=r["cuts"], seconds=r["shorter"]))
    if r["subtitles"]:
        lines.append(_("Subtitles: {n} lines (automatic; read them before publishing)").format(n=r["subtitle_lines"])
                     if r["subtitle_lines"] else _("Subtitles: no speech found, none added"))
    lines.append("\n" + _("Video written: {path}").format(path=r["output"]))
    return "\n".join(lines)


def report_many(results):
    """What make_clips made, as readable text."""
    lines = [_("{n} clips made:").format(n=len(results))]
    for r in results:
        lines.append("  " + _("{n}. {start} - {end}, {seconds:.0f} s: {path}").format(
            n=r["n"], start=format_time(r["start"]), end=format_time(r["end"]), seconds=r["duration"],
            path=r["output"].name))
    if any(r["subtitles"] for r in results):
        lines.append(_("The subtitles are automatic; read them before publishing."))
    lines.append(_("Folder: {path}").format(path=results[0]["output"].parent) if results else "")
    return "\n".join(lines)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Cut a vertical Reels / Shorts clip from a video.")
    p.add_argument("video", type=Path)
    p.add_argument("start", help="start time (e.g. 13:06)")
    p.add_argument("end", help="end time (e.g. 13:56)")
    p.add_argument("--kicker", default="", help="short line above the headline")
    p.add_argument("--headline", action="append", default=[],
                   help="headline line (give twice for two lines)")
    p.add_argument("--horizontal", type=float, default=0.5,
                   help="where the frame is taken from: 0 left, 0.5 centre, 1 right (default 0.5)")
    p.add_argument("--follow", action="store_true",
                   help="follow whichever of two people speaks (needs the transcript of Transcribe)")
    p.add_argument("--subtitles", action="store_true", help="add automatic subtitles from the speech")
    p.add_argument("--cover", action="store_true", help="add a 2.5 second intro cover")
    p.add_argument("--language", default="tr", help="spoken language code (default tr)")
    p.add_argument("--output", type=Path, default=None,
                   help="output file (default: <name>_vertical.mp4 next to the video)")
    a = p.parse_args()
    try:
        saved = transcript.load(a.video) if a.follow or a.subtitles else None
        result = make_clip(a.video, a.start, a.end, output=a.output, kicker=a.kicker,
                           headline=a.headline, horizontal=a.horizontal, subtitles=a.subtitles,
                           cover=a.cover, language=a.language, follow=a.follow,
                           words=saved["words"] if saved else None)
    except DavarError as e:
        sys.exit(_("ERROR: {message}").format(message=e))
    print(report(result))


if __name__ == "__main__":
    main()
