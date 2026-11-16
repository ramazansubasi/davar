"""Interface language. Source strings are English; other languages are lookup tables.

    from i18n import _
    print(_("Finished"))

To add a language, create lang_<code>.py with a TRANSLATIONS dict (see lang_tr.py)
and add it to LANGUAGES below.
"""

import importlib
import json
import locale
import os
from pathlib import Path

LANGUAGES = {"en": "English", "tr": "Türkçe"}
# how the operating system may name each language (Windows says "Turkish_Türkiye", Linux "tr_TR")
SYSTEM_NAMES = {"tr": ("tr", "turkish", "türk")}
_current = "en"
_table = {}


def settings_path():
    return Path.home() / ".davar" / "settings.json"


def load_settings():
    try:
        settings = json.loads(settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return settings if isinstance(settings, dict) else {}


def save_settings(settings):
    """Write the whole settings file. Written beside it first and then swapped in, so that a
    crash in the middle cannot leave half a file."""
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    draft = path.with_name(path.name + ".tmp")
    draft.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(draft, path)


def save_setting(key, value):
    settings = load_settings()
    settings[key] = value
    save_settings(settings)


def default_language():
    """The saved choice, or else the system language when Davar speaks it, or else English."""
    saved = load_settings().get("language")
    if saved in LANGUAGES:
        return saved
    try:
        system = (locale.getlocale()[0] or "").lower()
    except ValueError:
        system = ""
    return next((code for code, names in SYSTEM_NAMES.items() if system.startswith(names)), "en")


def set_language(code, remember=False):
    global _current, _table
    if code not in LANGUAGES:
        code = "en"
    _current = code
    _table = {} if code == "en" else importlib.import_module(f"lang_{code}").TRANSLATIONS
    if remember:
        save_setting("language", code)


def language():
    return _current


def _(text):
    """Translate a source string into the current interface language."""
    return _table.get(text, text)


def N_(text):
    """Mark a string for translation without translating it yet (for class-level constants)."""
    return text


set_language(default_language())
