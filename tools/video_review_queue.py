"""Local experimental Review Queue for crack_video result.json, not a production API."""
import argparse
import copy
import hashlib
import json
import math
import mimetypes
import re
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load_source(path):
    path = Path(path).resolve()
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('schema') != 'roadguard-crack-video-experimental-v1':
        raise ValueError('Unsupported experimental result schema')
    video = data['video']['sha256']
    if any(x['video_id'] != video for x in data['detections']):
        raise ValueError('Cross-video detections are forbidden')
    ids = [d['id'] for d in data['detections']]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate detection IDs')
    return data


def initial(source):
    proposals = {x['id']: x for x in source['association_proposals']}
    detections = {}
    for d in source['detections']:
        p = proposals.get(d['id'], {})
        detections[d['id']] = {'id': d['id'], 'frame': d['frame'], 'box': d['box'],
            'label': d.get('class_name', 'crack'), 'track_id': p.get('track_id', d['id']),
            'status': 'pending_review', 'source': d.get('source', 'model')}
    return {'revision': 0, 'detections': detections, 'coverage': {}, 'resolutions': {}}


def latest(folder, prefix, default=None):
    files = sorted(folder.glob(prefix + '*.json')) if folder.exists() else []
    return json.loads(files[-1].read_text(encoding='utf-8')) if files else default


def save_immutable(folder, prefix, value):
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{prefix}{value['revision']:06d}.json"
    with target.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    return target


def validate_rect(box, width, height):
    if (not isinstance(box, list) or len(box) != 4 or
        any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in box)):
        raise ValueError('Tọa độ phải gồm bốn số hữu hạn')
    x1, y1, x2, y2 = box
    if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
        raise ValueError('Box phải nằm trong ảnh và có diện tích')
    return box


def intersects(a, b):
    return max(a[0], b[0]) < min(a[2], b[2]) and max(a[1], b[1]) < min(a[3], b[3])


def contained(a, b):
    return b[0] <= a[0] and b[1] <= a[1] and b[2] >= a[2] and b[3] >= a[3]


def verified_negative_at(coverage, x, y, positive_boxes=()):
    """Point membership in explicitly verified scope, excluding uncertainty and positives."""
    def inside(rect):
        return rect[0] <= x < rect[2] and rect[1] <= y < rect[3]
    if not coverage or coverage.get('fully_inspected') is not True:
        return False
    scope = coverage.get('frame_bounds') if coverage.get('scope') == 'frame' else None
    verified = [scope] if scope else coverage.get('verified_regions', [])
    return (any(inside(r) for r in verified)
            and not any(inside(r) for r in coverage.get('unverified_regions', []))
            and not any(inside(r) for r in positive_boxes))


def frame_sizes(source, result_dir):
    import cv2
    import numpy as np
    result = {}
    for frame in source['frames']:
        path = (result_dir / frame['image']).resolve()
        if not path.is_relative_to(result_dir.resolve()):
            raise ValueError('Invalid frame path')
        image = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError('Cannot read frame')
        result[frame['frame']] = (image.shape[1], image.shape[0])
    return result


def unresolved(source, state):
    return [str(i) for i, link in enumerate(source['links'])
            if link['decision'] == 'suspected_duplicate' and str(i) not in state['resolutions']]


def independent_split_candidates(source, state, old_track, moved_id):
    """Rank independent groups using existing link/box/mask evidence only."""
    detections = state['detections']
    raw = {d['id']: d for d in source['detections']}
    groups = {}
    for d in detections.values():
        if d['track_id'] not in {old_track, detections[moved_id]['track_id']}:
            groups.setdefault(d['track_id'], []).append(d)
    found = []
    for track, members in groups.items():
        if len(members) < 2:
            continue
        ids = {d['id'] for d in members}
        evidence = []
        for index, link in enumerate(source['links']):
            if link['source_detection'] in ids and link['target_detection'] in ids:
                if link['decision'] == 'suspected_duplicate' or link.get('projected_iou', 1) < .65:
                    evidence.append({'kind': 'weak_internal_link', 'link_index': index,
                                     'source_detection': link['source_detection'], 'target_detection': link['target_detection'],
                                     'projected_iou': link.get('projected_iou')})
        aspects = [(d['box'][2]-d['box'][0]) / max(1., d['box'][3]-d['box'][1]) for d in members]
        if len({d['frame'] for d in members}) > 1 and max(aspects)/max(.001,min(aspects)) >= 3:
            evidence.append({'kind': 'box_shape_drift_across_frames',
                'reason': 'Tỷ lệ box thay đổi lớn; chỉ là tín hiệu rà soát, có thể do góc chụp',
                'observations': [{'detection_id': d['id'], 'frame': d['frame'], 'box': d['box']} for d in members]})
        if not evidence:
            continue
        outside = [d['id'] for d in members if raw.get(d['id'], {}).get('road_overlap') is not None
                   and raw[d['id']]['road_overlap'] < .6]
        if outside:
            evidence.append({'kind': 'outside_or_partial_road_mask', 'detection_ids': outside})
        found.append({'track_id': track, 'related_detection': members[0]['id'],
                      'risk_score': len(evidence), 'reason': 'Nhóm độc lập có liên kết nội bộ yếu, cần rà soát sau ca tách nhầm',
                      'evidence': evidence, 'detection_ids': sorted(ids)})
    return sorted(found, key=lambda x: (-x['risk_score'], x['track_id']))


def restore_revision(previous, target, payload):
    if payload.get('base_revision') != previous['revision']:
        raise ValueError('Revision đã thay đổi; tải lại')
    reviewer = str(payload.get('reviewer', '')).strip()
    reason = str(payload.get('reason', '')).strip()
    if not reviewer or not reason or payload.get('confirm_amendment') is not True or payload.get('confirm') is not True:
        raise ValueError('Khôi phục cần người duyệt, lý do và xác nhận sửa quyết định')
    restored = copy.deepcopy(target)
    restored.update(revision=previous['revision']+1, base_revision=previous['revision'],
                    restored_from_revision=target['revision'], reviewer=reviewer, reason=reason, saved_utc=now())
    return restored


def apply_review(source, previous, payload, sizes):
    if payload.get('base_revision') != previous['revision']:
        raise ValueError('Revision đã thay đổi; tải lại trước khi lưu')
    reviewer = str(payload.get('reviewer', '')).strip()
    if not reviewer or len(reviewer) > 100 or payload.get('confirm') is not True:
        raise ValueError('Cần tên và xác nhận rõ ràng của người duyệt')
    state = copy.deepcopy(previous)
    selected = payload.get('items', [])
    coverage = payload.get('coverage', [])
    resolutions = payload.get('resolutions', [])
    split_reviews = payload.get('split_reviews', [])
    if not all(isinstance(x, list) for x in (selected, coverage, resolutions, split_reviews)) or not (selected or coverage or resolutions or split_reviews):
        raise ValueError('Chưa chọn nội dung duyệt')
    if any(not isinstance(entry, dict) for group in (selected, coverage, resolutions, split_reviews) for entry in group):
        raise ValueError('Mỗi quyết định phải là một đối tượng')
    state.setdefault('split_suggestions', {})
    seen = set()
    for item in selected:
        key, frame = item.get('id'), item.get('frame')
        if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,160}', key) or key in seen or frame not in sizes:
            raise ValueError('ID hoặc frame không hợp lệ')
        seen.add(key)
        old = state['detections'].get(key)
        if old is None and item.get('source') != 'user':
            raise ValueError('Box mới phải do người dùng bổ sung')
        if old and old['frame'] != frame:
            raise ValueError('Không đổi frame của box')
        label, track = item.get('label'), item.get('track_id')
        if not isinstance(label, str) or not label.strip() or len(label) > 100 or not isinstance(track, str) or not track.strip() or len(track) > 160:
            raise ValueError('Cần nhãn và ID vết nứt')
        validate_rect(item.get('box'), *sizes[frame])
        verdict = item.get('verdict', 'approved')
        if verdict not in {'approved', 'rejected'}:
            raise ValueError('Quyết định box không hợp lệ')
        if old and old.get('status') == 'approved' and (verdict != 'approved' or any(item.get(k) != old.get(k) for k in ('box', 'label', 'track_id'))) and payload.get('confirm_amendment') is not True:
            raise ValueError('Sửa quyết định approved cần xác nhận sửa revision')
        if old and old.get('status') == 'approved' and old['track_id'] != track.strip():
            for other in state['detections'].values():
                if other['id'] != key and other['track_id'] == old['track_id']:
                    suggestion_id = f"{previous['revision']+1}:{key}:{other['id']}"
                    state['split_suggestions'][suggestion_id] = {'split_detection': key,
                        'related_detection': other['id'], 'previous_track_id': old['track_id'],
                        'new_track_id': track.strip(), 'status': 'pending_review',
                        'reviewer': reviewer, 'created_utc': now()}
        # Suspected duplicates require their own explicit decision first.
        pending = set(unresolved(source, state))
        if any(str(i) in pending and key in (link['source_detection'], link['target_detection'])
               for i, link in enumerate(source['links'])):
            raise ValueError('Xử lý nghi trùng riêng trước khi duyệt box')
        state['detections'][key] = {'id': key, 'frame': frame, 'box': item['box'],
            'label': label.strip(), 'track_id': track.strip(), 'status': verdict,
            'source': old['source'] if old else 'user', 'reviewer': reviewer, 'reviewed_utc': now()}
    for c in coverage:
        frame = c.get('frame')
        if frame not in sizes or c.get('scope') not in {'frame', 'regions'} or c.get('fully_inspected') is not True:
            raise ValueError('Phạm vi cần kiểm tra đầy đủ và xác nhận riêng')
        verified, unverified = c.get('verified_regions', []), c.get('unverified_regions', [])
        if not isinstance(verified, list) or not isinstance(unverified, list):
            raise ValueError('Danh sách vùng không hợp lệ')
        for rect in verified + unverified:
            validate_rect(rect, *sizes[frame])
        if c['scope'] == 'regions' and not (verified or unverified):
            raise ValueError('Cần ít nhất một vùng đã kiểm tra hoặc chưa xác minh')
        if c['scope'] == 'frame' and unverified:
            raise ValueError('Frame có vùng chưa kiểm tra không thể xác nhận toàn frame')
        old_coverage = state['coverage'].get(str(frame))
        if old_coverage and payload.get('confirm_amendment') is not True:
            raise ValueError('Sửa phạm vi đã duyệt cần xác nhận sửa revision')
        scope_regions = [[0, 0, *sizes[frame]]] if c['scope'] == 'frame' else verified
        for d in state['detections'].values():
            if (d['frame'] == frame and d['status'] == 'pending_review'
                and any(intersects(d['box'], region) for region in scope_regions)
                and not any(contained(d['box'], region) for region in unverified)):
                raise ValueError('Phạm vi chứa box chưa xử lý; xử lý box hoặc đánh dấu toàn box chưa xác minh')
        state['coverage'][str(frame)] = {'scope': c['scope'], 'fully_inspected': True,
            'verified_regions': verified, 'unverified_regions': unverified,
            'frame_bounds': [0, 0, *sizes[frame]],
            'negative_semantics': 'verified scope minus all unverified regions; approved positives excluded',
            'reviewer': reviewer, 'reviewed_utc': now()}
    for r in resolutions:
        idx = r.get('link')
        if not isinstance(idx, int) or idx < 0 or idx >= len(source['links']) or source['links'][idx]['decision'] != 'suspected_duplicate' or r.get('decision') not in {'same', 'different'}:
            raise ValueError('Quyết định nghi trùng không hợp lệ')
        state['resolutions'][str(idx)] = {'decision': r['decision'], 'reviewer': reviewer, 'reviewed_utc': now()}
    for entry in split_reviews:
        key = entry.get('id')
        if key not in state['split_suggestions'] or entry.get('decision') != 'reviewed':
            raise ValueError('Đề xuất rà soát sau tách không hợp lệ')
        state['split_suggestions'][key].update(status='reviewed', reviewed_by=reviewer, reviewed_utc=now())
    for item in selected:
        old = previous['detections'].get(item['id'])
        if old and old['status'] == 'approved' and old['track_id'] != item['track_id'].strip():
            for candidate in independent_split_candidates(source, state, old['track_id'], item['id']):
                key = f"independent:{previous['revision']+1}:{item['id']}:{candidate['related_detection']}"
                state['split_suggestions'][key] = {**candidate, 'split_detection': item['id'],
                    'previous_track_id': old['track_id'], 'status': 'pending_review',
                    'reviewer': reviewer, 'created_utc': now()}
    state.update(revision=previous['revision'] + 1, reviewer=reviewer, saved_utc=now(), base_revision=previous['revision'])
    return state


def report_snapshot(source, state, version, reviewer):
    groups = {}
    frames = {x['frame']: x for x in source['frames']}
    for d in state['detections'].values():
        if d['status'] != 'approved':
            continue
        f = frames[d['frame']]
        groups.setdefault(d['track_id'], []).append({'detection_id': d['id'], 'label': d['label'],
            'frame': d['frame'], 'timestamp_s': f['timestamp_s'], 'box': d['box'], 'image': f['image']})
    for key, items in groups.items():
        preferred = source.get('representatives', {}).get(key, {}).get('detection_id')
        items.sort(key=lambda item: item['detection_id'] != preferred)
    conflicts = []
    for i, link in enumerate(source['links']):
        resolution = state['resolutions'].get(str(i))
        if not resolution:
            continue
        a = state['detections'][link['source_detection']]
        b = state['detections'][link['target_detection']]
        if a['status'] == b['status'] == 'approved' and ((a['track_id'] == b['track_id']) != (resolution['decision'] == 'same')):
            conflicts.append(str(i))
    cracks = [{'id': key, 'type': items[0]['label'], 'representative': items[0], 'additional_views': items[1:]} for key, items in groups.items()]
    pending = [d['id'] for d in state['detections'].values() if d['status'] == 'pending_review']
    uncovered = [f['frame'] for f in source['frames'] if str(f['frame']) not in state['coverage']]
    partial = {k: v for k, v in state['coverage'].items() if v['scope'] != 'frame' or v.get('unverified_regions')}
    split_pending = [k for k, v in state.get('split_suggestions', {}).items() if v['status'] == 'pending_review']
    return {'revision': version, 'status': 'draft', 'created_utc': now(), 'created_by': reviewer,
        'video': source['video'], 'review_revision': state['revision'],
        'cracks': cracks,
        'overview': {'approved_physical_ids': len(cracks), 'ai_proposals_pending': len(pending),
                     'unverified_frames': uncovered, 'partially_verified_frames': list(partial)},
        'technical_appendix': {'approved_cracks': cracks, 'coverage': copy.deepcopy(state['coverage']),
                               'unverified_frames': uncovered, 'pending_ai_detection_ids': pending,
                               'source_model': source.get('models'), 'source_config': source.get('config')},
        'observation_limits': source['limitations'], 'limits_accepted': False,
        'unresolved_duplicates': unresolved(source, state), 'identity_conflicts': conflicts,
        'pending_split_reviews': split_pending, 'pending_detections': pending}


def transition_report(report, action, payload, state):
    if payload.get('base_revision') != report['revision']:
        raise ValueError('Báo cáo đã thay đổi; tải lại')
    reviewer = str(payload.get('reviewer', '')).strip()
    if not reviewer or payload.get('confirm') is not True:
        raise ValueError('Cần tên và xác nhận rõ ràng')
    new = copy.deepcopy(report)
    if action == 'ready':
        has_verified_scope = any(c.get('fully_inspected') is True and (c['scope'] == 'frame' or c.get('verified_regions'))
                                 for c in report.get('technical_appendix', {}).get('coverage', {}).values())
        if report['status'] != 'draft' or not (report['cracks'] or has_verified_scope) or report['unresolved_duplicates'] or report['identity_conflicts'] or report.get('pending_split_reviews'):
            raise ValueError('Báo cáo chưa đủ điều kiện: cần GT và xử lý nghi trùng, mâu thuẫn và đề xuất rà soát sau tách')
        if report['review_revision'] != state['revision']:
            raise ValueError('Nhãn đã thay đổi; tạo bản nháp mới')
        new['status'] = 'ready_for_approval'
    elif action == 'approve':
        if report['status'] != 'ready_for_approval' or payload.get('accept_limits') is not True:
            raise ValueError('Cần trạng thái sẵn sàng và chấp nhận giới hạn quan sát')
        if report['review_revision'] != state['revision']:
            raise ValueError('Nhãn đã thay đổi; tạo báo cáo mới')
        new.update(status='approved', limits_accepted=True, approved_by=reviewer, approved_utc=now())
    else:
        raise ValueError('Trạng thái không hợp lệ')
    new.update(revision=report['revision'] + 1, previous_revision=report['revision'], saved_utc=now())
    return new


class ReviewStore:
    """Same durable review/report store for the standalone and integrated UI."""
    def __init__(self, result_path, workspace, context=None):
        from filelock import FileLock
        self.result_path, self.workspace = Path(result_path).resolve(), Path(workspace).resolve()
        self.source = load_source(self.result_path)
        self.sizes = frame_sizes(self.source, self.result_path.parent)
        self.source_hash = sha(self.result_path)
        self.context = dict(context or {})
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.lock = FileLock(str(self.workspace/'.review.lock'))
        with self.lock:
            binding = self.workspace/'source.json'
            if binding.exists():
                if json.loads(binding.read_text(encoding='utf-8'))['result_sha256'] != self.source_hash:
                    raise ValueError('Workspace is bound to another AI result; never overwrite approved reviews')
            else:
                with binding.open('x', encoding='utf-8') as f:
                    json.dump({'result_sha256': self.source_hash, 'result_path': str(self.result_path)}, f)
        self.reviews, self.reports = self.workspace/'revisions', self.workspace/'reports'

    def state(self):
        if sha(self.result_path) != self.source_hash:
            raise ValueError('AI source changed; review revision is preserved, use a new run')
        with self.lock:
            return {'source': self.source, 'state': latest(self.reviews, 'r', initial(self.source)),
                    'report': latest(self.reports, 'v'), 'sizes': self.sizes,
                    'source_binding': {'result_sha256': self.source_hash, **self.context},
                    'history': sorted(p.name for p in self.reviews.glob('r*.json')),
                    'report_history': sorted(p.name for p in self.reports.glob('v*.json'))}

    def write(self, action, payload):
        if not isinstance(payload, dict):
            raise ValueError('Payload must be an object')
        with self.lock:
            state = self.state()['state']
            if action == 'review':
                saved = apply_review(self.source, state, payload, self.sizes)
                save_immutable(self.reviews, 'r', saved)
            elif action == 'restore':
                revision = payload.get('target_revision')
                if type(revision) is not int or revision < 1 or revision >= state['revision']:
                    raise ValueError('Chọn revision cũ hợp lệ')
                target = json.loads((self.reviews/f'r{revision:06d}.json').read_text(encoding='utf-8'))
                saved = restore_revision(state, target, payload)
                save_immutable(self.reviews, 'r', saved)
            elif action == 'report/draft':
                if payload.get('base_revision') != state['revision'] or not str(payload.get('reviewer', '')).strip():
                    raise ValueError('Cần reviewer và revision hiện tại')
                previous = latest(self.reports, 'v')
                saved = report_snapshot(self.source, state, (previous or {}).get('revision', 0)+1, payload['reviewer'].strip())
                saved['source_binding'] = {'result_sha256': self.source_hash, **self.context}
                saved['review_revision_sha256'] = sha(self.reviews/f"r{state['revision']:06d}.json") if state['revision'] else None
                save_immutable(self.reports, 'v', saved)
            elif action in ('report/ready', 'report/approve'):
                report = latest(self.reports, 'v')
                if report is None:
                    raise ValueError('Chưa có báo cáo')
                saved = transition_report(report, action.split('/')[1], payload, state)
                save_immutable(self.reports, 'v', saved)
            else:
                raise ValueError('Unknown review action')
            return saved


def create_server(result_path, workspace, port=0):
    service = ReviewStore(result_path, workspace)
    result_path, source, sizes = service.result_path, service.source, service.sizes
    reviews, reports = service.reviews, service.reports

    class Handler(BaseHTTPRequestHandler):
        def send(self, status, content, kind='application/json; charset=utf-8'):
            if not isinstance(content, bytes):
                content = json.dumps(content, ensure_ascii=False).encode('utf-8')
            self.send_response(status); self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(content))); self.send_header('Cache-Control', 'no-store')
            self.end_headers(); self.wfile.write(content)

        def do_GET(self):
            path = urlparse(self.path).path
            if path in ('/', '/ui.js'):
                f = ROOT / ('video_review_queue.html' if path == '/' else 'video_review_queue.js')
                return self.send(200, f.read_bytes(), 'text/html; charset=utf-8' if path == '/' else 'text/javascript; charset=utf-8')
            if path == '/api/state':
                try: return self.send(200, service.state())
                except ValueError as exc: return self.send(409, {'error': str(exc)})
            if path.startswith('/api/frame/'):
                try: idx = int(path.rsplit('/', 1)[1]); frame = next(f for f in source['frames'] if f['frame'] == idx)
                except (ValueError, StopIteration): return self.send(404, {'error': 'Frame not found'})
                return self.send(200, (result_path.parent/frame['image']).read_bytes(), 'image/jpeg')
            if path == '/api/video':
                video = Path(source['video']['path'])
                if not video.is_file() or sha(video) != source['video']['sha256']:
                    return self.send(404, {'error': 'Video gốc không có hoặc hash không khớp'})
                size = video.stat().st_size
                start, end = 0, size - 1
                header = self.headers.get('Range')
                if header:
                    match = re.fullmatch(r'bytes=(\d+)-(\d*)', header)
                    if not match or int(match.group(1)) >= size:
                        self.send_response(416); self.send_header('Content-Range', f'bytes */{size}'); self.end_headers(); return
                    start = int(match.group(1))
                    end = min(end, int(match.group(2))) if match.group(2) else end
                    if end < start:
                        self.send_response(416); self.end_headers(); return
                self.send_response(206 if header else 200)
                self.send_header('Content-Type', mimetypes.guess_type(video.name)[0] or 'application/octet-stream')
                self.send_header('Accept-Ranges', 'bytes')
                self.send_header('Content-Length', str(end-start+1))
                if header: self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
                self.end_headers()
                with video.open('rb') as stream:
                    stream.seek(start); remaining = end-start+1
                    while remaining:
                        chunk = stream.read(min(1024*1024, remaining))
                        if not chunk: break
                        self.wfile.write(chunk); remaining -= len(chunk)
                return
            if re.fullmatch(r'/api/(revision/r|report/v)\d{6}\.json', path):
                kind, name = path.removeprefix('/api/').split('/')
                f = (reviews if kind == 'revision' else reports)/name
                if f.is_file(): return self.send(200, f.read_bytes())
            self.send(404, {'error': 'Not found'})

        def do_POST(self):
            try:
                if self.headers.get('Origin') not in (None, f'http://127.0.0.1:{self.server.server_port}'):
                    raise ValueError('Origin không hợp lệ')
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 2_000_000: raise ValueError('Payload không hợp lệ')
                payload = json.loads(self.rfile.read(length))
                saved = service.write(self.path.removeprefix('/api/'), payload)
                self.send(201, saved)
            except (ValueError, KeyError, TypeError, json.JSONDecodeError, FileExistsError) as exc:
                self.send(400, {'error': str(exc)})
        def log_message(self, *args): pass
    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--result', required=True)
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--port', type=int, default=8767)
    args = parser.parse_args()
    server = create_server(args.result, args.workspace, args.port)
    print(f'http://127.0.0.1:{server.server_port}/', flush=True)
    try: server.serve_forever()
    finally: server.server_close()


if __name__ == '__main__': main()
