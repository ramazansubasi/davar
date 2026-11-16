"""Remembers the settings between sessions, so that nothing has to be entered twice.

Two kinds of settings are kept in the settings file (~/.davar/settings.json):

    defaults   the value last used, whatever the video: thresholds, ticked options ...
    videos     the values that belong to one video: trim times, output folder ...

A video that Davar wrote from another one (`talk_picture.mp4` from `talk.mp4`) starts with
the values of the video it was made from. This module only looks after the stored dict;
reading and filling the window is done in davar_gui.pyw.
"""

import os
import time
from pathlib import Path

KEPT_VIDEOS = 200  # beyond this the videos not used for the longest time are forgotten
DERIVED = ("_picture", "_audio")  # what Davar adds to the name of a video it writes
NOT_INHERITED = ("audio.clips",)  # already placed in the video that was made from the first


def key(path):
    """One spelling for one file, whatever the case and the slashes."""
    return os.path.normcase(os.path.abspath(str(path)))


def fits(value, like):
    """Whether a stored value may stand where `like` stands. The file may have been edited
    by hand or written by another version, so nothing in it is trusted."""
    if isinstance(like, bool):
        return isinstance(value, bool)
    if isinstance(like, (int, float)):
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if isinstance(like, list):
        return isinstance(value, list) and all(isinstance(v, str) for v in value)
    return isinstance(value, type(like))


def chosen(stored, prefix, initial):
    """`initial` with every stored value that fits put in its place.
    `prefix` is the page's name and a dot, as the values are stored."""
    return {name: stored[prefix + name] if fits(stored.get(prefix + name), value) else value
            for name, value in initial.items()}


def sources(stem):
    """Names of the videos this one may have been made from, nearest first:
    talk_audio_picture -> talk_audio, talk."""
    found = []
    while True:
        ending = next((e for e in DERIVED if stem.lower().endswith(e) and len(stem) > len(e)), None)
        if ending is None:
            return found
        stem = stem[:-len(ending)]
        found.append(stem)


def _videos(settings):
    videos = settings.get("videos")
    if not isinstance(videos, dict):
        return {}
    return {k: r for k, r in videos.items() if isinstance(r, dict) and isinstance(r.get("values"), dict)}


def video_values(settings, path):
    """The values stored for a video, or else those of the video it was made from, or else None."""
    videos = _videos(settings)
    record = videos.get(key(path))
    if record is not None:
        return dict(record["values"])
    folder = key(Path(path).parent)
    for stem in sources(Path(path).stem):
        for stored, record in videos.items():
            values = record["values"]
            written_to = values.get("folder")
            near = (key(Path(stored).parent) == folder
                    or (isinstance(written_to, str) and written_to.strip() and key(written_to) == folder))
            if near and Path(stored).stem == os.path.normcase(stem):
                return {name: value for name, value in values.items() if name not in NOT_INHERITED}
    return None


def store_video(settings, path, values, touch=False, now=None):
    """Keep a video's values. `touch` marks it as just used; the videos used longest ago are dropped."""
    videos = _videos(settings)
    old = videos.get(key(path))
    now = time.time() if now is None else now
    videos[key(path)] = {"path": str(path),
                         "used": now if touch or old is None else old.get("used", now),
                         "values": {**(old["values"] if old else {}), **values}}
    by_age = sorted(videos, key=lambda k: videos[k]["used"] if isinstance(videos[k].get("used"), (int, float)) else 0)
    for forgotten in by_age[:max(len(by_age) - KEPT_VIDEOS, 0)]:
        del videos[forgotten]
    settings["videos"] = videos
