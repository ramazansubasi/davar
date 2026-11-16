"""davar sounds - finds throat clearing with a sound model, for the listener to check.

A throat being cleared in the middle of speech is hard to tell from speech by its level
or its pitch, and the transcript often writes a word over it. Google's YAMNet, a model
trained on two million sound clips, describes every second of sound with 1024 numbers;
a small classifier trained on throat clearings marked by ear (models/throat_clearing.json)
picks the most likely moments from those numbers. They become unticked candidates in the
Rough Cut list: only a listener decides.

YAMNet (Apache 2.0) is downloaded once, on first use, and checked against its fingerprint.
It runs with onnxruntime, which comes with faster-whisper.
"""

import hashlib
import json
import math
import urllib.request
from pathlib import Path

import numpy as np

from common import SAMPLE_RATE, WINDOW, DavarError
from i18n import _

MODEL_URL = ("https://huggingface.co/audiomagic/yamnet-onnx/resolve/"
             "f25b741c2f0bdc6d7e6db24b5fddda23347dbafd/yamnet.onnx")
MODEL_SHA256 = "d3835ffbbd4a1bb3e777f0ca217b5007907f5171dd5d17c4236b95b2af8f908e"
MODEL_SIZE = 16093355
LISTEN = 0.96  # seconds of sound behind each description
STEP = 0.48  # how far apart the model describes the sound
OFFSETS = (0.0, 0.12, 0.24, 0.36)  # run four times, shifted, for a description every 0.12 s
PER_HOUR = 25  # places offered for an hour of video, at most
LIKELY = 0.5  # and only places the classifier finds at least this likely
PLACE_GAP = 2.0  # seconds; places closer than this are one
REACH = 0.6  # seconds a found sound may reach on each side of where it was pinned
SHORTEST = 0.15  # seconds
BRIDGE = 0.1  # seconds; a dip in the level shorter than this does not end a sound


def model_path():
    return Path.home() / ".davar" / "models" / "yamnet.onnx"


def _fingerprint(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def ensure_model(progress=None):
    """The path of the sound model, downloaded first if it is not there yet."""
    path = model_path()
    if path.is_file() and path.stat().st_size == MODEL_SIZE:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    draft = path.with_name(path.name + ".part")
    try:
        with urllib.request.urlopen(MODEL_URL, timeout=60) as response, open(draft, "wb") as out:
            done = 0
            while True:
                block = response.read(1 << 16)
                if not block:
                    break
                out.write(block)
                done += len(block)
                if progress:
                    progress(min(done / MODEL_SIZE, 1.0))
    except OSError as e:
        draft.unlink(missing_ok=True)
        raise DavarError(_("the sound model could not be downloaded: {message}").format(message=e))
    if draft.stat().st_size != MODEL_SIZE or _fingerprint(draft) != MODEL_SHA256:
        draft.unlink(missing_ok=True)
        raise DavarError(_("the downloaded sound model is not the expected file, so it was not used."))
    draft.replace(path)
    return path


def classifier():
    """(weights, bias) of the throat clearing classifier that comes with Davar."""
    data = json.loads((Path(__file__).resolve().parent / "models" / "throat_clearing.json").read_text(encoding="utf-8"))
    return np.array(data["weights"], np.float32), float(data["bias"])


def describe(samples, model, progress=None):
    """Start times and YAMNet descriptions (1024 numbers) of the sound, one every 0.12 s."""
    try:
        import onnxruntime
    except ImportError:
        raise DavarError(_("the sound model needs onnxruntime. Install it with: pip install onnxruntime"))
    session = onnxruntime.InferenceSession(str(model), providers=["CPUExecutionProvider"])
    name = session.get_inputs()[0].name
    samples = np.asarray(samples, np.float32)
    piece = SAMPLE_RATE * 60  # a minute at a time, with a second more so nothing is lost at the joins
    hop = int(STEP * SAMPLE_RATE)
    starts, found = [], []
    total = len(OFFSETS) * max(math.ceil(len(samples) / piece), 1)
    done = 0
    for offset in OFFSETS:
        for first in range(int(offset * SAMPLE_RATE), len(samples), piece):
            described = session.run(None, {name: samples[first:first + piece + SAMPLE_RATE]})[1]
            for k, row in enumerate(described):
                if k * hop < piece or first + piece >= len(samples):
                    starts.append((first + k * hop) / SAMPLE_RATE)
                    found.append(row)
            done += 1
            if progress:
                progress(done / total)
    order = np.argsort(starts)
    return np.array(starts)[order], np.array(found, np.float32)[order]


def score(descriptions, weights, bias):
    """How likely each description is to be a throat being cleared, 0 to 1."""
    return 1.0 / (1.0 + np.exp(-(descriptions @ weights + bias)))


def places(starts, scores, count, usable=lambda moment: True):
    """At most `count` likely places, at least PLACE_GAP apart, as (pinned start, pinned end, score).

    Each description hears a whole second, so a sound shows in several overlapping ones; the
    sound lies where the strongest of them overlap, which pins it more closely than any one does.
    """
    centres = starts + LISTEN / 2
    chosen = []
    for k in np.argsort(scores)[::-1]:
        if len(chosen) >= count or scores[k] < LIKELY:
            break
        moment = centres[k]
        if not usable(moment) or any(abs(moment - c[3]) < PLACE_GAP for c in chosen):
            continue
        near = np.flatnonzero(np.abs(centres - moment) <= 1.2)
        strong = near[scores[near] >= 0.7 * scores[k]]
        start, end = starts[strong].max(), (starts[strong] + LISTEN).min()
        if end <= start:
            start = end = moment
        chosen.append((float(start), float(end), float(scores[k]), float(moment)))
    return [(start, end, best) for start, end, best, _moment in sorted(chosen)]


def widen(start, end, db, threshold, words=(), is_filler=lambda text: False):
    """Grow a pinned place to the whole sound: up to silence, to the next or previous real word,
    or REACH seconds, whichever comes first."""
    first, last = start - REACH, end + REACH
    for text, word_start, word_end in words:
        if is_filler(text):
            continue
        if word_end <= start + 0.05:
            first = max(first, word_end)
        if word_start >= end - 0.05:
            last = min(last, word_start)
    def reach(k, direction, limit):
        """Step outward while there is sound; a dip shorter than BRIDGE does not end it."""
        edge, quiet = k, 0
        while 0 <= k + direction < len(db) and (k + direction) * WINDOW * direction <= limit * direction + 1e-9:
            k += direction
            quiet = quiet + 1 if db[k] <= threshold else 0
            if quiet > BRIDGE / WINDOW:
                break
            if not quiet:
                edge = k
        return edge
    start = max(reach(int(start / WINDOW), -1, first) * WINDOW, first)
    end = min((reach(int(end / WINDOW), 1, last) + 1) * WINDOW, last)
    if end - start < SHORTEST:
        middle = (start + end) / 2
        start, end = middle - SHORTEST / 2, middle + SHORTEST / 2
    return round(start, 2), round(end, 2)


def find_throat_clearing(samples, db, threshold, words=(), is_filler=lambda text: False,
                         usable=lambda moment: True, progress=None):
    """Likely throat clearings as (start, end, score), about PER_HOUR an hour, best first."""
    def step(share, text):
        if progress:
            progress(share, text)

    model = ensure_model(lambda share: step(0.3 * share, _("Downloading the sound model (16 MB, only once)")))
    starts, descriptions = describe(samples, model, lambda share: step(0.3 + 0.7 * share,
                                                                       _("Listening for throat clearing")))
    weights, bias = classifier()
    hours = len(samples) / SAMPLE_RATE / 3600
    found = places(starts, score(descriptions, weights, bias), max(int(round(hours * PER_HOUR)), 3), usable)
    return [(*widen(start, end, db, threshold, words, is_filler), best) for start, end, best in found]
