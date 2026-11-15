"""Shared helpers: errors, running ffmpeg/ffprobe, reading video metadata."""

import json
import math
import subprocess
import sys
from fractions import Fraction

from i18n import _

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
    }


def format_time(seconds):
    """123.456 -> "2:03.46"."""
    minutes, rest = divmod(seconds, 60)
    return f"{int(minutes)}:{rest:05.2f}"
