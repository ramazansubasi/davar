"""davar titles - makes a lower third for a speaker's name and title.

The result is a video with a transparent background and a soft entrance and exit
(ProRes 4444). In DaVinci Resolve it is dragged onto the track above the video; no
further effect is needed. From the window the names can also be placed on the
timeline, each where its speaker first speaks (see place_on_timeline).

    python titles.py "Jane Doe" "Journalist" --video "episode.mp4"
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

import roughcut
import speakers
from common import NO_WINDOW, DavarError, format_time, parse_time, two_microphones_note, video_info
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
# what may be written in a speaker's line to place that name, as roughcut.plain() spells it
# (it lowercases the Turkish way, so RIGHT arrives as "rıght")
PLACE_WORDS = {"left": "left", "sol": "left", "centre": "centre", "center": "centre", "orta": "centre",
               "right": "right", "rıght": "right", "sağ": "right", "sag": "right"}
PANEL = (14, 18, 26, 225)  # colour of the name band (dark, slightly transparent)
FADE_IN, FADE_OUT = 0.5, 0.4  # seconds
# Placing a name on the timeline. Where a turn begins is only known to within a few seconds,
# so the name comes a little late rather than over the last words of the person before.
PLACE_AFTER = 4.0  # seconds after a speaker's turn is found to begin
OPENING = 2.0  # seconds after the programme starts, for whoever speaks first
LONG_TURN = 10.0  # the name is put on the first turn at least this long, not on an interjection


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


def parse_people(rows):
    """Lines of the form "Name | Title | place | time" as dicts.

    Only the name is needed. The place (left, centre, right; also in Turkish) puts this name
    elsewhere than the others, and the time is the moment in the video it should appear.
    The two may come in either order: a word is a place, a number is a time.
    """
    people = []
    for row in rows:
        fields = [field.strip() for field in row.split("|")]
        if not fields[0]:
            continue
        if len(fields) > 4:
            raise DavarError(_("too many “|” in the line “{line}”. It reads: Name | Title | place | time").format(
                line=row.strip()))
        person = {"name": fields[0], "title": fields[1] if len(fields) > 1 else "", "position": None, "time": None}
        for field in fields[2:]:
            if not field:
                continue
            kind = "position" if plain(field) in PLACE_WORDS else "time" if field[0].isdigit() else None
            if kind is None or person[kind] is not None:
                raise DavarError(_("could not read “{field}” in the line “{line}”. After the title comes a place "
                                   "(left, centre, right) or a time (0:41), each once.").format(
                    field=field, line=row.strip()))
            person[kind] = PLACE_WORDS[plain(field)] if kind == "position" else parse_time(field)
        people.append(person)
    if not people:
        raise DavarError(_("a lower third needs at least a name."))
    return people


def plan_places(people, turns, start, end):
    """The moment in the video each person's name should appear, or None where it cannot be told.

    `turns` are (start, end, speaker) as found by speakers.find_turns; `start` and `end` are
    where the programme begins and ends. The people are taken to be listed in the order they
    first speak: the first listed gets the voice heard first, and so on. A person with a time
    of their own keeps it, and the voice heard at that time is taken to be theirs.
    """
    first = {}  # speaker -> (the moment their first long turn begins, whether the programme opens with it)
    for turn_start, turn_end, who in turns:
        begins, stops = max(turn_start, start), min(turn_end, end)
        if who not in first and stops - begins >= LONG_TURN:
            first[who] = (begins, turn_start <= start + 0.5)
    taken = {who for person in people if person["time"] is not None
             for turn_start, turn_end, who in turns if turn_start <= person["time"] < turn_end}
    free = [who for who in sorted(first, key=lambda who: first[who][0]) if who not in taken]
    places = []
    for person in people:
        if person["time"] is not None:
            places.append(person["time"])
        elif free:
            begins, opens = first[free.pop(0)]
            places.append(begins + (OPENING if opens else PLACE_AFTER))
        else:
            places.append(None)
    return places


def place_on_timeline(video, people, items, folder=None, words=None, language="tr", progress=None):
    """Put the lower thirds on the track above the video, each where its speaker first speaks.

    They go into the Rough Cut timeline of the video (`<video>_cut.fcpxml`) when there is one,
    replacing any names placed before; otherwise a timeline of the whole video is written
    (`<video>_titles.fcpxml`). `items` are the results of make_lower_third, in the order of `people`.
    """
    video = Path(video)
    target = Path(folder) if folder else video.parent
    info = video_info(video)
    fps = float(info["fps"])
    cut = target / (video.stem + "_cut.fcpxml")
    known = roughcut.read_timeline(cut, video, info)
    parts = known["parts"] if known else [(0, info["frames"])]
    output, label = (cut, "cut") if known else (target / (video.stem + "_titles.fcpxml"), "titles")
    start, end = parts[0][0] / fps, parts[-1][1] / fps
    for person in people:
        if person["time"] is not None and not 0 <= person["time"] < info["duration"]:
            raise DavarError(_("the time given for {name} is outside the video.").format(name=person["name"]))

    turns = []
    if any(person["time"] is None for person in people):
        if not words:
            raise DavarError(_("run Transcribe first, or give each name its time: Name | Title | 0:41"))
        if progress:
            progress(88, _("Listening for who speaks when"))
        turns = speakers.who_speaks(video, words, len(people), language)
    if progress:
        progress(96, _("Writing the timeline"))
    # titles of other kinds placed before (topic titles) stay; the names are placed anew
    overlays = [o for o in (known["overlays"] if known else []) if not o["path"].name.startswith("lowerthird_")
                and o["path"].is_file()]
    placed, missed = [], []
    for person, item, moment in zip(people, items, plan_places(people, turns, start, end)):
        place = roughcut.timeline_place(parts, round(moment * fps)) if moment is not None else None
        if place is None:
            missed.append(person["name"])
            continue
        overlays.append({"path": item["output"], "at": place[1], "frames": round(item["duration"] * item["fps"])})
        said = [word for word, word_start, _word_end in words or [] if word_start >= place[1] / fps - 0.3][:9]
        placed.append({"name": person["name"], "video": place[1] / fps, "timeline": place[2] / fps,
                       "said": " ".join(said)})
    roughcut.write_fcpxml(output, video, info, parts, label=label, overlays=overlays,  # the framings and
                          framings=known["framings"] if known else None,     # the corner logo stay
                          still=known["still"] if known else None, markers=known["markers"] if known else ())
    return {"timeline": output, "in_cut": bool(known), "placed": placed, "missed": missed}


def make_lower_thirds(rows, progress=None, timeline=False, words=None, language="tr", **settings):
    """Make several lower thirds from lines of the form "Name | Title | place | time" (see
    parse_people); `position` in the settings is for the lines that name no place. With `timeline`
    (and a video) they are also placed on the timeline; `words` is the transcript of the video."""
    people = parse_people(rows)
    share = 0.85 if timeline else 1.0  # of the progress bar
    results = []
    for i, person in enumerate(people):
        def step(percent, text, i=i):
            if progress:
                progress((i * 100 + percent) / len(people) * share, text)
        own = {**settings, "position": person["position"]} if person["position"] else settings
        results.append(make_lower_third(person["name"], person["title"], progress=step, **own))
    result = {"output": results[0]["output"], "items": results}
    if timeline and settings.get("video"):
        result.update(place_on_timeline(settings["video"], people, results, settings.get("folder"), words,
                                        language, progress))
        result["output"] = result["timeline"]
    if progress:
        progress(100, _("Finished"))
    return result


def report(r):
    first = r["items"][0]
    lines = [_("Lower thirds: {n}, {width}x{height}, {seconds:.0f} s, transparent background (ProRes 4444)").format(
                 n=len(r["items"]), width=first["size"][0], height=first["size"][1], seconds=first["duration"])]
    if "timeline" not in r:
        lines.append(_("How to use : in Resolve drag it onto the track above the video; the entrance and exit are built in"))
    lines += [""] + [_("Written: {path}").format(path=item["output"]) for item in r["items"]]
    if "timeline" in r:
        lines += ["", _("Placed on the Rough Cut timeline, on the track above the video:") if r["in_cut"]
                  else _("No Rough Cut timeline was found for this video, so a timeline of the whole video "
                         "was written:")]
        for p in r["placed"]:
            lines.append("  " + _("{name}: at {video} in the video, {timeline} on the timeline").format(
                name=p["name"], video=format_time(p["video"]), timeline=format_time(p["timeline"]))
                + (f"  «{p['said']} …»" if p["said"] else ""))
        for name in r["missed"]:
            lines.append("  " + _("{name}: could not tell where this person first speaks. Give the time "
                                  "yourself: Name | Title | 12:30").format(name=name))
        lines += [_("Check that each name stands over that person's own words; if two are swapped, "
                    "change the order of the lines."),
                  _("Timeline written: {path}").format(path=r["timeline"]),
                  _("In Resolve: File → Import → Timeline…"), two_microphones_note()]
    return "\n".join(lines)


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
