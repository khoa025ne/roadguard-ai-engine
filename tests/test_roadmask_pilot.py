import csv
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import numpy as np

from tools.roadmask_pilot import (
    box_overlap, latest_review, route_detection, save_review, validate_review,
)
from tools.annotate_dji_crack_pilot import create_server


def source(prediction="predicted_unreviewed"):
    return {"image": "DJI_9901_f000360_t000012012ms.jpg", "image_sha256": "abc",
            "width_px": 100, "height_px": 80, "prediction_status": prediction}


class RoadMaskPilotTest(unittest.TestCase):
    def test_local_review_api_is_append_only_and_not_engineering_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            pilot=Path(temp);(pilot/'images').mkdir();run=pilot/'roadmask_pilot_v1';run.mkdir()
            frames=[];road_frames=[];detections={}
            for index in range(20):
                name=f'DJI_9901_f{index:06d}_t{index:09d}ms.jpg'
                (pilot/'images'/name).write_bytes(b'private-test-image')
                frames.append({'image':f'images/{name}','image_sha256':'abc','width_px':100,
                               'height_px':80,'source_video':'DJI_9901.MP4',
                               'source_video_sha256':'video','source_srt_sha256':'srt',
                               'frame_index_zero_based':index,'timestamp_ms_from_fps':index})
                road_frames.append({'image':name,'image_sha256':'abc',
                                    'prediction_status':'prediction_missing','predicted_mask':None,
                                    'triage':'provisional_keep'})
                detections[name]=[]
            (pilot/'manifest.json').write_text(json.dumps({'frames':frames}),encoding='utf-8')
            with (pilot/'visual_triage.csv').open('w',newline='',encoding='utf-8') as stream:
                writer=csv.DictWriter(stream,fieldnames=['image','visual_triage'])
                writer.writeheader()
                for frame in road_frames:writer.writerow({'image':frame['image'],
                                                          'visual_triage':'provisional_keep'})
            (run/'manifest.json').write_text(json.dumps({'frames':road_frames}),encoding='utf-8')
            (run/'raw_detections.json').write_text(json.dumps(detections),encoding='utf-8')
            server=create_server(pilot,0);thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start();base=f'http://127.0.0.1:{server.server_port}'
            try:
                with urlopen(base+'/roadmask') as response:
                    self.assertIn(b'road mask',response.read())
                with urlopen(base+'/api/roadmask/items') as response:
                    self.assertEqual(len(json.load(response)),20)
                name=road_frames[0]['image']
                with self.assertRaises(HTTPError) as error:
                    urlopen(base+'/api/roadmask/predicted/'+name)
                self.assertEqual(error.exception.code,404)
                payload={'checked_by':'Owner','preliminary_check':'needs_correction',
                         'issues':[{'kind':'missing_road','box':[1,2,30,40]}]}
                request=Request(base+'/api/roadmask/review/'+name,data=json.dumps(payload).encode(),
                                headers={'Content-Type':'application/json'},method='POST')
                with urlopen(request) as response:
                    self.assertEqual(json.load(response)['review_status'],'pending_review')
                with urlopen(request) as response:
                    self.assertEqual(response.status,201)
                with urlopen(base+'/api/roadmask/record/'+name) as response:
                    record=json.load(response)
                self.assertEqual(record['review']['preliminary_check'],'needs_correction')
                self.assertEqual(record['review']['engineering_approval_status'],'not_requested')
                self.assertEqual(len(list((run/'reviews').glob('*.json'))),2)
                self.assertFalse((pilot/'annotations').exists())
            finally:
                server.shutdown();server.server_close();thread.join(timeout=2)

    def test_preliminary_review_never_grants_engineering_approval(self):
        payload = {"checked_by": "Owner", "preliminary_check": "needs_correction",
                   "issues": [{"kind": "missing_road", "box": [3, 4, 20, 30]}],
                   "notes": "Road edge omitted", "minutes_actual": 12}
        review = validate_review(payload, source())
        self.assertEqual(review["review_status"], "pending_review")
        self.assertEqual(review["engineering_approval_status"], "not_requested")
        self.assertEqual(review["issues"][0]["box"], [3, 4, 20, 30])
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp)
            first = save_review(run, source()["image"], review)
            original = first.read_bytes()
            second = save_review(run, source()["image"], review)
            self.assertNotEqual(first, second)
            self.assertEqual(first.read_bytes(), original)
            self.assertEqual(latest_review(run, source()["image"])["notes"], "Road edge omitted")

    def test_missing_prediction_cannot_be_called_correct(self):
        with self.assertRaises(ValueError):
            validate_review({"checked_by": "Owner", "preliminary_check": "looks_correct"},
                            source("prediction_missing"))
        with self.assertRaises(ValueError):
            validate_review({"checked_by": "Owner", "preliminary_check": "looks_correct",
                             "issues": [{"kind": "false_road", "box": [3, 4, 20, 30]}]}, source())

    def test_route_preserves_crack_edge_missing_and_issue(self):
        mask = np.zeros((80, 100), dtype=np.uint8)
        mask[20:60, 20:70] = 255
        checked = {"preliminary_check": "looks_correct", "issues": []}
        det = lambda box: {"box": box}
        self.assertEqual(box_overlap([20, 20, 40, 40], mask), 1.0)
        self.assertEqual(route_detection(det([25, 25, 40, 40]), mask, checked, [])["route"], "candidate")
        self.assertEqual(route_detection(det([25, 25, 40, 40]), mask,
                                         {"preliminary_check":"uncertain","issues":[]}, [])["route"],
                         "needs_review")
        self.assertEqual(route_detection(det([0, 0, 3, 3]), mask, checked, [])["route"], "reject")
        self.assertEqual(route_detection(det([0, 0, 3, 3]), mask, None, [])["route"], "needs_review")
        self.assertEqual(route_detection(det([0, 0, 3, 3]), None, checked, [])["route"], "needs_review")
        self.assertEqual(route_detection(det([7, 22, 15, 30]), mask, checked, [])["route"], "needs_review")
        self.assertEqual(route_detection(det([0, 0, 3, 3]), mask, checked, [[1, 1, 5, 5]])["route"],
                         "needs_review")
        marked = {"preliminary_check": "needs_correction", "issues": [
            {"kind": "false_road", "box": [23, 23, 42, 42]}]}
        self.assertEqual(route_detection(det([25, 25, 40, 40]), mask, marked, [])["route"], "needs_review")


if __name__ == "__main__":
    unittest.main()
