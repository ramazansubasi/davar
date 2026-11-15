"""davar audio - puts separately recorded audio in its place in the video and sets the loudness.

It finds by itself where a separate recording belongs (by comparing the rhythm of
the speech in both recordings), matches its level to the video's own audio and
replaces the video's audio there. Then the whole track is brought to YouTube loudness.

The picture is not re-encoded; the result is written as <video>_audio.mp4.

    python audio.py "video.mp4" --audio "lavalier.wav"
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from common import NO_WINDOW, DavarError, format_time, run, video_info
from i18n import _

RATE = 8000  # audio is resampled to this rate for comparison
ENVELOPE_STEP = 0.01  # the rhythm of speech is measured in 10 ms steps
MIN_MARGIN = 0.08  # the best position must lead the second best by at least this much
MIN_WAVEFORM = 0.25  # ... or the waveform must be at least this similar
TARGET_PEAK = -1.5  # dBTP


def read_audio(path, rate=RATE):
    raw = run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(rate), "-f", "s16le", "-"])
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def envelope(x, rate=RATE):
    """The rhythm of the speech: level of 10 ms slices with slow changes removed."""
    step = int(rate * ENVELOPE_STEP)
    n = len(x) // step
    if n < 20:
        return np.zeros(0, np.float32)
    rms = np.sqrt(np.mean(x[: n * step].reshape(n, step) ** 2, axis=1))
    db = 20 * np.log10(rms + 1e-4)
    kernel = np.ones(101, np.float32) / 101  # subtract the one-second average
    return (db - np.convolve(db, kernel, mode="same")).astype(np.float32)


def _correlate(long, short):
    """c[k] = sum(long[t + k] * short[t]); negative shifts sit at the end of the array."""
    n = 1 << int(np.ceil(np.log2(len(long) + len(short))))
    return np.fft.irfft(np.fft.rfft(long, n) * np.conj(np.fft.rfft(short, n)), n)


def _similarity(a, b):
    if len(a) < 20:
        return 0.0
    a, b = a - a.mean(), b - b.mean()
    norm = float(np.sqrt((a * a).sum() * (b * b).sum()))
    return float((a * b).sum() / norm) if norm > 0 else 0.0


def _fine_offset(video, clip, coarse, rate, centre, radius=0.08, window=6.0):
    """Refine the offset to sample accuracy using the part of the clip around `centre` seconds.

    Returns (offset, waveform similarity). The similarity is close to 1 when both
    recordings come from the same microphone; low values are normal across microphones.
    """
    half = int(window / 2 * rate)
    c0 = int(centre * rate) - half
    c1 = c0 + 2 * half
    r = int(radius * rate)
    v0 = c0 + int(round(coarse * rate)) - r
    v1 = c1 + int(round(coarse * rate)) + r
    if c0 < 0 or c1 > len(clip) or v0 < 0 or v1 > len(video):
        return None
    piece, target = clip[c0:c1], video[v0:v1]
    if np.abs(piece).max() < 0.005:
        return None
    c = np.abs(_correlate(target, piece)[: 2 * r + 1])
    i = int(np.argmax(c))
    matched = target[i:i + len(piece)]
    norm = float(np.sqrt((piece ** 2).sum() * (matched ** 2).sum())) + 1e-9
    return coarse + (i - r) / rate, float(c[i] / norm)


def _coarse_positions(env_video, env_clip, count=6):
    """The distinct positions where the rhythms agree best, as (envelope step, similarity)."""
    min_overlap = min(len(env_clip), len(env_video), 300) // 2
    pad = len(env_clip) - min_overlap
    wide = np.concatenate((np.zeros(pad, np.float32), env_video, np.zeros(pad, np.float32)))
    size = len(wide) - len(env_clip) + 1
    c = _correlate(wide, env_clip)[:size]
    energy = np.convolve(wide ** 2, np.ones(len(env_clip), np.float32), mode="valid")[:size]
    score = c / np.sqrt(np.maximum(energy, 0.05 * np.median(energy) + 1e-9) * float((env_clip ** 2).sum()) + 1e-9)
    chosen = []
    for i in np.argsort(score)[::-1][:4000]:
        if all(abs(int(i) - j) > 100 for j in chosen):  # peaks at least one second apart
            chosen.append(int(i))
            if len(chosen) == count:
                break
    result = []
    for i in chosen:
        k = i - pad
        a0, a1 = max(k, 0), min(k + len(env_clip), len(env_video))
        result.append((k, _similarity(env_video[a0:a1], env_clip[a0 - k:a1 - k])))
    return sorted(result, key=lambda x: -x[1])


def find_position(video, clip, rate=RATE):
    """Find where the clip belongs in the video.

    Returns:
      offset      the second of the video where the clip starts (negative if it starts earlier)
      similarity  rhythm similarity at that position (-1..1)
      margin      lead of the best position over the second best; near zero for unrelated audio
      waveform    waveform similarity (close to 1 when the same recording is inside the video)
      speed       clock difference between the two recorders; the factor to multiply the clip's length by
    """
    env_video, env_clip = envelope(video, rate), envelope(clip, rate)
    if len(env_video) < 100 or len(env_clip) < 100:
        raise DavarError(_("matching audio needs at least one second of recording."))
    positions = _coarse_positions(env_video, env_clip)
    k, similarity = positions[0]
    margin = similarity - positions[1][1] if len(positions) > 1 else similarity
    coarse = k * ENVELOPE_STEP

    # refine to sample accuracy; on long recordings measure near both ends to get the clock difference
    first, last = max(-coarse, 0.0), min(len(clip) / rate, len(video) / rate - coarse)
    overlap = last - first
    points = [first + overlap * f for f in ((0.15, 0.5, 0.85) if overlap > 20 else (0.5,))]
    measured = [(t, _fine_offset(video, clip, coarse, rate, t, 0.3 if overlap > 120 else 0.08)) for t in points]
    measured = [(t, m[0], m[1]) for t, m in measured if m is not None]
    offset, speed, waveform = coarse, 1.0, 0.0
    if measured:
        offset = float(np.median([o for _t, o, _w in measured]))
        waveform = float(np.median([w for _t, _o, w in measured]))
        if overlap > 120 and len(measured) >= 2:
            (t0, o0, _w0), (t1, o1, _w1) = measured[0], measured[-1]
            slope = (o1 - o0) / (t1 - t0)
            if abs(slope) * overlap > 0.03 and abs(slope) < 0.002:  # drifts by more than 30 ms
                speed = 1.0 + slope
                offset = o0 - slope * t0
    return {"offset": offset, "similarity": similarity, "margin": margin, "waveform": waveform,
            "speed": speed, "duration": len(clip) / rate}


def is_match(position):
    """Can the found position be trusted? Unrelated audio also resembles some spot; what counts
    is that one spot clearly stands out from the rest, or that the waveform agrees."""
    return position["margin"] >= MIN_MARGIN or position["waveform"] >= MIN_WAVEFORM


# --- measuring and applying with ffmpeg ---------------------------------------
def _ffmpeg(command, cwd=None):
    try:
        result = subprocess.run(command, capture_output=True, creationflags=NO_WINDOW, cwd=cwd)
    except FileNotFoundError:
        raise DavarError(_("{tool} was not found. ffmpeg must be installed and on PATH.").format(tool="ffmpeg"))
    log = result.stderr.decode("utf-8", "replace")
    if result.returncode != 0:
        raise DavarError(_("ffmpeg could not process the audio:") + "\n" + log.strip()[-600:])
    return log


def measure_loudness(inputs, chain=None, cwd=None):
    """Measure loudness (LUFS) and true peak; returns the values loudnorm needs for its second pass."""
    command = ["ffmpeg", "-hide_banner", "-nostats", *inputs]
    if chain is None:
        command += ["-vn", "-af", "loudnorm=print_format=json"]
    else:
        Path(cwd, "measure.txt").write_text(chain + ",loudnorm=print_format=json[a]", encoding="utf-8")
        command += ["-/filter_complex", "measure.txt", "-map", "[a]"]
    log = _ffmpeg(command + ["-f", "null", "-"], cwd)
    found = re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", log)
    if not found:
        raise DavarError(_("the loudness could not be measured."))
    return {k: float(v) for k, v in json.loads(found[-1]).items()
            if k.startswith(("input_", "target_")) and v not in ("inf", "-inf")}


def process(video, clips=(), folder=None, normalize=True, target=-14.0, balance=False,
            denoise=False, progress=None):
    """Place the separate recordings, set the loudness and write the new video."""
    def step(percent, text):
        if progress:
            progress(percent, text)

    video = Path(video)
    clips = [Path(c) for c in clips]
    for path in [video, *clips]:
        if not path.is_file():
            raise DavarError(_("file not found: {path}").format(path=path))
    if not (clips or normalize or balance or denoise):
        raise DavarError(_("no operation was selected."))
    step(2, _("Reading video information"))
    info = video_info(video)
    ext = video.suffix.lower() if video.suffix.lower() in (".mp4", ".mov", ".mkv", ".m4v") else ".mp4"
    output = (Path(folder) if folder else video.parent) / (video.stem + "_audio" + ext)

    # 1) find where each separate recording belongs
    found = []
    if clips:
        step(5, _("Reading the video's audio"))
        video_audio = read_audio(video)
        for i, path in enumerate(clips):
            step(8 + 22 * i / len(clips), _("Looking for the place of {name}").format(name=path.name))
            position = find_position(video_audio, read_audio(path))
            position["path"] = path
            position["placed"] = is_match(position)
            found.append(position)
        del video_audio
    placed = [p for p in found if p["placed"]]
    if clips and not placed and not (normalize or balance or denoise):
        raise DavarError(_("none of the separate recordings matched the video; no new video was written."))

    with tempfile.TemporaryDirectory(prefix="davar_audio_") as temp:
        inputs = ["-i", str(video.resolve())]
        for p in placed:
            inputs += ["-i", str(p["path"].resolve())]

        # 2) match the level of each clip to the video's own audio
        if placed:
            step(32, _("Measuring audio levels"))
            original = measure_loudness(["-i", str(video.resolve())])["input_i"]
            for p in placed:
                level = measure_loudness(["-i", str(p["path"].resolve())]).get("input_i", original)
                p["gain"] = float(np.clip(original - level, -20, 20))

        # 3) the mix: the video's audio is muted wherever a clip is placed
        chain = "[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo"
        if placed:
            spans = "+".join(
                f"between(t,{max(p['offset'], 0):.3f},{p['offset'] + p['duration'] * p['speed']:.3f})"
                for p in placed)
            chain += f",volume=0:enable='{spans}'[base];"
            for i, p in enumerate(placed, 1):
                c = f"[{i}:a]aresample=48000"
                if p["speed"] != 1.0:  # remove the clock difference between the recorders
                    c += f",asetrate={48000 / p['speed']:.4f},aresample=48000"
                c += f",aformat=sample_fmts=fltp:channel_layouts=stereo,volume={p['gain']:.2f}dB"
                length = p["duration"] * p["speed"]
                c += f",afade=t=in:d=0.02,afade=t=out:st={max(length - 0.02, 0):.3f}:d=0.02"
                if p["offset"] < 0:
                    c += f",atrim=start={-p['offset']:.4f},asetpts=PTS-STARTPTS"
                elif p["offset"] > 0:
                    c += f",adelay={p['offset'] * 1000:.2f}:all=1"
                chain += c + f"[c{i}];"
            chain += "[base]" + "".join(f"[c{i}]" for i in range(1, len(placed) + 1))
            chain += f"amix=inputs={len(placed) + 1}:normalize=0:duration=first"
        if denoise:
            chain += ",highpass=f=80,afftdn=nr=8:nf=-45:tn=1"
        if balance:
            chain += ",dynaudnorm=f=400:g=31:p=0.9:m=6"

        before = None
        if normalize:
            step(40, _("Measuring loudness"))
            m = measure_loudness(inputs, chain, temp)
            before = m["input_i"]
            chain += (f",loudnorm=I={target}:TP={TARGET_PEAK}:LRA=11:measured_I={m['input_i']}"
                      f":measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
                      f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
        Path(temp, "filter.txt").write_text(chain + "[a]", encoding="utf-8")
        command = ["ffmpeg", "-v", "error", "-y", *inputs, "-/filter_complex", "filter.txt",
                   "-map", "0:v?", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k",
                   "-ar", "48000", "-t", f"{info['duration']:.3f}", "-movflags", "+faststart",
                   "-progress", "pipe:1", "-nostats", str(output.resolve())]
        step(55, _("Writing the new video"))
        proc = subprocess.Popen(command, cwd=temp, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                creationflags=NO_WINDOW)
        for line in proc.stdout:
            match = re.match(rb"out_time_us=(\d+)", line)
            if match:
                step(55 + 40 * min(int(match.group(1)) / 1e6 / info["duration"], 1.0), _("Writing the new video"))
        log = proc.stderr.read().decode("utf-8", "replace").strip()
        if proc.wait() != 0:
            raise DavarError(_("ffmpeg could not write the video:") + "\n" + log[-600:])

    step(96, _("Measuring the result"))
    after = measure_loudness(["-i", str(output.resolve())])
    step(100, _("Finished"))
    return {"output": output, "clips": found, "before": before, "after": after["input_i"],
            "peak": after["input_tp"], "target": target if normalize else None,
            "balance": balance, "denoise": denoise}


def report(r):
    lines = []
    for p in r["clips"]:
        if p["placed"]:
            lines.append(
                _("Placed   : {name}  ->  {time}  (similarity {similarity:.0f}%, {margin:.0f}% ahead of "
                  "the runner-up, level {gain:+.1f} dB").format(
                    name=p["path"].name, time=format_time(max(p["offset"], 0)),
                    similarity=p["similarity"] * 100, margin=p["margin"] * 100, gain=p["gain"])
                + (", " + _("clock difference corrected") if p["speed"] != 1.0 else "") + ")")
        else:
            lines.append(_("No place : {name}  (no position stood out; this audio may not occur in "
                           "the video, so it was not placed)").format(name=p["path"].name))
    if r["before"] is not None:
        lines.append(_("Loudness : {before:.1f} -> {after:.1f} LUFS (target {target:.0f}), peak {peak:.1f} dBTP").format(
            before=r["before"], after=r["after"], target=r["target"], peak=r["peak"]))
    else:
        lines.append(_("Loudness : {after:.1f} LUFS (not adjusted)").format(after=r["after"]))
    extras = [name for name, on in ((_("speaker balancing"), r["balance"]),
                                    (_("noise reduction"), r["denoise"])) if on]
    if extras:
        lines.append(_("Applied  : {what} (check by ear)").format(what=", ".join(extras)))
    lines.append("\n" + _("Video written (picture not re-encoded): {path}").format(path=r["output"]))
    return "\n".join(lines)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Place separate audio recordings in a video and set the loudness.")
    p.add_argument("video", type=Path)
    p.add_argument("--audio", type=Path, action="append", default=[],
                   help="a separately recorded audio file (may be given several times)")
    p.add_argument("--folder", type=Path, default=None, help="output folder (default: next to the video)")
    p.add_argument("--no-normalize", action="store_true", help="do not adjust the loudness")
    p.add_argument("--target", type=float, default=-14.0, help="target loudness in LUFS (default -14)")
    p.add_argument("--balance", action="store_true", help="bring the speakers' levels closer together")
    p.add_argument("--denoise", action="store_true", help="reduce background noise")
    a = p.parse_args()
    try:
        result = process(a.video, a.audio, folder=a.folder, normalize=not a.no_normalize, target=a.target,
                         balance=a.balance, denoise=a.denoise,
                         progress=lambda pct, msg: print(f"\r{pct:5.1f}%  {msg}        ", end="", file=sys.stderr))
    except DavarError as e:
        sys.exit("\n" + _("ERROR: {message}").format(message=e))
    print("\n" + report(result))


if __name__ == "__main__":
    main()
