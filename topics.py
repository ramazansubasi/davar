"""davar topics - lower thirds for the subject being talked about: a question or a topic.

A white panel at the bottom of the picture: a red tab on top with the name of the
programme, a large headline (the question or the topic), a red line below it (the guest),
a red edge on the left and the channel's logo on the right. It opens from the left, the
red edge first, and closes back to the left. The result is a video with a transparent
background (ProRes 4444), like the name titles of titles.py, and can be put on the Rough
Cut timeline at the start of each chapter found by Content Analysis.

The look follows a brand folder, `.davar/brand` in the home folder: Montserrat from its
`fonts` folder when it is there, Segoe UI or Arial otherwise; the logo is any picture file.
"""

import re
import subprocess
from pathlib import Path

from common import NO_WINDOW, DavarError, two_microphones_note, video_info
from i18n import _
from roughcut import plain

RED = (206, 30, 38)
INK = (26, 31, 40)
WHITE = (255, 255, 255)
DIVIDER = (214, 210, 204)
BRAND = Path.home() / ".davar" / "brand"
FALLBACK = {"ExtraBold": ["C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf",
                          "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
            "Bold": ["C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf",
                     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
            "SemiBold": ["C:/Windows/Fonts/seguisb.ttf", "C:/Windows/Fonts/segoeuib.ttf",
                         "C:/Windows/Fonts/arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]}
OPEN, CLOSE = 0.65, 0.5  # seconds the entrance and the exit take
DURATION = 8.0  # seconds on screen by default
LOGO_ZONE = 400  # pixels (at 1920 wide) kept on the right for the logo


def font_path(weight):
    """Montserrat of the brand folder, or a common bold font. Returns (path, is it the brand's)."""
    own = BRAND / "fonts" / f"Montserrat-{weight}.ttf"
    if own.is_file():
        return own, True
    for path in FALLBACK[weight]:
        if Path(path).is_file():
            return Path(path), False
    return None, False


def _font(weight, size):
    from PIL import ImageFont
    path, _own = font_path(weight)
    return ImageFont.truetype(str(path), size) if path else ImageFont.load_default(size)


def upper(text):
    """Capitals the Turkish way: i becomes İ, ı becomes I."""
    return text.replace("i", "İ").replace("ı", "I").upper()


def _fit(draw, text, weight, size, width, smallest):
    """The font that fits the text into `width`, smaller if need be; a text too long even at the
    smallest size loses words from its end. Returns (font, text)."""
    font = _font(weight, size)
    while draw.textlength(text, font=font) > width and size > smallest:
        size -= 2
        font = _font(weight, size)
    words = text.split()
    while len(words) > 1 and draw.textlength(text, font=font) > width:
        words.pop()
        text = " ".join(words).rstrip(",.;:") + "…"
    return font, text


def layers(tag, headline, line, width=1920, height=1080, logo=None):
    """The pieces of the lower third, each a transparent picture of the whole frame:
    shadow, panel, edge, tab, text, logo. Also the box the panel fills."""
    from PIL import Image, ImageDraw, ImageFilter
    sx, sy = width / 1920, height / 1080
    x0, x1, y, h = round(96 * sx), round(1824 * sx), round(806 * sy), round(170 * sy)
    size = (width, height)
    blank = lambda: Image.new("RGBA", size, (0, 0, 0, 0))  # noqa: E731
    logo_picture = None
    if logo:
        try:
            logo_picture = Image.open(logo).convert("RGBA")
        except OSError:
            raise DavarError(_("the logo could not be opened: {path}").format(path=logo))
    zone = round(LOGO_ZONE * sx) if logo_picture else 0
    room = (x1 - zone) - (x0 + round(56 * sx)) - round(30 * sx)  # for the headline and the line

    tab_font = _font("Bold", round(24 * sy))
    shadow = blank()
    draw = ImageDraw.Draw(shadow)
    tab_width = draw.textlength(tag, font=tab_font) + round(64 * sx) if tag else 0
    draw.rounded_rectangle((x0, y - round(38 * sy) if tag else y, x1, y + h + round(6 * sy)),
                           radius=round(12 * sy), fill=(0, 0, 0, 110))
    shadow = shadow.filter(ImageFilter.GaussianBlur(round(24 * sy)))

    panel = blank()
    draw = ImageDraw.Draw(panel)
    draw.rounded_rectangle((x0, y, x1, y + h), radius=round(12 * sy), fill=WHITE)
    if zone:
        draw.line((x1 - zone, y + round(26 * sy), x1 - zone, y + h - round(26 * sy)), fill=DIVIDER,
                  width=max(round(3 * sy), 1))

    edge = blank()
    ImageDraw.Draw(edge).rectangle((x0, y, x0 + round(22 * sx), y + h), fill=RED)

    tab = blank()
    if tag:
        draw = ImageDraw.Draw(tab)
        draw.rounded_rectangle((x0, y - round(44 * sy), x0 + tab_width, y + round(10 * sy)), radius=round(10 * sy),
                               fill=RED)
        draw.text((x0 + round(32 * sx), y - round(18 * sy)), tag, font=tab_font, fill=WHITE, anchor="lm")

    text = blank()
    draw = ImageDraw.Draw(text)
    head_font, headline = _fit(draw, headline, "ExtraBold", round(50 * sy), room, round(34 * sy))
    if line:
        line_font, line = _fit(draw, line, "SemiBold", round(25 * sy), room, round(18 * sy))
        draw.text((x0 + round(56 * sx), y + round(62 * sy)), headline, font=head_font, fill=INK, anchor="lm")
        draw.text((x0 + round(56 * sx), y + round(118 * sy)), line, font=line_font, fill=RED, anchor="lm")
    else:
        draw.text((x0 + round(56 * sx), y + h // 2), headline, font=head_font, fill=INK, anchor="lm")

    mark = blank()
    if logo_picture:
        most_w, most_h = zone - round(60 * sx), h - round(50 * sy)
        scale = min(most_w / logo_picture.width, most_h / logo_picture.height)
        shown = logo_picture.resize((max(round(logo_picture.width * scale), 1),
                                     max(round(logo_picture.height * scale), 1)), Image.LANCZOS)
        mark.alpha_composite(shown, (x1 - zone + (zone - shown.width) // 2, y + (h - shown.height) // 2))
    return (shadow, panel, edge, tab, text, mark), (x0, y, x1, y + h)


def _ease(t):
    t = min(max(t, 0.0), 1.0)
    return 1 - (1 - t) ** 3


def frame(parts, box, moment, duration):
    """The lower third at a moment: the red edge grows, the panel opens from the left, then the
    tab, the logo and the texts; at the end everything closes back to the left."""
    from PIL import Image, ImageDraw
    shadow, panel, edge, tab, text, mark = parts
    x0, top, x1, bottom = box
    size = panel.size
    left = duration - moment
    opening = _ease((moment - 0.15) / 0.5)
    if left < CLOSE:
        opening = min(opening, _ease(left / CLOSE))

    def cut(layer, share):
        """Only the part of the layer left of `share` of the panel's width."""
        if share >= 1:
            return layer
        mask = Image.new("L", size, 0)
        if share > 0:
            ImageDraw.Draw(mask).rectangle((0, 0, int(x0 + (x1 - x0) * share), size[1]), fill=255)
        out = layer.copy()
        out.putalpha(Image.composite(out.getchannel("A"), mask, mask))
        return out

    def faded(layer, amount):
        if amount >= 1:
            return layer
        out = layer.copy()
        out.putalpha(out.getchannel("A").point(lambda a: int(a * max(amount, 0.0))))
        return out

    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    canvas.alpha_composite(faded(cut(shadow, opening), opening))
    canvas.alpha_composite(cut(panel, opening))
    grown = _ease(moment / 0.2)
    rising = edge.copy()
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rectangle((0, bottom - int((bottom - top) * grown), size[0], size[1]), fill=255)
    rising.putalpha(Image.composite(rising.getchannel("A"), mask, mask))
    canvas.alpha_composite(faded(rising, min(1.0, left / 0.15) if left < 0.15 else 1.0))
    for layer, start in ((mark, 0.55), (tab, 0.6), (text, 0.65)):
        amount = _ease((moment - start) / 0.3)
        if left < CLOSE + 0.15:
            amount = min(amount, max((left - CLOSE + 0.15) / 0.15, 0.0))
        canvas.alpha_composite(faded(cut(layer, opening), amount))
    return canvas


def file_name(number, headline):
    slug = plain(headline.replace(" ", "_")).translate(str.maketrans("çğıöşü", "cgiosu"))
    slug = re.sub(r"[^a-z0-9]+", "_", slug).strip("_")[:40] or "topic"
    return f"topic_{number:02d}_{slug}.mov"


def make_topic(headline, tag="", line="", number=1, video=None, folder=None, duration=DURATION, logo=None,
               width=1920, height=1080, fps=30.0, progress=None):
    """Write one transparent lower third for a topic; returns where and how long."""
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        raise DavarError(_("this needs Pillow. Install it with: pip install pillow"))
    headline, tag, line = upper(headline.strip()), upper(tag.strip()), upper(line.strip())
    if not headline:
        raise DavarError(_("a topic title needs a headline."))
    if not 3.0 <= duration <= 60.0:
        raise DavarError(_("a topic title must last between 3 and 60 seconds."))
    rate = f"{fps:.3f}"
    if video:
        info = video_info(video)
        width, height, fps = info["width"], info["height"], float(info["fps"])
        rate = f"{info['fps'].numerator}/{info['fps'].denominator}"
    target = Path(folder) if folder else (Path(video).parent if video else Path.cwd())
    if not target.is_dir():
        raise DavarError(_("output folder not found: {path}").format(path=target))
    output = target / file_name(number, headline)
    parts, box = layers(tag, headline, line, width, height, logo)
    frames = round(duration * fps)
    command = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{width}x{height}",
               "-r", rate, "-i", "-", "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le",
               "-vendor", "apl0", "-an", str(output.resolve())]
    try:
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=NO_WINDOW)
    except FileNotFoundError:
        raise DavarError(_("{tool} was not found. ffmpeg must be installed and on PATH.").format(tool="ffmpeg"))
    still = None  # the fully open lower third, drawn once and written while it stands
    try:
        for i in range(frames):
            moment = i / fps
            standing = 1.0 <= moment <= duration - CLOSE - 0.2
            if standing and still is None:
                still = frame(parts, box, moment, duration).tobytes()
            proc.stdin.write(still if standing else frame(parts, box, moment, duration).tobytes())
            if progress and i % 10 == 0:
                progress(100 * i / frames)
        proc.stdin.close()
    except (BrokenPipeError, OSError):
        pass
    log = proc.stderr.read().decode("utf-8", "replace").strip()
    if proc.wait() != 0:
        raise DavarError(_("ffmpeg could not write the video:") + "\n" + log[-600:])
    return {"output": output, "headline": headline, "duration": duration, "fps": fps, "size": (width, height)}


# --- on the timeline -------------------------------------------------------------------
DELAY = 3.0  # seconds after the chapter begins; the subject has settled by then
GAP = 0.5  # seconds kept free between two titles


def parse_topics(rows):
    """Lines of the form "time | headline | line" as dicts. The time is on the Rough Cut timeline,
    as Content Analysis gives it; the line under the headline is optional."""
    found = []
    for row in rows:
        fields = [field.strip() for field in row.split("|")]
        if not any(fields):
            continue
        if len(fields) < 2 or not fields[1] or len(fields) > 3:
            raise DavarError(_("could not read the line “{line}”. It reads: time | headline | line under it")
                             .format(line=row.strip()))
        from common import parse_time
        found.append({"time": parse_time(fields[0]), "headline": fields[1],
                      "line": fields[2] if len(fields) == 3 and fields[2] else None})
    return sorted(found, key=lambda topic: topic["time"])


def plan_starts(times, length, busy=(), total=None, delay=DELAY):
    """When each title starts on the timeline (seconds), or None where it does not fit.

    A title starts `delay` after its chapter; if a name title is on screen then (`busy` are
    (start, end) spans) or the previous title has not finished, it waits for it.
    """
    starts, previous_end = [], -1.0
    for moment in times:
        start = max(moment + delay, previous_end + GAP)
        moved = True
        while moved:
            moved = False
            for a, b in busy:
                if start < b + GAP and start + length > a - GAP:
                    start, moved = b + GAP, True
        if total is not None and start + length > total:
            starts.append(None)
            continue
        starts.append(start)
        previous_end = start + length
    return starts


def place_on_timeline(video, made, folder=None):
    """Put the topic titles on the Rough Cut timeline of the video (or on a timeline of the whole
    video when it has none), replacing the topic titles placed before; the name titles stay.
    `made` are dicts with the "time" asked for (on the timeline) and what make_topic returned."""
    import roughcut
    from content import video_moment
    video = Path(video)
    target = Path(folder) if folder else video.parent
    info = video_info(video)
    fps = float(info["fps"])
    cut = target / (video.stem + "_cut.fcpxml")
    known = roughcut.read_timeline(cut, video, info)
    if known is None:
        titles = roughcut.read_timeline(target / (video.stem + "_titles.fcpxml"), video, info)
        known = {"parts": [(0, info["frames"])], "overlays": titles["overlays"] if titles else [], "framings": None,
                 "still": titles["still"] if titles else None}
        output, label, in_cut = target / (video.stem + "_titles.fcpxml"), "titles", False
    else:
        output, label, in_cut = cut, "cut", True
    parts = known["parts"]
    kept = [o for o in known["overlays"] if not o["path"].name.startswith("topic_") and o["path"].is_file()]
    busy = []
    for overlay in kept:
        place = roughcut.timeline_place(parts, overlay["at"])
        if place is not None:
            busy.append((place[2] / fps, (place[2] + overlay["frames"]) / fps))
    total = sum(b - a for a, b in parts) / fps
    placed, missed, overlays = [], [], list(kept)
    length = made[0]["duration"] if made else DURATION
    for item, start in zip(made, plan_starts([m["time"] for m in made], length, busy, total)):
        if start is None:
            missed.append(item["headline"])
            continue
        at = round(video_moment(parts, fps, start) * fps)
        overlays.append({"path": item["output"], "at": at, "frames": round(item["duration"] * item["fps"])})
        placed.append({"headline": item["headline"], "timeline": start, "video": at / fps})
    roughcut.write_fcpxml(output, video, info, parts, label=label, overlays=overlays, framings=known.get("framings"),
                          still=known.get("still"))
    return {"timeline": output, "in_cut": in_cut, "placed": placed, "missed": missed}


def make_topics(rows, tag="", line="", video=None, folder=None, duration=DURATION, logo=None, timeline=True,
                progress=None):
    """Make a topic title for each line "time | headline | line" and put them on the timeline."""
    topics = parse_topics(rows)
    if not topics:
        raise DavarError(_("write at least one topic: time | headline"))
    made = []
    for n, topic in enumerate(topics, 1):
        def step(percent, n=n):
            if progress:
                progress(((n - 1) * 100 + percent) / len(topics) * (0.95 if timeline else 1.0),
                         _("Drawing the topic title {n} of {count}").format(n=n, count=len(topics)))
        result = make_topic(topic["headline"], tag, topic["line"] if topic["line"] is not None else line, n,
                            video, folder, duration, logo, progress=step)
        made.append({**result, "time": topic["time"]})
    result = {"output": made[0]["output"], "items": made, "font": font_path("ExtraBold")}
    if timeline and video:
        result.update(place_on_timeline(video, made, folder))
        result["output"] = result["timeline"]
    return result


def report(r):
    from common import format_time
    path, own = r["font"]
    lines = [_("Topic titles: {n}, {seconds:.0f} s each, transparent background (ProRes 4444)").format(
        n=len(r["items"]), seconds=r["items"][0]["duration"])]
    if not own:
        lines.append(_("Montserrat was not found in {folder}; {font} was used.").format(
            folder=BRAND / "fonts", font=Path(path).stem if path else "?"))
    lines += [_("Written: {path}").format(path=item["output"]) for item in r["items"]]
    if "timeline" in r:
        lines.append("")
        lines.append(_("Placed on the Rough Cut timeline, on the track above the video:") if r["in_cut"]
                     else _("No Rough Cut timeline was found for this video, so a timeline of the whole video "
                            "was written:"))
        for p in r["placed"]:
            lines.append("  " + _("{headline}: {timeline} on the timeline").format(
                headline=p["headline"], timeline=format_time(p["timeline"])))
        for headline in r["missed"]:
            lines.append("  " + _("{headline}: no room left before the end; not placed").format(headline=headline))
        lines += [_("Timeline written: {path}").format(path=r["timeline"]), _("In Resolve: File → Import → Timeline…"),
                  two_microphones_note()]
    return "\n".join(lines)
