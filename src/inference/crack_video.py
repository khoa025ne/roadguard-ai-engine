"""Experimental, append-only video observations and conservative crack association."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import cv2
import numpy as np

from src.ingestion.video_extractor import VideoFrameExtractor
from src.inference.mvp_video import sample_indices

ROOT = Path(__file__).resolve().parents[2]
FT95 = ROOT / 'weights/trained/RoadGuard_YOLO11_UAVPDD2023_FT95_v1.pt'
ROAD = ROOT / 'weights/pretrained/yolo11m-road-seg.pt'


def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def registration(a, b):
    """Map a to b using local visual features; never infer from GPS or detector scores."""
    orb = cv2.ORB_create(nfeatures=2500)
    ka, da = orb.detectAndCompute(cv2.cvtColor(a, cv2.COLOR_BGR2GRAY), None)
    kb, db = orb.detectAndCompute(cv2.cvtColor(b, cv2.COLOR_BGR2GRAY), None)
    if da is None or db is None or len(da) < 8 or len(db) < 8:
        return None
    pairs = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(da, db, k=2)
    good = [x for pair in pairs if len(pair) == 2 for x, y in [pair] if x.distance < .72 * y.distance]
    if len(good) < 12:
        return None
    src = np.float32([ka[m.queryIdx].pt for m in good])
    dst = np.float32([kb[m.trainIdx].pt for m in good])
    h, inliers = cv2.findHomography(src, dst, cv2.RANSAC, 3.0)
    if h is None or inliers is None or not np.isfinite(h).all():
        return None
    sel = inliers.ravel().astype(bool)
    if int(sel.sum()) < 10 or float(sel.mean()) < .55:
        return None
    return h, src[sel], dst[sel], len(good)


def overlap(a, b):
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0., x2-x1) * max(0., y2-y1)
    area_a = max(0., (a[2]-a[0])*(a[3]-a[1]))
    area_b = max(0., (b[2]-b[0])*(b[3]-b[1]))
    return inter / max(1., area_a + area_b - inter)


def frame_overlap(reg, source_shape, target_shape):
    if reg is None:
        return None
    sh, sw = source_shape[:2]
    th, tw = target_shape[:2]
    corners = np.float32([[[0, 0], [sw, 0], [sw, sh], [0, sh]]])
    mapped = cv2.perspectiveTransform(corners, reg[0])[0]
    if not np.isfinite(mapped).all() or not cv2.isContourConvex(mapped):
        return None
    target = np.float32([[0, 0], [tw, 0], [tw, th], [0, th]])
    area, _ = cv2.intersectConvexConvex(mapped, target)
    return float(max(0., min(1., area / max(1., tw * th))))


def compare(a, b, image_a, image_b):
    if a['video_id'] != b['video_id'] or a['frame'] == b['frame']:
        return None
    reg = registration(image_a, image_b)
    if reg is None:
        return None
    h, src, dst, matches = reg
    x1, y1, x2, y2 = a['box']
    points = np.float32([[[x1,y1],[x2,y1],[x2,y2],[x1,y2]]])
    mapped = cv2.perspectiveTransform(points, h)[0]
    if not np.isfinite(mapped).all():
        return None
    projected = [float(mapped[:,0].min()), float(mapped[:,1].min()),
                 float(mapped[:,0].max()), float(mapped[:,1].max())]
    iou = overlap(projected, b['box'])
    # Local support guards against extrapolation of a homography across the scene.
    margin = max(x2-x1, y2-y1, 30) * .5
    local = ((src[:,0] >= x1-margin) & (src[:,0] <= x2+margin) &
             (src[:,1] >= y1-margin) & (src[:,1] <= y2+margin))
    count = int(local.sum())
    if iou < .15:
        return None
    # An intersection alone is weak: similar complete box extents plus local support required.
    strong = iou >= .65 and count >= 6
    return {'kind': 'same_candidate' if strong else 'suspected_duplicate',
            'projected_iou': round(iou, 4), 'local_inliers': count,
            'inliers': len(src), 'feature_matches': matches,
            'homography': h.tolist(), 'projected_box': projected,
            'source_detection': a['id'], 'target_detection': b['id'],
            'source_frame': a['frame'], 'target_frame': b['frame']}


def associate(detections, images):
    """Output proposals without changing source or approved identities/labels."""
    records = [dict(d) for d in detections]
    links, tracks = [], {}
    for d in records:
        if d.get('approved_id'):
            d['track_id'] = d['approved_id']
        else:
            d['track_id'] = 'track-' + d['video_id'][:16] + '-' + d['id']
        tracks[d['id']] = d['track_id']
    # Process sequentially; ambiguity or any approved identity prevents automatic merge.
    for i, b in enumerate(records):
        candidates = []
        for a in records[:i]:
            if a['video_id'] != b['video_id'] or a['frame'] == b['frame']:
                continue
            ev = compare(a, b, images[(a['video_id'], a['frame'])], images[(b['video_id'], b['frame'])])
            if ev:
                candidates.append((a, ev))
        strong_ids = {tracks[a['id']] for a, ev in candidates if ev['kind'] == 'same_candidate'}
        safe = len(strong_ids) == 1 and not b.get('approved_id')
        if safe:
            target = next(iter(strong_ids))
            # Never attach a second detection from this frame to an existing track.
            safe = not any(x['frame'] == b['frame'] and x['video_id'] == b['video_id']
                           and tracks[x['id']] == target for x in records[:i])
        if safe:
            tracks[b['id']] = target
            b['track_id'] = target
        for a, ev in candidates:
            ev['decision'] = ('linked' if safe and tracks[a['id']] == tracks[b['id']]
                              and ev['kind'] == 'same_candidate' else 'suspected_duplicate')
            links.append(ev)
    return records, links


def run(video, output, *, sample_fps=1., risk_fps=4., blur_threshold=50.,
        detections_file=None, anchors_file=None, detector_path=FT95, road_path=ROAD):
    video, output = Path(video).resolve(), Path(output).resolve()
    if output.exists():
        raise FileExistsError('Output must be new; existing results are immutable')
    if not (0 < sample_fps <= risk_fps <= 30) or blur_threshold < 0:
        raise ValueError('Invalid sampling configuration')
    cap = cv2.VideoCapture(str(video))
    fps, total = cap.get(cv2.CAP_PROP_FPS), int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if not cap.isOpened() or not math.isfinite(fps) or fps <= 0 or total <= 0:
        cap.release()
        raise ValueError('Invalid video metadata')
    config = {'sample_fps': sample_fps, 'risk_fps': risk_fps, 'blur_threshold': blur_threshold,
              'detector_conf': .25, 'tiling': True, 'tile_size': 640, 'tile_overlap': .2,
              'road_conf': .25, 'road_imgsz': 640, 'association': 'orb-homography-iou-v1',
              'risk_min_estimated_overlap': .65, 'risk_min_registration_inliers': 20}
    video_id = digest(video)
    injected = json.loads(Path(detections_file).read_text(encoding='utf-8')) if detections_file else None
    anchors = json.loads(Path(anchors_file).read_text(encoding='utf-8')) if anchors_file else []
    models = {'source': 'injected_test_detections', 'sha256': digest(detections_file)} if injected is not None else {}
    detector = segmenter = None
    if injected is None:
        from ultralytics import YOLO
        import ultralytics, torch
        from src.inference.predictor import RoadDefectPredictor
        detector = RoadDefectPredictor(detector_path, conf_threshold=.25)
        detector.class_map = {int(k): str(v) for k, v in detector.model.names.items()}
        segmenter = YOLO(str(road_path))
        if detector.model.task != 'detect' or segmenter.task != 'segment' or segmenter.names != {0: 'road'}:
            raise ValueError('Unexpected model taxonomy')
        models = {'detector': {'path': str(detector_path), 'sha256': digest(detector_path), 'classes': detector.class_map},
                  'road': {'path': str(road_path), 'sha256': digest(road_path)},
                  'ultralytics': ultralytics.__version__, 'torch': torch.__version__, 'opencv': cv2.__version__}
    output.mkdir(parents=True)
    (output/'frames').mkdir()
    (output/'masks').mkdir()
    base = set(sample_indices(total, fps, sample_fps))
    candidates = sorted(set(sample_indices(total, fps, risk_fps)) | base | {int(a['frame']) for a in anchors})
    observations, frames, images = [], [], {}
    prior = None
    extractor = VideoFrameExtractor()
    try:
        for idx in candidates:
            if idx < 0 or idx >= total:
                raise ValueError('Anchor frame outside video')
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, image = cap.read()
            if not ok:
                raise ValueError(f'Cannot decode frame {idx}')
            sharpness = extractor.calc_blur_score(image)
            reg = registration(prior, image) if prior is not None else None
            coverage = frame_overlap(reg, prior.shape, image.shape) if prior is not None else None
            risk = prior is not None and (reg is None or coverage is None or coverage < .65
                                          or len(reg[1]) < 20 or sharpness < blur_threshold)
            if idx not in base and not risk and idx not in {int(a['frame']) for a in anchors}:
                continue
            images[(video_id, idx)] = image
            prior = image
            name = f'frames/{idx:08d}.jpg'
            cv2.imencode('.jpg', image)[1].tofile(str(output/name))
            frame = {'frame': idx, 'timestamp_s': idx/fps, 'image': name,
                     'sharpness': sharpness, 'blur_warning': sharpness < blur_threshold,
                     'sampling_reason': 'scheduled' if idx in base else 'risk_or_user_anchor',
                     'registration_inliers_previous': len(reg[1]) if reg else 0,
                     'estimated_overlap_previous': coverage}
            frames.append(frame)
            if injected is None:
                from tools.roadmask_pilot import predict_road, box_overlap
                mask = predict_road(segmenter, image)
                if mask is not None:
                    frame['road_mask'] = f'masks/{idx:08d}.png'
                    cv2.imencode('.png', mask)[1].tofile(str(output/frame['road_mask']))
                frame['road_mask_status'] = 'unreviewed' if mask is not None else 'missing_needs_review'
                raw = detector.predict_full_frame(image, use_tiling=True)
            else:
                mask = None
                frame['road_mask_status'] = 'not_run_test_input'
                raw = injected.get(str(idx), [])
            raw = list(raw) + [dict(a, source='user', review_status=a.get('review_status', 'user_proposal')) for a in anchors if int(a['frame']) == idx]
            for n, item in enumerate(raw):
                box = item.get('box')
                if not isinstance(box, list) or len(box) != 4 or not (0 <= box[0] < box[2] <= image.shape[1] and 0 <= box[1] < box[3] <= image.shape[0]):
                    raise ValueError(f'Invalid box at frame {idx}')
                record = {**item, 'id': f'{idx:08d}-{n:04d}', 'video_id': video_id,
                          'frame': idx, 'timestamp_s': idx/fps, 'box': box,
                          'source': item.get('source', 'model' if injected is None else 'injected_test'),
                          'model': models, 'config': config,
                          'road_overlap': box_overlap(box, mask) if mask is not None else None,
                          'road_status': 'unreviewed' if mask is not None else 'needs_review'}
                observations.append(record)
    finally:
        cap.release()
    associated, links = associate(observations, images)
    representatives = {}
    for d in associated:
        f = next(x for x in frames if x['frame'] == d['frame'])
        x1, y1, x2, y2 = d['box']
        h, w = images[(video_id, d['frame'])].shape[:2]
        complete = x1 > 2 and y1 > 2 and x2 < w-2 and y2 < h-2
        score = (int(complete), f['sharpness'])
        if d['track_id'] not in representatives or score > representatives[d['track_id']][0]:
            representatives[d['track_id']] = (score, d['id'])
    result = {'schema': 'roadguard-crack-video-experimental-v1', 'video': {'path': str(video), 'sha256': video_id, 'fps': fps, 'frames': total},
              'config': config, 'models': models, 'frames': frames, 'detections': observations,
              'association_proposals': associated, 'links': links,
              'representatives': {k: {'detection_id': v[1], 'criterion': 'box_not_cut_by_frame_then_sharpness'} for k,v in representatives.items()},
              'limitations': ['Experimental associations require review', 'No GPS or physical dimensions', 'Detector operation is not accuracy evidence']}
    (output/'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--video', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--detections', help='JSON object of frame index to test detections; skips model inference')
    p.add_argument('--anchors', help='JSON array of user boxes with frame, box and optional approved_id')
    p.add_argument('--sample-fps', type=float, default=1.)
    p.add_argument('--risk-fps', type=float, default=4.)
    p.add_argument('--blur-threshold', type=float, default=50.)
    args = p.parse_args()
    r = run(args.video, args.output, sample_fps=args.sample_fps, risk_fps=args.risk_fps,
            blur_threshold=args.blur_threshold, detections_file=args.detections, anchors_file=args.anchors)
    print(json.dumps({'frames': len(r['frames']), 'detections': len(r['detections']),
                      'links': len(r['links']), 'result': str(Path(args.output)/'result.json')}))


if __name__ == '__main__':
    main()
