"""davar rhythm - the pauses of finished episodes, turned into Rough Cut settings.

Every programme has a rhythm of its own: how long a speaker is left silent between two
phrases, and how long a pause may run before it is cut. Rather than guess the three
silence settings of Rough Cut, they can be measured on episodes already finished and
published, whether cut by hand or by Davar and checked by ear.

A pause is a stretch below the silence threshold between two sounds, 0.05 seconds or
longer. Most are the short breaks inside a sentence; those of 0.2 seconds or more fall
between phrases, and their usual (median) length is what a cut pause is shortened to.
95 out of 100 pauses are shorter than the longest one kept; a longer one is cut.

The idea of shortening long pauses to the measured median, two thirds of it after the
speech and one third before, comes from ffmpeg-skill (MIT) by Shogo Kajiyama.
"""

from pathlib import Path

import numpy as np

from common import WINDOW, DavarError
from i18n import _

PAUSE = 0.05  # seconds; a shorter dip is a break inside a word
PHRASE = 0.2  # seconds; a pause this long falls between two phrases
LONGEST = 95  # percent of pauses that are shorter than the longest one kept
FRAMES_LEFT = 0.05  # seconds a cut leaves on top of its padding, as it lands on whole frames
FEWEST = 30  # pauses between phrases needed for a measurement


def pauses(db, threshold):
    """Lengths in seconds of the pauses between two sounds: stretches below `threshold`
    lasting PAUSE or longer, leaving out the silence at the very start and end."""
    quiet = np.asarray(db) < threshold
    if not quiet.any():
        return np.zeros(0)
    changes = np.flatnonzero(np.diff(quiet.astype(np.int8)))
    bounds = np.concatenate(([0], changes + 1, [len(quiet)]))
    return np.array([(end - start) * WINDOW for start, end in zip(bounds[:-1], bounds[1:])
                     if quiet[start] and start > 0 and end < len(quiet) and (end - start) * WINDOW >= PAUSE])


def settings(found):
    """Rough Cut settings that give a cut the rhythm of these pause lengths:
    dict of min_silence, pad_before, pad_after (seconds), with the measured "phrase" and "longest"."""
    found = np.asarray(found)
    between = found[found >= PHRASE]
    if len(between) < FEWEST:
        raise DavarError(_("too few pauses to measure a rhythm ({n}); choose longer or more episodes.").format(
            n=len(between)))
    phrase, longest = float(np.median(between)), float(np.percentile(found, LONGEST))
    keep = min(max(phrase - FRAMES_LEFT, 0.05), 0.75)  # what is left of a pause that is cut
    return {"phrase": phrase, "longest": longest,
            "min_silence": round(min(max(longest, keep + 0.1, 0.2), 2.0), 2),
            "pad_before": round(keep / 3, 2), "pad_after": round(keep * 2 / 3, 2)}


def measure(paths, progress=None):
    """Measure the pauses of finished episodes; returns the Rough Cut settings (see settings)
    with "files": each episode's name, minutes and its own phrase pause and longest pause."""
    import roughcut  # imported here: it is large and only needed when measuring

    paths = [Path(p) for p in paths]
    if not paths:
        raise DavarError(_("choose at least one finished episode."))
    every, files = [], []
    for n, path in enumerate(paths):
        if progress:
            progress(n, len(paths), path.name)
        if not path.is_file():
            raise DavarError(_("file not found: {path}").format(path=path))
        _samples, db = roughcut.audio_levels(path)
        found = pauses(db, roughcut.auto_threshold(db)[0])
        between = found[found >= PHRASE]
        files.append({"name": path.name, "minutes": len(db) * WINDOW / 60, "pauses": len(found),
                      "phrase": float(np.median(between)) if len(between) else None,
                      "longest": float(np.percentile(found, LONGEST)) if len(found) else None})
        every.append(found)
    result = settings(np.concatenate(every))
    result["files"] = files
    return result


def report(r):
    """The measurement as readable text."""
    lines = [_("Rhythm of finished episodes:")]
    for f in r["files"]:
        lines.append("  " + _("{name}: {minutes:.0f} min, {pauses} pauses; between phrases {phrase}, "
                              "longest kept {longest}").format(
            name=f["name"], minutes=f["minutes"], pauses=f["pauses"],
            phrase=f"{f['phrase']:.2f} {_('s')}" if f["phrase"] is not None else "-",
            longest=f"{f['longest']:.2f} {_('s')}" if f["longest"] is not None else "-"))
    lines.append(_("A pause between phrases lasts {phrase:.2f} s; 95 in 100 pauses are shorter than {longest:.2f} s.")
                 .format(phrase=r["phrase"], longest=r["longest"]))
    lines.append(_("Set: shortest silence {min:.2f} s, padding before a word {before:.2f} s, after a word "
                   "{after:.2f} s. A longer silence is cut down to about {kept:.2f} s.").format(
        min=r["min_silence"], before=r["pad_before"], after=r["pad_after"],
        kept=r["pad_before"] + r["pad_after"] + FRAMES_LEFT))
    return "\n".join(lines)
