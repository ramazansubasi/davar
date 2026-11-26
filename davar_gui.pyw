"""davar interface - pick a workflow on the left, a video at the top, and start.

Opened by double-clicking Davar.bat. The real work lives in audio.py, transcript.py,
roughcut.py, titles.py and clips.py.

To add a workflow: write a class derived from Page (build, missing, read_settings,
run, result_text) and add it to the PAGES list near the bottom. Name its settings in
`general` and `per_video` and they are remembered between sessions (see memory.py).
"""

import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import wave
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ai  # noqa: E402
import audio  # noqa: E402
import clips  # noqa: E402
import content  # noqa: E402
import dictionary  # noqa: E402
import i18n  # noqa: E402
import logo as corner_logo  # noqa: E402
import memory  # noqa: E402
import picture  # noqa: E402
import rhythm  # noqa: E402
import roughcut  # noqa: E402
import speakers  # noqa: E402
import titles  # noqa: E402
import topics  # noqa: E402
import transcript  # noqa: E402
from common import (SAMPLE_RATE, VERSION, DavarError, format_time, parse_ranges,  # noqa: E402
                    parse_time, run, video_info)
from i18n import N_, _  # noqa: E402

try:
    import winsound  # for playing candidates; Windows only
except ImportError:
    winsound = None

BACKGROUND = "#0F131A"
PANEL = "#161B24"
CARD = "#1C2330"
BORDER = "#2A3342"
FIELD = "#0F131A"
TEXT = "#E8ECF2"
MUTED = "#8C97A8"
RED = "#E30613"
RED_DARK = "#B80510"
ACCENT = "#FF7880"
CUT = "#FF4B55"  # the sound or word that will be cut
AMBER = "#F2B84B"  # low confidence
SPEECH_LANGUAGES = ["tr", "en", "de", "fr", "es", "it", "pt", "nl", "ru", "ar"]


def font_ok():
    """Whether the brand's Montserrat is there for the topic titles."""
    return topics.font_path("ExtraBold")[1]


def media_types():
    return [(_("Video and audio files"), "*.mp4 *.mov *.mkv *.avi *.mts *.m4v *.webm *.wav *.mp3"),
            (_("All files"), "*.*")]


class Held:
    """A setting that is not a tk variable (a list of files, a text box) but is read and
    filled like one, so that it can be remembered with the others."""

    def __init__(self, get, set):
        self.get, self.set = get, set


class Page(ttk.Frame):
    """One workflow's page. The video, output folder, progress bar and log are shared
    (they sit at the top and bottom of the application); a page holds only its own settings.
    """

    name = ""  # shown in the menu
    description = ""
    ready = True  # False for a workflow that is not written yet
    needs_video = True  # False if it can also run without a selected video
    key = ""  # the page's name in the settings file
    general = ()  # settings remembered as last used, whatever the video
    per_video = ()  # settings remembered with the video they were entered for

    def __init__(self, parent, app, number):
        super().__init__(parent, style="Panel.TFrame", padding=(28, 22))
        self.app = app
        top = ttk.Frame(self, style="Panel.TFrame")
        top.pack(fill="x")
        left = ttk.Frame(top, style="Panel.TFrame")
        left.pack(side="left")
        ttk.Label(left, text=_("WORKFLOW") + f"  /  {number:02d}", style="Tag.TLabel").pack(anchor="w")
        ttk.Label(left, text=_(self.name), style="Title.TLabel").pack(anchor="w", pady=(4, 0))
        if self.ready:  # the button sits at the top so it stays visible however long the settings grow
            self.start_button = ttk.Button(top, text=_("Start"), style="Main.TButton", command=self._start)
            self.start_button.pack(side="right")
            if self.general:
                ttk.Button(top, text=_("Back to defaults"), command=self._back_to_defaults).pack(
                    side="right", padx=(0, 10))
            self.status = ttk.Label(top, text="", style="PanelMuted.TLabel")
            self.status.pack(side="right", padx=14)
        ttk.Label(self, text=_(self.description), style="PanelMuted.TLabel", wraplength=760,
                  justify="left").pack(anchor="w", pady=(4, 14))
        self.build(self._scroll_area())
        self.initial = self.values(self.general + self.per_video)  # what a fresh page shows
        for name in self.initial:
            if isinstance(getattr(self, name), tk.Variable):
                getattr(self, name).trace_add("write", lambda *_args: self.app.remember_soon())

    def _scroll_area(self):
        """The area holding the settings; scrolls with the mouse wheel when it does not fit."""
        canvas = tk.Canvas(self, bg=PANEL, highlightthickness=0, bd=0)
        bar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas, style="Panel.TFrame")
        window = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=bar.set)
        canvas.pack(side="left", fill="both", expand=True)

        def fits():
            return inner.winfo_reqheight() <= canvas.winfo_height()

        def refresh(_event=None):
            canvas.configure(scrollregion=(0, 0, inner.winfo_reqwidth(), inner.winfo_reqheight()))
            if fits():
                bar.pack_forget()
                canvas.yview_moveto(0)
            elif not bar.winfo_ismapped():
                bar.pack(side="right", fill="y", padx=(8, 0))

        def wheel(event):
            if not fits():
                canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

        inner.bind("<Configure>", refresh)
        canvas.bind("<Configure>", lambda e: (canvas.itemconfigure(window, width=e.width), refresh()))
        self.bind("<Enter>", lambda _e: self.bind_all("<MouseWheel>", wheel))
        self.bind("<Leave>", lambda _e: self.unbind_all("<MouseWheel>"))
        return inner

    # --- for subclasses to fill in ---------------------------------------------
    def build(self, parent):
        """Place the workflow's own settings inside `parent`."""

    def missing(self):
        """Return a description of what stops it from starting, or "" when it can start."""
        return ""

    def read_settings(self):
        """Return the settings as a dict; raise ValueError for an invalid value."""
        return {}

    def run(self, settings, progress):
        """Do the work (called in the background); return a dict that contains "output"."""

    def result_text(self, result):
        return ""

    def finish(self, result):
        """Called in the main window when the work is done; may ask the user something and
        change the result. Returning None means the work was cancelled."""
        return result

    # --- remembered settings -----------------------------------------------------
    def values(self, names):
        """The current value of each named setting. One that cannot be read at the moment
        (a number box in the middle of being typed in) is left out."""
        found = {}
        for name in names:
            try:
                found[name] = getattr(self, name).get()
            except (tk.TclError, KeyError):
                pass
        return found

    def set_values(self, values):
        for name, value in values.items():
            getattr(self, name).set(value)
        self.refresh_state()

    def _back_to_defaults(self):
        """The settings shared by every video go back to what Davar starts with. What belongs to
        the video (trim times and the like) stays."""
        self.set_values({name: self.initial[name] for name in self.general})

    # --- shared pieces ---------------------------------------------------------
    def card(self, parent, variable, title, description=""):
        """A card with a title. With `variable` the title becomes a checkbox and the
        settings inside are greyed out while it is unticked."""
        card = ttk.Frame(parent, style="Card.TFrame", padding=(16, 12))
        card.pack(fill="x", pady=(0, 10))
        if variable is not None:
            ttk.Checkbutton(card, text=title, variable=variable,
                            style="CardTitle.TCheckbutton").pack(anchor="w")
        else:
            ttk.Label(card, text=title, style="CardTitle.TLabel").pack(anchor="w")
        indent = 26 if variable is not None else 0
        if description:
            ttk.Label(card, text=description, style="CardMuted.TLabel", wraplength=700,
                      justify="left").pack(anchor="w", padx=(indent, 0))
        body = ttk.Frame(card, style="Card.TFrame")
        body.pack(fill="x", padx=(indent, 0))
        if variable is not None:
            def toggle(*_args):
                for w in body.winfo_children():
                    if isinstance(w, (ttk.Spinbox, ttk.Entry, ttk.Checkbutton, ttk.Scale)):
                        w.configure(state="normal" if variable.get() else "disabled")
            variable.trace_add("write", toggle)
            variable.trace_add("write", lambda *_args: self.refresh_state())
        return body

    def seconds_row(self, body, row, label, variable, low, high, hint):
        ttk.Label(body, text=label, style="Card.TLabel").grid(
            row=row, column=0, sticky="w", padx=(0, 12), pady=(8, 0))
        ttk.Spinbox(body, textvariable=variable, from_=low, to=high, increment=0.05,
                    width=6, format="%.2f").grid(row=row, column=1, sticky="w", pady=(8, 0))
        ttk.Label(body, text=_("s"), style="Card.TLabel").grid(
            row=row, column=2, sticky="w", padx=(6, 14), pady=(8, 0))
        ttk.Label(body, text=hint, style="CardMuted.TLabel").grid(row=row, column=3, sticky="w", pady=(8, 0))
        body.columnconfigure(3, weight=1)  # extra width of wide rows goes to the last column

    def check_row(self, body, row, variable, label, hint):
        ttk.Checkbutton(body, text=label, variable=variable, style="Card.TCheckbutton").grid(
            row=row, column=0, sticky="w", pady=(8, 0))
        ttk.Label(body, text=hint, style="CardMuted.TLabel").grid(
            row=row, column=1, sticky="w", padx=(14, 0), pady=(8, 0))

    def refresh_state(self):
        if not self.ready:
            return
        if self.app.busy:
            self.start_button.configure(state="disabled")
            return
        no_video = self.needs_video and not self.app.video.get().strip()
        reason = _("Choose a video at the top first") if no_video else self.missing()
        self.start_button.configure(state="disabled" if reason else "normal")
        self.status.configure(text=reason)

    def _start(self):
        try:
            settings = self.read_settings()
        except (tk.TclError, ValueError):
            self.app.log(_("One of the number boxes holds something that is not a number."), error=True)
            return
        except DavarError as e:
            self.app.log(_("Failed: {message}").format(message=e), error=True)
            return
        self.app.start_job(self, settings)


class AudioPage(Page):
    name = N_("Audio")
    description = N_("Puts separately recorded audio in its place in the video and sets the loudness. "
                     "The picture is not re-encoded; the result is written as a new video and the next "
                     "steps continue with it.")
    key = "audio"
    general = ("normalize", "balance", "denoise")
    per_video = ("clips",)

    def build(self, parent):
        self.normalize = tk.BooleanVar(value=True)
        self.balance = tk.BooleanVar(value=False)
        self.denoise = tk.BooleanVar(value=False)
        self.files = []
        self.clips = Held(lambda: [str(path) for path in self.files], self._set_files)

        g = self.card(parent, None, _("Separately recorded audio"),
                      _("A lavalier microphone, an audio recorder or parts recorded afterwards. Davar finds "
                        "by itself where each one belongs in the video, matches its level to the video's "
                        "audio and replaces the video's audio there. Audio that does not occur in the "
                        "video is not placed."))
        row = ttk.Frame(g, style="Card.TFrame")
        row.pack(fill="x", pady=(8, 0))
        self.listbox = tk.Listbox(row, height=4, bg=FIELD, fg=TEXT, bd=0, highlightthickness=1,
                                  highlightbackground=BORDER, selectbackground="#36415A",
                                  selectforeground="white", activestyle="none", font=("Segoe UI", 10))
        self.listbox.pack(side="left", fill="x", expand=True)
        buttons = ttk.Frame(row, style="Card.TFrame")
        buttons.pack(side="left", padx=(10, 0), anchor="n")
        ttk.Button(buttons, text=_("Add…"), command=self._browse).pack(fill="x")
        ttk.Button(buttons, text=_("Remove"), command=self._remove).pack(fill="x", pady=(6, 0))

        g = self.card(parent, None, _("Loudness"))
        for row, (variable, label, hint) in enumerate((
                (self.normalize, _("Bring to YouTube loudness"),
                 _("Sets the audio to -14 LUFS; fixes audio that is too quiet or too loud")),
                (self.balance, _("Balance the speakers' levels"), _("Raises the quiet speaker; check by ear")),
                (self.denoise, _("Reduce background noise"), _("Lowers hum and hiss; check by ear")))):
            self.check_row(g, row, variable, label, hint)
            variable.trace_add("write", lambda *_args: self.refresh_state())

        self.card(parent, None, _("Coming next"),
                  _("For recordings where each speaker has their own microphone: lowering the bleed "
                    "that reaches the microphone of the person who is not speaking."))

    def _browse(self):
        start = self.app.video_path().parent if self.app.video.get().strip() else None
        types = [(_("Audio and video files"), "*.wav *.mp3 *.m4a *.aac *.ogg *.flac *.mp4 *.mov *.mkv"),
                 (_("All files"), "*.*")]
        for path in filedialog.askopenfilenames(title=_("Choose the separate audio files"), filetypes=types,
                                                initialdir=start if start and start.is_dir() else None):
            self.add(path)

    def add(self, path):
        path = Path(os.path.normpath(path))
        if path not in self.files:
            self.files.append(path)
            self.listbox.insert("end", path.name)
        self.refresh_state()
        self.app.remember_soon()

    def _remove(self):
        for i in reversed(self.listbox.curselection()):
            self.listbox.delete(i)
            del self.files[i]
        self.refresh_state()
        self.app.remember_soon()

    def _set_files(self, paths):
        """Replace the list; a remembered file that is no longer there is dropped."""
        self.files.clear()
        self.listbox.delete(0, "end")
        for path in paths:
            if Path(path).is_file():
                self.add(path)

    def missing(self):
        if not (self.files or self.normalize.get() or self.balance.get() or self.denoise.get()):
            return _("Add an audio file or tick an operation")
        return ""

    def read_settings(self):
        return dict(video=self.app.video_path(), clips=list(self.files), folder=self.app.output_folder(),
                    normalize=self.normalize.get(), balance=self.balance.get(), denoise=self.denoise.get())

    def run(self, settings, progress):
        return audio.process(progress=progress, **settings)

    def finish(self, result):
        self.app.continue_with(result["output"])  # the next steps should work on the new video
        self.clips.set([])  # they are in the new video now
        return result

    def result_text(self, result):
        return (audio.report(result) + "\n"
                + _("The video field now points to this new file; the next steps work on it."))


class PicturePage(Page):
    name = N_("Picture")
    description = N_("Reframes the video to 16:9 and holds a tripod shot still. The picture is re-encoded and "
                     "written as a new video; the audio is not touched, so a transcript already made stays "
                     "valid. The next steps continue with the new video.")
    key = "picture"
    general = ("reframe", "position", "lock")

    def build(self, parent):
        self.reframe = tk.BooleanVar(value=True)
        self.position = tk.DoubleVar(value=50)
        self.lock = tk.BooleanVar(value=True)

        g = self.card(parent, self.reframe, _("Reframe to 16:9"),
                      _("Cuts the sides of a picture wider than 16:9 (most phones), or the top and bottom of "
                        "a narrower one, so that it fills the YouTube frame with no black bars."))
        ttk.Label(g, text=_("Position of the frame"), style="Card.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 12), pady=(8, 0))
        ttk.Spinbox(g, textvariable=self.position, from_=0, to=100, increment=5, width=6).grid(
            row=0, column=1, sticky="w", pady=(8, 0))
        ttk.Label(g, text=_("0 = keep the left (or top) edge, 50 = middle, 100 = keep the right (or bottom) edge"),
                  style="CardMuted.TLabel").grid(row=0, column=2, sticky="w", padx=(14, 0), pady=(8, 0))

        self.card(parent, self.lock, _("Lock the frame (tripod shots)"),
                  _("A phone on a tripod still makes the picture pump and hop while it hunts for focus, and "
                    "the frame creeps over a long recording. Every frame is lined up with one reference "
                    "frame, so the background stands perfectly still and cuts show less. The blur of the "
                    "moment the focus slips stays. Only for a camera that does not move. Needs OpenCV.\n"
                    "It takes one to two times the length of the video; the time left is shown at the bottom."))

    def missing(self):
        if not (self.reframe.get() or self.lock.get()):
            return _("Tick an operation")
        return ""

    def read_settings(self):
        return dict(video=self.app.video_path(), folder=self.app.output_folder(),
                    aspect="16:9" if self.reframe.get() else None, position=float(self.position.get()),
                    lock=self.lock.get())

    def run(self, settings, progress):
        return picture.process(progress=progress, **settings)

    def finish(self, result):
        self.app.continue_with(result["output"])  # the next steps should work on the new video
        return result

    def result_text(self, result):
        return (picture.report(result) + "\n"
                + _("The video field now points to this new file; the next steps work on it."))


class TranscribePage(Page):
    name = N_("Transcribe")
    description = N_("Transcribes the speech once, word by word with timing, and saves it next to the "
                     "video. The later workflows use this; the same video is not transcribed again.")
    key = "transcribe"
    general = ("srt", "text", "model")  # the speech language is kept apart: other pages read it too

    def build(self, parent):
        settings = i18n.load_settings()
        self.srt = tk.BooleanVar(value=True)
        self.text = tk.BooleanVar(value=True)
        self.model = tk.StringVar(value="small")
        self.speech = tk.StringVar(value=settings.get("speech_language", "tr"))
        self.force = tk.BooleanVar(value=False)

        g = self.card(parent, None, _("Status"))
        self.saved_status = ttk.Label(g, text="", style="Card.TLabel", wraplength=700, justify="left")
        self.saved_status.pack(anchor="w", pady=(6, 0))
        row = ttk.Frame(g, style="Card.TFrame")
        row.pack(anchor="w", pady=(10, 0))
        self.edit_button = ttk.Button(row, text=_("Edit the text…"), command=self._edit_text)
        self.edit_button.pack(side="left")
        ttk.Button(row, text=_("Open the dictionary"), command=self._open_dictionary).pack(side="left", padx=(8, 0))
        ttk.Label(row, text=_("Dictionary: teach a word that is always misspelt once, then it fixes itself"),
                  style="CardMuted.TLabel").pack(side="left", padx=(12, 0))

        g = self.card(parent, None, _("Transcription"),
                      _("Runs on your computer; nothing is sent to the internet. It can take about half "
                        "the length of the video; the model is downloaded on first use."))
        ttk.Label(g, text=_("Speech language"), style="Card.TLabel").grid(row=0, column=0, sticky="w", pady=(10, 0))
        box = ttk.Frame(g, style="Card.TFrame")
        box.grid(row=0, column=1, sticky="w", padx=(14, 0), pady=(10, 0))
        ttk.Combobox(box, textvariable=self.speech, values=SPEECH_LANGUAGES, width=9).pack(side="left")
        ttk.Label(box, text="  " + _("language code of the speech: tr, en, de …"),
                  style="CardMuted.TLabel").pack(side="left")
        ttk.Label(g, text=_("Accuracy"), style="Card.TLabel").grid(row=1, column=0, sticky="w", pady=(10, 0))
        box = ttk.Frame(g, style="Card.TFrame")
        box.grid(row=1, column=1, sticky="w", padx=(14, 0), pady=(10, 0))
        ttk.Combobox(box, textvariable=self.model, values=["base", "small", "medium"],
                     width=9, state="readonly").pack(side="left")
        ttk.Label(box, text="  " + _("base is fast but error-prone · small is balanced · medium is the "
                                     "most accurate and very slow"),
                  style="CardMuted.TLabel").pack(side="left")
        ttk.Checkbutton(g, text=_("Transcribe again even if a transcript is saved"), variable=self.force,
                        style="Card.TCheckbutton").grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 0))

        g = self.card(parent, None, _("Extra files"), _("Made from the transcript; nothing is transcribed again."))
        self.check_row(g, 0, self.srt, _("Subtitle file (.srt)"), _("Uploaded in YouTube Studio → Subtitles"))
        self.check_row(g, 1, self.text, _("Time-stamped text (.txt)"), _("Each line starts with [minute:second]"))

    def missing(self):
        saved = self.app.transcript()
        if saved:
            self.saved_status.configure(
                text=_("A transcript is saved for this video: {words} words, model {model}. "
                       "Start will only write the extra files.").format(words=len(saved["words"]),
                                                                       model=saved["model"]))
        else:
            self.saved_status.configure(text=_("This video has not been transcribed yet."))
        self.edit_button.configure(state="normal" if saved and not self.app.busy else "disabled")
        return ""

    def _edit_text(self):
        saved = self.app.transcript()
        if saved:
            window = TranscriptWindow(self.app, saved, self.app.video_path())
            if window.summary:
                self.app.log(window.summary)
            self.refresh_state()

    def _open_dictionary(self):
        path = dictionary.dictionary_path()
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# Davar personal dictionary. Each line: wrong = right\n"
                            "# Example:\n# tuzda = Tuzla\n# top sen = TÜPSAN\n", encoding="utf-8")
        if hasattr(os, "startfile"):
            os.startfile(path)  # opens in Notepad
        self.app.log(_("Dictionary file: {path}").format(path=path) + "\n"
                     + _("Each line: wrong = right. Once saved it applies to every transcript, new and old."))

    def read_settings(self):
        language = self.speech.get().strip().lower() or "tr"
        i18n.save_setting("speech_language", language)
        return dict(video=self.app.video_path(), folder=self.app.output_folder(), srt=self.srt.get(),
                    text=self.text.get(), model=self.model.get(), language=language, force=self.force.get())

    def run(self, settings, progress):
        return transcript.transcribe(progress=progress, **settings)

    def result_text(self, result):
        return transcript.report(result)


class RoughCutPage(Page):
    name = N_("Rough Cut")
    description = N_("Finds silences, “uh / um” hesitations and the filler words you choose, and prepares "
                     "a trimmed timeline for DaVinci Resolve. The original video is not touched. "
                     "In Resolve: File → Import → Timeline…")
    key = "rough_cut"
    general = ("silence", "hesitations", "noises", "throat", "retakes", "review_file", "mark_joins", "ask", "min_silence", "pad_before",
               "pad_after", "min_hesitation", "fillers", "punch", "closeup", "every")
    per_video = ("keep_from", "keep_to", "remove")

    def build(self, parent):
        self.silence = tk.BooleanVar(value=True)
        self.hesitations = tk.BooleanVar(value=True)
        self.noises = tk.BooleanVar(value=True)
        self.throat = tk.BooleanVar(value=False)
        self.retakes = tk.BooleanVar(value=True)
        self.review_file = tk.BooleanVar(value=False)
        self.mark_joins = tk.BooleanVar(value=True)
        self.ask = tk.BooleanVar(value=True)
        self.min_silence = tk.DoubleVar(value=0.5)
        self.pad_before = tk.DoubleVar(value=0.10)
        self.pad_after = tk.DoubleVar(value=0.15)
        self.min_hesitation = tk.DoubleVar(value=0.30)
        self.fillers = tk.StringVar()
        self.punch = tk.BooleanVar(value=False)
        self.closeup = tk.DoubleVar(value=round(roughcut.CLOSE_UP * 100))
        self.every = tk.DoubleVar(value=roughcut.CHANGE_EVERY)
        self.keep_from = tk.StringVar()
        self.keep_to = tk.StringVar()
        self.remove = tk.StringVar()

        g = self.card(parent, None, _("Trim the start, the end and takes in between"),
                      _("Drops what was recorded before the programme starts and after it ends, and any "
                        "range in the middle such as a repeated take. Leave a box empty to trim nothing there."))
        ttk.Label(g, text=_("Programme starts at"), style="Card.TLabel").grid(row=0, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(g, textvariable=self.keep_from, width=10).grid(row=0, column=1, sticky="w", padx=(12, 20), pady=(8, 0))
        ttk.Label(g, text=_("Programme ends at"), style="Card.TLabel").grid(row=0, column=2, sticky="w", pady=(8, 0))
        box = ttk.Frame(g, style="Card.TFrame")
        box.grid(row=0, column=3, sticky="w", pady=(8, 0))
        ttk.Entry(box, textvariable=self.keep_to, width=10).pack(side="left", padx=(12, 14))
        ttk.Label(box, text=_("minute:second, e.g. 13:06"), style="CardMuted.TLabel").pack(side="left")
        ttk.Label(g, text=_("Also remove"), style="Card.TLabel").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(g, textvariable=self.remove).grid(row=1, column=1, columnspan=3, sticky="ew", padx=(12, 0), pady=(8, 0))
        g.columnconfigure(3, weight=1)
        row = ttk.Frame(g, style="Card.TFrame")
        row.grid(row=2, column=0, columnspan=4, sticky="w", pady=(8, 0))
        self.excerpt_button = ttk.Button(row, text=_("Show the start and end of the transcript"),
                                         command=self._show_excerpt)
        self.excerpt_button.pack(side="left")
        ttk.Label(row, text=_("ranges as start-end, separated by commas: 50:46-51:03, 12:00-12:30"),
                  style="CardMuted.TLabel").pack(side="left", padx=(12, 0))

        g = self.card(parent, self.silence, _("Cut silences"), _("Removes the gaps where nobody speaks."))
        self.seconds_row(g, 0, _("Shortest silence"), self.min_silence, 0.2, 2.0,
                         _("Shorter gaps are left alone"))
        self.seconds_row(g, 1, _("Padding before a word"), self.pad_before, 0.0, 0.5,
                         _("Raise it if word starts are clipped"))
        self.seconds_row(g, 2, _("Padding after a word"), self.pad_after, 0.0, 0.5,
                         _("Raise it if word ends are clipped"))
        row = ttk.Frame(g, style="Card.TFrame")
        row.grid(row=3, column=0, columnspan=4, sticky="w", pady=(10, 0))
        self.rhythm_button = ttk.Button(row, text=_("Take the rhythm of finished episodes…"),
                                        command=self._measure_rhythm)
        self.rhythm_button.pack(side="left")
        ttk.Label(row, text=_("measures their pauses and sets the three boxes above"),
                  style="CardMuted.TLabel").pack(side="left", padx=(12, 0))

        g = self.card(parent, self.hesitations, _("Find “uh / um” hesitations"),
                      _("Finds drawn-out thinking sounds from the audio itself."))
        self.seconds_row(g, 0, _("Shortest hesitation"), self.min_hesitation, 0.2, 1.0,
                         _("Lower it to catch more; wrong candidates increase"))

        self.card(parent, self.noises, _("Find coughs and other non-speech sounds"),
                  _("Coughs, throat clearing, loud breaths and clicks standing between silences. With a "
                    "transcript, a sound no word was written for is taken as non-speech; without one only "
                    "the noisy ones can be told apart."))

        self.card(parent, self.throat, _("Find throat clearing with the sound model"),
                  _("Also the throat clearing that runs into speech, which the rule above misses. A sound "
                    "model picks about 25 likely places an hour; they arrive unticked as “throat clearing? "
                    "(listen)”, and Show → Non-speech sounds lists them. The model (16 MB) is downloaded "
                    "once, on first use. It was trained on one programme; it may miss some or pick others."))

        self.card(parent, self.retakes, _("Find repeated words and talk about the recording"),
                  _("From the transcript: a word or a few said twice in a row, a sentence begun again after "
                    "a pause, and what is said to the crew (“baştan alıyorum”, “bunu keseriz”). They arrive "
                    "unticked as “repeated words? (listen)” and “talk about the recording? (listen)”, and "
                    "Show → Repeats and retakes lists them. Speech also repeats on purpose; only you can tell."))

        g = self.card(parent, None, _("Filler words"),
                      _("The speaker's verbal habits. Separate with commas: you know, like, I mean"))
        ttk.Entry(g, textvariable=self.fillers).pack(fill="x", pady=(8, 0))
        self.transcript_status = ttk.Label(g, text="", style="CardMuted.TLabel", wraplength=700, justify="left")
        self.transcript_status.pack(anchor="w", pady=(6, 0))

        g = self.card(parent, self.punch, _("Move closer to the speaker (hides jump cuts)"),
                      _("As with a second camera: during a long answer the picture moves closer to the speaker, "
                        "in quick exchanges it stays on everyone. Inside a long answer the framing changes now "
                        "and then, at the cut that jumps most; other cuts keep their framing. Who speaks is "
                        "found from the transcript; who sits where is taken from the Titles page."))
        for row, (label, variable, low, high, step, hint) in enumerate((
                (_("Closer framing"), self.closeup, 105, 140, 1,
                 _("percent of the picture; above 130 the picture grows soft")),
                (_("Change inside a long answer every"), self.every, 15, 120, 5, _("seconds")))):
            ttk.Label(g, text=label, style="Card.TLabel").grid(row=row, column=0, sticky="w", padx=(0, 12), pady=(8, 0))
            ttk.Spinbox(g, textvariable=variable, from_=low, to=high, increment=step, width=6,
                        format="%.0f").grid(row=row, column=1, sticky="w", pady=(8, 0))
            ttk.Label(g, text=hint, style="CardMuted.TLabel").grid(row=row, column=2, sticky="w", padx=(14, 0),
                                                                   pady=(8, 0))
        self.seating = ttk.Label(g, text="", style="CardMuted.TLabel", wraplength=680, justify="left")
        self.seating.grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))
        self.punch.set(False)  # let the card grey out its boxes

        g = self.card(parent, None, _("Applying"))
        ttk.Checkbutton(g, text=_("Show me the candidates before cutting"), variable=self.ask,
                        style="Card.TCheckbutton").pack(anchor="w", pady=(8, 0))
        ttk.Label(g, text=_("Hesitations and filler words arrive in a list; you can listen and change "
                            "their ticks. When off, only the confident ones are cut."),
                  style="CardMuted.TLabel", wraplength=680, justify="left").pack(anchor="w", padx=(26, 0))
        ttk.Checkbutton(g, text=_("Also write a review timeline"), variable=self.review_file,
                        style="Card.TCheckbutton").pack(anchor="w", pady=(8, 0))
        ttk.Label(g, text=_("A second timeline showing the cut candidates with one second before and "
                            "after each, for checking inside Resolve."),
                  style="CardMuted.TLabel", wraplength=680, justify="left").pack(anchor="w", padx=(26, 0))
        ttk.Checkbutton(g, text=_("Mark the joins to listen to"), variable=self.mark_joins,
                        style="Card.TCheckbutton").pack(anchor="w", pady=(8, 0))
        ttk.Label(g, text=_("A marker on the timeline wherever a cut goes through a word of the transcript "
                            "with sound at the join, where a word may be clipped. The log lists them too."),
                  style="CardMuted.TLabel", wraplength=680, justify="left").pack(anchor="w", padx=(26, 0))
        for variable in (self.fillers, self.keep_from, self.keep_to, self.remove):
            variable.trace_add("write", lambda *_args: self.refresh_state())

    def _measure_rhythm(self):
        """Measure the pauses of finished episodes chosen by the user and set the silence boxes."""
        start = self.app.video_path().parent if self.app.video.get().strip() else None
        paths = filedialog.askopenfilenames(title=_("Choose finished episodes"), filetypes=media_types(),
                                            initialdir=start if start and start.is_dir() else None)
        if not paths:
            return
        self.rhythm_button.configure(state="disabled")
        self.app.log(_("Measuring the rhythm of {n} episodes…").format(n=len(paths)))
        outcome = {}

        def work():
            try:
                outcome["result"] = rhythm.measure(paths)
            except DavarError as e:
                outcome["error"] = str(e)
            except Exception as e:  # shown in the log, like the errors of a workflow
                outcome["error"] = _("Unexpected error: {kind}: {message}").format(kind=type(e).__name__, message=e)

        def check():
            if worker.is_alive():
                self.after(300, check)
                return
            self.rhythm_button.configure(state="normal")
            if "error" in outcome:
                self.app.log(_("Failed: {message}").format(message=outcome["error"]), error=True)
                return
            r = outcome["result"]
            self.silence.set(True)
            self.min_silence.set(r["min_silence"])
            self.pad_before.set(r["pad_before"])
            self.pad_after.set(r["pad_after"])
            self.app.log(rhythm.report(r), tall=True)
        worker = threading.Thread(target=work, daemon=True)
        worker.start()
        self.after(300, check)

    def _trimming(self):
        return any(v.get().strip() for v in (self.keep_from, self.keep_to, self.remove))

    def _show_excerpt(self):
        """Write the first and last lines of the transcript to the log, to help choose trim times."""
        saved = self.app.transcript()
        if not saved:
            return
        rows = transcript.lines(saved["words"], language=saved.get("language", "tr"))
        head, tail = rows[:10], rows[-22:] if len(rows) > 32 else rows[10:]

        def show(part):
            return "\n".join(f"{format_time(b):>9}  {text}" for b, _e, text in part)
        self.app.log(_("Start of the transcript:") + "\n" + show(head) + "\n\n"
                     + _("End of the transcript:") + "\n" + show(tail), tall=True)

    def _filler_list(self):
        return [f.strip() for f in self.fillers.get().split(",") if f.strip()]

    def missing(self):
        saved = self.app.transcript()
        if saved:
            self.transcript_status.configure(
                text=_("Transcript found: hesitations will be checked against it and filler words can be searched."))
        else:
            self.transcript_status.configure(
                text=_("No transcript for this video: hesitations are found from the audio only and "
                       "filler words cannot be searched."))
        self.excerpt_button.configure(state="normal" if saved else "disabled")
        self.seating.configure(text=self._seating_text())
        if self._filler_list() and not saved:
            return _("Run Transcribe first to use filler words")
        if self.punch.get() and not saved:
            return _("Run Transcribe first to move closer to the speaker")
        if not (self.silence.get() or self.hesitations.get() or self.noises.get()
                or self._filler_list() or self._trimming()):
            return _("Tick at least one thing to cut")
        return ""

    def _seated(self):
        """The speakers written on the Titles page, in the order they first speak: (name, place)."""
        page = next((p for p in self.app.pages if isinstance(p, TitlesPage)), None)
        try:
            people = titles.parse_people(page._rows()) if page is not None else []
        except DavarError:
            people = []
        return [(person["name"], person["position"]) for person in people]

    def _seating_text(self):
        seated = self._seated()
        if not seated:
            return _("No speakers are written on the Titles page: two are assumed, and the closer framing "
                     "stays in the middle. Write them there as Name | Title | left to move toward the speaker.")
        names = {"left": _("left"), "right": _("right")}
        return _("Speakers from the Titles page: {list}").format(list=", ".join(
            f"{name} ({names.get(place, _('middle'))})" for name, place in seated))

    def read_settings(self):
        video = self.app.video_path()
        saved = self.app.transcript()
        seated = self._seated()
        return dict(
            output=self.app.output_folder() / (video.stem + "_cut.fcpxml"),
            review=self.review_file.get(), ask=self.ask.get(), mark_joins=self.mark_joins.get(),
            close_up=float(self.closeup.get()) / 100 if self.punch.get() else None,
            places=[place for _name, place in seated], speakers=len(seated) or 2,
            every=float(self.every.get()),
            analysis=dict(
                video=video, silence=self.silence.get(), hesitations=self.hesitations.get(),
                noises=self.noises.get(), throat=self.throat.get(), retakes=self.retakes.get() and bool(saved),
                min_silence=float(self.min_silence.get()), pad_before=float(self.pad_before.get()),
                pad_after=float(self.pad_after.get()), min_hesitation=float(self.min_hesitation.get()),
                words=saved["words"] if saved else None, filler_words=self._filler_list(),
                language=saved.get("language", "tr") if saved else "tr",
                keep_from=parse_time(self.keep_from.get()) if self.keep_from.get().strip() else None,
                keep_to=parse_time(self.keep_to.get()) if self.keep_to.get().strip() else None,
                remove=parse_ranges(self.remove.get())),
        )

    def run(self, settings, progress):
        state = roughcut.analyze(progress=progress, **settings["analysis"])
        if settings["close_up"] and state["words"]:  # done here, away from the window, as it takes a while
            progress(95, _("Listening for who speaks when"))
            state["turns"] = speakers.who_speaks(state["video"], state["words"], settings["speakers"],
                                                 state["language"], samples=state["samples"],
                                                 microphones=state.get("microphones"))
        return {"state": state, "settings": settings}

    def finish(self, result):
        state, settings = result["state"], result["settings"]
        if settings["ask"] and state["candidates"]:
            if not ReviewWindow(self.app, state).approved:
                return None
        return roughcut.apply(state, output=settings["output"], review=settings["review"],
                              close_up=settings["close_up"], places=settings["places"],
                              speakers=settings["speakers"], every=settings["every"],
                              mark_joins=settings["mark_joins"])

    def result_text(self, result):
        return roughcut.report(result, detailed=False)


def shown_in(view, candidate):
    """Whether a cut candidate belongs in a view of the review list."""
    return {"all": True,
            "ticked": candidate["selected"],
            "unticked": not candidate["selected"],
            "uncertain": candidate["confidence"] != "high",
            "sounds": candidate["kind"] in ("noise", "unknown", "throat"),
            "retakes": candidate["kind"] in ("repeat", "retake")}[view]


class ReviewWindow(tk.Toplevel):
    """The list of cut candidates: listen, change a tick, apply."""

    def __init__(self, app, state):
        super().__init__(app)
        self.state = state
        self.candidates = state["candidates"]
        self.suggested = [c["selected"] for c in self.candidates]
        self.approved = False
        self.temp = tempfile.TemporaryDirectory(prefix="davar_listen_")
        self.title("Davar — " + _("Rough Cut candidates"))
        self.configure(bg=PANEL)
        self.geometry("1200x680")
        self.minsize(1080, 460)
        self.transient(app)

        top = ttk.Frame(self, style="Panel.TFrame", padding=(18, 14, 18, 8))
        top.pack(fill="x")
        ttk.Label(top, text=_("Review the cut candidates"), style="Title.TLabel").pack(anchor="w")
        ttk.Label(top, text=_("Ticked ones will be cut. Double-click a row: listen. Click the first column "
                              "or press space: change the tick. Silences are not in this list; they are "
                              "cut directly.")
                  + ("" if state["has_transcript"] else "  " + _("There is no transcript, so no context text.")),
                  style="PanelMuted.TLabel", wraplength=1100, justify="left").pack(anchor="w", pady=(4, 0))
        row = ttk.Frame(top, style="Panel.TFrame")
        row.pack(anchor="w", pady=(8, 0))
        ttk.Label(row, text=_("Show"), style="Panel.TLabel").pack(side="left")
        self.views = {_("All"): "all", _("To be cut"): "ticked", _("Not to be cut"): "unticked",
                      _("Uncertain ones"): "uncertain", _("Non-speech sounds"): "sounds",
                      _("Repeats and retakes"): "retakes"}
        self.view = tk.StringVar(value=_("All"))
        choice = ttk.Combobox(row, textvariable=self.view, values=list(self.views), width=22, state="readonly")
        choice.pack(side="left", padx=(8, 0))
        choice.bind("<<ComboboxSelected>>", lambda _e: (self._fill(), self.table.focus_set()))
        ttk.Label(row, text=_("A row whose tick you change stays in the list until you choose again."),
                  style="PanelMuted.TLabel").pack(side="left", padx=(14, 0))

        bottom = ttk.Frame(self, style="Panel.TFrame", padding=(18, 8, 18, 14))
        bottom.pack(side="bottom", fill="x")
        self.summary = ttk.Label(bottom, text="", style="Panel.TLabel")
        self.summary.pack(anchor="w", pady=(0, 10))
        for label, command in ((_("Listen"), lambda: self._listen(False)),
                               (_("Listen with the cut"), lambda: self._listen(True)),
                               (_("Tick the medium ones too"), self._tick_medium),
                               (_("Tick all"), lambda: self._set_all(True)),
                               (_("Tick none"), lambda: self._set_all(False)),
                               (_("Back to suggested"), lambda: self._set_all(None))):
            ttk.Button(bottom, text=label, command=command).pack(side="left", padx=(0, 8))
        ttk.Button(bottom, text=_("Apply"), style="Main.TButton", command=self._apply).pack(side="right")
        ttk.Button(bottom, text=_("Cancel"), command=self._close).pack(side="right", padx=(0, 10))

        middle = ttk.Frame(self, style="Panel.TFrame", padding=(18, 4))
        middle.pack(fill="both", expand=True)
        # A Text widget used as a table: a tree view cannot colour part of a cell, and the
        # point of this list is to show the cut sound in red inside its white sentence.
        tabs = ("34", "center", "150", "right", "228", "right", "250", "left", "490", "left", "580", "left")
        header = tk.Text(middle, height=1, bg=CARD, fg=TEXT, bd=0, highlightthickness=0, tabs=tabs,
                         font=("Segoe UI Semibold", 10), spacing1=7, spacing3=7, cursor="arrow", wrap="none")
        header.insert("1.0", "\t" + "\t".join((_("Cut"), _("Time"), _("Length"), _("Kind"),
                                               _("Confidence"), _("Context"))))
        header.configure(state="disabled")
        header.pack(fill="x")
        self.table = tk.Text(middle, bg=FIELD, fg=TEXT, bd=0, highlightthickness=1,
                             highlightbackground=BORDER, highlightcolor=BORDER, tabs=tabs,
                             font=("Segoe UI", 10), spacing1=5, spacing3=5, cursor="arrow", wrap="none",
                             insertwidth=0, takefocus=True)
        bar = ttk.Scrollbar(middle, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=bar.set)
        self.table.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y", padx=(6, 0))
        self.table.tag_configure("kept", foreground=MUTED)  # a row that will not be cut
        self.table.tag_configure("cut", foreground=CUT, font=("Segoe UI Semibold", 10))
        self.table.tag_configure("low", foreground=AMBER)
        self.table.tag_configure("current", background="#2B3550")
        self.table.tag_raise("cut")
        self.table.bind("<Button-1>", self._click)
        self.table.bind("<Double-1>", lambda _e: (self._listen(False), "break")[1])
        self.table.bind("<B1-Motion>", lambda _e: "break")  # no text selection by dragging
        self.table.bind("<space>", lambda _e: (self._toggle(), "break")[1])
        self.table.bind("<Return>", lambda _e: (self._listen(False), "break")[1])
        self.table.bind("<Up>", lambda _e: (self._move(-1), "break")[1])
        self.table.bind("<Down>", lambda _e: (self._move(1), "break")[1])

        self.rows = []  # candidate index shown on each line
        self.current = None  # the selected candidate index
        self._fill()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.grab_set()
        self.table.focus_set()
        self.wait_window()

    # --- list -----------------------------------------------------------------
    def _write_row(self, line, i):
        """Write candidate `i` on the given line: white sentence, the cut sound in red."""
        c = self.candidates[i]
        base = () if c["selected"] else ("kept",)
        at = f"{line}.end"
        self.table.insert(at, "\t" + ("☑" if c["selected"] else "☐") + "\t" + format_time(c["start"])
                          + "\t" + f"{c['end'] - c['start']:.2f} " + _("s") + "\t" + roughcut.kind_name(c)
                          + "\t", base)
        self.table.insert(at, roughcut.confidence_name(c["confidence"]),
                          base + (("low",) if c["confidence"] == "low" and c["selected"] else ()))
        self.table.insert(at, "\t", base)
        for n, (word, is_cut) in enumerate(c.get("parts", [])):
            self.table.insert(at, (" " if n else "") + word,
                              base + (("cut",) if is_cut and c["selected"] else ()))

    def _fill(self):
        self.table.configure(state="normal")
        self.table.delete("1.0", "end")
        self.rows = [i for i, c in enumerate(self.candidates) if shown_in(self.views[self.view.get()], c)]
        for line, i in enumerate(self.rows, 1):
            if line > 1:
                self.table.insert("end", "\n")
            self._write_row(line, i)
        self.table.configure(state="disabled")
        self._select(self.current if self.current in self.rows else (self.rows[0] if self.rows else None))
        self._summarize()

    def _summarize(self):
        cuts, _parts = roughcut.cut_plan(self.state)
        removed = sum(end - start for start, end in cuts) / self.state["fps"]
        self.summary.configure(
            text=_("{selected} of {total} candidates will be cut ({shown} in the list). With the silences "
                   "the timeline gets {time} shorter.").format(
                selected=sum(c["selected"] for c in self.candidates), total=len(self.candidates),
                shown=len(self.rows), time=format_time(removed)))

    def _select(self, i):
        self.current = i
        self.table.tag_remove("current", "1.0", "end")
        if i is not None:
            line = self.rows.index(i) + 1
            self.table.tag_add("current", f"{line}.0", f"{line + 1}.0")
            self.table.see(f"{line}.0")

    def _selected(self):
        return self.current

    def _move(self, step):
        if self.current in self.rows:
            self._select(self.rows[min(max(self.rows.index(self.current) + step, 0), len(self.rows) - 1)])

    def _toggle(self, i=None):
        i = self.current if i is None else i
        if i is None:
            return
        self.candidates[i]["selected"] = not self.candidates[i]["selected"]
        line = self.rows.index(i) + 1
        self.table.configure(state="normal")
        self.table.delete(f"{line}.0", f"{line}.end")
        self._write_row(line, i)
        self.table.configure(state="disabled")
        self._select(i)
        self._summarize()

    def _click(self, event):
        self.table.focus_set()
        line = int(self.table.index(f"@{event.x},{event.y}").split(".")[0])
        if 1 <= line <= len(self.rows) and self.table.dlineinfo(f"{line}.0"):
            self._select(self.rows[line - 1])
            if event.x < 70:  # the tick column
                self._toggle()
        return "break"

    def _set_all(self, value):
        for i, c in enumerate(self.candidates):
            c["selected"] = self.suggested[i] if value is None else value
        self._fill()

    def _tick_medium(self):
        """Also tick the medium-confidence sound candidates that arrive unticked, such as short hesitations."""
        for c in self.candidates:
            if c["confidence"] == "medium" and c["kind"] in ("alone", "before_word", "noise"):
                c["selected"] = True
        self._fill()

    # --- listening --------------------------------------------------------------
    def _listen(self, with_cut):
        i = self._selected()
        if i is None:
            return
        if winsound is None:
            self.summary.configure(text=_("Listening only works on Windows."))
            return
        c, samples = self.candidates[i], self.state["samples"]
        first, last = int(max(c["start"] - 1.5, 0) * SAMPLE_RATE), int((c["end"] + 1.5) * SAMPLE_RATE)
        if with_cut:
            pad = roughcut.HESITATION_PAD
            piece = roughcut.np.concatenate((samples[first:int((c["start"] + pad) * SAMPLE_RATE)],
                                             samples[int((c["end"] - pad) * SAMPLE_RATE):last]))
        else:
            piece = samples[first:last]
        path = Path(self.temp.name) / f"candidate_{i}_{int(with_cut)}.wav"
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SAMPLE_RATE)
            w.writeframes((roughcut.np.clip(piece, -1, 1) * 32767).astype("<i2").tobytes())
        winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)

    # --- closing ----------------------------------------------------------------
    def _apply(self):
        self.approved = True
        self._close()

    def _close(self):
        if winsound is not None:
            winsound.PlaySound(None, winsound.SND_PURGE)
        if not self.approved:  # on cancel the ticks go back to what they were
            for i, c in enumerate(self.candidates):
                c["selected"] = self.suggested[i]
        try:
            self.temp.cleanup()
        except OSError:
            pass
        self.grab_release()
        self.destroy()


class TranscriptWindow(tk.Toplevel):
    """Line-by-line editor for the transcript."""

    def __init__(self, app, record, video):
        super().__init__(app)
        self.record, self.video = record, video
        self.language = record.get("language", "tr")
        self.words = [list(w) for w in record["words"]]
        self.corrections = []
        self.changed = False
        self.edited = set()  # start times of the corrected lines
        self.summary = ""
        self.temp = tempfile.TemporaryDirectory(prefix="davar_text_")
        self.title("Davar — " + _("edit the text"))
        self.configure(bg=PANEL)
        self.geometry("1100x700")
        self.minsize(820, 460)
        self.transient(app)

        top = ttk.Frame(self, style="Panel.TFrame", padding=(18, 14, 18, 8))
        top.pack(fill="x")
        ttk.Label(top, text=_("Edit the text"), style="Title.TLabel").pack(anchor="w")
        ttk.Label(top, text=_("Select a line, correct it in the box below and press Enter: the correction "
                              "is applied and the next line is selected. Saving also rewrites the subtitle "
                              "and text files."),
                  style="PanelMuted.TLabel", wraplength=1040, justify="left").pack(anchor="w", pady=(4, 0))

        bottom = ttk.Frame(self, style="Panel.TFrame", padding=(18, 8, 18, 14))
        bottom.pack(side="bottom", fill="x")
        self.text = tk.StringVar()
        self.entry = ttk.Entry(bottom, textvariable=self.text, font=("Segoe UI", 12))
        self.entry.pack(fill="x", ipady=5)
        row = ttk.Frame(bottom, style="Panel.TFrame")
        row.pack(fill="x", pady=(10, 0))
        ttk.Button(row, text=_("Listen"), command=self._listen).pack(side="left")
        ttk.Button(row, text=_("Apply and next (Enter)"), command=self._apply).pack(side="left", padx=(8, 0))
        self.status = ttk.Label(row, text="", style="Panel.TLabel")
        self.status.pack(side="left", padx=14)
        ttk.Button(row, text=_("Save"), style="Main.TButton", command=self._save).pack(side="right")
        ttk.Button(row, text=_("Cancel"), command=self._close).pack(side="right", padx=(0, 10))

        middle = ttk.Frame(self, style="Panel.TFrame", padding=(18, 4))
        middle.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(middle, columns=("time", "text"), show="headings", selectmode="browse")
        self.tree.heading("time", text=_("Time"), anchor="e")
        self.tree.heading("text", text=_("Text"), anchor="w")
        self.tree.column("time", width=90, anchor="e", stretch=False)
        self.tree.column("text", width=900, anchor="w")
        bar = ttk.Scrollbar(middle, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=bar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y", padx=(6, 0))
        self.tree.tag_configure("edited", foreground=ACCENT)
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._selection_changed())
        self.tree.bind("<Double-1>", lambda _e: self._listen())
        self.entry.bind("<Return>", lambda _e: self._apply())

        self._fill(0.0)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.grab_set()
        self.entry.focus_set()
        self.wait_window()

    def _line_text(self, group):
        return " ".join(self.words[i][0] for i in group)

    def _fill(self, select_time):
        """Rebuild the list and select the line closest to the given time."""
        self.groups = transcript.line_groups(self.words, language=self.language)
        self.tree.delete(*self.tree.get_children())
        closest, gap = None, 1e9
        for i, group in enumerate(self.groups):
            start = self.words[group[0]][1]
            self.tree.insert("", "end", iid=str(i), values=(format_time(start), self._line_text(group)),
                             tags=("edited",) if round(start, 2) in self.edited else ())
            if abs(start - select_time) < gap:
                closest, gap = i, abs(start - select_time)
        if closest is not None:
            self._select(closest)
        self.status.configure(text=_("{lines} lines, {edited} corrected").format(
            lines=len(self.groups), edited=len(self.edited)))

    def _select(self, i):
        i = min(max(i, 0), len(self.groups) - 1)
        self.tree.selection_set(str(i))
        self.tree.focus(str(i))
        self.tree.see(str(i))
        self._selection_changed()  # the selection event arrives late; show the new line at once

    def _selected(self):
        selection = self.tree.selection()
        return int(selection[0]) if selection else None

    def _selection_changed(self):
        i = self._selected()
        if i is not None:
            self.text.set(self._line_text(self.groups[i]))
            self.entry.icursor("end")

    def _apply(self):
        i = self._selected()
        if i is None:
            return
        group, new = self.groups[i], self.text.get().strip()
        start = self.words[group[0]][1]
        following = self.words[self.groups[i + 1][0]][1] if i + 1 < len(self.groups) else start
        if new and new != self._line_text(group):
            self.words, corrections = transcript.edit_line(self.words, group, new)
            self.corrections += corrections
            self.edited.add(round(start, 2))
            self.changed = True
        self._fill(following)

    def _listen(self):
        i = self._selected()
        if i is None:
            return
        if winsound is None:
            self.status.configure(text=_("Listening only works on Windows."))
            return
        group = self.groups[i]
        start = max(self.words[group[0]][1] - 0.2, 0)
        length = self.words[group[-1]][2] + 0.3 - start
        path = Path(self.temp.name) / "line.wav"
        winsound.PlaySound(None, winsound.SND_PURGE)  # let the previous playback release the file
        try:
            run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.2f}", "-t", f"{length:.2f}",
                 "-i", str(self.video), "-vn", "-ac", "1", "-ar", "22050", str(path)])
        except DavarError as e:
            self.status.configure(text=str(e).splitlines()[0])
            return
        winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)

    def _save(self):
        if self.text.get().strip() != self._line_text(self.groups[self._selected() or 0]):
            self._apply()  # do not lose a correction still waiting in the box
        if not self.changed:
            self._close()
            return
        self.record["words"] = self.words
        transcript.save(self.record)
        folder, stem = Path(self.record["path"]).parent, self.video.stem
        rewritten = []
        for file, write in ((folder / (stem + ".srt"), transcript.write_srt),
                            (folder / (stem + "_transcript.txt"), transcript.write_text)):
            if file.exists():
                write(self.record, file)
                rewritten.append(file.name)
        # the subtitles of the Rough Cut timeline follow the correction too
        timeline = folder / (stem + "_cut.fcpxml")
        if timeline.exists():
            try:
                info = video_info(self.video)
                known = roughcut.read_timeline(timeline, self.video, info)
            except DavarError:
                known = None
            if known:
                subtitles = roughcut.cut_subtitles_path(timeline)
                roughcut.write_cut_subtitles(subtitles, self.words, known["parts"], float(info["fps"]),
                                             self.language)
                rewritten.append(subtitles.name)
        self.summary = _("Text corrected: {n} lines saved.").format(n=len(self.edited))
        if rewritten:
            self.summary += " " + _("Files rewritten: {files}.").format(files=", ".join(rewritten))
        # offer to add single-word corrections to the dictionary
        pairs = list(dict.fromkeys((old, new) for old, new in self.corrections if old and new))
        if pairs:
            shown = "\n".join(f"   {old}  →  {new}" for old, new in pairs[:12])
            if len(pairs) > 12:
                shown += "\n   " + _("… and {n} more").format(n=len(pairs) - 12)
            if messagebox.askyesno(
                    _("Add to the dictionary?"),
                    _("Add these corrections to your personal dictionary? They will then be fixed "
                      "automatically in every video from now on.") + "\n\n" + shown, parent=self):
                dictionary.add(pairs)
                self.summary += " " + _("{n} words added to the dictionary.").format(n=len(pairs))
        self._close()

    def _close(self):
        if winsound is not None:
            winsound.PlaySound(None, winsound.SND_PURGE)
        try:
            self.temp.cleanup()
        except OSError:
            pass
        self.grab_release()
        self.destroy()


class TitlesPage(Page):
    name = N_("Titles")
    description = N_("Makes lower thirds: a speaker's name and title, and the topic being talked about. "
                     "Ready videos with a transparent background and a soft entrance and exit; Davar puts "
                     "them on the timeline, or drag them onto the track above the video in Resolve.")
    needs_video = False
    key = "titles"
    general = ("names_on", "speakers", "duration", "spot", "colour", "timeline",
               "topics_on", "tag", "topic_line", "topic_duration", "logo", "logo_on", "corner", "logo_size")
    per_video = ("topic_rows",)

    def build(self, parent):
        self.duration = tk.DoubleVar(value=6.0)
        self.positions = {_("Bottom left"): "left", _("Bottom centre"): "centre", _("Bottom right"): "right"}
        self.position = tk.StringVar(value=_("Bottom left"))
        self.colour = tk.StringVar(value="#E30613")
        self.timeline = tk.BooleanVar(value=True)
        self.names_on = tk.BooleanVar(value=True)
        self.topics_on = tk.BooleanVar(value=False)
        self.tag = tk.StringVar()
        self.topic_line = tk.StringVar()
        self.topic_duration = tk.DoubleVar(value=topics.DURATION)
        self.logo = tk.StringVar()
        self.logo_on = tk.BooleanVar(value=False)
        self.corners = {_("Top right"): "top right", _("Top left"): "top left",
                        _("Bottom right"): "bottom right", _("Bottom left"): "bottom left"}
        self.corner_label = tk.StringVar(value=_("Top right"))
        self.logo_size = tk.DoubleVar(value=corner_logo.SIZE)
        self.corner = Held(lambda: self.corners[self.corner_label.get()],
                           lambda corner: self.corner_label.set(next(
                               (label for label, value in self.corners.items() if value == corner),
                               self.corner_label.get())))
        self.corner_label.trace_add("write", lambda *_args: self.app.remember_soon())
        # remembered by its meaning, not by its label, which changes with the interface language
        self.spot = Held(lambda: self.positions[self.position.get()],
                         lambda spot: self.position.set(next(
                             (label for label, value in self.positions.items() if value == spot),
                             self.position.get())))
        self.speakers = Held(lambda: self.people.get("1.0", "end-1c"), self._set_speakers)
        self.position.trace_add("write", lambda *_args: self.app.remember_soon())

        g = self.card(parent, self.names_on, _("Speakers"),
                      _("One person per line: Name | Title. The title is optional. "
                        "A separate file is written for each person. To put one name elsewhere than "
                        "the others, add its place on the screen, as the viewer sees it (left, centre, "
                        "right): Name | Title | right"))
        self.people = tk.Text(g, height=4, bg=FIELD, fg=TEXT, insertbackground=TEXT, bd=0,
                              highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT,
                              font=("Segoe UI", 11), padx=8, pady=6, wrap="none")
        self.people.pack(fill="x", pady=(8, 0))
        self.people.bind("<KeyRelease>", lambda _e: (self.refresh_state(), self.app.remember_soon()))

        g = self.card(parent, self.timeline, _("Place them on the timeline"),
                      _("Write the speakers in the order they first speak. Davar listens for who speaks when "
                        "and puts each name on the track above the video, a few seconds after that person "
                        "first speaks. It needs the transcript. To choose the moment yourself, add the time "
                        "in the video to the line: Name | Title | 0:41"))
        self.timeline_note = ttk.Label(g, text="", style="Card.TLabel", wraplength=680, justify="left")
        self.timeline_note.pack(anchor="w", pady=(6, 0))

        g = self.card(parent, None, _("Look"))
        ttk.Label(g, text=_("Time on screen"), style="Card.TLabel").grid(row=0, column=0, sticky="w", pady=(8, 0))
        ttk.Spinbox(g, textvariable=self.duration, from_=2, to=30, increment=0.5, width=6,
                    format="%.1f").grid(row=0, column=1, sticky="w", padx=(12, 6), pady=(8, 0))
        ttk.Label(g, text=_("s") + "      " + _("Opens in half a second, fades out at the end"),
                  style="CardMuted.TLabel").grid(row=0, column=2, sticky="w", pady=(8, 0))
        ttk.Label(g, text=_("Place"), style="Card.TLabel").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Combobox(g, textvariable=self.position, values=list(self.positions), width=14,
                     state="readonly").grid(row=1, column=1, sticky="w", padx=(12, 6), pady=(8, 0))
        ttk.Label(g, text=_("For the names whose line gives no place of its own"),
                  style="CardMuted.TLabel").grid(row=1, column=2, sticky="w", pady=(8, 0))
        ttk.Label(g, text=_("Accent colour"), style="Card.TLabel").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(g, textvariable=self.colour, width=10).grid(row=2, column=1, sticky="w", padx=(12, 6), pady=(8, 0))
        ttk.Label(g, text=_("Colour of the stripe and the title band; example #E30613"),
                  style="CardMuted.TLabel").grid(row=2, column=2, sticky="w", pady=(8, 0))
        self.size_note = ttk.Label(g, text="", style="CardMuted.TLabel")
        self.size_note.grid(row=3, column=0, columnspan=3, sticky="w", pady=(10, 0))

        g = self.card(parent, self.topics_on, _("Topic titles"),
                      _("A title for the question or the subject, at the bottom of the picture with the logo "
                        "on the right. One per line: time | headline. The time is on the Rough Cut timeline; "
                        "each title opens a few seconds later, and waits if a name is on screen. A line of "
                        "its own under the headline can be added: time | headline | line."))
        self.topic_box = tk.Text(g, height=6, bg=FIELD, fg=TEXT, insertbackground=TEXT, bd=0, highlightthickness=1,
                                 highlightbackground=BORDER, highlightcolor=ACCENT, font=("Segoe UI", 11), padx=8,
                                 pady=6, wrap="none")
        self.topic_box.pack(fill="x", pady=(8, 0))
        self.topic_box.bind("<KeyRelease>", lambda _e: (self.refresh_state(), self.app.remember_soon()))
        self.topic_rows = Held(lambda: self.topic_box.get("1.0", "end-1c"), self._set_topic_rows)
        self.chapters_button = ttk.Button(g, text=_("Take the chapters of Content Analysis"),
                                          command=self._take_chapters)
        self.chapters_button.pack(anchor="w", pady=(8, 0))
        box = ttk.Frame(g, style="Card.TFrame")
        box.pack(fill="x", pady=(4, 0))
        box.columnconfigure(1, weight=1)
        for row, (label, variable, hint) in enumerate((
                (_("Tab"), self.tag, _("the name of the programme; empty: the one written on Content Analysis")),
                (_("Line under it"), self.topic_line, _("e.g. GUEST: NAME · TITLE; the same on every title")))):
            ttk.Label(box, text=label, style="Card.TLabel").grid(row=row, column=0, sticky="w", pady=(8, 0))
            ttk.Entry(box, textvariable=variable).grid(row=row, column=1, sticky="ew", padx=(12, 0), pady=(8, 0))
            ttk.Label(box, text=hint, style="CardMuted.TLabel").grid(row=row, column=2, sticky="w", padx=(12, 0),
                                                                   pady=(8, 0))
        ttk.Label(box, text=_("Time on screen"), style="Card.TLabel").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Spinbox(box, textvariable=self.topic_duration, from_=3, to=30, increment=0.5, width=6,
                    format="%.1f").grid(row=2, column=1, sticky="w", padx=(12, 0), pady=(8, 0))
        self.topic_note = ttk.Label(g, text="", style="CardMuted.TLabel", wraplength=680, justify="left")
        self.topic_note.pack(anchor="w", pady=(8, 0))
        self.topics_on.set(False)  # let the card grey out its boxes

        g = self.card(parent, None, _("Logo"),
                      _("The logo shown on the topic titles, and if you like in a corner of the picture from the "
                        "start to the end."))
        g.columnconfigure(1, weight=1)
        ttk.Label(g, text=_("Logo file"), style="Card.TLabel").grid(row=0, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(g, textvariable=self.logo).grid(row=0, column=1, columnspan=2, sticky="ew", padx=(12, 0),
                                                 pady=(8, 0))
        ttk.Button(g, text=_("Choose"), command=self._choose_logo).grid(row=0, column=3, sticky="w", padx=(12, 0),
                                                                        pady=(8, 0))
        ttk.Checkbutton(g, text=_("Put it in a corner of the picture, from the start to the end"),
                        variable=self.logo_on, style="Card.TCheckbutton").grid(row=1, column=0, columnspan=4,
                                                                               sticky="w", pady=(10, 0))
        ttk.Label(g, text=_("Corner"), style="Card.TLabel").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Combobox(g, textvariable=self.corner_label, values=list(self.corners), width=14,
                     state="readonly").grid(row=2, column=1, sticky="w", padx=(12, 0), pady=(8, 0))
        ttk.Label(g, text=_("Width"), style="Card.TLabel").grid(row=3, column=0, sticky="w", pady=(8, 0))
        row = ttk.Frame(g, style="Card.TFrame")
        row.grid(row=3, column=1, columnspan=3, sticky="w", padx=(12, 0), pady=(8, 0))
        ttk.Spinbox(row, textvariable=self.logo_size, from_=3, to=40, increment=1, width=6,
                    format="%.0f").pack(side="left")
        ttk.Label(row, text="  " + _("percent of the picture's width"), style="CardMuted.TLabel").pack(side="left")
        for variable in (self.logo_on, self.logo):
            variable.trace_add("write", lambda *_args: self.refresh_state())

    def _set_topic_rows(self, text):
        self.topic_box.delete("1.0", "end")
        self.topic_box.insert("1.0", text)

    def _topic_lines(self):
        return [x for x in self.topic_box.get("1.0", "end").splitlines() if x.strip()]

    def _content_file(self, video):
        try:
            return self.app.output_folder() / (video.stem + "_content.json")
        except DavarError:
            return None

    def _take_chapters(self):
        """Fill the box with the on-screen titles Content Analysis wrote for the chapters."""
        video = self._video()
        path = self._content_file(video) if video else None
        try:
            saved = json.loads(path.read_text(encoding="utf-8")) if path and path.is_file() else {}
        except ValueError:
            saved = {}
        found = saved.get("topics") or [chapter for chapter in saved.get("chapters", [])[1:]]
        if not found:
            self.app.log(_("No chapters yet: write the texts on the Content Analysis page first."), error=True)
            return
        self._set_topic_rows("\n".join(f"{content.clock(at)} | {topics.upper(title)}" for at, title in found))
        self.topics_on.set(True)
        self.refresh_state()
        self.app.remember_soon()

    def _choose_logo(self):
        path = filedialog.askopenfilename(title=_("Choose the logo"), filetypes=[
            (_("Pictures"), "*.png *.jpg *.jpeg *.webp"), (_("All files"), "*.*")])
        if path:
            self.logo.set(os.path.normpath(path))

    def _programme(self):
        page = next((p for p in self.app.pages if isinstance(p, ContentAnalysisPage)), None)
        return page.programme.get().strip() if page is not None else ""

    def _set_speakers(self, text):
        self.people.delete("1.0", "end")
        self.people.insert("1.0", text)

    def _rows(self):
        return [x for x in self.people.get("1.0", "end").splitlines() if x.strip()]

    def _video(self):
        video = self.app.video_path()
        return video if self.app.video.get().strip() and video.is_file() else None

    def missing(self):
        video = self._video()
        self.size_note.configure(
            text=_("The size and frame rate are taken from the selected video.") if video
            else _("No video selected: made at 1920x1080, 30 frames per second."))
        self.timeline_note.configure(text=self._timeline_note(video))
        path = self._content_file(video) if video else None
        self.chapters_button.configure(state="normal" if path and path.is_file() else "disabled")
        logo = self.logo.get().strip()
        self.topic_note.configure(text=(
            _("The logo file was not found.") if logo and not Path(logo).is_file()
            else "" if font_ok() else _("Montserrat is not in {folder}; a common bold font will be used.").format(
                folder=topics.BRAND / "fonts")))
        names, topic_rows = self.names_on.get() and self._rows(), self.topics_on.get() and self._topic_lines()
        if not names and not topic_rows and not self.logo_on.get():
            return _("Write at least one name or one topic")
        if (topic_rows or self.logo_on.get()) and not video:
            return _("Choose a video at the top first")
        if self.logo_on.get() and not (logo and Path(logo).is_file()):
            return _("Choose the logo file")
        if not names:
            return ""
        if not video and not self.app.folder.get().strip():
            return _("Choose an output folder to make one without a video")
        try:
            untimed = any(person["time"] is None for person in titles.parse_people(self._rows()))
        except DavarError:
            untimed = False  # a line that cannot be read is explained in the log when Start is pressed
        if self.timeline.get() and video and untimed and not self.app.transcript():
            return _("Run Transcribe first, or give each name a time")
        return ""

    def _timeline_note(self, video):
        """Say where the names will go, so that nothing is written unexpectedly."""
        if not video:
            return _("No video selected: the names are made but not placed.")
        try:
            cut = self.app.output_folder() / (video.stem + "_cut.fcpxml")
        except DavarError:
            return ""
        if cut.is_file():
            return _("They will be added to the Rough Cut timeline of this video: {name}").format(name=cut.name)
        return _("This video has no Rough Cut timeline yet, so a timeline of the whole video will be "
                 "written. Run Rough Cut first to get the names on the cut.")

    def read_settings(self):
        video = self._video()
        saved = self.app.transcript() if video else None
        names = self.names_on.get() and self._rows()
        topic_rows = self.topics_on.get() and self._topic_lines()
        if names:
            titles.parse_people(self._rows())  # a line that cannot be read stops here, with its reason
        if topic_rows:
            topics.parse_topics(topic_rows)
        logo = self.logo.get().strip()
        return dict(
            names=dict(rows=self._rows(), video=video, folder=self.app.output_folder(),
                       duration=float(self.duration.get()), colour=self.colour.get(),
                       position=self.positions[self.position.get()],
                       timeline=self.timeline.get() and video is not None,
                       words=saved["words"] if saved else None,
                       language=saved.get("language", "tr") if saved else "tr") if names else None,
            topics=dict(rows=topic_rows, tag=self.tag.get().strip() or self._programme(),
                        line=self.topic_line.get(), video=video, folder=self.app.output_folder(),
                        duration=float(self.topic_duration.get()),
                        logo=logo if logo and Path(logo).is_file() else None) if topic_rows else None,
            corner=dict(video=video, logo=logo, corner=self.corner.get(), size=float(self.logo_size.get()),
                        folder=self.app.output_folder()) if self.logo_on.get() else None)

    def run(self, settings, progress):
        result = {}
        if settings["names"]:
            names = settings["names"]
            share = 0.5 if settings["topics"] else 1.0
            rows = names.pop("rows")
            result["names"] = titles.make_lower_thirds(rows, progress=lambda p, t: progress(p * share, t), **names)
            result["output"] = result["names"]["output"]
        if settings["topics"]:
            start = 50 if settings["names"] else 0
            rows = settings["topics"].pop("rows")
            result["topics"] = topics.make_topics(rows, progress=lambda p, t: progress(start + p * (100 - start) / 100, t),
                                                  **settings["topics"])
            result["output"] = result["topics"]["output"]
        if settings["corner"]:  # last, so that it goes onto the timeline the titles were written to
            result["corner"] = corner_logo.place(**settings["corner"])
            result["output"] = result["corner"]["output"]
        return result

    def result_text(self, result):
        return "\n\n".join(text for text in (titles.report(result["names"]) if "names" in result else "",
                                               topics.report(result["topics"]) if "topics" in result else "",
                                               corner_logo.report(result["corner"]) if "corner" in result else "")
                             if text)


class SocialClipsPage(Page):
    name = N_("Social Clips")
    description = N_("Cuts the range you choose from a landscape video into a vertical (9:16) Reels / Shorts "
                     "video. Puts the speaker's frame over a blurred background and adds a headline, "
                     "subtitles and an intro cover.")
    key = "social_clips"
    general = ("kicker", "subtitles", "cover", "use_cut")
    per_video = ("start", "end", "horizontal", "headline1", "headline2")

    def build(self, parent):
        self.start = tk.StringVar()
        self.end = tk.StringVar()
        self.horizontal = tk.DoubleVar(value=50)
        self.kicker = tk.StringVar()
        self.headline1 = tk.StringVar()
        self.headline2 = tk.StringVar()
        self.subtitles = tk.BooleanVar(value=True)
        self.cover = tk.BooleanVar(value=False)
        self.use_cut = tk.BooleanVar(value=True)
        self.candidates, self.ticks = [], []  # Content Analysis's clips, with their ticks

        g = self.card(parent, None, _("Candidates of Content Analysis"),
                      _("The clips Content Analysis suggests, with their ranges fitted to whole sentences. "
                        "Tick the ones to make: Start then makes them one after the other, with the texts the AI "
                        "wrote and the extras below, as “Clip 1 - …”. Fill in puts one in the boxes below, "
                        "to change it and make it alone."))
        row = ttk.Frame(g, style="Card.TFrame")
        row.pack(anchor="w", pady=(8, 0))
        ttk.Button(row, text=_("Take the candidates"), command=self._take_candidates).pack(side="left")
        self.ticked_status = ttk.Label(row, text="", style="CardMuted.TLabel")
        self.ticked_status.pack(side="left", padx=(12, 0))
        self.candidate_rows = ttk.Frame(g, style="Card.TFrame")
        self.candidate_rows.pack(fill="x", pady=(4, 0))

        g = self.card(parent, None, _("Range and framing"))
        ttk.Label(g, text=_("From"), style="Card.TLabel").grid(row=0, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(g, textvariable=self.start, width=10).grid(row=0, column=1, sticky="w", padx=(12, 20), pady=(8, 0))
        ttk.Label(g, text=_("To"), style="Card.TLabel").grid(row=0, column=2, sticky="w", pady=(8, 0))
        box = ttk.Frame(g, style="Card.TFrame")
        box.grid(row=0, column=3, sticky="w", pady=(8, 0))
        ttk.Entry(box, textvariable=self.end, width=10).pack(side="left", padx=(12, 14))
        ttk.Label(box, text=_("minute:second, e.g. 13:06"), style="CardMuted.TLabel").pack(side="left")
        ttk.Label(g, text=_("Framing"), style="Card.TLabel").grid(row=1, column=0, sticky="w", pady=(12, 0))
        box = ttk.Frame(g, style="Card.TFrame")
        box.grid(row=1, column=1, columnspan=3, sticky="w", padx=(12, 0), pady=(12, 0))
        ttk.Label(box, text=_("left"), style="CardMuted.TLabel").pack(side="left")
        ttk.Scale(box, variable=self.horizontal, from_=0, to=100, length=220).pack(side="left", padx=8)
        ttk.Label(box, text=_("right") + "     " + _("move it if the speaker is not in the centre"),
                  style="CardMuted.TLabel").pack(side="left")

        g = self.card(parent, None, _("Texts"), _("A line left empty is not written."))
        g.columnconfigure(1, weight=1)
        for row, (label, variable) in enumerate(((_("Kicker"), self.kicker), (_("Headline line 1"), self.headline1),
                                                 (_("Headline line 2"), self.headline2))):
            ttk.Label(g, text=label, style="Card.TLabel").grid(row=row, column=0, sticky="w", pady=(8, 0))
            ttk.Entry(g, textvariable=variable).grid(row=row, column=1, sticky="ew", padx=(12, 0), pady=(8, 0))

        g = self.card(parent, None, _("Extras"))
        self.check_row(g, 0, self.subtitles, _("Add subtitles"),
                       _("Burns the speech into the video (uses the transcript when there is one). "
                         "They cannot be corrected afterwards; read them first."))
        self.check_row(g, 1, self.cover, _("Add an intro cover"),
                       _("Puts a 2.5 second cover showing the kicker and headline at the start."))
        self.check_row(g, 2, self.use_cut, _("Apply the Rough Cut's cuts"),
                       _("Leaves out the silences and hesitations it cut; the times above stay those of the video."))
        for variable in (self.start, self.end, self.kicker, self.headline1, self.headline2, self.cover):
            variable.trace_add("write", lambda *_args: self.refresh_state())

    def _ticked(self):
        return [dict(clip, n=n) for n, (clip, tick) in enumerate(zip(self.candidates, self.ticks), 1) if tick.get()]

    def _take_candidates(self):
        if not self.app.video.get().strip() or not self.app.video_path().is_file():
            self.app.log(_("Choose a video at the top first"), error=True)
            return
        video = self.app.video_path()
        try:
            found = content.clip_candidates(video, self.app.output_folder())
        except DavarError as e:
            self.app.log(_("Failed: {message}").format(message=e), error=True)
            return
        if not found:
            self.app.log(_("This video has no social clip candidates yet: run Content Analysis first."), error=True)
            return
        words = (self.app.transcript() or {}).get("words")
        for clip in found:
            clip["start"], clip["end"] = clips.fit_to_sentences(words, clip["start"], clip["end"])
        for child in self.candidate_rows.winfo_children():
            child.destroy()
        self.candidates, self.ticks = found, []
        for n, clip in enumerate(found, 1):
            tick = tk.BooleanVar(value=True)
            tick.trace_add("write", lambda *_args: self.refresh_state())
            self.ticks.append(tick)
            line = ttk.Frame(self.candidate_rows, style="Card.TFrame")
            line.pack(fill="x", pady=(6, 0))
            ttk.Checkbutton(line, variable=tick, style="Card.TCheckbutton",
                            text=f"{n}. {format_time(clip['start'])} - {format_time(clip['end'])}  "
                                 f"({clip['end'] - clip['start']:.0f} {_('s')})  {' '.join(clip['lines'])}"
                            ).pack(side="left")
            ttk.Button(line, text=_("Fill in"), command=lambda clip=clip: self._fill_in(clip)).pack(side="right")
            if clip["why"]:
                ttk.Label(self.candidate_rows, text=clip["why"], style="CardMuted.TLabel", wraplength=640,
                          justify="left").pack(anchor="w", padx=(24, 0))
        self.app.log(_("{n} social clip candidates taken from Content Analysis; their ranges are fitted to "
                       "whole sentences.").format(n=len(found)))
        self.refresh_state()

    def _fill_in(self, clip):
        self.start.set(format_time(clip["start"]))
        self.end.set(format_time(clip["end"]))
        lines = list(clip["lines"]) + ["", ""]
        self.headline1.set(lines[0])
        self.headline2.set(lines[1])
        for tick in self.ticks:  # the boxes are made now, not the ticked candidates
            tick.set(False)

    def missing(self):
        ticked = self._ticked()
        self.ticked_status.configure(text=_("{n} ticked: Start makes them").format(n=len(ticked)) if ticked
                                     else "")
        if ticked:
            return ""
        if not self.start.get().strip() or not self.end.get().strip():
            return _("Write the start and end time")
        if self.cover.get() and not (self.kicker.get().strip() or self.headline1.get().strip()
                                     or self.headline2.get().strip()):
            return _("Write a headline or a kicker for the intro cover")
        return ""

    def read_settings(self):
        video = self.app.video_path()
        saved = self.app.transcript() or {}
        if self._ticked():
            return dict(
                video=video, folder=self.app.output_folder(), candidates=self._ticked(), kicker=self.kicker.get(),
                horizontal=float(self.horizontal.get()) / 100, subtitles=self.subtitles.get(),
                cover=self.cover.get(), words=saved.get("words"),
                language=saved.get("language", i18n.load_settings().get("speech_language", "tr")),
                parts=self._cut_parts(video) if self.use_cut.get() else None)
        return dict(
            video=video, output=self.app.output_folder() / (video.stem + "_vertical.mp4"),
            start=self.start.get(), end=self.end.get(), kicker=self.kicker.get(),
            headline=[self.headline1.get(), self.headline2.get()], horizontal=float(self.horizontal.get()) / 100,
            subtitles=self.subtitles.get(), cover=self.cover.get(), words=saved.get("words"),
            language=saved.get("language", i18n.load_settings().get("speech_language", "tr")),
            parts=self._cut_parts(video) if self.use_cut.get() else None,
        )

    def _cut_parts(self, video):
        """The parts of the video's Rough Cut timeline, or None when it has none."""
        known = roughcut.read_timeline(self.app.output_folder() / (video.stem + "_cut.fcpxml"), video,
                                       video_info(video))
        return known["parts"] if known else None

    def run(self, settings, progress):
        if "candidates" in settings:
            made = clips.make_clips(progress=progress, **settings)
            return {"output": made[-1]["output"], "many": made}
        return clips.make_clip(progress=progress, **settings)

    def result_text(self, result):
        return clips.report_many(result["many"]) if "many" in result else clips.report(result)


class Planned(Page):
    """A workflow that is not written yet: explains what it will do and what it needs."""

    ready = False
    will_do = ()
    needs = ""

    def build(self, parent):
        self.card(parent, None, _("Not written yet"), _("This workflow is planned but does not work."))
        g = self.card(parent, None, _("What it will do"))
        for line in self.will_do:
            ttk.Label(g, text="•  " + _(line), style="Card.TLabel", wraplength=700,
                      justify="left").pack(anchor="w", pady=(6, 0))
        if self.needs:
            self.card(parent, None, _("What it needs"), _(self.needs))


class MultiCamPage(Planned):
    name = N_("Multicam Edit")
    description = N_("Picks the camera of whoever is speaking and returns to the wide shot now and then "
                     "to keep the edit natural.")
    will_do = (
        N_("You link each microphone to a speaker and to the camera to show while they speak."),
        N_("It picks the camera by speaker, respecting the shortest and longest shot length."),
        N_("At intervals it returns to the wide shot (two-shot or wide)."),
        N_("It writes the result as one timeline for Resolve."),
    )
    needs = N_("Synchronised camera files and separate audio per speaker. Cannot be used on single-camera shoots.")


class ContentAnalysisPage(Page):
    name = N_("Content Analysis")
    description = N_("Has an AI write the YouTube texts: title suggestions, a description with chapters, tags, "
                     "a summary and social clip candidates. No key and no fee: Claude Code, when it is installed, "
                     "is asked straight away with your own Claude subscription; otherwise you paste Davar's "
                     "prompt into an AI chat and its answer back here.")
    key = "content"
    general = ("programme", "channel", "direct")
    per_video = ("notes",)

    def build(self, parent):
        self.programme = tk.StringVar()
        self.channel = tk.StringVar()
        self.notes = tk.StringVar()
        self.direct = tk.BooleanVar(value=True)

        g = self.card(parent, None, _("1. Prepare the prompt"),
                      _("Start writes the transcript with its times on the Rough Cut timeline and who says "
                        "what, and copies it. The speakers and their titles are taken from the Titles page. "
                        "The text goes to the AI service you paste it into."))
        g.columnconfigure(1, weight=1)
        for row, (label, variable, hint) in enumerate((
                (_("Programme"), self.programme, _("e.g. the name of the series")),
                (_("Channel"), self.channel, ""),
                (_("Notes"), self.notes, _("anything the AI should know: the date, the subject, a spelling")))):
            ttk.Label(g, text=label, style="Card.TLabel").grid(row=row, column=0, sticky="w", pady=(8, 0))
            ttk.Entry(g, textvariable=variable).grid(row=row, column=1, sticky="ew", padx=(12, 0), pady=(8, 0))
            ttk.Label(g, text=hint, style="CardMuted.TLabel").grid(row=row, column=2, sticky="w", padx=(12, 0),
                                                                   pady=(8, 0))
        self.prompt_status = ttk.Label(g, text="", style="CardMuted.TLabel", wraplength=680, justify="left")
        self.prompt_status.grid(row=3, column=0, columnspan=3, sticky="w", pady=(8, 0))
        self.direct_box = ttk.Checkbutton(g, text=_("Ask Claude Code straight away"), variable=self.direct,
                                          style="Card.TCheckbutton")
        self.direct_box.grid(row=4, column=0, columnspan=3, sticky="w", pady=(8, 0))
        self.direct_status = ttk.Label(g, text="", style="CardMuted.TLabel", wraplength=680, justify="left")
        self.direct_status.grid(row=5, column=0, columnspan=3, sticky="w")
        self.copy_button = ttk.Button(g, text=_("Copy the prompt again"), command=self._copy_again)
        self.copy_button.grid(row=6, column=0, columnspan=3, sticky="w", pady=(8, 0))

        g = self.card(parent, None, _("2. Paste the answer"),
                      _("Copy the AI chat's whole answer, paste it here and press Write the texts. The texts are "
                        "written next to the video, ready for YouTube Studio."))
        self.answer = tk.Text(g, height=7, bg=FIELD, fg=TEXT, insertbackground=TEXT, bd=0, highlightthickness=1,
                              highlightbackground=BORDER, highlightcolor=ACCENT, font=("Consolas", 9),
                              padx=8, pady=6, wrap="word")
        self.answer.pack(fill="x", pady=(8, 0))
        row = ttk.Frame(g, style="Card.TFrame")
        row.pack(anchor="w", pady=(8, 0))
        ttk.Button(row, text=_("Write the texts"), command=self._write_texts).pack(side="left")
        ttk.Button(row, text=_("Clear"), command=lambda: self.answer.delete("1.0", "end")).pack(side="left",
                                                                                              padx=(8, 0))

    def _prompt_path(self):
        try:
            return self.app.output_folder() / (self.app.video_path().stem + "_prompt.txt")
        except DavarError:
            return None

    def _people(self):
        page = next((p for p in self.app.pages if isinstance(p, TitlesPage)), None)
        try:
            people = titles.parse_people(page._rows()) if page is not None else []
        except DavarError:
            people = []
        return [(person["name"], person["title"]) for person in people]

    def missing(self):
        video = self.app.video.get().strip() and self.app.video_path().is_file()
        prompt = self._prompt_path() if video else None
        people = self._people()
        self.prompt_status.configure(text=(_("Speakers from the Titles page: {list}").format(
            list=", ".join(name for name, _title in people)) if people
            else _("No speakers are written on the Titles page; the lines will not say who speaks.")))
        self.copy_button.configure(state="normal" if prompt is not None and prompt.is_file() else "disabled")
        installed = ai.claude_path() is not None
        self.direct_box.configure(state="normal" if installed else "disabled")
        self.direct_status.configure(text=(
            _("Claude Code writes the texts with your Claude subscription, in a few minutes. It is sent what "
              "you would paste into a chat: the transcript and the notes. The first time, sign in to it: "
              "type claude in a terminal and then /login.") if installed else
            _("Claude Code is not installed on this computer, so the prompt is copied for an AI chat. "
              "Claude Code is Anthropic's command-line program: claude.com/product/claude-code")))
        if video and not self.app.transcript():
            return _("Run Transcribe first")
        return ""

    def read_settings(self):
        saved = self.app.transcript()
        return dict(video=self.app.video_path(), folder=self.app.output_folder(),
                    words=saved["words"] if saved else None, language=saved.get("language", "tr") if saved else "tr",
                    programme=self.programme.get(), channel=self.channel.get(), notes=self.notes.get(),
                    people=self._people(), direct=self.direct.get() and ai.claude_path() is not None)

    def run(self, settings, progress):
        settings = dict(settings)
        direct = settings.pop("direct")
        result = content.prepare(progress=progress, **settings)
        if direct:  # Claude Code answers here; a failure leaves the prompt to be pasted into a chat
            progress(95, _("Claude Code is writing the texts (a few minutes)"))
            try:
                result["answer_text"] = ai.ask_claude(result["prompt"])
                result["texts"] = content.finish(settings["video"], result["answer_text"], settings["folder"],
                                                 settings["language"])
            except DavarError as e:
                result["asked_error"] = str(e)
        return result

    def finish(self, result):
        if result.get("answer_text"):  # shown in box 2, where it can be changed and written again
            self.answer.delete("1.0", "end")
            self.answer.insert("1.0", result["answer_text"])
        if result.get("texts"):
            result["output"] = result["texts"]["output"]
        else:
            self._copy(result["prompt"])
        return result

    def result_text(self, result):
        if result.get("texts"):
            return "\n".join([content.report_prompt(result, copied=False), "",
                              _("Claude Code answered."), content.report_texts(result["texts"])])
        text = content.report_prompt(result)
        if result.get("asked_error"):
            text = (_("Claude Code could not write the texts: {message}").format(message=result["asked_error"])
                    + "\n" + text)
        return text

    def _copy(self, text):
        self.app.clipboard_clear()
        self.app.clipboard_append(text)

    def _copy_again(self):
        path = self._prompt_path()
        if path is not None and path.is_file():
            self._copy(path.read_text(encoding="utf-8"))
            self.app.log(_("The prompt is copied again: {path}").format(path=path))

    def _write_texts(self):
        if not self.app.video.get().strip() or not self.app.video_path().is_file():
            self.app.log(_("Choose a video at the top first"), error=True)
            return
        saved = self.app.transcript()
        try:
            result = content.finish(self.app.video_path(), self.answer.get("1.0", "end"), self.app.output_folder(),
                                    saved.get("language", "tr") if saved else "tr")
        except DavarError as e:
            self.app.log(_("Failed: {message}").format(message=e), error=True)
            return
        self.app.last_output = result["output"]
        self.app.folder_button.configure(state="normal")
        self.app.log(content.report_texts(result))


class VisualAssetsPage(Planned):
    name = N_("Visual Assets")
    description = N_("Arranges the photos, documents and footage to cut in, according to what is being said.")
    will_do = (
        N_("Lists the places, people and documents named in the text: which visual should go where."),
        N_("Places the visuals you choose at the right time, with a slow zoom."),
    )
    needs = N_("The scope of this workflow is not settled yet; the others come first.")


class PublishPage(Planned):
    name = N_("Publish")
    description = N_("Gathers the texts and files needed before uploading to YouTube. The description, "
                     "chapters, titles and tags are already written by Content Analysis.")
    will_do = (
        N_("Suggests text and a frame for the thumbnail."),
        N_("Makes the thumbnail picture."),
    )
    needs = N_("The texts of Content Analysis.")


PAGES = [AudioPage, PicturePage, TranscribePage, RoughCutPage, MultiCamPage, ContentAnalysisPage,
         TitlesPage, VisualAssetsPage, SocialClipsPage, PublishPage]


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Davar {VERSION}")
        self.configure(bg=BACKGROUND)
        self.geometry("1180x900")
        self.minsize(1040, 800)
        self._style()
        self.video = tk.StringVar()
        self.folder = tk.StringVar()
        self.queue = queue.Queue()
        self.busy = False
        self.last_output = None
        self.root_frame = None
        self.owner = None  # the video whose own settings (trim times ...) are on screen
        self.restoring = True  # while settings are being put back nothing is written
        self._inherit = False
        self._pending = None
        last = i18n.load_settings()
        page = last.get("last_page")
        self.shown = page if type(page) is int and 0 <= page < len(PAGES) else 0
        self.video.trace_add("write", lambda *_args: self._video_changed())
        self.folder.trace_add("write", lambda *_args: (self._refresh_pages(), self.remember_soon()))
        self._build()
        self.after(100, self._poll)
        self.protocol("WM_DELETE_WINDOW", self._close)
        start = last.get("last_video")
        if len(sys.argv) > 1 and Path(sys.argv[1]).is_file():  # a file dropped onto the launcher
            start = sys.argv[1]
        if isinstance(start, str) and Path(start).is_file():  # else carry on with the last video
            self.video.set(start)

    # --- layout -----------------------------------------------------------------
    def _build(self):
        """Create every widget. Called again when the interface language changes."""
        if self.root_frame is not None:
            self.root_frame.destroy()
        self.restoring = True  # until _recall has filled the new pages
        self.pages, self.menu_buttons = [], []
        self.root_frame = tk.Frame(self, bg=BACKGROUND)
        self.root_frame.pack(fill="both", expand=True)
        self._header(self.root_frame)
        self._footer(self.root_frame)
        middle = tk.Frame(self.root_frame, bg=BACKGROUND)
        middle.pack(fill="both", expand=True, padx=16)
        menu = tk.Frame(middle, bg=BACKGROUND, width=250)
        menu.pack(side="left", fill="y", pady=(0, 12))
        menu.pack_propagate(False)
        body = ttk.Frame(middle, style="Panel.TFrame")
        body.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=(0, 12))
        for index, page_class in enumerate(PAGES):
            page = page_class(body, self, index + 1)
            page.place(relx=0, rely=0, relwidth=1, relheight=1)
            button = tk.Label(menu, text=f"{index + 1:02d}    " + _(page_class.name), anchor="w", padx=18,
                              pady=10, font=("Segoe UI Semibold", 11), cursor="hand2")
            button.pack(fill="x", pady=(0, 2))
            button.bind("<Button-1>", lambda _e, i=index: self.show(i))
            self.pages.append(page)
            self.menu_buttons.append(button)
        self.show(self.shown)
        self._recall()
        self.log(_("Davar is ready. Choose a video, then a workflow on the left."))

    def _header(self, parent):
        top = ttk.Frame(parent, style="Panel.TFrame", padding=(22, 16))
        top.pack(fill="x", padx=16, pady=(16, 12))
        left = ttk.Frame(top, style="Panel.TFrame")
        left.pack(side="left")
        ttk.Label(left, text="DAVAR", style="Logo.TLabel").pack(anchor="w")
        ttk.Label(left, text=_("Pre-edit helper for DaVinci Resolve") + f"  ·  v{VERSION}",
                  style="PanelMuted.TLabel").pack(anchor="w")
        row = ttk.Frame(left, style="Panel.TFrame")
        row.pack(anchor="w", pady=(8, 0))
        ttk.Label(row, text=_("Interface"), style="PanelMuted.TLabel").pack(side="left")
        self.language_box = ttk.Combobox(row, values=list(i18n.LANGUAGES.values()), width=10, state="readonly")
        self.language_box.set(i18n.LANGUAGES[i18n.language()])
        self.language_box.pack(side="left", padx=(8, 0))
        self.language_box.bind("<<ComboboxSelected>>", lambda _e: self._change_language())

        right = ttk.Frame(top, style="Panel.TFrame")
        right.pack(side="right")
        ttk.Label(right, text=_("Video / audio file"), style="Panel.TLabel").grid(row=0, column=0, sticky="e", padx=(0, 10))
        ttk.Entry(right, textvariable=self.video, width=56).grid(row=0, column=1, ipady=3)
        ttk.Button(right, text=_("Choose"), command=self._choose_video).grid(row=0, column=2, padx=(8, 0))
        ttk.Label(right, text=_("Output folder"), style="Panel.TLabel").grid(
            row=1, column=0, sticky="e", padx=(0, 10), pady=(8, 0))
        ttk.Entry(right, textvariable=self.folder, width=56).grid(row=1, column=1, ipady=3, pady=(8, 0))
        ttk.Button(right, text=_("Choose"), command=self._choose_folder).grid(row=1, column=2, padx=(8, 0), pady=(8, 0))
        ttk.Label(right, text=_("Leave empty to write the outputs next to the video"),
                  style="PanelMuted.TLabel", font=("Segoe UI", 8)).grid(row=2, column=1, sticky="w", pady=(2, 0))

    def _footer(self, parent):
        bottom = ttk.Frame(parent, style="Panel.TFrame", padding=(18, 12))
        bottom.pack(side="bottom", fill="x", padx=16, pady=(0, 16))
        row = ttk.Frame(bottom, style="Panel.TFrame")
        row.pack(fill="x")
        ttk.Label(row, text=_("PROCESS"), style="Tag.TLabel").pack(side="left")
        self.folder_button = ttk.Button(row, text=_("Show the output in its folder"),
                                        command=self._open_folder, state="disabled")
        self.folder_button.pack(side="right")
        self.overall = ttk.Label(row, text=_("Ready"), style="Panel.TLabel")
        self.overall.pack(side="right", padx=14)
        self.bar = ttk.Progressbar(bottom, style="Red.Horizontal.TProgressbar", maximum=100)
        self.bar.pack(fill="x", pady=(8, 10))
        ttk.Label(bottom, text=_("LOG"), style="Tag.TLabel").pack(anchor="w")
        self.log_box = tk.Text(bottom, height=7, wrap="word", bd=0, bg=FIELD, fg=TEXT,
                               insertbackground=TEXT, font=("Consolas", 10), padx=12, pady=10,
                               highlightthickness=1, highlightbackground=BORDER, state="disabled")
        self.log_box.pack(fill="x", pady=(6, 0))
        self.log_box.tag_configure("error", foreground=ACCENT)
        self.log_box.tag_configure("clock", foreground=MUTED)

    def _style(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(".", background=BACKGROUND, foreground=TEXT, font=("Segoe UI", 10),
                    bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER)
        for name, colour in (("Panel", PANEL), ("Card", CARD)):
            s.configure(f"{name}.TFrame", background=colour)
            s.configure(f"{name}.TLabel", background=colour, foreground=TEXT)
            s.configure(f"{name}Muted.TLabel", background=colour, foreground=MUTED, font=("Segoe UI", 9))
        s.configure("PanelMuted.TLabel", font=("Segoe UI", 10))
        s.configure("Logo.TLabel", background=PANEL, foreground="white", font=("Segoe UI", 22, "bold"))
        s.configure("Title.TLabel", background=PANEL, foreground="white", font=("Segoe UI Semibold", 20))
        s.configure("Tag.TLabel", background=PANEL, foreground=ACCENT, font=("Segoe UI Semibold", 9))
        s.configure("CardTitle.TLabel", background=CARD, foreground="white", font=("Segoe UI Semibold", 11))
        for name, font in (("Card.TCheckbutton", ("Segoe UI", 10)),
                           ("CardTitle.TCheckbutton", ("Segoe UI Semibold", 11))):
            s.configure(name, background=CARD, foreground=TEXT, font=font, indicatorbackground=FIELD,
                        indicatorforeground="white", indicatormargin=(0, 0, 8, 0))
            s.map(name, background=[("active", CARD)], foreground=[("disabled", MUTED)],
                  indicatorbackground=[("selected", RED), ("active", FIELD)],
                  indicatorforeground=[("selected", "white")])
        for name in ("TEntry", "TSpinbox", "TCombobox"):
            s.configure(name, fieldbackground=FIELD, foreground=TEXT, insertcolor=TEXT, background=CARD,
                        arrowcolor=TEXT, bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER, padding=4)
            s.map(name, fieldbackground=[("disabled", CARD), ("readonly", FIELD)],
                  foreground=[("disabled", MUTED), ("readonly", TEXT)],
                  bordercolor=[("focus", ACCENT)], lightcolor=[("focus", ACCENT)],
                  selectbackground=[("readonly", FIELD)], selectforeground=[("readonly", TEXT)])
        self.option_add("*TCombobox*Listbox.background", FIELD)
        self.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.option_add("*TCombobox*Listbox.selectBackground", RED)
        s.configure("TButton", background="#2A3342", foreground=TEXT, padding=(14, 6), borderwidth=0,
                    font=("Segoe UI Semibold", 10))
        s.map("TButton", background=[("disabled", "#1F2632"), ("active", "#36415A")],
              foreground=[("disabled", "#566072")])
        s.configure("Main.TButton", background=RED, foreground="white", padding=(30, 10),
                    font=("Segoe UI Semibold", 12))
        s.map("Main.TButton", background=[("disabled", "#3A2327"), ("active", RED_DARK)],
              foreground=[("disabled", "#8A6D70")])
        s.configure("Vertical.TScrollbar", background="#2A3342", troughcolor=PANEL, bordercolor=PANEL,
                    lightcolor="#2A3342", darkcolor="#2A3342", arrowcolor=MUTED, gripcount=0)
        s.map("Vertical.TScrollbar", background=[("active", "#36415A")])
        s.configure("Panel.TCheckbutton", background=PANEL, foreground=TEXT, indicatorbackground=FIELD,
                    indicatorforeground="white")
        s.map("Panel.TCheckbutton", background=[("active", PANEL)],
              indicatorbackground=[("selected", RED), ("active", FIELD)])
        s.configure("Treeview", background=FIELD, fieldbackground=FIELD, foreground=TEXT, rowheight=28,
                    bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER, font=("Segoe UI", 10))
        s.configure("Treeview.Heading", background=CARD, foreground=TEXT, relief="flat",
                    font=("Segoe UI Semibold", 10), padding=(6, 6))
        s.map("Treeview", background=[("selected", "#36415A")], foreground=[("selected", "white")])
        s.map("Treeview.Heading", background=[("active", CARD)])
        s.configure("Horizontal.TScale", background=CARD, troughcolor=FIELD, bordercolor=BORDER,
                    lightcolor=BORDER, darkcolor=BORDER)
        s.configure("Red.Horizontal.TProgressbar", background=RED, troughcolor=FIELD,
                    bordercolor=BORDER, lightcolor=RED, darkcolor=RED, thickness=10)

    # --- shared behaviour ---------------------------------------------------------
    def _change_language(self):
        code = next(c for c, label in i18n.LANGUAGES.items() if label == self.language_box.get())
        if code == i18n.language():
            return
        if self.busy:  # the running job reports in the old language; switch once it is done
            self.language_box.set(i18n.LANGUAGES[i18n.language()])
            self.log(_("The language can be changed once the running job has finished."), error=True)
            return
        self._remember()  # the pages are built anew and filled from what is remembered
        i18n.set_language(code, remember=True)
        self._build()

    # --- remembered settings (see memory.py) ----------------------------------------
    def _recall(self):
        """Fill the freshly built pages with the settings last used."""
        self.restoring = True
        settings = i18n.load_settings()
        defaults = settings.get("defaults") if isinstance(settings.get("defaults"), dict) else {}
        for page in self.pages:
            page.set_values(memory.chosen(defaults, page.key + ".", {n: page.initial[n] for n in page.general}))
        if self.owner is not None:
            self._show_own(memory.video_values(settings, self.owner) or {})
        self.restoring = False
        self._refresh_pages()

    def _own_start(self):
        """What a video's own settings are before anything is entered for it."""
        start = {"folder": ""}
        for page in self.pages:
            start.update({f"{page.key}.{name}": page.initial[name] for name in page.per_video})
        return start

    def _own_values(self):
        """The video's own settings as they stand on screen."""
        values = {"folder": self.folder.get().strip()}
        for page in self.pages:
            values.update({f"{page.key}.{name}": value for name, value in page.values(page.per_video).items()})
        return values

    def _show_own(self, stored):
        """Put a video's own settings on screen; what was never entered for it starts empty."""
        was, self.restoring = self.restoring, True
        self.folder.set(memory.chosen(stored, "", {"folder": ""})["folder"])
        for page in self.pages:
            if page.per_video:
                page.set_values(memory.chosen(stored, page.key + ".", {n: page.initial[n] for n in page.per_video}))
        self.restoring = was

    def _video_changed(self):
        """Another video was chosen: keep the settings of the one left, bring back those of the new one."""
        self._refresh_pages()
        text, path = self.video.get().strip(), self.video_path()
        if self.restoring or not text or not path.is_file():
            return
        if self.owner is not None and memory.key(path) == memory.key(self.owner):
            return
        self._remember()  # what is on screen still belongs to the video being left
        stored = memory.video_values(i18n.load_settings(), path)
        inherit, self._inherit = self._inherit, False
        previous, self.owner = self.owner, str(path)
        # A video made from the one on screen keeps what is on screen. So does the first video
        # chosen in a session when nothing is remembered for it: something may have been typed already.
        if not inherit and (stored is not None or previous is not None):
            self._show_own(stored or {})
            start = self._own_start()
            if stored and any(memory.fits(stored.get(name), value) and stored[name] != value
                              for name, value in start.items()):
                self.log(_("The settings last used for this video were brought back."))
        self._remember(touch=True)

    def continue_with(self, video):
        """Carry on with a video made from the selected one; it keeps that one's settings."""
        self._inherit = True
        self.video.set(str(video))
        self._inherit = False

    def remember_soon(self):
        """Something changed: write the settings shortly, once, however fast the changes come."""
        if self.restoring:
            return
        if self._pending is not None:
            self.after_cancel(self._pending)
        self._pending = self.after(600, self._remember)

    def _remember(self, touch=False):
        if self._pending is not None:
            self.after_cancel(self._pending)
            self._pending = None
        settings = i18n.load_settings()
        before = json.dumps(settings, sort_keys=True)
        defaults = settings.get("defaults") if isinstance(settings.get("defaults"), dict) else {}
        for page in self.pages:
            defaults.update({f"{page.key}.{name}": value for name, value in page.values(page.general).items()})
        settings["defaults"] = defaults
        settings["last_page"] = self.shown
        if self.owner is not None:
            memory.store_video(settings, self.owner, self._own_values(), touch=touch)
            settings["last_video"] = self.owner
        if json.dumps(settings, sort_keys=True) != before:
            try:
                i18n.save_settings(settings)
            except OSError:
                pass  # remembering is a convenience; the work itself must not stop for it

    def _close(self):
        self._remember()
        self.destroy()

    def show(self, index):
        self.shown = index
        self.remember_soon()
        self.pages[index].tkraise()
        for i, button in enumerate(self.menu_buttons):
            if i == index:
                button.configure(bg=RED, fg="white")
            else:
                button.configure(bg=PANEL, fg=TEXT if PAGES[i].ready else "#66707F")

    def video_path(self):
        return Path(self.video.get().strip().strip('"'))

    def transcript(self):
        """The saved transcript of the selected video, or None."""
        video = self.video_path()
        if not self.video.get().strip() or not video.is_file():
            return None
        folder = self.folder.get().strip().strip('"')
        return transcript.load(video, folder if folder and Path(folder).is_dir() else None)

    def output_folder(self):
        """The folder of the video is used when no output folder is given."""
        given = self.folder.get().strip().strip('"')
        folder = Path(given) if given else self.video_path().parent
        if not folder.is_dir():
            raise DavarError(_("output folder not found: {path}").format(path=folder))
        return folder

    def _choose_video(self):
        start = self.video_path().parent if self.video.get().strip() else None
        path = filedialog.askopenfilename(title=_("Choose a video"), filetypes=media_types(),
                                          initialdir=start if start and start.is_dir() else None)
        if path:
            self.video.set(os.path.normpath(path))

    def _choose_folder(self):
        path = filedialog.askdirectory(title=_("Choose the output folder"))
        if path:
            self.folder.set(os.path.normpath(path))

    def _refresh_pages(self):
        for page in getattr(self, "pages", []):
            page.refresh_state()

    def log(self, text, error=False, tall=False):
        """Add a time-stamped entry to the log. `tall` makes room for a long entry."""
        if tall:
            self.log_box.configure(height=11)
        self.log_box.configure(state="normal")
        self.log_box.insert("end", time.strftime("%H:%M:%S  "), "clock")
        self.log_box.insert("end", text.strip().replace("\n", "\n          ") + "\n", "error" if error else ())
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def start_job(self, page, settings):
        self.busy = True
        self.log_box.configure(height=7)  # back to normal after a tall entry
        self.last_output = None
        self.folder_button.configure(state="disabled")
        self.bar["value"] = 0
        self._refresh_pages()
        self.log(_("{workflow} started.").format(workflow=_(page.name)))

        def work():
            try:
                result = page.run(settings, lambda pct, msg: self.queue.put(("progress", pct, msg)))
                self.queue.put(("done", page, result))
            except DavarError as e:
                self.queue.put(("error", str(e)))
            except Exception as e:  # show unexpected errors in the log as well
                self.queue.put(("error", _("Unexpected error: {kind}: {message}").format(
                    kind=type(e).__name__, message=e)))
        threading.Thread(target=work, daemon=True).start()

    def _poll(self):
        try:
            while True:
                event = self.queue.get_nowait()
                if event[0] == "progress":
                    self.bar["value"] = event[1]
                    self.overall.configure(text=event[2] + "…")
                    continue
                self.busy = False
                if event[0] == "done":
                    page = event[1]
                    try:
                        result = page.finish(event[2])
                    except DavarError as e:
                        result = None
                        self.log(_("Failed: {message}").format(message=e), error=True)
                    if result is None:
                        self.bar["value"] = 0
                        self.log(_("{workflow}: nothing was written.").format(workflow=_(page.name)))
                        self.overall.configure(text=_("Ready"))
                    else:
                        self.last_output = result["output"]
                        self.log(page.result_text(result))
                        self.overall.configure(text=_("Finished"))
                        self.folder_button.configure(state="normal")
                else:
                    self.bar["value"] = 0
                    self.log(_("Failed: {message}").format(message=event[1]), error=True)
                    self.overall.configure(text=_("Ready"))
                self._refresh_pages()
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _open_folder(self):
        if self.last_output:
            # show the output file selected in Explorer
            subprocess.Popen(["explorer", "/select,", os.path.normpath(str(self.last_output))])


if __name__ == "__main__":
    App().mainloop()
