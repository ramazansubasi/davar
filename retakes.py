"""davar retakes - finds repeated words, restarted sentences and talk about the recording.

Three things a speaker says that an editor usually takes out, found in the transcript:

- **Repeats.** The same word or words said twice in a row ("rahat konuşun rahat konuşun"),
  or a word broken off and said again whole ("yayın yayından"). The first one goes.
- **Restarts.** A sentence begun, dropped after a pause or an "uh", and begun again with a
  different ending ("ve 24 tane politika başkanı … ve 24 tane politika başkan yardımcısı").
  The dropped beginning goes.
- **Retake talk.** What is said to the crew rather than to the viewer: "baştan alıyorum",
  "bunu keseriz", "kayıttayız". When the words after it were already said a little earlier,
  the whole take between is offered; otherwise the sentence holding it.

Speech repeats itself on purpose too ("Her ikisi de … Her ikisi de …", "kaybede kaybede"),
and a transcript cannot tell the two apart. So these are only suggestions for a listener:
they arrive unticked in the Rough Cut list. The rules were tuned on two programmes whose
editor's own cuts were known.
"""

import difflib
import re

from roughcut import is_filler_sound, plain

LOOK_AHEAD = 7  # words; how far ahead a repeat of a word is searched
SENTENCE_GAP = 0.7  # seconds of quiet that end a sentence for retake talk
LONGEST_SENTENCE = 10.0  # seconds before retake talk taken as its sentence
SENTENCE_AFTER = 3.0  # and seconds after it: what follows is often the new take
TAKE_BACK = 120.0  # seconds; how far back the beginning of an abandoned take is searched
PAUSE = 0.3  # seconds; a pause this long before a repeat makes a restart likely

# Words too common to say anything when repeated once.
COMMON = {
    "tr": set("bir bu ve de da ki o şu ne çok daha en hep iyi ya yani şey işte gibi için ama evet tamam "
              "ben sen biz siz onlar tabii tabi hayır".split()),
    "en": set("a an the and or but so to of in on at it is be i you we they he she that this yes no "
              "well like just very really".split()),
}
# Turkish says some words twice on purpose: "yavaş yavaş", "tek tek", "kaybede kaybede".
DOUBLED_ON_PURPOSE = set("yavaş tek ayrı kat yer zaman sık bol teker birer ikişer adım sıra kapı ev göz "
                         "again very".split())
# Talk about the recording. Matched against the words without punctuation, lowercased.
CUES = {
    "tr": re.compile(r"(baştan al\w*|başa al\w*|tekrar al\w*|bir daha al\w*|keser\w*|kesebilir\w*|"
                     r"kayıttayız|kayıt\w* başla\w*|kapattın\w*|başlıyor musun|çekiyor mu\w*|"
                     r"yeniden başla\w*|kamerayı kapat\w*)\b"),
    "en": re.compile(r"(let me start (again|over)|start (again|over)|from the top|take two|"
                     r"(well|we will|you can|we can) cut (this|that)|cut that|are we recording|is it recording)\b"),
}
# Of those, the ones after which the new take begins at once: nothing after them is cut.
STARTS_AGAIN = re.compile(r"(baştan|başa|tekrar|bir daha|yeniden|let me start|start|from the top|take two)")


def similar(a, b):
    """Two plain words that are the same, one broken off from the other, or nearly the same."""
    if a == b:
        return True
    if min(len(a), len(b)) >= 3 and (a.startswith(b) or b.startswith(a)):
        return True
    return min(len(a), len(b)) >= 4 and difflib.SequenceMatcher(None, a, b).ratio() >= 0.8


def _repeats(spoken, words, language):
    """Repeats and restarts as (first, last, kind, confidence) over the indexes in `spoken`."""
    common = COMMON.get(language, COMMON["en"])
    text = [plain(words[k][0]) for k in spoken]
    found = []
    i = 0
    while i < len(spoken):
        best = None
        for j in range(i + 1, min(i + LOOK_AHEAD + 1, len(spoken))):
            m = 0  # how many words from i are said again from j
            while j + m < len(spoken) and i + m < j and similar(text[i + m], text[j + m]):
                m += 1
            if m == 0:
                continue
            letters = sum(len(text[i + k]) for k in range(m))
            gap = words[spoken[j]][1] - words[spoken[j - 1]][2]
            hesitated = any(is_filler_sound(w[0], language) for w in words[spoken[i]:spoken[j]])
            paused = gap >= PAUSE or hesitated
            if j - i == m:  # said again straight away
                if m == 1:
                    a, b = text[i], text[j]
                    broken_off = a != b and b.startswith(a)
                    if a in common or len(a) < 4:
                        continue
                    if not broken_off and not paused and (a in DOUBLED_ON_PURPOSE or a[-1] in "ae"):
                        continue  # "kaybede kaybede", "sallaya sallaya": doubled on purpose
                elif letters < 6:
                    continue
                confidence = "medium"
            elif j - i <= m + 2 and m >= 2 and letters >= 8:
                # begun again with a different ending: only when the first try was not a whole
                # sentence ("Her ikisi de kul hakkıdır. Her ikisi de …" is said on purpose)
                if any(words[k][0].rstrip()[-1:] in ".?!" for k in spoken[i:j]):
                    continue
                if not (paused or m >= 3):
                    continue
                confidence = "low"
            else:
                continue
            if best is None or m > best[1]:
                best = (j, m, confidence)
        if best:
            j, m, confidence = best
            found.append((spoken[i], spoken[j], "repeat", confidence))
            i = j
        else:
            i += 1
    return found


def _sentence(spoken, words, k, n, forward=True):
    """The words around spoken[k:k+n] up to a sentence end or a pause: (first, last) indexes.
    With `forward` false the sentence ends with those words."""
    first = k
    while (first > 0 and words[spoken[k]][1] - words[spoken[first - 1]][1] <= LONGEST_SENTENCE
           and words[spoken[first - 1]][0].rstrip()[-1:] not in ".?!"
           and words[spoken[first]][1] - words[spoken[first - 1]][2] < SENTENCE_GAP):
        first -= 1
    last = k + n  # exclusive
    while (forward and last < len(spoken) and words[spoken[last]][2] - words[spoken[k + n - 1]][2] <= SENTENCE_AFTER
           and words[spoken[last - 1]][0].rstrip()[-1:] not in ".?!"
           and words[spoken[last]][1] - words[spoken[last - 1]][2] < SENTENCE_GAP):
        last += 1
    return first, last


def _retake_talk(spoken, words, language):
    """Talk about the recording as (first, last, kind, confidence)."""
    cues = CUES.get(language)
    if cues is None:
        return []
    text = [plain(words[k][0]) for k in spoken]
    found = []
    k = 0
    while k < len(spoken):
        match = cues.match(" ".join(text[k:k + 4]))
        if not match:
            k += 1
            continue
        n = len(match.group(0).split())
        while True:  # "kamerayı kapatıyorum, baştan alıyoruz": one after another
            more = cues.match(" ".join(text[k + n:k + n + 4]))
            if not more:
                break
            n += len(more.group(0).split())
        first, last = _sentence(spoken, words, k, n, not STARTS_AGAIN.match(" ".join(text[k + n - 2:k + n])))
        # "baştan alıyorum, geçtiğimiz günlerde…": if those words were said a little earlier,
        # the take that was abandoned starts there
        after = text[k + n:k + n + 2]
        if len(after) == 2 and len("".join(after)) >= 6:
            for p in range(k - 2, -1, -1):
                if words[spoken[k]][1] - words[spoken[p]][1] > TAKE_BACK:
                    break
                if similar(text[p], after[0]) and similar(text[p + 1], after[1]):
                    first, last = p, k + n
                    break
        found.append((spoken[first], spoken[last - 1] + 1, "retake", "low" if first < k - 30 else "medium"))
        k = last
    return found


def find_retakes(words, language="tr"):
    """Repeats, restarts and retake talk in a transcript, for a listener to check.

    `words` is the transcript's list of (text, start, end). Returns (start, end, first, last,
    kind, confidence): the seconds offered for cutting, and words first..last-1 inside them.
    A repeat's cut ends where the second try begins. Kind is "repeat" for repeats and
    restarts, "retake" for talk about the recording.
    """
    spoken = [k for k, w in enumerate(words) if plain(w[0]) and not is_filler_sound(w[0], language)]
    found = _repeats(spoken, words, language) + _retake_talk(spoken, words, language)
    found.sort()
    merged = []
    for item in found:  # retake talk said twice in one breath is one candidate
        if merged and item[0] < merged[-1][1] and item[2] == merged[-1][2] == "retake":
            merged[-1] = (merged[-1][0], max(merged[-1][1], item[1]), "retake", merged[-1][3])
        else:
            merged.append(item)
    return [(words[first][1], words[last][1] if kind == "repeat" else words[last - 1][2], first, last, kind,
             confidence) for first, last, kind, confidence in merged]
