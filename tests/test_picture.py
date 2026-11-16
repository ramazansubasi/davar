"""Tests the Picture workflow's geometry and frame following with synthetic pictures.
Needs neither ffmpeg nor a video; the following tests are skipped without OpenCV."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import picture  # noqa: E402
import transcript  # noqa: E402
from common import DavarError  # noqa: E402

try:
    import cv2
except ImportError:
    cv2 = None


class Geometry(unittest.TestCase):
    def test_wide_picture_loses_its_sides(self):
        self.assertEqual(picture.frame_box(2336, 1080, 16 / 9, 100), (416, 0, 1920, 1080), "all cut from the left")
        self.assertEqual(picture.frame_box(2336, 1080, 16 / 9, 0), (0, 0, 1920, 1080), "all cut from the right")
        self.assertEqual(picture.frame_box(2336, 1080, 16 / 9, 50), (208, 0, 1920, 1080))

    def test_narrow_picture_loses_top_and_bottom(self):
        self.assertEqual(picture.frame_box(1080, 1920, 16 / 9, 50), (0, 656, 1080, 608))

    def test_picture_of_the_right_shape_is_kept_whole(self):
        self.assertEqual(picture.frame_box(1920, 1080, 16 / 9, 30), (0, 0, 1920, 1080))
        self.assertEqual(picture.frame_box(2336, 1080, None, 50), (0, 0, 2336, 1080))

    def test_bad_values_are_refused(self):
        with self.assertRaises(DavarError):
            picture.frame_box(1920, 1080, 16 / 9, 120)
        with self.assertRaises(DavarError):
            picture.parse_aspect("wide")
        self.assertAlmostEqual(picture.parse_aspect("16:9"), 16 / 9)
        self.assertIsNone(picture.parse_aspect(None))

    def test_usual_position_is_the_median_and_gaps_are_filled(self):
        found = [picture.similarity(1, 0, 0, 0), None, picture.similarity(3, 0, 0, 0),
                 picture.similarity(2, 0, 0, 0), picture.similarity(2, 0, 0, 0)]
        settled = picture.settle(found)
        self.assertEqual([round(m[0, 2], 6) for m in settled], [-1, 0, 1, 0, 0],
                         "most frames need no correction; the lost frame sits between its neighbours")

    def test_nothing_followed_is_an_error(self):
        with self.assertRaises(DavarError):
            picture.settle([None, None])

    def test_zoom_hides_the_moving_edges_and_no_more(self):
        still = np.array([np.eye(3)] * 50)
        whole = (0, 0, 1000, 600)
        self.assertEqual(picture.needed_zoom(still, whole, 1000, 600), 1.0)
        moved = np.array([picture.similarity(5, 0, 0, 0)] * 50)
        self.assertAlmostEqual(picture.needed_zoom(moved, whole, 1000, 600), 1.010, places=3,
                               msg="5 pixels on a 1000 pixel picture: about one percent")
        inside = (100, 0, 800, 600)  # the kept part has room on both sides
        self.assertEqual(picture.needed_zoom(moved, inside, 1000, 600), 1.0)
        wild = np.array([picture.similarity(200, 0, 0, 0)] * 50)
        self.assertEqual(picture.needed_zoom(wild, whole, 1000, 600), picture.MAX_ZOOM, "never beyond the limit")

    def test_one_stray_frame_does_not_set_the_zoom(self):
        frames = np.array([np.eye(3)] * 5000)
        frames[10] = picture.similarity(9, 0, 0, 0)
        self.assertEqual(picture.needed_zoom(frames, (0, 0, 1000, 600), 1000, 600), 1.0)

    def test_wander_is_measured_at_the_corners(self):
        frames = np.array([np.eye(3), picture.similarity(3, 4, 0, 0)])
        np.testing.assert_allclose(picture.wander(frames, (0, 0, 1000, 600)), [0, 5], atol=1e-9)

    def test_output_pixels_are_read_from_the_kept_part(self):
        m = picture.sampling_matrix(np.eye(3), (416, 0, 1920, 1080), 1.0)
        np.testing.assert_allclose(m @ [0, 0, 1], [416, 0, 1], atol=1e-9)
        np.testing.assert_allclose(m @ [1919, 1079, 1], [2335, 1079, 1], atol=1e-9)
        closer = picture.sampling_matrix(np.eye(3), (0, 0, 1000, 600), 1.25)
        np.testing.assert_allclose(closer @ [499.5, 299.5, 1], [499.5, 299.5, 1], atol=1e-9, err_msg="the centre stays")

    def test_colour_planes_move_half_as_far(self):
        chroma = picture.chroma_matrix(picture.similarity(4, 2, 0, 0))
        np.testing.assert_allclose(chroma[:2, 2], [2, 1], atol=1e-9)


@unittest.skipIf(cv2 is None, "OpenCV is not installed")
class Following(unittest.TestCase):
    def texture(self, seed, width=640, height=360):
        """A picture with detail at every scale, like a room."""
        rng = np.random.default_rng(seed)
        fine = cv2.GaussianBlur(rng.normal(0, 1, (height, width)).astype(np.float32), (0, 0), 2)
        coarse = cv2.GaussianBlur(rng.normal(0, 1, (height, width)).astype(np.float32), (0, 0), 12)
        both = fine / fine.std() + coarse / coarse.std()
        return np.clip(128 + 40 * both, 0, 255).astype(np.uint8)

    def moved(self, room, transform):
        """The room as a camera that moved by `transform` (reference -> frame) sees it."""
        h, w = room.shape
        return cv2.warpAffine(room, transform[:2], (w, h), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REFLECT)

    def test_movement_is_measured_while_someone_moves_in_front(self):
        room = self.texture(1)
        points = picture.find_points(room)
        truth = picture.similarity(3.3, -1.7, 0.004, 0.0005)  # a focus pump: shift and 0.4% growth
        frame = self.moved(room, truth)
        frame[120:330, 80:240] = self.texture(2)[120:330, 80:240]  # a person: other content, a quarter of the picture
        found = picture.measure(room, points, frame)
        self.assertIsNotNone(found)
        np.testing.assert_allclose(found[:2, 2], truth[:2, 2], atol=0.1, err_msg="shift, in pixels")
        self.assertAlmostEqual(found[0, 0], truth[0, 0], delta=0.0005, msg="scale")

    def test_unrelated_picture_is_reported_as_lost(self):
        room = self.texture(1)
        self.assertIsNone(picture.measure(room, picture.find_points(room), self.texture(3)))

    def test_plain_picture_cannot_be_followed(self):
        with self.assertRaises(DavarError):
            picture.find_points(np.full((360, 640), 128, np.uint8))

    def test_locking_puts_the_background_back_in_place(self):
        room = self.texture(4)
        points = picture.find_points(room)
        frame = self.moved(room, picture.similarity(-2.6, 3.1, -0.003, 0))
        found = picture.measure(room, points, frame)
        h, w = room.shape
        matrix = picture.sampling_matrix(found, (0, 0, w, h), 1.0)
        back = cv2.warpAffine(frame, matrix[:2], (w, h), flags=cv2.WARP_INVERSE_MAP | cv2.INTER_LANCZOS4)
        inner = (slice(20, h - 20), slice(20, w - 20))
        before = np.abs(frame[inner].astype(int) - room[inner]).mean()
        after = np.abs(back[inner].astype(int) - room[inner]).mean()
        self.assertLess(after, before / 5, "the locked frame matches the reference again")

    def test_frame_that_did_not_move_is_copied_exactly(self):
        rng = np.random.default_rng(5)
        planes = (rng.integers(0, 255, (360, 640), dtype=np.uint8), rng.integers(0, 255, (180, 320), dtype=np.uint8),
                  rng.integers(0, 255, (180, 320), dtype=np.uint8))
        box = (160, 0, 480, 360)
        y, u, v = picture.warp(planes, picture.sampling_matrix(np.eye(3), box, 1.0), (480, 360))
        np.testing.assert_array_equal(y, planes[0][:, 160:])
        np.testing.assert_array_equal(u, planes[1][:, 80:])
        np.testing.assert_array_equal(v, planes[2][:, 80:])


class TranscriptFollowsTheVideo(unittest.TestCase):
    def test_transcript_is_carried_over_to_a_video_with_the_same_audio(self):
        with tempfile.TemporaryDirectory() as folder:
            source, target, other = (Path(folder) / name for name in ("talk.mp4", "talk_picture.mp4", "other.mp4"))
            source.write_bytes(b"original")
            target.write_bytes(b"the same talk, reframed")
            other.write_bytes(b"something else")
            self.assertFalse(transcript.carry_over(source, target), "nothing to carry yet")
            record = {"version": transcript.VERSION, "language": "en", "model": "small", "duration": 2.0,
                      "words": [["Hello", 0.0, 0.5], ["there.", 0.5, 1.0]],
                      "video": transcript._identity(source)}
            transcript.transcript_path(source).write_text(json.dumps(record), encoding="utf-8")
            self.assertTrue(transcript.carry_over(source, target))
            carried = transcript.load(target)
            self.assertEqual([w[0] for w in carried["words"]], ["Hello", "there."])
            self.assertIsNotNone(transcript.load(source), "the original keeps its own")
            self.assertIsNone(transcript.load(other))


if __name__ == "__main__":
    unittest.main()
