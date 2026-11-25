"""davar social clips - cuts a time range of a landscape video into a vertical (9:16)
Reels / Shorts video.

Puts the speaker's frame over a blurred background, with a short kicker and a
headline on top, optional subtitles (from the speech) and an intro cover. When the
video has a Rough Cut timeline, its cuts are applied inside the range: the silences,
hesitations and trimmed parts are left out of the clip, and the subtitles follow.

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


def make_clip(video, start, end, output=None, kicker="", headline=(), horizontal=0.5,
              subtitles=False, cover=False, language="tr", words=None, parts=None, progress=None):
    """Cut the range as a vertical video; returns information about the output file.

    `horizontal`: where the speaker's frame is taken from, 0 (left) to 1 (right).
    `words`: the transcript's list of (text, start, end); when given, the range is
    not transcribed again for the subtitles.
    `parts`: the parts of the Rough Cut timeline (frames of the video); when given, only
    what they keep of the range goes into the clip.
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
    return {"output": output, "duration": total, "start": start, "end": end,
            "subtitle_lines": subtitle_lines, "subtitles": subtitles, "cover": cover,
            "cuts": len(pieces) - 1 + (pieces[0][0] > 0) + (pieces[-1][1] < round(span * fps)) if pieces else 0,
            "shorter": span - duration}


def report(r):
    lines = [
        _("Range    : {start} - {end}").format(start=format_time(r["start"]), end=format_time(r["end"])),
        _("Video    : {width}x{height}, {seconds:.1f} s").format(width=WIDTH, height=HEIGHT, seconds=r["duration"])
        + ("  " + _("(including the intro cover)") if r["cover"] else ""),
    ]
    if r.get("cuts"):
        lines.append(_("Cuts     : the Rough Cut's {n} cuts applied, {seconds:.1f} s shorter").format(
            n=r["cuts"], seconds=r["shorter"]))
    if r["subtitles"]:
        lines.append(_("Subtitles: {n} lines (automatic; read them before publishing)").format(n=r["subtitle_lines"])
                     if r["subtitle_lines"] else _("Subtitles: no speech found, none added"))
    lines.append("\n" + _("Video written: {path}").format(path=r["output"]))
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
    p.add_argument("--subtitles", action="store_true", help="add automatic subtitles from the speech")
    p.add_argument("--cover", action="store_true", help="add a 2.5 second intro cover")
    p.add_argument("--language", default="tr", help="spoken language code (default tr)")
    p.add_argument("--output", type=Path, default=None,
                   help="output file (default: <name>_vertical.mp4 next to the video)")
    a = p.parse_args()
    try:
        result = make_clip(a.video, a.start, a.end, output=a.output, kicker=a.kicker,
                           headline=a.headline, horizontal=a.horizontal, subtitles=a.subtitles,
                           cover=a.cover, language=a.language)
    except DavarError as e:
        sys.exit(_("ERROR: {message}").format(message=e))
    print(report(result))


if __name__ == "__main__":
    main()
