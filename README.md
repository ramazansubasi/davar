# Davar

A pre-edit helper for DaVinci Resolve. It takes over the tedious manual work on talking-head videos: syncing audio, cutting silences and "uh / um" hesitations, transcribing, making lower thirds and vertical clips.

*Türkçe: [README.tr.md](README.tr.md)*

> **Status: early release.** So far it has been tried with one user's handful of videos. Always watch the cuts before you publish, and please open an issue if you find a bug.

The name nods to two things: **Da**Vinci **R**esolve, and *Katır* ("mule"), İlker Canikligil's tool that pioneered this kind of workflow in Turkey. *Davar* is Turkish for a flock of sheep and goats, and like them it grazes off what your video does not need.

![The Davar window](docs/screenshot.png)

## Workflows

Five of the nine workflows work; four are planned.

| No | Workflow | Status | What it does |
|---|---|---|---|
| 01 | Audio | works | Puts separately recorded audio in its place in the video and sets the loudness for YouTube |
| 02 | Transcribe | works | Transcribes the speech once with word-level timing and saves it; writes subtitles (`.srt`) and text (`.txt`) |
| 03 | Rough Cut | works | Finds silences, "uh / um" hesitations and filler words, lets you review the candidates, writes a Resolve timeline (`.fcpxml`) |
| 04 | Multicam Edit | planned | Picks the camera of whoever is speaking |
| 05 | Content Analysis | planned | Extracts topics, chapter times and highlights |
| 06 | Titles | works | Makes a transparent lower third with a soft entrance and exit for a speaker's name and title |
| 07 | Visual Assets | planned | Places photos and documents to cut in |
| 08 | Social Clips | works | Cuts a chosen range into a vertical Reels / Shorts video with headline, subtitles and cover |
| 09 | Publish | planned | YouTube description, chapter times, title suggestions |

No workflow modifies your original video. Davar works with the **free version** of Resolve: it does not remote-control Resolve, it writes files that Resolve imports.

The interface is available in English and Turkish; pick the language at the top left of the window.

## Installation

You need:

- **Python 3.10** or newer
- **ffmpeg** (`ffmpeg` and `ffprobe` on your PATH)
- **numpy** and **Pillow**
- **faster-whisper** (for Transcribe and automatic subtitles)

```bash
pip install -r requirements.txt
```

An easy way to get ffmpeg on Windows:

```bash
winget install Gyan.FFmpeg
```

## Usage

### With the window

Double-click `Davar.bat`. Choose the video (and an output folder if you like) at the top, pick a workflow on the left, tick the settings and press **Start**. Progress and results appear in the log at the bottom. Dropping a video onto `Davar.bat` opens the window with that video selected.

Outside Windows:

```bash
python davar_gui.pyw
```

### From the command line

Every workflow is also a script:

```bash
python audio.py "video.mp4" --audio "lavalier.wav"
```

```bash
python transcript.py "video.mp4" --srt --text
```

```bash
python roughcut.py "video.mp4" --from 0:07 --to 51:19 --remove "50:46-51:03" --fillers "you know, like"
```

```bash
python titles.py "Jane Doe" "Journalist" --video "video.mp4"
```

```bash
python clips.py "video.mp4" 13:06 13:56 --headline "TRAFFIC IN TUZLA" --subtitles --cover
```

Run any of them with `--help` for all options.

### Importing into Resolve

1. Open a project in Resolve.
2. **File → Import → Timeline…** and choose the `<video>_cut.fcpxml` written next to the video.
3. Press **OK** in the dialog. The trimmed timeline opens on the Edit page.

## 01 Audio

Puts separately recorded audio (a lavalier microphone, an audio recorder, parts recorded afterwards) in its place in the video. It finds the place by itself: it compares the rhythm of the speech in both recordings, then aligns to sample accuracy. On long recordings it also measures and removes the drift caused by the two devices' clocks.

- Each recording's level is matched to the video's own audio, and it replaces the video's audio there.
- Audio that does not occur in the video is not placed; the report says which file was rejected.
- The whole track is brought to YouTube loudness (-14 LUFS). Optionally the speakers' levels are balanced and background noise is reduced.

The picture is not re-encoded; the result is written as `<video>_audio.mp4`. Do the next steps with that new video.

## 02 Transcribe

Transcribes the speech word by word with timing and saves it next to the video as `<video>.davar.json`. The other workflows read that file; the same video is never transcribed twice. It can also write subtitles you can upload to YouTube Studio (`.srt`) and a time-stamped text file (`_transcript.txt`).

Transcription runs on your computer with the Whisper model; nothing is sent to the internet (the model is downloaded once on first use). It gets names and numbers wrong; check before publishing.

### Editing the text and the personal dictionary

The **Edit the text** window shows the transcript line by line: listen to a line, correct it, press Enter for the next. Saving also rewrites the subtitle and text files.

Davar offers to add single-word corrections to your **personal dictionary**, the file `.davar/dictionary.txt` in your home folder. Each line reads `wrong = right`:

```
tuzda = Tuzla
Akbörse = Akköse
top sen = TÜPSAN
```

The dictionary is applied every time a transcript is read: a word taught once is fixed in later videos and in the ones transcribed before. A suffix after an apostrophe is kept (`Akbörse'nin` → `Akköse'nin`).

## 03 Rough Cut

| What it finds | How |
|---|---|
| Silences | From the audio level. The threshold is chosen from the recording's own background noise. Cut directly. |
| "Uh / um" hesitations | From the audio itself (flat pitch, steady sound). Checked against the transcript when there is one. |
| Filler words | From your list ("you know, like"), searched in the transcript. |
| Coughs and other non-speech sounds | Short bursts standing between silences. With a transcript, a burst no word was written for is non-speech. |

**Trimming.** You can also give the time the programme starts and ends, and ranges to drop from the middle (a repeated take, an off-air exchange): everything outside is removed. The page can print the first and last lines of the transcript to help you pick the times.

Hesitations and filler words arrive as **candidates** in a list with time, kind, confidence and the surrounding sentence. You can listen to each candidate, hear how it sounds with the cut, and change its tick. Confident ones arrive ticked, doubtful ones unticked; filler words always arrive unticked, because only you can tell which ones are superfluous.

### How silences and hesitations are found

**Silence.** The audio is split into 10 millisecond slices and each slice's level is measured. The threshold is placed between the background noise and the speech level. Stretches that stay below it long enough are cut, leaving a little padding around words.

**Hesitation.** An "uh" differs from speech in three ways: it is voiced, its pitch stays flat and the mouth shape does not change. In normal speech those three never hold together for 0.3 seconds. Davar looks for stretches that fit this pattern and sorts them:

- standing alone, with silence on both sides,
- following a silence and running straight into a word ("uh so…"),
- glued to the *end* of a word. These are usually part of a real word, so they are shown but not cut by default.

An "uh" rarely stops abruptly: it fades for another 0.1-0.3 seconds. The cut follows that fading tail to where the next sound begins, so no stub is left behind.

No AI model or internet connection is needed for this; it is computed from the audio. That is why Rough Cut also works on videos that have not been transcribed.

## 06 Titles

Makes a lower third for a speaker's name and title: an accent stripe on the left, the name on top, the title below. It opens from the left in half a second and fades out at the end. The output is a video with a transparent background (ProRes 4444, `lowerthird_<name>.mov`); in Resolve you drag it onto the track above the video and need no further effect.

The size and frame rate come from the selected video; the duration, place (left, centre, right) and accent colour can be set.

## 08 Social Clips

Cuts the time range you give from a landscape video into a 1080x1920 vertical video: the speaker's frame over a blurred background, a short kicker and up to two headline lines on top. Optionally it adds subtitles and a 2.5 second intro cover. Loudness is brought to the social media level (-14 LUFS).

Subtitles use the transcript when there is one; otherwise the chosen range is transcribed on the spot. They are burned in and cannot be corrected afterwards, so fix the transcript first.

## Limits

- Only clear hesitations of at least 0.3 seconds are cut by default. Shorter ones are offered as suggestions when the transcript also heard them.
- Filler-word timing comes from the transcript and is approximate; use "Listen with the cut" before cutting them.
- On recordings with a noisy background (street, wind, music) silence detection gets weaker. Davar warns when that happens.
- On recordings with a variable frame rate (some phone and screen recordings) cut points may drift in Resolve. Davar warns when that happens.
- Cuts are automatic; watching them before you publish is your job.

## Development

The computational parts (silence and hesitation detection, candidate selection, subtitles, audio matching, dictionary, transcript editing, lower-third drawing) and the completeness of the translations are tested with synthetic data; neither ffmpeg nor a video is needed.

```bash
python -m unittest discover tests
```

**Adding a workflow.** In `davar_gui.pyw` write a class derived from `Page` and add it to the `PAGES` list; the video and output folder pickers, the Start button, the progress bar and the log come for free. Planned workflows live in the same file as stubs derived from `Planned`.

**Adding a language.** Source strings are English. Create `lang_<code>.py` with a `TRANSLATIONS` dict (see `lang_tr.py`) and add the language to `LANGUAGES` in `i18n.py`. A test fails if a string used in the code has no Turkish translation.

## Changes

What changed in each version is listed in [CHANGELOG.md](CHANGELOG.md).

## Contributing

Bug reports and suggestions are welcome as issues. Trials with different speakers, languages and recording conditions are especially valuable.

## License

[MIT](LICENSE)
