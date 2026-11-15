"""davar titles - makes a lower third for a speaker's name and title.

The result is a video with a transparent background and a soft entrance and exit
(ProRes 4444). In DaVinci Resolve it is dragged onto the track above the video; no
further effect is needed.

    python titles.py "Jane Doe" "Journalist" --video "episode.mp4"
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

from common import NO_WINDOW, DavarError, video_info
from i18n import _
from roughcut import plain

FONTS = {
    "bold": ["C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf",
             "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    "regular": ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf",
                "/System/Library/Fonts/Supplemental/Arial.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
}
POSITIONS = ("left", "centre", "right")
PANEL = (14, 18, 26, 225)  # colour of the name band (dark, slightly transparent)
FADE_IN, FADE_OUT = 0.5, 0.4  # seconds


def parse_colour(text):
    """Turn "#E30613" or "E30613" into (r, g, b)."""
    match = re.fullmatch(r"#?([0-9a-fA-F]{6})", text.strip())
    if not match:
        raise DavarError(_("could not read the colour “{text}”. Example: #E30613").format(text=text))
    return tuple(int(match.group(1)[i:i + 2], 16) for i in (0, 2, 4))


def _font(kind, size):
    from PIL import ImageFont
    for path in FONTS[kind]:
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def draw_lower_third(name, title, width, height, colour=(227, 6, 19), position="left"):
    """Return the fully visible lower third and where it goes: (image, x, y, stripe width).

    The image is only as large as the lower third itself: an accent stripe on the
    left, the name band on top and, if given, the title band below.
    """
    from PIL import Image, ImageDraw
    scale = height / 1080  # every measure is given for 1080 lines
    name_font, title_font = _font("bold", round(50 * scale)), _font("regular", round(30 * scale))
    measure = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    padding, stripe = round(26 * scale), round(10 * scale)
    max_width = int(width * 0.7)

    def fit(text, font, kind, size):
        while measure.textlength(text, font=font) > max_width and size > 14:
            size -= 2
            font = _font(kind, size)
        return font

    name_font = fit(name, name_font, "bold", round(50 * scale))
    name_h = round(name_font.size * 1.62)
    name_w = round(measure.textlength(name, font=name_font)) + 2 * padding
    title_h = title_w = 0
    if title:
        title_font = fit(title, title_font, "regular", round(30 * scale))
        title_h = round(title_font.size * 1.75)
        title_w = round(measure.textlength(title, font=title_font)) + 2 * padding

    w, h = stripe + max(name_w, title_w), name_h + title_h
    image = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, stripe - 1, h - 1), fill=colour + (255,))
    draw.rectangle((stripe, 0, stripe + name_w - 1, name_h - 1), fill=PANEL)
    draw.text((stripe + padding, name_h / 2), name, font=name_font, fill=(255, 255, 255, 255), anchor="lm")
    if title:
        draw.rectangle((stripe, name_h, stripe + title_w - 1, h - 1), fill=colour + (255,))
        draw.text((stripe + padding, name_h + title_h / 2), title, font=title_font,
                  fill=(255, 255, 255, 255), anchor="lm")

    margin = round(width * 0.06)
    x = {"left": margin, "centre": (width - w) // 2, "right": width - w - margin}[position]
    return image, x, height - h - round(height * 0.12), stripe


def _ease(t):
    """Turn 0-1 progress into a movement that slows down at the end."""
    t = min(max(t, 0.0), 1.0)
    return 1 - (1 - t) ** 3


def lower_third_frame(full, stripe, time, duration):
    """The lower third at a given moment: it opens from the left and fades out at the end."""
    from PIL import Image
    w, h = full.size
    opening = _ease((time - 0.12) / (FADE_IN - 0.12))  # the stripe first, then the bands open
    stripe_height = _ease(time / 0.22)
    frame = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    s = round(h * stripe_height)
    if s > 0:
        frame.paste(full.crop((0, h - s, stripe, h)), (0, h - s))
    g = round((w - stripe) * opening)
    if g > 0:
        frame.paste(full.crop((stripe, 0, stripe + g, h)), (stripe, 0))
    left = duration - time
    if left < FADE_OUT:  # the whole thing fades at the exit
        frame.putalpha(frame.getchannel("A").point(lambda a: int(a * max(left, 0) / FADE_OUT)))
    return frame


def make_lower_third(name, title="", video=None, folder=None, duration=6.0, colour="#E30613",
                     position="left", width=1920, height=1080, fps=30.0, progress=None):
    """Write the transparent lower-third video. With a video, its size and frame rate are used."""
    try:
        from PIL import Image
    except ImportError:
        raise DavarError(_("this needs Pillow. Install it with: pip install pillow"))
    name, title = name.strip(), title.strip()
    if not name:
        raise DavarError(_("a lower third needs at least a name."))
    if position not in POSITIONS:
        raise DavarError(_("the position can be: {choices}").format(choices=", ".join(POSITIONS)))
    if not 2.0 <= duration <= 60.0:
        raise DavarError(_("the lower third must last between 2 and 60 seconds."))
    rgb = parse_colour(colour) if isinstance(colour, str) else tuple(colour)
    rate = f"{fps:.3f}"
    if video:
        info = video_info(video)
        width, height, fps = info["width"], info["height"], float(info["fps"])
        rate = f"{info['fps'].numerator}/{info['fps'].denominator}"
    target = Path(folder) if folder else (Path(video).parent if video else Path.cwd())
    if not target.is_dir():
        raise DavarError(_("output folder not found: {path}").format(path=target))
    # ASCII-only file name, so every program opens it without trouble
    slug = plain(name.replace(" ", "_")).translate(str.maketrans("çğıöşü", "cgiosu"))
    slug = re.sub(r"[^a-z0-9]+", "_", slug).strip("_") or "name"
    output = target / f"lowerthird_{slug}.mov"

    full, x, y, stripe = draw_lower_third(name, title, width, height, rgb, position)
    frames = round(duration * fps)
    command = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba",
               "-s", f"{width}x{height}", "-r", rate, "-i", "-",
               "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le",
               "-vendor", "apl0", "-an", str(output.resolve())]
    try:
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=NO_WINDOW)
    except FileNotFoundError:
        raise DavarError(_("{tool} was not found. ffmpeg must be installed and on PATH.").format(tool="ffmpeg"))
    empty = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    try:
        for i in range(frames):
            canvas = empty.copy()
            canvas.paste(lower_third_frame(full, stripe, i / fps, duration), (x, y))
            proc.stdin.write(canvas.tobytes())
            if progress and i % 10 == 0:
                progress(100 * i / frames, _("Drawing the lower third: {name}").format(name=name))
        proc.stdin.close()
    except (BrokenPipeError, OSError):
        pass
    log = proc.stderr.read().decode("utf-8", "replace").strip()
    if proc.wait() != 0:
        raise DavarError(_("ffmpeg could not write the video:") + "\n" + log[-600:])
    if progress:
        progress(100, _("Finished"))
    return {"output": output, "name": name, "title": title, "duration": duration,
            "size": (width, height), "fps": fps}


def make_lower_thirds(rows, progress=None, **settings):
    """Make several lower thirds from lines of the form "Name | Title"."""
    people = []
    for row in rows:
        if row.strip():
            name, _sep, title = row.partition("|")
            people.append((name.strip(), title.strip()))
    if not people:
        raise DavarError(_("a lower third needs at least a name."))
    results = []
    for i, (name, title) in enumerate(people):
        def step(percent, text, i=i):
            if progress:
                progress((i * 100 + percent) / len(people), text)
        results.append(make_lower_third(name, title, progress=step, **settings))
    return {"output": results[0]["output"], "items": results}


def report(r):
    first = r["items"][0]
    lines = [_("Lower thirds: {n}, {width}x{height}, {seconds:.0f} s, transparent background (ProRes 4444)").format(
                 n=len(r["items"]), width=first["size"][0], height=first["size"][1], seconds=first["duration"]),
             _("How to use : in Resolve drag it onto the track above the video; the entrance and exit are built in"),
             ""]
    return "\n".join(lines + [_("Written: {path}").format(path=item["output"]) for item in r["items"]])


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Make a transparent lower-third video for a speaker's name.")
    p.add_argument("name", help="the speaker's name")
    p.add_argument("title", nargs="?", default="", help="their title (optional)")
    p.add_argument("--video", type=Path, default=None, help="take the size and frame rate from this video")
    p.add_argument("--folder", type=Path, default=None, help="output folder")
    p.add_argument("--duration", type=float, default=6.0, help="time on screen in seconds (default 6)")
    p.add_argument("--colour", default="#E30613", help="accent colour (default #E30613)")
    p.add_argument("--position", default="left", choices=POSITIONS, help="horizontal place (default left)")
    a = p.parse_args()
    try:
        result = make_lower_thirds([f"{a.name} | {a.title}"], video=a.video, folder=a.folder,
                                   duration=a.duration, colour=a.colour, position=a.position)
    except DavarError as e:
        sys.exit(_("ERROR: {message}").format(message=e))
    print(report(result))


if __name__ == "__main__":
    main()
