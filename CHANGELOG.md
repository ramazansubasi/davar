# Changelog

## Unreleased

### Added

- **Picture**, a new workflow (02) for footage shot on a phone:
  - **Reframe to 16:9.** Cuts the sides of a picture wider than 16:9, from the left, the right or both, so it fills the frame with no black bars.
  - **Lock the frame.** For a camera on a tripod. While a phone hunts for focus the whole picture grows, shrinks and hops, and over a long recording the frame creeps by several pixels. Every frame is lined up with one reference frame, so the background stands still and cuts show less.
  - The audio is copied untouched, and a transcript already made is carried over to the new video.
- **Settings are remembered.** Nothing has to be entered again when Davar is opened:
  - General settings (thresholds, paddings, filler words, ticked options, speaker names) come back as last used.
  - Settings that belong to one video (trim times, the range of a social clip, separate audio files, the output folder) are kept with that video and come back when it is chosen again.
  - Davar opens with the video and the page last worked on, and a video it wrote from another one starts with the settings of its source.
  - Each page has a **Back to defaults** button, and the settings survive a change of the interface language.
- **Titles: names placed on the timeline.** Write the speakers in the order they first speak; Davar tells the voices apart and puts each lower third on the track above the video, a few seconds after that person first speaks. The names go into the Rough Cut timeline when there is one, the log shows the words spoken at each place, a time can be given by hand (`Name | Title | 0:41`), and running Rough Cut again keeps the names.
- **Rough Cut: move closer to the speaker.** To hide jump cuts the timeline is framed as with a second camera: closer to whoever gives a long answer, toward the side they sit on, and on everyone during quick exchanges. Inside a long answer the framing changes about every half minute, at the cut that jumps most. Who speaks comes from the transcript, who sits where from the Titles page; name titles already on the timeline stay.
- **Rough Cut: subtitles for the cut.** With a transcript, Rough Cut also writes subtitles that follow the cut timeline (`<video>_cut.srt`); words cut away are left out and the rest move to their time on the timeline. Correcting the text rewrites them too.
- **Titles: a place for each name.** A line may say where its name goes (`Name | Title | right`), for people sitting on different sides; the place chosen on the page is for the lines that say nothing.

### Changed

- The workflows after Audio moved down by one: Transcribe is now 03, Rough Cut 04, Titles 07, Social Clips 09.

### Fixed

- A time just under a whole minute was shown as 4:60.00 instead of 5:00.00; an hour or more is now shown as 1:02:03.00.
- A trim time past the end of the video, such as `16:40:00` (read as 16 hours), was silently ignored. It is now refused with an explanation.

## 0.2.0 - 2026-11-16

### Added

- **Rough Cut: trimming.** Give the time the programme starts and ends, and ranges to drop in between (a repeated take, a break). The page can show the first and last lines of the transcript to help find those times.
- **Rough Cut: coughs and other non-speech sounds.** Coughs, throat clearing, loud breaths and clicks standing between silences are found and offered as candidates. With a transcript, a sound no word was written for counts as non-speech; a clear voice with no word is listed for you to listen to, not cut.
- **Interface languages.** The interface is available in English and Turkish, chosen at the top left of the window. It starts in the language of the system.
- The version number is shown in the window title.

### Changed

- **Hesitations are cut whole.** An "uh" fades and wavers for another 0.1-0.3 seconds after its steady part; the cut now follows that tail, and a second steady stretch right after the first, so no stub is left behind.
- **More hesitations are cut by default** when the transcript heard them too: those between two words with no pause (0.2 seconds or longer) and those glued to the end of a word. A hesitation that creeps in slowly after a pause is recognised as one.
- **A cut never swallows a word by default.** A candidate with a transcribed word inside it arrives unticked.
- **Review list.** The sentence is shown in white and only the sound to be cut in red.
- Code, messages and the names of the files Davar writes are now English (`_cut.fcpxml`, `_transcript.txt`). Transcripts saved by 0.1 still load.

## 0.1.0 - 2026-11-15

First public release: Audio, Transcribe, Rough Cut, Titles and Social Clips.
