"""davar interface - pick a workflow on the left, a video at the top, and start.

Opened by double-clicking Davar.bat. The real work lives in audio.py, transcript.py,
roughcut.py, titles.py and clips.py.

To add a workflow: write a class derived from Page (build, missing, read_settings,
run, result_text) and add it to the PAGES list near the bottom.
"""

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
import audio  # noqa: E402
import clips  # noqa: E402
import dictionary  # noqa: E402
import i18n  # noqa: E402
import roughcut  # noqa: E402
import titles  # noqa: E402
import transcript  # noqa: E402
from common import SAMPLE_RATE, DavarError, format_time, parse_ranges, parse_time, run  # noqa: E402
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
SPEECH_LANGUAGES = ["tr", "en", "de", "fr", "es", "it", "pt", "nl", "ru", "ar"]


def media_types():
    return [(_("Video and audio files"), "*.mp4 *.mov *.mkv *.avi *.mts *.m4v *.webm *.wav *.mp3"),
            (_("All files"), "*.*")]


class Page(ttk.Frame):
    """One workflow's page. The video, output folder, progress bar and log are shared
    (they sit at the top and bottom of the application); a page holds only its own settings.
    """

    name = ""  # shown in the menu
    description = ""
    ready = True  # False for a workflow that is not written yet
    needs_video = True  # False if it can also run without a selected video

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
            self.status = ttk.Label(top, text="", style="PanelMuted.TLabel")
            self.status.pack(side="right", padx=14)
        ttk.Label(self, text=_(self.description), style="PanelMuted.TLabel", wraplength=760,
                  justify="left").pack(anchor="w", pady=(4, 14))
        self.build(self._scroll_area())

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

    def build(self, parent):
        self.normalize = tk.BooleanVar(value=True)
        self.balance = tk.BooleanVar(value=False)
        self.denoise = tk.BooleanVar(value=False)
        self.files = []

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

    def _remove(self):
        for i in reversed(self.listbox.curselection()):
            self.listbox.delete(i)
            del self.files[i]
        self.refresh_state()

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
        self.app.video.set(str(result["output"]))  # the next steps should work on the new video
        return result

    def result_text(self, result):
        return (audio.report(result) + "\n"
                + _("The video field now points to this new file; the next steps work on it."))


class TranscribePage(Page):
    name = N_("Transcribe")
    description = N_("Transcribes the speech once, word by word with timing, and saves it next to the "
                     "video. The later workflows use this; the same video is not transcribed again.")

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

    def build(self, parent):
        self.silence = tk.BooleanVar(value=True)
        self.hesitations = tk.BooleanVar(value=True)
        self.review_file = tk.BooleanVar(value=False)
        self.ask = tk.BooleanVar(value=True)
        self.min_silence = tk.DoubleVar(value=0.5)
        self.pad_before = tk.DoubleVar(value=0.10)
        self.pad_after = tk.DoubleVar(value=0.15)
        self.min_hesitation = tk.DoubleVar(value=0.30)
        self.fillers = tk.StringVar()
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

        g = self.card(parent, self.hesitations, _("Find “uh / um” hesitations"),
                      _("Finds drawn-out thinking sounds from the audio itself."))
        self.seconds_row(g, 0, _("Shortest hesitation"), self.min_hesitation, 0.2, 1.0,
                         _("Lower it to catch more; wrong candidates increase"))

        g = self.card(parent, None, _("Filler words"),
                      _("The speaker's verbal habits. Separate with commas: you know, like, I mean"))
        ttk.Entry(g, textvariable=self.fillers).pack(fill="x", pady=(8, 0))
        self.transcript_status = ttk.Label(g, text="", style="CardMuted.TLabel", wraplength=700, justify="left")
        self.transcript_status.pack(anchor="w", pady=(6, 0))

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
        for variable in (self.fillers, self.keep_from, self.keep_to, self.remove):
            variable.trace_add("write", lambda *_args: self.refresh_state())

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
        if self._filler_list() and not saved:
            return _("Run Transcribe first to use filler words")
        if not (self.silence.get() or self.hesitations.get() or self._filler_list() or self._trimming()):
            return _("Tick at least one thing to cut")
        return ""

    def read_settings(self):
        video = self.app.video_path()
        saved = self.app.transcript()
        return dict(
            output=self.app.output_folder() / (video.stem + "_cut.fcpxml"),
            review=self.review_file.get(), ask=self.ask.get(),
            analysis=dict(
                video=video, silence=self.silence.get(), hesitations=self.hesitations.get(),
                min_silence=float(self.min_silence.get()), pad_before=float(self.pad_before.get()),
                pad_after=float(self.pad_after.get()), min_hesitation=float(self.min_hesitation.get()),
                words=saved["words"] if saved else None, filler_words=self._filler_list(),
                language=saved.get("language", "tr") if saved else "tr",
                keep_from=parse_time(self.keep_from.get()) if self.keep_from.get().strip() else None,
                keep_to=parse_time(self.keep_to.get()) if self.keep_to.get().strip() else None,
                remove=parse_ranges(self.remove.get())),
        )

    def run(self, settings, progress):
        return {"state": roughcut.analyze(progress=progress, **settings["analysis"]), "settings": settings}

    def finish(self, result):
        state, settings = result["state"], result["settings"]
        if settings["ask"] and state["candidates"]:
            if not ReviewWindow(self.app, state).approved:
                return None
        return roughcut.apply(state, output=settings["output"], review=settings["review"])

    def result_text(self, result):
        return roughcut.report(result, detailed=False)


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
        self.doubtful = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text=_("Show only the uncertain ones"), variable=self.doubtful,
                        style="Panel.TCheckbutton", command=self._fill).pack(anchor="w", pady=(8, 0))

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
        columns = (("cut", _("Cut"), 50, "center"), ("time", _("Time"), 90, "e"),
                   ("length", _("Length"), 70, "e"), ("kind", _("Kind"), 230, "w"),
                   ("confidence", _("Confidence"), 90, "w"), ("context", _("Context"), 480, "w"))
        self.tree = ttk.Treeview(middle, columns=[c[0] for c in columns], show="headings", selectmode="browse")
        for code, label, width, anchor in columns:
            self.tree.heading(code, text=label, anchor=anchor)
            self.tree.column(code, width=width, anchor=anchor, stretch=code == "context")
        bar = ttk.Scrollbar(middle, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=bar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y", padx=(6, 0))
        self.tree.tag_configure("doubtful", foreground=ACCENT)
        self.tree.tag_configure("kept", foreground=MUTED)
        self.tree.bind("<Button-1>", self._click)
        self.tree.bind("<Double-1>", lambda _e: self._listen(False))
        self.tree.bind("<space>", lambda _e: self._toggle())
        self.tree.bind("<Return>", lambda _e: self._listen(False))

        self._fill()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.grab_set()
        self.tree.focus_set()
        self.wait_window()

    # --- list -----------------------------------------------------------------
    def _row(self, i):
        c = self.candidates[i]
        return ("☑" if c["selected"] else "☐", format_time(c["start"]),
                f"{c['end'] - c['start']:.2f} " + _("s"), roughcut.kind_name(c),
                roughcut.confidence_name(c["confidence"]), c["context"])

    def _tags(self, i):
        c = self.candidates[i]
        return ("doubtful",) if c["confidence"] == "low" else (() if c["selected"] else ("kept",))

    def _fill(self):
        self.tree.delete(*self.tree.get_children())
        for i, c in enumerate(self.candidates):
            if self.doubtful.get() and c["confidence"] == "high":
                continue
            self.tree.insert("", "end", iid=str(i), values=self._row(i), tags=self._tags(i))
        rows = self.tree.get_children()
        if rows:
            self.tree.selection_set(rows[0])
            self.tree.focus(rows[0])
        self._summarize()

    def _summarize(self):
        cuts, _parts = roughcut.cut_plan(self.state)
        removed = sum(end - start for start, end in cuts) / self.state["fps"]
        self.summary.configure(
            text=_("{selected} of {total} candidates will be cut ({shown} in the list). With the silences "
                   "the timeline gets {time} shorter.").format(
                selected=sum(c["selected"] for c in self.candidates), total=len(self.candidates),
                shown=len(self.tree.get_children()), time=format_time(removed)))

    def _selected(self):
        selection = self.tree.selection()
        return int(selection[0]) if selection else None

    def _toggle(self, i=None):
        i = self._selected() if i is None else i
        if i is None:
            return
        self.candidates[i]["selected"] = not self.candidates[i]["selected"]
        self.tree.item(str(i), values=self._row(i), tags=self._tags(i))
        self._summarize()

    def _click(self, event):
        row = self.tree.identify_row(event.y)
        if row and self.tree.identify_column(event.x) == "#1":
            self._toggle(int(row))

    def _set_all(self, value):
        for i, c in enumerate(self.candidates):
            c["selected"] = self.suggested[i] if value is None else value
        self._fill()

    def _tick_medium(self):
        """Also tick the medium-confidence sound candidates that arrive unticked, such as short hesitations."""
        for c in self.candidates:
            if c["confidence"] == "medium" and c["kind"] in ("alone", "before_word"):
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
    description = N_("Makes a lower third for a speaker's name and title: a ready video with a transparent "
                     "background and a soft entrance and exit. In Resolve it is dragged onto the track "
                     "above the video.")
    needs_video = False

    def build(self, parent):
        self.duration = tk.DoubleVar(value=6.0)
        self.positions = {_("Bottom left"): "left", _("Bottom centre"): "centre", _("Bottom right"): "right"}
        self.position = tk.StringVar(value=_("Bottom left"))
        self.colour = tk.StringVar(value="#E30613")

        g = self.card(parent, None, _("Speakers"),
                      _("One person per line: Name | Title. The title is optional. "
                        "A separate file is written for each person."))
        self.people = tk.Text(g, height=4, bg=FIELD, fg=TEXT, insertbackground=TEXT, bd=0,
                              highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT,
                              font=("Segoe UI", 11), padx=8, pady=6, wrap="none")
        self.people.pack(fill="x", pady=(8, 0))
        self.people.bind("<KeyRelease>", lambda _e: self.refresh_state())

        g = self.card(parent, None, _("Look"))
        ttk.Label(g, text=_("Time on screen"), style="Card.TLabel").grid(row=0, column=0, sticky="w", pady=(8, 0))
        ttk.Spinbox(g, textvariable=self.duration, from_=2, to=30, increment=0.5, width=6,
                    format="%.1f").grid(row=0, column=1, sticky="w", padx=(12, 6), pady=(8, 0))
        ttk.Label(g, text=_("s") + "      " + _("Opens in half a second, fades out at the end"),
                  style="CardMuted.TLabel").grid(row=0, column=2, sticky="w", pady=(8, 0))
        ttk.Label(g, text=_("Place"), style="Card.TLabel").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Combobox(g, textvariable=self.position, values=list(self.positions), width=14,
                     state="readonly").grid(row=1, column=1, columnspan=2, sticky="w", padx=(12, 0), pady=(8, 0))
        ttk.Label(g, text=_("Accent colour"), style="Card.TLabel").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(g, textvariable=self.colour, width=10).grid(row=2, column=1, sticky="w", padx=(12, 6), pady=(8, 0))
        ttk.Label(g, text=_("Colour of the stripe and the title band; example #E30613"),
                  style="CardMuted.TLabel").grid(row=2, column=2, sticky="w", pady=(8, 0))
        self.size_note = ttk.Label(g, text="", style="CardMuted.TLabel")
        self.size_note.grid(row=3, column=0, columnspan=3, sticky="w", pady=(10, 0))

        self.card(parent, None, _("Coming next"),
                  _("Topic titles that appear as the subject changes, and placing lower thirds on the "
                    "timeline automatically."))

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
        if not self._rows():
            return _("Write at least one name")
        if not video and not self.app.folder.get().strip():
            return _("Choose an output folder to make one without a video")
        return ""

    def read_settings(self):
        return dict(rows=self._rows(), video=self._video(), folder=self.app.output_folder(),
                    duration=float(self.duration.get()), colour=self.colour.get(),
                    position=self.positions[self.position.get()])

    def run(self, settings, progress):
        rows = settings.pop("rows")
        return titles.make_lower_thirds(rows, progress=progress, **settings)

    def result_text(self, result):
        return titles.report(result)


class SocialClipsPage(Page):
    name = N_("Social Clips")
    description = N_("Cuts the range you choose from a landscape video into a vertical (9:16) Reels / Shorts "
                     "video. Puts the speaker's frame over a blurred background and adds a headline, "
                     "subtitles and an intro cover.")

    def build(self, parent):
        self.start = tk.StringVar()
        self.end = tk.StringVar()
        self.horizontal = tk.DoubleVar(value=50)
        self.kicker = tk.StringVar()
        self.headline1 = tk.StringVar()
        self.headline2 = tk.StringVar()
        self.subtitles = tk.BooleanVar(value=True)
        self.cover = tk.BooleanVar(value=False)

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
        for variable in (self.start, self.end, self.kicker, self.headline1, self.headline2, self.cover):
            variable.trace_add("write", lambda *_args: self.refresh_state())

    def missing(self):
        if not self.start.get().strip() or not self.end.get().strip():
            return _("Write the start and end time")
        if self.cover.get() and not (self.kicker.get().strip() or self.headline1.get().strip()
                                     or self.headline2.get().strip()):
            return _("Write a headline or a kicker for the intro cover")
        return ""

    def read_settings(self):
        video = self.app.video_path()
        saved = self.app.transcript() or {}
        return dict(
            video=video, output=self.app.output_folder() / (video.stem + "_vertical.mp4"),
            start=self.start.get(), end=self.end.get(), kicker=self.kicker.get(),
            headline=[self.headline1.get(), self.headline2.get()], horizontal=float(self.horizontal.get()) / 100,
            subtitles=self.subtitles.get(), cover=self.cover.get(), words=saved.get("words"),
            language=saved.get("language", i18n.load_settings().get("speech_language", "tr")),
        )

    def run(self, settings, progress):
        return clips.make_clip(progress=progress, **settings)

    def result_text(self, result):
        return clips.report(result)


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


class ContentAnalysisPage(Planned):
    name = N_("Content Analysis")
    description = N_("Reads the transcript and extracts the video's topics, chapters and highlights.")
    will_do = (
        N_("Extracts topic titles and YouTube chapter times."),
        N_("Lists a summary of the video and its standout sentences."),
        N_("Suggests candidate ranges for social clips (hook, context, payoff)."),
    )
    needs = N_("A language model that understands the text: either an online AI service (needs a key and a "
               "small fee, and the text leaves your computer) or a model running on your computer (free, "
               "slow and weaker). Which one will be used is not decided yet.")


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
    description = N_("Gathers the texts and files needed before uploading to YouTube.")
    will_do = (
        N_("Drafts a YouTube description with chapter times."),
        N_("Prepares title suggestions and tags."),
        N_("Suggests text and a frame for the thumbnail."),
    )
    needs = N_("The chapter extraction step of Content Analysis.")


PAGES = [AudioPage, TranscribePage, RoughCutPage, MultiCamPage, ContentAnalysisPage, TitlesPage,
         VisualAssetsPage, SocialClipsPage, PublishPage]


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Davar")
        self.configure(bg=BACKGROUND)
        self.geometry("1180x900")
        self.minsize(1040, 800)
        self._style()
        self.video = tk.StringVar()
        self.folder = tk.StringVar()
        self.queue = queue.Queue()
        self.busy = False
        self.last_output = None
        self.shown = 0
        self.root_frame = None
        self.video.trace_add("write", lambda *_args: self._refresh_pages())
        self.folder.trace_add("write", lambda *_args: self._refresh_pages())
        self._build()
        self.after(100, self._poll)
        if len(sys.argv) > 1 and Path(sys.argv[1]).is_file():  # a file dropped onto the launcher
            self.video.set(sys.argv[1])

    # --- layout -----------------------------------------------------------------
    def _build(self):
        """Create every widget. Called again when the interface language changes."""
        if self.root_frame is not None:
            self.root_frame.destroy()
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
                              pady=13, font=("Segoe UI Semibold", 11), cursor="hand2")
            button.pack(fill="x", pady=(0, 2))
            button.bind("<Button-1>", lambda _e, i=index: self.show(i))
            self.pages.append(page)
            self.menu_buttons.append(button)
        self.show(self.shown)
        self._refresh_pages()
        self.log(_("Davar is ready. Choose a video, then a workflow on the left."))

    def _header(self, parent):
        top = ttk.Frame(parent, style="Panel.TFrame", padding=(22, 16))
        top.pack(fill="x", padx=16, pady=(16, 12))
        left = ttk.Frame(top, style="Panel.TFrame")
        left.pack(side="left")
        ttk.Label(left, text="DAVAR", style="Logo.TLabel").pack(anchor="w")
        ttk.Label(left, text=_("Pre-edit helper for DaVinci Resolve"), style="PanelMuted.TLabel").pack(anchor="w")
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
        i18n.set_language(code, remember=True)
        self._build()

    def show(self, index):
        self.shown = index
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
