"""Shared helpers: errors, running ffmpeg/ffprobe, reading video metadata."""

import json
import math
import re
import subprocess
import sys
from fractions import Fraction

from i18n import _

VERSION = "0.3.0"  # keep in step with the top entry of CHANGELOG.md
SAMPLE_RATE = 16000  # audio is resampled to this rate for analysis
WINDOW = 0.01  # audio level is measured in 10 ms slices
STANDARD_FPS = [
    Fraction(24000, 1001), Fraction(24), Fraction(25), Fraction(30000, 1001),
    Fraction(30), Fraction(50), Fraction(60000, 1001), Fraction(60),
]
# keep a black console window from flashing when launched from the GUI
NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


class DavarError(Exception):
    """An error with a message meant to be shown to the user."""


def run(command):
    """Run a command and return its stdout; raise DavarError with its stderr on failure."""
    try:
        result = subprocess.run(command, capture_output=True, creationflags=NO_WINDOW)
    except FileNotFoundError:
        raise DavarError(_("{tool} was not found. ffmpeg must be installed and on PATH.").format(tool=command[0]))
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", "replace").strip()
        raise DavarError(_("{tool} failed:").format(tool=command[0]) + "\n" + message)
    return result.stdout


def video_info(path):
    """Read frame rate, size, duration and audio layout with ffprobe."""
    raw = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)])
    data = json.loads(raw)
    video = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
    audio = next((s for s in data["streams"] if s["codec_type"] == "audio"), None)
    if video is None:
        raise DavarError(_("the file has no video stream."))
    if audio is None:
        raise DavarError(_("the file has no audio, so silence cannot be analysed."))

    average = Fraction(video.get("avg_frame_rate") or "0/1") if not video.get(
        "avg_frame_rate", "0/0").endswith("/0") else Fraction(0)
    if average == 0:
        average = Fraction(video["r_frame_rate"])
    # snap to a standard rate such as 29.97 when very close to it
    fps = min(STANDARD_FPS, key=lambda f: abs(f - average))
    variable = abs(fps - average) / average > 0.005
    if variable:
        fps = average.limit_denominator(1001)

    duration = float(video.get("duration") or data["format"]["duration"])
    return {
        "fps": fps,
        "variable_rate": variable,
        "width": int(video["width"]),
        "height": int(video["height"]),
        "duration": duration,
        "frames": int(math.floor(duration * fps + 1e-6)),
        "audio_channels": int(audio.get("channels", 2)),
        "audio_rate": int(audio.get("sample_rate", 48000)),
        "timecode": start_timecode(data, fps),
    }


def start_timecode(data, fps):
    """The frame the file's own timecode starts on, as cameras write it (Sony: 00:03:34:28);
    0 when there is none. Editors such as Resolve find clips by this timecode."""
    tags = [s.get("tags", {}) for s in data.get("streams", [])] + [data.get("format", {}).get("tags", {})]
    text = next((t.get("timecode") for t in tags if t.get("timecode")), None)
    match = re.fullmatch(r"(\d+):(\d+):(\d+)([:;.,])(\d+)", (text or "").strip())
    if not match:
        return 0
    hours, minutes, seconds, mark, frames = match.groups()
    nominal = round(fps)
    total = ((int(hours) * 60 + int(minutes)) * 60 + int(seconds)) * nominal + int(frames)
    if mark in ";,":  # drop frame: two frame numbers (four at 59.94) skipped each minute but every tenth
        drop = nominal // 15
        minutes_in = int(hours) * 60 + int(minutes)
        total -= drop * (minutes_in - minutes_in // 10)
    return total


def parse_time(text):
    """Turn "13:06", "1:02:03.5" or "786.4" into seconds."""
    text = str(text).strip().replace(",", ".")
    if not re.fullmatch(r"\d+(\.\d+)?(:\d+(\.\d+)?){0,2}", text):
        raise DavarError(_("could not read the time “{text}”. Example: 13:06 or 1:02:03").format(text=text))
    seconds = 0.0
    for part in text.split(":"):
        seconds = seconds * 60 + float(part)
    return seconds


def parse_ranges(text):
    """Turn "50:46-51:03, 12:00-12:30" into [(3046.0, 3063.0), (720.0, 750.0)]."""
    ranges = []
    for piece in re.split(r"[,;\n]", str(text)):
        if not piece.strip():
            continue
        ends = re.split(r"\s*[-–—]\s*", piece.strip())
        if len(ends) != 2:
            raise DavarError(_("could not read the range “{text}”. Example: 50:46-51:03").format(text=piece.strip()))
        start, end = parse_time(ends[0]), parse_time(ends[1])
        if end <= start:
            raise DavarError(_("the range “{text}” ends before it starts.").format(text=piece.strip()))
        ranges.append((start, end))
    return ranges


def format_time(seconds):
    """123.456 -> "2:03.46"; an hour or more as 1:02:03.46."""
    minutes, rest = divmod(round(seconds, 2), 60)  # rounded first, or 299.996 reads 4:60.00
    if minutes >= 60:
        return f"{int(minutes // 60)}:{int(minutes % 60):02d}:{rest:05.2f}"
    return f"{int(minutes)}:{rest:05.2f}"


def two_microphones_note():
    """The line that goes with every timeline written: how two microphones recorded on the
    two channels of the video come into Resolve on tracks of their own."""
    return _("If two microphones were recorded on the video's two channels, tick “Import multi-channel "
             "audio tracks as linked groups” when importing: each microphone then comes on a track of its own.")
