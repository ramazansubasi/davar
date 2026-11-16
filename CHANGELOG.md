# Changelog

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
