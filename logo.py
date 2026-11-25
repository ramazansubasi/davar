"""davar logo - the channel's logo in a corner of the picture, from the start to the end.

Davar draws the logo on a transparent picture of the size of the video, in the corner
chosen, and puts that picture on a track of its own above the video and the titles of
the Rough Cut timeline, lasting the whole timeline. Nothing is re-encoded: in Resolve the
logo can still be moved, resized or switched off. Running Rough Cut or Titles again keeps it.
"""

from pathlib import Path

import roughcut
from common import DavarError, two_microphones_note, video_info
from i18n import _

CORNERS = ("top right", "top left", "bottom right", "bottom left")
SIZE = 12.0  # width of the logo, in percent of the width of the picture
MARGIN = 0.025  # space to the edges, as a share of the width


def picture(logo, corner, size, width, height, output):
    """Write the transparent picture with the logo in its corner; returns where the logo lies."""
    from PIL import Image
    if corner not in CORNERS:
        raise DavarError(_("the corner can be: {choices}").format(choices=", ".join(CORNERS)))
    if not 3 <= size <= 40:
        raise DavarError(_("the logo's width must be between 3 and 40 percent of the picture."))
    try:
        mark = Image.open(logo).convert("RGBA")
    except OSError:
        raise DavarError(_("the logo could not be opened: {path}").format(path=logo))
    shown_w = round(width * size / 100)
    shown_h = max(round(mark.height * shown_w / mark.width), 1)
    mark = mark.resize((shown_w, shown_h), Image.LANCZOS)
    margin = round(width * MARGIN)
    x = width - margin - shown_w if "right" in corner else margin
    y = margin if "top" in corner else height - margin - shown_h
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    canvas.alpha_composite(mark, (x, y))
    canvas.save(output)
    return (x, y, x + shown_w, y + shown_h)


def place(video, logo, corner="top right", size=SIZE, folder=None):
    """Put the logo in a corner of the Rough Cut timeline of the video (or of a timeline of the
    whole video when it has none). The titles on it stay."""
    video = Path(video)
    if not logo or not Path(logo).is_file():
        raise DavarError(_("choose the logo file first."))
    target = Path(folder) if folder else video.parent
    info = video_info(video)
    cut = target / (video.stem + "_cut.fcpxml")
    known = roughcut.read_timeline(cut, video, info)
    output, label, in_cut = cut, "cut", True
    if known is None:
        output, label, in_cut = target / (video.stem + "_titles.fcpxml"), "titles", False
        known = roughcut.read_timeline(output, video, info) or {
            "parts": [(0, info["frames"])], "overlays": [], "framings": None, "still": None, "markers": []}
    still = target / (video.stem + "_logo.png")
    box = picture(logo, corner, size, info["width"], info["height"], still)
    roughcut.write_fcpxml(output, video, info, known["parts"], label=label, overlays=known["overlays"],
                          framings=known["framings"], still=still, markers=known["markers"])
    return {"output": output, "picture": still, "corner": corner, "box": box, "in_cut": in_cut}


def report(r):
    names = {"top right": _("top right"), "top left": _("top left"), "bottom right": _("bottom right"),
             "bottom left": _("bottom left")}
    return "\n".join([
        _("Logo         : {corner} corner, {width} pixels wide, from the start to the end").format(
            corner=names[r["corner"]], width=r["box"][2] - r["box"][0]),
        _("Placed on the Rough Cut timeline, on a track of its own above the titles.") if r["in_cut"]
        else _("No Rough Cut timeline was found for this video, so a timeline of the whole video was written."),
        _("Timeline written: {path}").format(path=r["output"]),
        _("In Resolve: File → Import → Timeline…"), two_microphones_note()])
