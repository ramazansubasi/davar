# Changelog

## Unreleased

### Added

- **Rough Cut: repeated words and talk about the recording.** From the transcript: a word or a few said twice in a row ("rahat konuşun rahat konuşun", "yayın yayından"), a sentence begun again after a pause, and what is said to the crew ("baştan alıyorum", "bunu keseriz", "kayıttayız"). When the words after "baştan alıyorum" were already said a little earlier, the whole abandoned take is offered. They arrive unticked, as speech also repeats on purpose, and **Show → Repeats and retakes** lists them. On by default when there is a transcript.
- **Rough Cut: the rhythm of finished episodes.** **Take the rhythm of finished episodes…** measures the pauses of episodes already finished, cut by hand or by Davar, and sets the three silence settings from them: a pause that is cut keeps the usual length of a pause between two phrases (two thirds of it after the speech, one third before), and only pauses longer than 95 in 100 of theirs are cut. A hand-cut 18-minute episode gave 0.41 s between phrases and kept pauses up to 0.77 s; Davar's defaults leave about 0.30 s. The idea comes from ffmpeg-skill (MIT) by Shogo Kajiyama.
- **Rough Cut: joins to listen to.** A cut made in a silence is never heard; one made at an "uh" glued to a word cuts into sound on purpose. The joins worth a listen are those where a cut goes through a word of the transcript, part of it kept and part of it gone, with sound right at the join: about 20 in a 50-minute talk. Each gets a marker on the timeline ("Davar: listen to this join"), and the log lists them with their times on the timeline. The markers stay when Titles adds names, topic titles or the logo. As Resolve does not read the markers of an FCPXML file, they are also written to `<video>_cut_markers.edl`, for Timelines > Import > Timeline Markers from EDL.
- **Two microphones tell who speaks.** When two people each wear a microphone recorded on one of the two channels of the camera, Davar notices it and gives each word of the transcript to the microphone on which it is louder. The moment a turn changes is then known to the word instead of to a few seconds, for Move closer to the speaker, the name titles and Content Analysis. On two programmes it agreed with the voices for 98 in 100 words and placed a change of speaker the voices had put five seconds early. Otherwise the voices are used as before.
- **Content Analysis: asking Claude Code straight away.** With Claude Code installed and signed in, Start hands it the prompt and turns its answer into the texts at once, with the user's own Claude subscription: no copying and pasting. Claude Code runs with none of its tools, in an empty folder, and the conversation is not kept. Without it, or when it does not answer, the prompt is copied as before. The command line takes `--claude` for the same.
- **Social Clips: the candidates of Content Analysis, made in one go.** Content Analysis now also writes the two-line headline of each clip (the most striking words said in it, quoted, in capitals). **Take the candidates** lists them on the Social Clips page with their ranges moved to whole sentences of the transcript; Start makes the ticked ones one after the other as `Clip 1 - <headline>.mp4`, and **Fill in** puts one in the boxes to change it first.
- **Times given by hand move to a pause.** A trim time of Rough Cut (start, end, Also remove) or the start and end of a social clip that falls inside a word moves to the nearest pause, looked for up to 0.9 seconds before it and 0.3 seconds after, so no word is clipped. The log says when times moved.
- **Social Clips: soft joins.** Where the Rough Cut's cuts join two pieces of a clip, the sound fades out and in over 8 milliseconds, so a cut in the middle of a sound does not click.

### Changed

- When the speakers are told apart, short turns are given to a neighbour shortest first, so that a single word heard louder on the other microphone, or in the other voice, no longer hands that person a whole short turn.

## 0.4.0 - 2026-11-25

### Added

- **Titles: topic titles.** A lower third for the question or the subject being talked about: a white panel with the programme's name on a red tab, a large headline, a red line under it (the guest) and the channel's logo on the right; it opens from the left like the name titles. One line per title, `time | headline`, filled from the chapters of Content Analysis with one click. Each title opens three seconds into its chapter on the Rough Cut timeline and waits while a name is on screen; the name titles and the topic titles keep each other when either is made again.
- **Titles: the logo in a corner.** The channel's logo can be put in a corner of the picture (top right, top left, bottom right, bottom left) from the start of the timeline to its end, at a chosen width. It goes on a track of its own above the titles, so in Resolve it can still be moved or switched off, and running Rough Cut or Titles again keeps it.
- **Brand folder.** The topic titles use Montserrat when it is in `.davar/brand/fonts` in the home folder, and the logo chosen on the Titles page.
- **Content Analysis** asks the AI for a short on-screen title for each chapter, used by the topic titles.

### Changed

- On the Titles page the speakers and the topic titles each have their own tick, so either can be made alone.
- The README and the log after every timeline written say how two microphones recorded on a camera's two channels come into Resolve on tracks of their own: tick **Import multi-channel audio tracks as linked groups** when importing. Each microphone then comes on a track of its own, cut along with the picture and linked to it.

### Fixed

- Timelines of recordings whose camera writes a start timecode of its own (Sony counts on from where the last recording ended) came into Resolve offline, as Resolve finds clips by that timecode. The timelines now keep it.
- Transcribe said “Loading the model (downloaded on first use)” on every run, though the model is downloaded only once. The download is now mentioned only while the model is not on the computer yet.

## 0.3.0 - 2026-11-17

### Added

- **Picture**, a new workflow (02) for footage shot on a phone:
  - **Reframe to 16:9.** Cuts the sides of a picture wider than 16:9, from the left, the right or both, so it fills the frame with no black bars.
  - **Lock the frame.** For a camera on a tripod. While a phone hunts for focus the whole picture grows, shrinks and hops, and over a long recording the frame creeps by several pixels. Every frame is lined up with one reference frame, so the background stands still and cuts show less.
  - The audio is copied untouched, and a transcript already made is carried over to the new video.
- **Rough Cut: subtitles for the cut.** With a transcript, Rough Cut also writes subtitles that follow the cut timeline (`<video>_cut.srt`); words cut away are left out and the rest move to their time on the timeline. Correcting the text rewrites them too.
- **Rough Cut: move closer to the speaker.** To hide jump cuts the timeline is framed as with a second camera: closer to whoever gives a long answer, toward the side they sit on, and on everyone during quick exchanges. Inside a long answer the framing changes about every half minute, at the cut that jumps most. Who speaks comes from the transcript, who sits where from the Titles page; name titles already on the timeline stay.
- **Rough Cut: throat clearing found with a sound model.** An option finds the throat clearing that runs into speech, which the silence rule misses. YAMNet (16 MB, downloaded once and checked) describes the audio and a small classifier trained on throat clearings marked by ear picks about 25 likely places an hour, offered unticked as "throat clearing? (listen)". The stretch offered is the shortest one whose removal takes the sound away, so the words around it stay.
- **Rough Cut: views of the review list.** The **Show** choice lists all candidates, those to be cut, those not to be cut, the uncertain ones or the non-speech sounds.
- **Content Analysis**, a new workflow (06): an AI chat of your choice writes the YouTube texts, with no key and no fee. Davar writes a prompt holding the transcript with its times on the Rough Cut timeline and who says what; the answer pasted back becomes title suggestions, a description with chapters, tags, a summary and social clip candidates (`<video>_youtube.txt`). The chapters follow YouTube's rules.
- **Titles: names placed on the timeline.** Write the speakers in the order they first speak; Davar tells the voices apart and puts each lower third on the track above the video, a few seconds after that person first speaks. The names go into the Rough Cut timeline when there is one, the log shows the words spoken at each place, a time can be given by hand (`Name | Title | 0:41`), and running Rough Cut again keeps the names.
- **Titles: a place for each name.** A line may say where its name goes on the screen (`Name | Title | right`), for people sitting on different sides; the place chosen on the page is for the lines that say nothing.
- **Social Clips: the Rough Cut's cuts applied.** When the video has a Rough Cut timeline, the silences, hesitations and trimmed parts it cut are left out of the clip too, and the burned-in subtitles follow. On by default; the times given stay those of the video.
- **Settings are remembered.** Nothing has to be entered again when Davar is opened:
  - General settings (thresholds, paddings, filler words, ticked options, speaker names) come back as last used.
  - Settings that belong to one video (trim times, the range of a social clip, separate audio files, the output folder) are kept with that video and come back when it is chosen again.
  - Davar opens with the video and the page last worked on, and a video it wrote from another one starts with the settings of its source.
  - Each page has a **Back to defaults** button, and the settings survive a change of the interface language.

### Changed

- The workflows after Audio moved down by one: Transcribe is now 03, Rough Cut 04, Content Analysis 06, Titles 07, Social Clips 09.
- The review list's box "Show only the uncertain ones", which hid only the confident candidates, is replaced by the **Show** choice.
- Publish (10) now plans only the thumbnail; its texts are written by Content Analysis.

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
