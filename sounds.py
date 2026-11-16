"""davar sounds - finds throat clearing with a sound model, for the listener to check.

A throat being cleared in the middle of speech is hard to tell from speech by its level
or its pitch, and the transcript often writes a word over it. Google's YAMNet, a model
trained on two million sound clips, describes every second of sound with 1024 numbers;
a small classifier trained on throat clearings marked by ear (models/throat_clearing.json)
picks the most likely moments from those numbers. What exactly to cut is found by trying:
the shortest stretch between two dips of the level whose removal leaves the model hearing
no throat clearing. They become unticked candidates in the Rough Cut list: only a listener
decides.

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
SEARCH = 0.8  # seconds on each side of a place searched for where its sound begins and ends
SHORTEST = 0.15  # seconds


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


def open_model(model):
    """A function that gives the YAMNet descriptions of a piece of sound."""
    try:
        import onnxruntime
    except ImportError:
        raise DavarError(_("the sound model needs onnxruntime. Install it with: pip install onnxruntime"))
    session = onnxruntime.InferenceSession(str(model), providers=["CPUExecutionProvider"])
    name = session.get_inputs()[0].name
    return lambda audio: session.run(None, {name: np.asarray(audio, np.float32)})[1]


def describe(samples, run, progress=None):
    """Start times and YAMNet descriptions (1024 numbers) of the sound, one every 0.12 s.
    `run` is what open_model gives."""
    samples = np.asarray(samples, np.float32)
    piece = SAMPLE_RATE * 60  # a minute at a time, with a second more so nothing is lost at the joins
    hop = int(STEP * SAMPLE_RATE)
    starts, found = [], []
    total = len(OFFSETS) * max(math.ceil(len(samples) / piece), 1)
    done = 0
    for offset in OFFSETS:
        for first in range(int(offset * SAMPLE_RATE), len(samples), piece):
            described = run(samples[first:first + piece + SAMPLE_RATE])
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


def edges(db, threshold, start, end):
    """Where the sound may be cut between `start` and `end` (seconds): the two ends and every dip
    of the level, a moment quieter than the 30 ms around it and either silent or 6 dB below the
    loudest moment of the 150 ms on each side. Syllables, and a throat being cleared, lie between dips."""
    first, last = max(int(start / WINDOW), 0), min(int(end / WINDOW), len(db))
    found = [first]
    for i in range(first + 3, last - 3):
        if db[i] > db[i - 3:i + 4].min():
            continue
        left, right = db[max(i - 15, 0):i].max(), db[i:i + 15].max()
        if (db[i] < threshold or (left - db[i] >= 6 and right - db[i] >= 6)) and i - found[-1] >= 4:
            found.append(i)
    if last - found[-1] < 4:
        found.pop()
    return [i * WINDOW for i in found + [last]]


def narrow(samples, db, threshold, start, end, hears):
    """The stretch to cut for a place pinned between `start` and `end`, or None.

    Every stretch between two dips near the place is tried: it is taken out of the three
    seconds around the place and `hears(audio)` says how surely a throat is still being cleared
    in what is left. The shortest stretch whose removal brings that below LIKELY is the one;
    so nothing of the words around it is cut.
    """
    middle = (start + end) / 2
    cuts = edges(db, threshold, middle - SEARCH, middle + SEARCH)
    low = max(int((middle - 1.5) * SAMPLE_RATE), 0)
    high = min(int((middle + 1.5) * SAMPLE_RATE), len(samples))
    tried = []
    for i, first in enumerate(cuts):
        for last in cuts[i + 1:i + 6]:
            if not SHORTEST - 0.03 <= last - first <= 0.8 or last < start - 0.25 or first > end + 0.25:
                continue
            a, b = int(first * SAMPLE_RATE), int(last * SAMPLE_RATE)
            left = hears(np.concatenate([samples[low:a], samples[b:high]]))
            tried.append((left, last - first, round(first, 2), round(last, 2)))
    gone = [t for t in tried if t[0] < LIKELY]
    if not gone:
        return None
    _left, _length, first, last = min(gone, key=lambda t: (t[1], t[0]))
    return first, last


def find_throat_clearing(samples, db, threshold, usable=lambda moment: True, progress=None):
    """Likely throat clearings as (start, end, score), about PER_HOUR an hour, best first.
    A place whose throat clearing cannot be cut out cleanly is not offered."""
    def step(share, text):
        if progress:
            progress(share, text)

    model = ensure_model(lambda share: step(0.3 * share, _("Downloading the sound model (16 MB, only once)")))
    run = open_model(model)
    starts, descriptions = describe(samples, run, lambda share: step(0.3 + 0.6 * share,
                                                                     _("Listening for throat clearing")))
    weights, bias = classifier()
    hours = len(samples) / SAMPLE_RATE / 3600
    found = places(starts, score(descriptions, weights, bias), max(int(round(hours * PER_HOUR)), 3), usable)
    step(0.9, _("Finding where each throat clearing begins and ends"))
    result = []
    for start, end, best in found:
        stretch = narrow(samples, db, threshold, start, end, lambda audio: float(score(run(audio), weights, bias).max()))
        if stretch is not None:
            result.append((*stretch, best))
    return result
