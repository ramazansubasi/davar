"""davar speakers - tells who is speaking when, from the colour of each voice.

No names are known here: the voices are numbered in the order they first speak. It
works on recordings where the voices differ clearly (two or three people around a
microphone) and is meant for coarse questions such as "where does the guest first
speak?"; the moment a turn changes is only known to within a few seconds.

How: the voice colour (cepstrum) of every three seconds of speech is measured, the
measurements are gathered into as many groups as there are speakers, and the result is
smoothed in time, since people speak in turns and not in fragments.

Two people with a microphone each, recorded on the two channels of the camera, are told
apart surer and more exactly: whoever speaks is much louder on their own microphone than
on the other's, so each word of the transcript is given to the louder one (see who_speaks).
"""

import numpy as np

from common import SAMPLE_RATE, WINDOW, DavarError, video_info
from i18n import _
from roughcut import audio_levels, auto_threshold, is_filler_sound

FRAME, HOP = 400, 160  # 25 ms frames every 10 ms
BANDS, COEFFICIENTS = 40, 20
LENGTH, STEP = 3.0, 1.0  # seconds of speech measured together, and how far apart
JOINED_GAP = 0.35  # words closer than this are one stretch of speech
SWITCH_COST = 12.0  # how unwilling the smoothing is to change speaker between two measurements
SURE_TURN = 8.0  # a turn this long is trusted when the voices are learnt a second time
SHORTEST_TURN = 4.0  # shorter ones are slips or interjections; they join a neighbour
FEWEST_MEASUREMENTS = 12  # per speaker; with less speech the voices cannot be told apart
APART = 6.0  # dB; one channel this much louder than the other is the microphone of whoever speaks
APART_SHARE = 0.6  # of the speech is that much louder on one of them when the two are two microphones
EACH_SHARE = 0.05  # and each of them is the louder one in at least this much of it
WORD_MARGIN = 4.0  # dB; a word is given to a microphone this much louder than the other


def voice_colour(samples):
    """Cepstrum and level in dB of every 10 ms frame."""
    def mel(f):
        return 2595 * np.log10(1 + f / 700)
    edges = 700 * (10 ** (np.linspace(mel(60), mel(7600), BANDS + 2) / 2595) - 1)
    bins = np.fft.rfftfreq(512, 1 / SAMPLE_RATE)
    bank = np.zeros((BANDS, len(bins)), np.float32)
    for band in range(BANDS):
        low, middle, high = edges[band:band + 3]
        bank[band] = np.clip(np.minimum((bins - low) / (middle - low), (high - bins) / (high - middle)), 0, None)
    transform = np.cos(np.pi / BANDS * (np.arange(BANDS) + 0.5)[None, :]
                       * np.arange(1, COEFFICIENTS + 1)[:, None]).astype(np.float32)
    window = np.hanning(FRAME).astype(np.float32)
    count = max(1 + (len(samples) - FRAME) // HOP, 0)
    colour, level = np.empty((count, COEFFICIENTS), np.float32), np.empty(count, np.float32)
    for first in range(0, count, 20000):
        last = min(first + 20000, count)
        frames = samples[np.arange(first, last)[:, None] * HOP + np.arange(FRAME)[None, :]] * window
        power = np.abs(np.fft.rfft(frames, 512)) ** 2
        colour[first:last] = np.log(power @ bank.T + 1e-8) @ transform.T
        level[first:last] = 10 * np.log10(power.sum(1) + 1e-10)
    return colour, level


def measurements(colour, level, words, language="tr"):
    """One measurement of the voice for every few seconds of speech: (vectors, their time spans).

    Only the loud frames inside real words count. Hesitation sounds are left out: a
    drawn-out "uh" sounds much the same whoever makes it.
    """
    usable = np.zeros(len(colour), bool)
    stretches = []
    for word, start, end in words:
        if not is_filler_sound(word, language):
            usable[int(start * 100):int(end * 100)] = True
        if stretches and start - stretches[-1][1] < JOINED_GAP:
            stretches[-1][1] = end
        else:
            stretches.append([start, end])
    vectors, spans = [], []
    for start, end in stretches:
        moment = start
        while moment < end - 0.6:
            first, last = int(moment * 100), min(int(min(moment + LENGTH, end) * 100), len(colour))
            chosen = usable[first:last].copy()
            if chosen.sum() >= 40:
                chosen &= level[first:last] > np.percentile(level[first:last][chosen], 40)
                if chosen.sum() >= 25:
                    part = colour[first:last][chosen]
                    vectors.append(np.concatenate([part.mean(0), part.std(0)]))
                    spans.append((moment, min(moment + LENGTH, end)))
            moment += STEP
    return np.array(vectors, np.float32), spans


def _groups(vectors, count):
    """Centres of `count` groups (k-means); the best of a few fixed starts, so the result repeats."""
    best = None
    for seed in range(8):
        centres = vectors[np.random.default_rng(seed).choice(len(vectors), count, replace=False)]
        for _round in range(60):
            distance = ((vectors[:, None] - centres[None]) ** 2).sum(2)
            nearest = distance.argmin(1)
            moved = np.array([vectors[nearest == g].mean(0) if (nearest == g).any() else centres[g]
                              for g in range(count)])
            if np.allclose(moved, centres):
                break
            centres = moved
        spread = distance.min(1).sum()
        if best is None or spread < best[0]:
            best = (spread, centres)
    return best[1]


def _smooth(vectors, spans, centres):
    """The likeliest speaker of every measurement when changing speaker has a cost (Viterbi)."""
    count = len(centres)
    cost = ((vectors[:, None] - centres[None]) ** 2).sum(2)
    best, back = cost[0].copy(), np.zeros((len(vectors), count), int)
    for i in range(1, len(vectors)):
        pause = spans[i][0] - spans[i - 1][1]
        change = (SWITCH_COST if pause < 1.0 else SWITCH_COST / 3) * (1 - np.eye(count))  # likelier after a pause
        arriving = best[:, None] + change
        back[i] = arriving.argmin(0)
        best = arriving.min(0) + cost[i]
    path = np.empty(len(vectors), int)
    path[-1] = best.argmin()
    for i in range(len(vectors) - 1, 0, -1):
        path[i - 1] = back[i, path[i]]
    return path


def _turns(spans, path):
    """Join neighbouring measurements of the same speaker: [start, end, speaker, measurement indexes]."""
    turns = []
    for i, ((start, end), who) in enumerate(zip(spans, path)):
        if turns and turns[-1][2] == who:
            turns[-1][1] = end
            turns[-1][3].append(i)
        else:
            turns.append([start, end, int(who), [i]])
    return turns


def join_short_turns(turns, shortest=SHORTEST_TURN):
    """Give every turn shorter than `shortest` to its longer neighbour, the shortest first, so
    that a slip inside a short turn does not take the turn with it. Turns are (start, end, speaker)."""
    turns = [list(t[:3]) for t in turns]
    while len(turns) > 1:
        n = min(range(len(turns)), key=lambda i: turns[i][1] - turns[i][0])
        if turns[n][1] - turns[n][0] >= shortest:
            break
        beside = [m for m in (n - 1, n + 1) if 0 <= m < len(turns)]
        into = max(beside, key=lambda m: turns[m][1] - turns[m][0])
        turns[into][0], turns[into][1] = min(turns[into][0], turns[n][0]), max(turns[into][1], turns[n][1])
        del turns[n]
        joined = []
        for turn in turns:  # the two neighbours may now be the same speaker
            if joined and joined[-1][2] == turn[2]:
                joined[-1][1] = turn[1]
            else:
                joined.append(turn)
        turns = joined
    return [tuple(t) for t in turns]


def find_turns(samples, words, count, language="tr"):
    """Who speaks when: a list of (start, end, speaker), the speakers numbered from 0 in the
    order they first speak. `words` is the transcript; `count` the number of people speaking."""
    if not words:
        raise DavarError(_("run Transcribe first; the speakers are told apart with the help of the transcript."))
    if count < 2:
        return [(words[0][1], words[-1][2], 0)]
    colour, level = voice_colour(samples)
    vectors, spans = measurements(colour, level, words, language)
    if len(vectors) < FEWEST_MEASUREMENTS * count:
        raise DavarError(_("there is too little speech to tell the speakers apart."))
    vectors = (vectors - vectors.mean(0)) / (vectors.std(0) + 1e-6)
    path = _smooth(vectors, spans, _groups(vectors, count))
    for _round in range(2):  # learn each voice again from its long turns only, where it is surely alone
        sure = np.array([i for start, end, _who, indexes in _turns(spans, path) if end - start >= SURE_TURN
                         for i in indexes], int)
        if not all((path[sure] == g).sum() >= 5 for g in range(count)):
            break
        path = _smooth(vectors, spans, np.array([vectors[sure][path[sure] == g].mean(0) for g in range(count)]))
    return _numbered(join_short_turns(_turns(spans, path)))


def _numbered(turns):
    """Number the speakers of (start, end, speaker) turns from 0 in the order they first speak."""
    order = list(dict.fromkeys(who for _start, _end, who in turns))
    return [(float(start), float(end), order.index(who)) for start, end, who in turns]


def own_microphones(levels):
    """Whether two channels (their levels in dB for every 10 ms, shape (n, 2)) are two
    microphones, each close to one of two speakers: most of the speech is much louder on one
    of them, and each is the louder one some of the time. Not so for the same sound on both
    channels, a stereo microphone, or two microphones of which only one is used."""
    if levels is None or len(levels) == 0:
        return False
    loudest = np.max(levels, axis=1)
    heard = loudest > auto_threshold(loudest)[0]
    if heard.sum() < 100:
        return False
    apart = levels[heard, 0] - levels[heard, 1]
    return bool((np.abs(apart) >= APART).mean() >= APART_SHARE
                and min((apart >= APART).mean(), (apart <= -APART).mean()) >= EACH_SHARE)


def turns_by_microphone(levels, words):
    """Who speaks when, read from two microphones (see own_microphones): each word goes to the
    microphone on which it is louder, and the turns are smoothed as find_turns smooths them.
    A word heard about as loud on both stays with the speaker before it."""
    loudest = np.max(levels, axis=1)
    heard = loudest > auto_threshold(loudest)[0]
    apart = levels[:, 0] - levels[:, 1]
    turns = []
    for _text, start, end in words:
        first = int(start / WINDOW)
        last = max(int(end / WINDOW), first + 1)
        loud = heard[first:last]
        who = None
        if loud.any():
            middle = float(np.median(apart[first:last][loud]))
            who = 0 if middle >= WORD_MARGIN else 1 if middle <= -WORD_MARGIN else None
        if who is None or (turns and turns[-1][2] == who):
            if turns:
                turns[-1][1] = end
        else:
            turns.append([start, end, who])
    if not turns:
        raise DavarError(_("there is too little speech to tell the speakers apart."))
    return _numbered(join_short_turns(turns))


def who_speaks(video, words, count, language="tr", samples=None, microphones=None):
    """Who speaks when, as find_turns gives it. Two people with a microphone each on the two
    channels of the recording are told apart by their microphones, word by word; otherwise
    by their voices. `samples` and `microphones` are the audio as audio_levels gives it, when
    it has been read already; without `samples` the audio of `video` is read here."""
    if not words:
        raise DavarError(_("run Transcribe first; the speakers are told apart with the help of the transcript."))
    if samples is None:
        if count == 2 and video_info(video)["audio_channels"] == 2:
            samples, _db, microphones = audio_levels(video, microphones=True)
        else:
            samples, _db = audio_levels(video)
    if count == 2 and own_microphones(microphones):
        return turns_by_microphone(microphones, words)
    return find_turns(samples, words, count, language)
