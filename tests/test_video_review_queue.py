import copy
import json
import os
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import cv2
import numpy as np

from tools.video_review_queue import apply_review, create_server, initial, report_snapshot, transition_report, verified_negative_at, restore_revision, independent_split_candidates


def fixture():
    ds = [{'id': 'a', 'video_id': 'v', 'frame': 0, 'box': [1, 2, 20, 30], 'class_name': 'crack'},
          {'id': 'b', 'video_id': 'v', 'frame': 1, 'box': [4, 2, 22, 30], 'class_name': 'crack'}]
    return {'schema': 'roadguard-crack-video-experimental-v1', 'video': {'sha256': 'v', 'path': 'missing'},
            'frames': [{'frame': 0, 'timestamp_s': 0, 'image': '0.jpg'}, {'frame': 1, 'timestamp_s': 1, 'image': '1.jpg'}],
            'detections': ds, 'association_proposals': [{'id': x['id'], 'track_id': x['id']} for x in ds],
            'links': [{'decision': 'suspected_duplicate', 'source_detection': 'a', 'target_detection': 'b'}],
            'limitations': ['no GPS'], 'representatives': {}}


def request(state, **kw):
    return {'base_revision': state['revision'], 'reviewer': 'Khoa', 'confirm': True, **kw}


def browser_env():
    """Find installed desktop runtime; fail explicitly rather than skipping smoke."""
    env = dict(os.environ)
    if env.get('ROADGUARD_NODE_MODULES'):
        env.setdefault('NODE_PATH', env['ROADGUARD_NODE_MODULES'])
    if not env.get('ROADGUARD_BROWSER'):
        candidates = [Path(env.get('ProgramFiles(x86)', 'C:/Program Files (x86)'))/'Microsoft/Edge/Application/msedge.exe',
                      Path(env.get('ProgramFiles', 'C:/Program Files'))/'Google/Chrome/Application/chrome.exe']
        env['ROADGUARD_BROWSER'] = next((str(p) for p in candidates if p.is_file()), '')
    return env


class ReviewTest(unittest.TestCase):
    def setUp(self):
        self.source = fixture()
        self.state = initial(self.source)
        self.sizes = {0: (100, 80), 1: (100, 80)}

    def apply(self, **kw):
        self.state = apply_review(self.source, self.state, request(self.state, **kw), self.sizes)

    def test_batch_and_coverage_and_unverified(self):
        a, b = self.state['detections'].values()
        with self.assertRaises(ValueError): self.apply(items=[a, b])
        self.apply(resolutions=[{'link': 0, 'decision': 'different'}])
        self.apply(items=[a, b])
        self.assertEqual([d['status'] for d in self.state['detections'].values()], ['approved', 'approved'])
        self.assertEqual(self.state['coverage'], {})
        self.apply(coverage=[{'frame': 0, 'scope': 'regions', 'fully_inspected': True,
                              'verified_regions': [[0, 0, 90, 70]], 'unverified_regions': [[10, 10, 20, 20]]}])
        self.assertEqual(self.state['coverage']['0']['unverified_regions'], [[10, 10, 20, 20]])
        self.assertIn('minus all unverified', self.state['coverage']['0']['negative_semantics'])
        with self.assertRaises(ValueError): self.apply(coverage=[{'frame': 1, 'scope': 'frame', 'fully_inspected': False}])
        with self.assertRaises(ValueError): self.apply(coverage=[{'frame': 1, 'scope': 'frame', 'fully_inspected': True, 'unverified_regions': [[1,1,2,2]]}])

    def test_amend_and_stale_and_user(self):
        self.apply(resolutions=[{'link': 0, 'decision': 'different'}])
        item = copy.deepcopy(self.state['detections']['a'])
        self.apply(items=[item])
        item['box'] = [2, 2, 20, 30]
        with self.assertRaises(ValueError): self.apply(items=[item])
        self.apply(items=[item], confirm_amendment=True)
        self.assertEqual(self.state['detections']['a']['box'], [2, 2, 20, 30])
        with self.assertRaises(ValueError): apply_review(self.source, self.state, {'base_revision': 0}, self.sizes)
        self.apply(items=[{'id':'user-1','frame':1,'box':[3,3,9,9], 'label':'crack','track_id':'new','source':'user'}])
        self.assertEqual(self.state['detections']['user-1']['source'], 'user')

    def test_geometry_boundary_and_coverage_revision(self):
        self.source['frames'].append({'frame': 2, 'timestamp_s': 2, 'image': '2.jpg'})
        self.sizes[2] = (100, 80)
        c = {'frame':2, 'scope':'regions', 'fully_inspected':True,
             'verified_regions':[[0,0,40,40]], 'unverified_regions':[[10,10,20,20]]}
        self.apply(coverage=[c])
        old = copy.deepcopy(self.state)
        v = self.state['coverage']['2']
        self.assertTrue(verified_negative_at(v, 9, 10))
        self.assertFalse(verified_negative_at(v, 10, 10))
        self.assertFalse(verified_negative_at(v, 40, 20))
        self.assertFalse(verified_negative_at(v, 25, 25, [[20,20,30,30]]))
        with self.assertRaises(ValueError): self.apply(coverage=[c])
        c['verified_regions'] = [[0,0,50,50]]
        self.apply(coverage=[c], confirm_amendment=True)
        self.assertEqual(old['coverage']['2']['verified_regions'], [[0,0,40,40]])
        self.assertFalse(verified_negative_at(self.state['coverage']['2'], 15, 15))
        self.assertEqual(self.state['coverage']['2']['reviewer'], 'Khoa')
        self.apply(coverage=[{'frame':2, 'scope':'frame', 'fully_inspected':True}], confirm_amendment=True)
        self.assertTrue(verified_negative_at(self.state['coverage']['2'], 99, 79))
        self.assertFalse(verified_negative_at(self.state['coverage']['2'], 100, 79))

    def test_pending_box_touching_verified_boundary(self):
        self.apply(coverage=[{'frame':0, 'scope':'regions', 'fully_inspected':True,
                              'verified_regions':[[20,2,30,30]]}])
        with self.assertRaises(ValueError):
            self.apply(coverage=[{'frame':0, 'scope':'regions', 'fully_inspected':True,
                                  'verified_regions':[[19,2,30,30]]}], confirm_amendment=True)

    def test_split_identity_conflict_and_report_pending_proposals(self):
        self.apply(resolutions=[{'link':0,'decision':'same'}])
        a, b = copy.deepcopy(list(self.state['detections'].values()))
        b['track_id'] = a['track_id']
        self.apply(items=[a,b])
        b = copy.deepcopy(self.state['detections']['b']); b['track_id'] = 'split-b'
        self.apply(items=[b], confirm_amendment=True)
        self.assertEqual(self.state['detections']['a']['track_id'], a['track_id'])
        self.assertEqual(len(self.state['split_suggestions']), 1)
        report = report_snapshot(self.source, self.state, 1, 'Khoa')
        self.assertEqual(report['identity_conflicts'], ['0'])
        self.assertEqual(report['overview']['approved_physical_ids'], 2)
        with self.assertRaises(ValueError): transition_report(report, 'ready', request({'revision':1}), self.state)
        self.apply(resolutions=[{'link':0,'decision':'different'}])
        key = next(iter(self.state['split_suggestions']))
        self.apply(split_reviews=[{'id':key,'decision':'reviewed'}])
        self.source['detections'].append({'id':'c','video_id':'v','frame':0,'box':[30,30,40,40], 'class_name':'crack'})
        self.state['detections']['c'] = {'id':'c','frame':0,'box':[30,30,40,40],'label':'crack','track_id':'c','status':'pending_review','source':'model'}
        report = report_snapshot(self.source, self.state, 2, 'Khoa')
        self.assertEqual(report['overview']['ai_proposals_pending'], 1)
        self.assertIn('technical_appendix', report)
        ready = transition_report(report, 'ready', request({'revision':2}), self.state)
        self.assertEqual(ready['status'], 'ready_for_approval')

    def test_report_gates_and_immutability(self):
        r = report_snapshot(self.source, self.state, 1, 'Khoa')
        with self.assertRaises(ValueError): transition_report(r, 'ready', request({'revision':1}), self.state)
        self.apply(resolutions=[{'link':0,'decision':'different'}])
        self.apply(items=list(self.state['detections'].values()))
        r1 = report_snapshot(self.source, self.state, 2, 'Khoa')
        r2 = transition_report(r1, 'ready', request({'revision':2}), self.state)
        with self.assertRaises(ValueError): transition_report(r2, 'approve', request({'revision':3}), self.state)
        r3 = transition_report(r2, 'approve', request({'revision':3}, accept_limits=True), self.state)
        self.assertEqual((r1['status'], r2['status'], r3['status']), ('draft','ready_for_approval','approved'))
        with self.assertRaises(ValueError): transition_report(r3, 'ready', request({'revision':4}), self.state)
        r4 = report_snapshot(self.source, self.state, 5, 'Khoa')
        self.assertEqual(r3['status'], 'approved')
        self.assertEqual(r4['status'], 'draft')

    def test_independent_split_candidates_and_undo(self):
        self.apply(resolutions=[{'link':0,'decision':'same'}])
        a,b = copy.deepcopy(list(self.state['detections'].values()))
        b['track_id'] = a['track_id']
        self.apply(items=[a,b])
        target = copy.deepcopy(self.state)
        for key, frame in [('c',0), ('d',1)]:
            self.state['detections'][key] = {**a,'id':key,'frame':frame,'track_id':'independent'}
            self.source['detections'].append({'id':key,'frame':frame,'video_id':'v','box':a['box'],'road_overlap':.2})
        self.source['links'].append({'decision':'linked','source_detection':'c','target_detection':'d','projected_iou':.4})
        b = copy.deepcopy(self.state['detections']['b']);b['track_id']='new-b'
        before = copy.deepcopy(self.state['detections']['c'])
        self.apply(items=[b],confirm_amendment=True)
        candidates=[v for v in self.state['split_suggestions'].values() if v.get('track_id')=='independent']
        self.assertEqual(len(candidates),1)
        self.assertEqual(candidates[0]['risk_score'],2)
        self.assertTrue(candidates[0]['evidence'])
        self.assertEqual(before,self.state['detections']['c'])
        self.source['links'] = self.source['links'][:1]
        self.state['detections']['d']['box'] = [1,2,80,5]
        fallback = independent_split_candidates(self.source,self.state,a['track_id'],'b')
        self.assertTrue(any(e['kind']=='box_shape_drift_across_frames' for e in fallback[0]['evidence']))
        with self.assertRaises(ValueError): restore_revision(self.state,target,request(self.state))
        restored=restore_revision(self.state,target,request(self.state,confirm_amendment=True,reason='Undo split'))
        self.assertEqual(restored['revision'],self.state['revision']+1)
        self.assertEqual(restored['restored_from_revision'],target['revision'])
        self.assertEqual(restored['detections']['b']['track_id'],target['detections']['b']['track_id'])

    def test_http_persistence_and_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); result = root/'result.json'; work = root/'review'
            result.write_text(json.dumps(self.source), encoding='utf-8')
            for name in ['0.jpg','1.jpg']: cv2.imwrite(str(root/name), np.zeros((80,100,3),np.uint8))
            server = create_server(result, work)
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            try:
                url = f'http://127.0.0.1:{server.server_port}'
                with urlopen(url+'/api/state') as response: self.assertEqual(json.load(response)['state']['revision'], 0)
                payload = request(self.state, resolutions=[{'link':0,'decision':'same'}])
                req = Request(url+'/api/review', data=json.dumps(payload).encode(), headers={'Content-Type':'application/json'})
                with urlopen(req) as response: self.assertEqual(json.load(response)['revision'],1)
                with self.assertRaises(HTTPError): urlopen(req)
                self.assertTrue((work/'revisions/r000001.json').is_file())
                def post(path, payload):
                    req = Request(url+path, data=json.dumps(payload).encode(), headers={'Content-Type':'application/json'})
                    with urlopen(req) as response: return json.load(response)
                with urlopen(url+'/api/state') as response: state = json.load(response)['state']
                items = list(state['detections'].values())
                items[1]['track_id'] = items[0]['track_id']
                post('/api/review', request(state, items=items))
                state['revision'] = 2
                draft = post('/api/report/draft', {'base_revision':2, 'reviewer':'Khoa'})
                ready = post('/api/report/ready', request(draft))
                approved = post('/api/report/approve', request(ready, accept_limits=True))
                old = (work/'reports/v000003.json').read_bytes()
                next_draft = post('/api/report/draft', {'base_revision':2, 'reviewer':'Khoa'})
                self.assertEqual((approved['status'], next_draft['status']), ('approved', 'draft'))
                self.assertEqual((work/'reports/v000003.json').read_bytes(), old)
            finally:
                server.shutdown(); server.server_close(); thread.join()
            result.write_text(json.dumps({**self.source, 'limitations':['changed AI']}), encoding='utf-8')
            with self.assertRaises(ValueError): create_server(result, work)

    def test_browser_smoke(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = fixture(); source['links'] = []
            result = root/'result.json'; result.write_text(json.dumps(source), encoding='utf-8')
            for name in ['0.jpg', '1.jpg']:
                cv2.imwrite(str(root/name), np.zeros((80,100,3),np.uint8))
            server = create_server(result, root/'review')
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            try:
                script = Path(__file__).with_name('browser_video_review_queue.cjs')
                proc = subprocess.run(['node', str(script), f'http://127.0.0.1:{server.server_port}/'],
                                      capture_output=True, text=True, timeout=60, env=browser_env())
                self.assertEqual(proc.returncode, 0, proc.stdout+'\n'+proc.stderr)
            finally:
                server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__': unittest.main()
