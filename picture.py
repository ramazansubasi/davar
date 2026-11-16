"""Picture: reframe a video to 16:9 and lock a tripod shot so the background stands still.

A phone on a tripod still makes the picture move: while it hunts for focus the lens
travels, and the whole picture grows, shrinks and hops by a few pixels. In a video that
is cut every few seconds this shows at every cut. Locking lines every frame up with one
reference frame, so the background does not move at all.

The picture is re-encoded and written as a new video; the audio is copied untouched, so
a transcript made for the original stays valid for the new file.
"""

import argparse
import json
import math
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

import transcript
from common import NO_WINDOW, DavarError, run, video_info
from i18n import _

ANALYSIS_WIDTH = 1280  # frames are followed on a picture about this wide
MAX_ZOOM = 1.03  # never zoom in more than this to hide the edges
MAX_WANDER = 0.04  # a picture moving more than this share of its width is not a tripod shot
QUALITY = ["-c:v", "libx264", "-crf", "16", "-preset", "veryfast"]  # an intermediate: quick to write, large


# --- geometry (no video needed) -------------------------------------------------
def parse_aspect(text):
    """Turn "16:9" into 16 / 9; None or "" means: keep the shape of the picture."""
    if not text:
        return None
    try:
        w, h = (float(part) for part in str(text).replace("/", ":").split(":"))
        if w <= 0 or h <= 0:
            raise ValueError
    except ValueError:
        raise DavarError(_("could not read the frame shape “{text}”. Example: 16:9").format(text=text))
    return w / h


def frame_box(width, height, aspect=None, position=50.0):
    """Return (x, y, w, h): the part of the picture to keep for the wanted shape.

    A picture wider than `aspect` loses its sides, a narrower one its top and bottom.
    `position` says where the kept part sits: 0 = at the left (or top) edge,
    50 = in the middle, 100 = at the right (or bottom) edge.
    """
    if not 0 <= position <= 100:
        raise DavarError(_("the frame position must be between 0 and 100."))
    even = lambda v: int(v) // 2 * 2  # noqa: E731  (4:2:0 video needs even numbers)
    width, height = even(width), even(height)
    if aspect is None:
        return 0, 0, width, height
    if width / height > aspect:
        w = min(even(round(height * aspect)), width)
        return even(round((width - w) * position / 100)), 0, w, height
    h = min(even(round(width / aspect)), height)
    return 0, even(round((height - h) * position / 100)), width, h


def parameters(matrix):
    """(shift x, shift y, log of the scale, rotation) of a similarity transform."""
    return (matrix[0, 2], matrix[1, 2], math.log(math.hypot(matrix[0, 0], matrix[1, 0])),
            math.atan2(matrix[1, 0], matrix[0, 0]))


def similarity(tx, ty, log_scale, rotation):
    c, s = math.exp(log_scale) * math.cos(rotation), math.exp(log_scale) * math.sin(rotation)
    return np.array([[c, -s, tx], [s, c, ty], [0, 0, 1.0]])


def settle(transforms):
    """Turn per-frame transforms (reference -> frame, None where the frame could not be
    followed) into transforms from the picture's usual position -> frame.

    Frames that could not be followed take a position between their neighbours'. The
    usual position is the median over the whole video: most frames then need almost no
    correction, whatever state the reference frame happened to be in.
    """
    p = np.array([parameters(m) if m is not None else (np.nan,) * 4 for m in transforms], dtype=float)
    known = ~np.isnan(p[:, 0])
    if not known.any():
        raise DavarError(_("the picture could not be followed in any frame."))
    index = np.arange(len(p))
    for column in range(4):
        p[:, column] = np.interp(index, index[known], p[known, column])
    usual = np.linalg.inv(similarity(*np.median(p, axis=0)))
    return np.array([similarity(*row) @ usual for row in p])


def _corners(box, zoom=1.0):
    x, y, w, h = box
    cx, cy = x + (w - 1) / 2, y + (h - 1) / 2
    half_w, half_h = (w - 1) / 2 / zoom, (h - 1) / 2 / zoom
    return np.array([[cx - half_w, cy - half_h, 1], [cx + half_w, cy - half_h, 1],
                     [cx - half_w, cy + half_h, 1], [cx + half_w, cy + half_h, 1]]).T


def wander(transforms, box):
    """How far each frame's corners sit from their usual place, in pixels (one value per frame)."""
    corners = _corners(box)
    moved = transforms @ corners  # (frames, 3, 4)
    return np.hypot(moved[:, 0] - corners[0], moved[:, 1] - corners[1]).max(axis=1)


def needed_zoom(transforms, box, width, height, limit=MAX_ZOOM, share=0.999):
    """The smallest zoom that keeps the kept part inside the picture in nearly every frame."""
    for zoom in np.arange(1.0, limit + 1e-9, 0.001):
        moved = transforms @ _corners(box, zoom)
        inside = ((moved[:, 0] >= -0.5) & (moved[:, 0] <= width - 0.5)
                  & (moved[:, 1] >= -0.5) & (moved[:, 1] <= height - 0.5)).all(axis=1)
        if inside.mean() >= share:
            return float(zoom)
    return float(limit)


def sampling_matrix(transform, box, zoom):
    """The matrix that says, for each pixel of the output, where to read it in the frame."""
    x, y, w, h = box
    cx, cy = x + (w - 1) / 2, y + (h - 1) / 2
    place = np.array([[1 / zoom, 0, cx - (w - 1) / 2 / zoom], [0, 1 / zoom, cy - (h - 1) / 2 / zoom], [0, 0, 1]])
    return transform @ place


def chroma_matrix(matrix):
    """The same mapping for the half-size colour planes of 4:2:0 video."""
    double = np.array([[2, 0, 0.5], [0, 2, 0.5], [0, 0, 1.0]])
    return np.linalg.inv(double) @ matrix @ double


# --- following the picture (OpenCV) ----------------------------------------------
def _cv2():
    try:
        import cv2
    except ImportError:
        raise DavarError(_("OpenCV is needed to lock the frame. Install it with: pip install opencv-python"))
    return cv2


def find_points(gray):
    """Corners worth following in the reference frame."""
    points = _cv2().goodFeaturesToTrack(gray, maxCorners=800, qualityLevel=0.01, minDistance=10, blockSize=7)
    if points is None or len(points) < 80:
        raise DavarError(_("the picture has too little detail to follow (a plain wall, or too dark)."))
    return points


def measure(reference, points, gray):
    """Where the reference frame's points are in `gray`: a 3x3 similarity, or None.

    People move and the background does not; the background's points agree on one
    transform and everything else is thrown out as an outlier.
    """
    cv2 = _cv2()
    moved, ok, _error = cv2.calcOpticalFlowPyrLK(reference, gray, points, None, winSize=(21, 21), maxLevel=2)
    good = ok.ravel() == 1
    if good.sum() < 40:
        return None
    matrix, inliers = cv2.estimateAffinePartial2D(points[good], moved[good], method=cv2.RANSAC,
                                                  ransacReprojThreshold=0.5)
    if matrix is None or inliers.sum() < max(30, 0.15 * len(points)):
        return None
    return np.vstack([matrix, [0, 0, 1.0]])


def warp(planes, matrix, size):
    """Read the output's Y, U and V planes out of the frame's planes."""
    cv2 = _cv2()
    w, h = size
    chroma = chroma_matrix(matrix)
    flags = cv2.WARP_INVERSE_MAP
    return (cv2.warpAffine(planes[0], matrix[:2], (w, h), flags=flags | cv2.INTER_LANCZOS4,
                           borderMode=cv2.BORDER_REPLICATE),
            cv2.warpAffine(planes[1], chroma[:2], (w // 2, h // 2), flags=flags | cv2.INTER_CUBIC,
                           borderMode=cv2.BORDER_REPLICATE),
            cv2.warpAffine(planes[2], chroma[:2], (w // 2, h // 2), flags=flags | cv2.INTER_CUBIC,
                           borderMode=cv2.BORDER_REPLICATE))


# --- reading and writing the video -------------------------------------------------
def _stream(video):
    """Pixel format, colour tags and rotation of the video stream."""
    raw = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-print_format", "json", "-show_streams",
               str(video)])
    s = json.loads(raw)["streams"][0]
    rotation = 0
    for side in s.get("side_data_list", []):
        rotation = int(float(side.get("rotation", rotation)))
    rotation = int(float(s.get("tags", {}).get("rotate", rotation)))
    tags = []
    for option, key in (("-color_range", "color_range"), ("-colorspace", "color_space"),
                        ("-color_trc", "color_transfer"), ("-color_primaries", "color_primaries")):
        if s.get(key) and s[key] not in ("unknown", "unspecified"):
            tags += [option, s[key]]
    return {"raw": "yuvj420p" if str(s.get("pix_fmt", "")).startswith("yuvj") else "yuv420p",
            "tags": tags, "turned": abs(rotation) % 180 == 90}


def _popen(command, **pipes):
    try:
        return subprocess.Popen(command, creationflags=NO_WINDOW, **pipes)
    except FileNotFoundError:
        raise DavarError(_("{tool} was not found. ffmpeg must be installed and on PATH.").format(tool=command[0]))


def _left(started, done, total):
    """Text such as "about 12 min left"; "" until there is something to go by."""
    if done < 50 or total <= done:
        return ""
    minutes = (time.monotonic() - started) / done * (total - done) / 60
    return "  (" + _("about {minutes} min left").format(minutes=max(1, round(minutes))) + ")"


def _follow(video, info, rate, step):
    """Pass 1: follow the picture through the whole video on a reduced copy."""
    width, height = info["width"], info["height"]
    factor = max(1.0, width / ANALYSIS_WIDTH)
    small = (int(width / factor) // 2 * 2, int(height / factor) // 2 * 2)
    size = small[0] * small[1]
    shape = f"scale={small[0]}:{small[1]},format=gray"

    # the reference: the sharpest of nine frames spread over the video
    best, reference = -1.0, None
    for k in range(1, 10):
        raw = run(["ffmpeg", "-v", "error", "-ss", f"{info['duration'] * k / 10:.3f}", "-i", str(video),
                   "-frames:v", "1", "-vf", shape, "-f", "rawvideo", "-"])
        if len(raw) < size:
            continue
        frame = np.frombuffer(raw[:size], np.uint8).reshape(small[1], small[0])
        sharpness = float(_cv2().Laplacian(frame, 6).var())  # 6 = 64-bit float
        if sharpness > best:
            best, reference = sharpness, frame
    if reference is None:
        raise DavarError(_("no frame could be read from the video."))
    points = find_points(reference)

    reader = _popen(["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"fps={rate}:start_time=0,{shape}",
                     "-f", "rawvideo", "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    total = max(1, round(info["duration"] * info["fps"]))
    to_full = np.diag([width / small[0], height / small[1], 1.0])
    to_small = np.linalg.inv(to_full)
    found, started = [], time.monotonic()
    try:
        while True:
            raw = reader.stdout.read(size)
            if len(raw) < size:
                break
            m = measure(reference, points, np.frombuffer(raw, np.uint8).reshape(small[1], small[0]))
            found.append(None if m is None else to_full @ m @ to_small)
            if len(found) % 100 == 0:
                step(4 + 30 * min(len(found) / total, 1.0),
                     _("Following the picture") + _left(started, len(found), total))
    finally:
        reader.kill()
        reader.wait()
    if not found:
        raise DavarError(_("no frame could be read from the video."))
    return found


def _write_locked(video, output, info, stream, rate, box, zoom, transforms, step):
    """Pass 2: read every frame, put it in its place, hand it to the encoder."""
    width, height = info["width"], info["height"]
    out_size = (box[2], box[3])
    frame_bytes = width * height * 3 // 2
    reader = _popen(["ffmpeg", "-v", "error", "-i", str(video), "-vf",
                     f"fps={rate}:start_time=0,crop={width}:{height}:0:0", "-f", "rawvideo",
                     "-pix_fmt", stream["raw"], "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    # The colour tags describe the raw frames going in. Given on the output side instead,
    # ffmpeg converts the picture to match them and the result comes out darker.
    writer = _popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", stream["raw"],
                     "-s", f"{out_size[0]}x{out_size[1]}", "-r", rate, *stream["tags"], "-i", "-",
                     "-i", str(video), "-map", "0:v", "-map", "1:a?", *QUALITY, "-pix_fmt", stream["raw"],
                     "-c:a", "copy", "-movflags", "+faststart", str(output)],
                    stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    total, done, started = len(transforms), 0, time.monotonic()
    y_size, c_size = width * height, width * height // 4
    try:
        while True:
            raw = reader.stdout.read(frame_bytes)
            if len(raw) < frame_bytes:
                break
            data = np.frombuffer(raw, np.uint8)
            planes = (data[:y_size].reshape(height, width),
                      data[y_size:y_size + c_size].reshape(height // 2, width // 2),
                      data[y_size + c_size:].reshape(height // 2, width // 2))
            matrix = sampling_matrix(transforms[min(done, total - 1)], box, zoom)
            for plane in warp(planes, matrix, out_size):
                writer.stdin.write(plane.tobytes())
            done += 1
            if done % 30 == 0:
                step(35 + 63 * min(done / total, 1.0), _("Writing the new video") + _left(started, done, total))
        writer.stdin.close()
        log = writer.stderr.read().decode("utf-8", "replace").strip()
        if writer.wait() != 0:
            raise DavarError(_("ffmpeg could not write the video:") + "\n" + log[-600:])
    except (BrokenPipeError, OSError):
        log = writer.stderr.read().decode("utf-8", "replace").strip()
        raise DavarError(_("ffmpeg could not write the video:") + "\n" + log[-600:])
    finally:
        for process in (reader, writer):
            if process.poll() is None:
                process.kill()
            process.wait()
    return done


def _write_cropped(video, output, info, box, step):
    """Reframing alone needs no frame-by-frame work: ffmpeg cuts the picture itself."""
    x, y, w, h = box
    command = ["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", f"crop={w}:{h}:{x}:{y}",
               "-map", "0:v:0", "-map", "0:a?", *QUALITY, "-c:a", "copy", "-movflags", "+faststart",
               "-progress", "pipe:1", "-nostats", str(output)]
    proc = _popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    started = time.monotonic()
    for line in proc.stdout:
        if line.startswith(b"out_time_us=") and line[12:].strip().isdigit():
            seconds = int(line[12:]) / 1e6
            step(5 + 93 * min(seconds / info["duration"], 1.0),
                 _("Writing the new video") + _left(started, seconds * 30, info["duration"] * 30))
    log = proc.stderr.read().decode("utf-8", "replace").strip()
    if proc.wait() != 0:
        raise DavarError(_("ffmpeg could not write the video:") + "\n" + log[-600:])


def process(video, folder=None, aspect="16:9", position=50.0, lock=True, progress=None):
    """Reframe the video to `aspect` (None: keep its shape) and, with `lock`, hold the
    picture still. Writes `<name>_picture.<ext>` and returns what was done."""
    def step(percent, text):
        if progress:
            progress(percent, text)

    video = Path(video)
    if not video.is_file():
        raise DavarError(_("file not found: {path}").format(path=video))
    ratio = parse_aspect(aspect)
    step(1, _("Reading video information"))
    info = dict(video_info(video))
    stream = _stream(video)
    if stream["turned"]:  # a phone held upright: the stored picture is lying on its side
        info["width"], info["height"] = info["height"], info["width"]
    info["width"], info["height"] = info["width"] // 2 * 2, info["height"] // 2 * 2
    box = frame_box(info["width"], info["height"], ratio, position)
    reframed = (box[2], box[3]) != (info["width"], info["height"])
    if not reframed and not lock:
        raise DavarError(_("the picture already has this shape and locking is off: there is nothing to do."))
    ext = video.suffix.lower() if video.suffix.lower() in (".mp4", ".mov", ".mkv", ".m4v") else ".mp4"
    output = (Path(folder) if folder else video.parent) / (video.stem + "_picture" + ext)
    if output.resolve() == video.resolve():
        raise DavarError(_("the new video would overwrite the original."))
    result = {"output": output, "size": (info["width"], info["height"]), "box": box, "locked": lock,
              "zoom": 1.0, "wander": 0.0, "scale": 0.0, "lost": 0, "frames": 0, "steadied_rate": False}
    started = time.monotonic()
    writing = False  # an earlier result is only replaced once there is something to replace it with
    try:
        if lock:
            _cv2()
            rate = f"{info['fps'].numerator}/{info['fps'].denominator}"
            step(3, _("Following the picture"))
            found = _follow(video, info, rate, step)
            lost = sum(m is None for m in found)
            if lost > 0.2 * len(found):
                raise DavarError(_("the picture could not be followed in {share:.0f}% of the frames. Locking "
                                   "only works for a camera that does not move.").format(
                                       share=100 * lost / len(found)))
            transforms = settle(found)
            moved = wander(transforms, box)
            if np.percentile(moved, 99) > MAX_WANDER * info["width"]:
                raise DavarError(_("the camera moves too much in this video (up to {pixels:.0f} pixels). "
                                   "Locking only works for a camera that does not move.").format(
                                       pixels=float(np.percentile(moved, 99))))
            scales = np.array([math.hypot(m[0, 0], m[1, 0]) for m in transforms])
            zoom = needed_zoom(transforms, box, info["width"], info["height"])
            step(35, _("Writing the new video"))
            writing = True
            frames = _write_locked(video, output, info, stream, rate, box, zoom, transforms, step)
            result.update(zoom=zoom, wander=float(np.percentile(moved, 99.9)), lost=lost, frames=frames,
                          scale=float((np.percentile(scales, 99.9) - np.percentile(scales, 0.1)) * 100),
                          steadied_rate=info["variable_rate"])
        else:
            step(5, _("Writing the new video"))
            writing = True
            _write_cropped(video, output, info, box, step)
    except BaseException:
        if writing:
            output.unlink(missing_ok=True)  # do not leave half a video behind
        raise
    result["transcript"] = transcript.carry_over(video, output)
    result["seconds"] = time.monotonic() - started
    step(100, _("Finished"))
    return result


def report(r):
    lines = []
    (width, height), (x, y, w, h) = r["size"], r["box"]
    if (w, h) != (width, height):
        lines.append(_("Frame    : {width}x{height} -> {w}x{h}  (cut: left {left}, right {right}, top {top}, "
                       "bottom {bottom} pixels)").format(width=width, height=height, w=w, h=h, left=x,
                                                         right=width - w - x, top=y, bottom=height - h - y))
    if r["locked"]:
        lines.append(_("Locked   : the picture wandered by up to {pixels:.1f} pixels and {scale:.2f}% in size; "
                       "every frame now lines up with one reference frame").format(
                           pixels=r["wander"], scale=r["scale"]))
        if r["zoom"] > 1.0:
            lines.append(_("Zoom     : {percent:.1f}% closer, so the moving edges stay out of sight").format(
                percent=(r["zoom"] - 1) * 100))
        if r["lost"]:
            lines.append(_("Lost     : {count} of {frames} frames could not be followed and took the position "
                           "of their neighbours").format(count=r["lost"], frames=r["frames"]))
        if r["steadied_rate"]:
            lines.append(_("Rate     : the variable frame rate was turned into a constant one"))
    if r["transcript"]:
        lines.append(_("Text     : the transcript was carried over to the new video (the audio is unchanged)"))
    lines.append(_("Time     : {minutes:.0f} min").format(minutes=r["seconds"] / 60))
    lines.append("\n" + _("Video written (audio not touched): {path}").format(path=r["output"]))
    return "\n".join(lines)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Reframe a video and lock a tripod shot so the background stands still.")
    p.add_argument("video", type=Path)
    p.add_argument("--folder", type=Path, default=None, help="output folder (default: next to the video)")
    p.add_argument("--aspect", default="16:9", help="shape of the frame (default 16:9); 'keep' leaves it as it is")
    p.add_argument("--position", type=float, default=50.0,
                   help="where the kept part sits: 0 = left/top edge, 50 = middle, 100 = right/bottom edge")
    p.add_argument("--no-lock", action="store_true", help="only reframe; do not hold the picture still")
    a = p.parse_args()
    try:
        result = process(a.video, folder=a.folder, aspect=None if a.aspect == "keep" else a.aspect,
                         position=a.position, lock=not a.no_lock,
                         progress=lambda pct, msg: print(f"\r{pct:5.1f}%  {msg}        ", end="", file=sys.stderr))
    except DavarError as e:
        sys.exit("\n" + _("ERROR: {message}").format(message=e))
    print("\n" + report(result))


if __name__ == "__main__":
    main()
