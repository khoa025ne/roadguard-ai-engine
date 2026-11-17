"""Reports from stored video observations and source-bound human review."""
import html
import json
from collections import Counter
from pathlib import Path

from src.api import video_job_store as store
from src.inference.ckey import CLASSES
from tools.video_review_queue import latest, sha


def review_facts(folder, job):
    facts = {'status': 'chưa rà soát', 'revision': None, 'approved_labels': 0,
             'physical_defects': None, 'approved_report_revision': None,
             'reviewed_frames': 0}
    if job.get('reviews'):
        facts.update(status='duyệt box theo luồng cũ',
            approved_labels=sum(item.get('status') == 'approved' for item in job['reviews'].values()))
        return facts
    workspace, source = folder/'review', folder/'review_source.json'
    if not (workspace/'source.json').is_file():
        return facts
    try:
        with store.GUARD:
            binding = json.loads((workspace/'source.json').read_text(encoding='utf-8'))
            if sha(source) != binding['result_sha256']:
                raise ValueError('Review source changed')
            origin = json.loads(source.read_text(encoding='utf-8'))
            if (origin['source_job_id'] != job['job_id']
                or origin['source_analysis_sha256'] != sha(folder/'analysis.json')):
                raise ValueError('Analysis source changed')
            revision = latest(workspace/'revisions', 'r')
            approved = latest(workspace/'reports', 'v')
        if revision:
            facts.update(status='đã có quyết định rà soát', revision=revision['revision'],
                approved_labels=sum(row['status']=='approved' for row in revision['detections'].values()),
                reviewed_frames=len(revision.get('coverage', {})))
        if (revision and approved and approved.get('status') == 'approved'
            and approved.get('review_revision') == revision['revision']
            and approved.get('source_binding', {}).get('result_sha256') == binding['result_sha256']):
            facts.update(physical_defects=approved['overview']['approved_physical_ids'],
                         approved_report_revision=approved['revision'])
    except (OSError, ValueError, KeyError, TypeError):
        facts['status'] = 'không xác minh được nguồn revision'
    return facts


def snapshot(job, folder):
    result = job['result']
    frames = result.get('frames', [])
    detections = result.get('detections')
    counts = Counter(str(box.get('class_name', '')).strip().lower() for box in detections or [])
    mask = result.get('road_mask') or {}
    mask_frames = sum(bool(frame.get('road_mask')) for frame in frames)
    review = review_facts(folder, job)
    return {'schema_version': 2, 'job_id': job['job_id'], 'provider': 'local-statistics',
            'video': Path(job.get('source_name') or 'Video local').name,
            'analyzed_at': job.get('completed_at') or next((event['timestamp']
                for event in reversed(store.events(folder.parent, job['job_id']))
                if event.get('code') == 'JOB_COMPLETED'), None),
            'generated_at': store.now(), 'models': result.get('models', []),
            'sampled_frames': result.get('summary', {}).get('sampled_frames', len(frames)),
            'summary': result.get('summary', {}), 'limitations': result.get('limitations') or 'Chưa có dữ liệu.',
            'observations': {'frame_boxes': len(detections) if detections is not None else None,
                'ft95_classes': {label: counts[label] if detections is not None else None for label in CLASSES},
                'other_boxes': sum(count for label, count in counts.items() if label not in CLASSES)},
            'road_mask': {'enabled': bool(mask.get('enabled', mask_frames)), 'predicted_frames': mask_frames,
                'missing_frames': sum(frame.get('road_mask_status')=='missing_needs_review' for frame in frames),
                'verification': 'AI chưa được xác minh' if mask_frames else 'Chưa có mask dự đoán',
                'model': mask.get('model')},
            'human_review': review['status'], 'review': review}


def ai_facts(report):
    """Whitelist numeric aggregates and approved report state. No file data or path."""
    review = report['review']
    model_refs = [{'model': row.get('label'), 'version': row.get('version')}
                  for row in report['models']]
    return {
        'executive_summary': report['observations'],
        'inspection_scope': {'sampled_frames': report['sampled_frames']},
        'physical_defect_summary': {'physical_defects': review['physical_defects']},
        'review_status': {'status': 'draft', 'review_revision': review['revision'],
                          'approved_labels': review['approved_labels']},
        'coverage_and_limitations': {'reviewed_frames': review['reviewed_frames'],
            'road_mask_predicted_frames': report['road_mask']['predicted_frames'],
            'unreviewed_frames_are_not_ground_truth': True},
        'recommended_followup': [],
        'technical_appendix': {'detector_versions': model_refs,
            'approved_report_revision': review['approved_report_revision']},
        'allowed_followups': ['Kiểm tra bổ sung các vùng chưa xác minh'],
    }


def render(report, frames):
    def esc(value):
        return html.escape('Chưa có dữ liệu' if value is None else str(value))

    def table(rows):
        return '<dl>' + ''.join(f'<dt>{esc(label)}</dt><dd>{esc(value)}</dd>' for label,value in rows) + '</dl>'

    review, obs, mask = report['review'], report['observations'], report['road_mask']
    model_text = ', '.join(f"{m.get('label') or m.get('name') or 'Model'} / {m.get('version') or 'chưa có phiên bản'}"
                           for m in report['models'])
    model_mask = mask.get('model') or {}
    evidence = ''.join(f'<figure><img src="{esc(f["image"])}" alt="Khung hình lấy mẫu"><figcaption>Frame {esc(f["frame"])} · {esc(f["timestamp_s"])} s</figcaption></figure>'
                       for f in frames[:12] if f.get('image') and Path(f['image']).name == f['image'])
    return ('<!doctype html><html lang="vi"><meta charset="utf-8"><title>Báo cáo RoadGuard</title>'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<style>body{font:16px system-ui;max-width:900px;margin:auto;padding:24px;color:#182a38}'
        'dl{display:grid;grid-template-columns:minmax(130px,1fr) 2fr;gap:10px}dd{margin:0;overflow-wrap:anywhere}'
        'dt{font-weight:600}img{max-width:100%}</style>'
        '<h1>Báo cáo thống kê local</h1><h2>Phiên phân tích</h2>'
        + table([('Video', report['video']), ('Job ID', report['job_id']), ('Ngày phân tích', report['analyzed_at']),
                 ('Khung hình lấy mẫu', report['sampled_frames']), ('Model / phiên bản', model_text or None)])
        + '<h2>Khuyết tật và rà soát</h2>'
        + table([('Box quan sát theo frame', obs['frame_boxes']), *obs['ft95_classes'].items(),
                 ('Box lớp khác', obs['other_boxes']), ('Nhãn được người dùng duyệt', review['approved_labels']),
                 ('Khuyết tật vật lý theo báo cáo đã duyệt', review['physical_defects']),
                 ('Trạng thái rà soát', review['status']), ('Revision rà soát', review['revision']),
                 ('Khung hình có ghi nhận phạm vi rà soát', review['reviewed_frames'])])
        + '<h2>Road Mask</h2>'
        + table([('Có dự đoán', mask['predicted_frames']), ('Thiếu dự đoán', mask['missing_frames']),
                 ('Xác minh', mask['verification']), ('Model', model_mask.get('name')), ('Phiên bản', model_mask.get('version'))])
        + '<h2>Giới hạn quan sát</h2><p>' + esc(report['limitations'])
        + '</p><p>Box theo frame có thể lặp. Số khuyết tật vật lý lấy từ phiên bản báo cáo được người dùng duyệt khi có.</p>'
        '<h2>Khung hình tham chiếu</h2>' + evidence + '</html>')


def write(job, folder):
    with store.GUARD:
        report = snapshot(job, folder)
        files = {'report_local.json': json.dumps(report, ensure_ascii=False, indent=2),
                 'report_local.html': render(report, job['result'].get('frames', []))}
        for name, content in files.items():
            pending = folder/(name + '.tmp')
            pending.write_text(content, encoding='utf-8')
            pending.replace(folder/name)
        return report
