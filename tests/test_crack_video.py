import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from src.inference.crack_video import associate, run


class CrackVideoTest(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(42)
        self.a = rng.integers(0, 256, (240, 320, 3), dtype=np.uint8)
        self.b = cv2.rotate(self.a, cv2.ROTATE_180)
        self.images = {('a', 0): self.a, ('a', 1): self.b, ('b', 1): self.b}

    def d(self, id, frame, box, video='a', **extra):
        return {'id': id, 'frame': frame, 'box': box, 'video_id': video, **extra}

    def test_turnaround_and_ambiguous_crossing(self):
        # 180-degree turnaround, with a second distinct overlapping crack.
        ds = [self.d('one', 0, [60, 70, 150, 140]),
              self.d('cross', 0, [90, 50, 130, 180]),
              self.d('return', 1, [170, 100, 260, 170])]
        out, links = associate(ds, self.images)
        self.assertEqual(out[0]['track_id'], out[2]['track_id'])
        self.assertNotEqual(out[0]['track_id'], out[1]['track_id'])
        self.assertTrue(any(x['decision'] == 'linked' for x in links))
        self.assertTrue(any(x['decision'] == 'suspected_duplicate' for x in links))
        self.assertTrue(all('homography' in x for x in links))

    def test_cross_video_and_approved_are_preserved(self):
        ds = [self.d('x', 0, [60, 70, 150, 140], approved_id='approved-A', label='crack'),
              self.d('y', 1, [170, 100, 260, 170], approved_id='approved-B', label='other'),
              self.d('z', 1, [170, 100, 260, 170], video='b')]
        out, links = associate(ds, self.images)
        self.assertEqual([x['track_id'] for x in out[:2]], ['approved-A', 'approved-B'])
        self.assertEqual(out[0]['box'], ds[0]['box'])
        self.assertEqual(out[1]['label'], 'other')
        self.assertTrue(all(x['target_detection'] != 'z' for x in links))
        self.assertTrue(any(x['decision'] == 'suspected_duplicate' for x in links))

    def test_video_and_user_anchor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            video = root/'test.avi'
            writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*'MJPG'), 2, (320,240))
            self.assertTrue(writer.isOpened())
            writer.write(self.a)
            writer.write(self.b)
            writer.release()
            detections = root/'detections.json'
            detections.write_text(json.dumps({'1': [{'box': [170,100,260,170], 'class_name':'crack'}]}))
            anchors = root/'anchors.json'
            anchors.write_text(json.dumps([{'frame': 0, 'box': [60,70,150,140], 'approved_id': 'user-1'}]))
            out = root/'out'
            result = run(video, out, sample_fps=2, risk_fps=2, detections_file=detections, anchors_file=anchors)
            self.assertEqual(len(result['frames']), 2)
            self.assertEqual(len(result['detections']), 2)
            self.assertEqual(result['association_proposals'][0]['track_id'], 'user-1')
            self.assertEqual(result['association_proposals'][1]['track_id'], 'user-1')
            self.assertTrue((out/'result.json').is_file())
            with self.assertRaises(FileExistsError):
                run(video, out, detections_file=detections)


if __name__ == '__main__':
    unittest.main()
