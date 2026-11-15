"""davar dictionary - fixes the words the speech model keeps getting wrong.

The personal dictionary is the file .davar/dictionary.txt in the user's home
folder. Each line reads "wrong = right":

    tuzda = Tuzla
    Akbörse = Akköse
    top sen = TÜPSAN

Corrections are applied every time a transcript is read, without changing the
saved file; a word added later also fixes transcripts made earlier.
"""

import re
from pathlib import Path

APOSTROPHES = "'’"


def _plain(word):
    from roughcut import plain  # imported late: roughcut does not depend on this module
    return plain(word)


def dictionary_path():
    return Path.home() / ".davar" / "dictionary.txt"


def load(path=None):
    """Read the dictionary as [(plain words of the wrong form, right form)], longest phrases first."""
    path = Path(path) if path else dictionary_path()
    try:
        rows = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    entries = {}
    for row in rows:
        row = row.split("#", 1)[0]
        if "=" not in row:
            continue
        wrong, right = (x.strip() for x in row.split("=", 1))
        key = tuple(_plain(w) for w in wrong.split() if _plain(w))
        if key and right:
            entries[key] = right
    return sorted(entries.items(), key=lambda e: -len(e[0]))


def add(pairs, path=None):
    """Append (wrong, right) pairs to the dictionary file; an existing key is updated."""
    path = Path(path) if path else dictionary_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        rows = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        rows = ["# Davar personal dictionary. Each line: wrong = right"]
    for wrong, right in pairs:
        key = tuple(_plain(w) for w in wrong.split())
        rows = [r for r in rows
                if "=" not in r or tuple(_plain(w) for w in r.split("#")[0].split("=")[0].split()) != key]
        rows.append(f"{wrong.strip()} = {right.strip()}")
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return path


def split_word(word):
    """ "Akbörse'nin," -> (stem "Akbörse", suffix "'nin", punctuation ",")"""
    match = re.match(r"^(.*?)([^\w]*)$", word, re.S)
    body, punctuation = match.group(1), match.group(2)
    for i, char in enumerate(body):
        if char in APOSTROPHES and i > 0:
            return body[:i], body[i:], punctuation
    return body, "", punctuation


def apply(words, entries=None):
    """Apply the dictionary to a word list; return (new list, number of corrections).

    A suffix after an apostrophe ("'nin") and trailing punctuation are kept. When a
    wrong form of several words becomes one word, their times are merged.
    """
    entries = load() if entries is None else entries
    if not entries:
        return [list(w) for w in words], 0
    stems = [_plain(split_word(w[0])[0]) for w in words]
    result, count, i = [], 0, 0
    while i < len(words):
        for key, right in entries:
            n = len(key)
            if tuple(stems[i:i + n]) != key:
                continue
            # words inside a phrase must carry no suffix ("top'un sen" does not match)
            if any(split_word(words[j][0])[1] for j in range(i, i + n - 1)):
                continue
            _stem, suffix, punctuation = split_word(words[i + n - 1][0])
            result.append([right + suffix + punctuation, words[i][1], words[i + n - 1][2]])
            count += 1
            i += n
            break
        else:
            result.append(list(words[i]))
            i += 1
    return result, count
