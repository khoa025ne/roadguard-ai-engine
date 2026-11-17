"""Job-scoped local review routes using the existing Review Queue revision store."""
import json
import re
from pathlib import Path

from fastapi import Body, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from src.api import video_job_store as jobs
from tools.video_review_queue import ROOT as REVIEW_WEB, ReviewStore, sha


def prepare_review(job, folder):
    """Add a read-only adapter; never rewrite analysis or import legacy approvals."""
    if job['status'] != 'COMPLETED':
        raise ValueError('Job chưa hoàn tất')
    if job.get('reviews'):
        raise ValueError('LEGACY_REVIEW_REQUIRES_MIGRATION: giữ nguyên nhãn cũ; cần xác minh contract trước khi chuyển')
    raw_path = folder/'analysis.json'
    source_video = folder/'source.video'
    if raw_path.is_symlink() or not raw_path.is_file() or not source_video.is_file() or source_video.is_symlink():
        raise ValueError('Thiếu kết quả AI hoặc video gốc của job')
    raw_hash = sha(raw_path)
    adapted_path = folder/'review_source.json'
    if adapted_path.exists():
        existing = json.loads(adapted_path.read_text(encoding='utf-8'))
        if existing.get('source_analysis_sha256') != raw_hash or existing.get('source_job_id') != job['job_id']:
            raise ValueError('AI rerun đã thay đổi nguồn; giữ revision cũ và tạo job mới')
        return adapted_path
    raw = json.loads(raw_path.read_text(encoding='utf-8'))
    video_hash = sha(source_video)
    if job.get('source_sha256') and video_hash != job['source_sha256']:
        raise ValueError('Video hash không khớp job')
    # Existing main app has observations, not physical identities. Start each
    # observation as a separate proposal; only the reviewer may merge IDs.
    frames = [{**f, 'image': f.get('original') or f['image']} for f in raw['frames']]
    detections = [{**d, 'id': f'det-{i:08d}', 'video_id': video_hash,
                   'box': d['bbox'], 'source': 'model', 'source_detection_index': i}
                  for i, d in enumerate(raw['detections'])]
    summary = raw.get('summary', {})
    adapted = {'schema': 'roadguard-crack-video-experimental-v1',
        'source_job_id': job['job_id'], 'source_analysis_sha256': raw_hash,
        'video': {'path': str(source_video.resolve()), 'sha256': video_hash,
                  'fps': summary.get('source_fps'), 'frames': job.get('video', {}).get('total_frames')},
        'frames': frames, 'detections': detections,
        'association_proposals': [{'id': d['id'], 'track_id': 'proposal-'+d['id']} for d in detections],
        'links': [], 'representatives': {}, 'models': raw.get('models', []),
        'config': {'sample_fps': job.get('sample_fps'), 'selection': job.get('selection'),
                   'confidence_threshold': summary.get('confidence_threshold'), 'analysis_summary': summary,
                   'road_mask': raw.get('road_mask', {'enabled': False})},
        'limitations': [raw.get('limitations', 'Chưa đo chất lượng AI'),
                       f"Phạm vi quan sát: {len(frames)} frame lấy mẫu, {summary.get('analyzed_seconds', 'chưa xác minh')} giây phân tích; các frame/vùng khác chưa được xác minh.",
                       'Luồng job hiện tại chưa có tracking: mỗi observation là ID đề xuất riêng, cần người dùng xác minh danh tính.']}
    with adapted_path.open('x', encoding='utf-8') as stream:
        json.dump(adapted, stream, ensure_ascii=False, indent=2)
    return adapted_path


def install_review_routes(router, get_job, runs_root, guard):
    cache = {}

    def service(job_id):
        try:
            folder = jobs.directory(runs_root(), job_id)
            job = get_job(job_id)
            if job['status'] != 'COMPLETED':
                raise ValueError('Job chưa hoàn tất')
            if job.get('reviews'):
                raise ValueError('LEGACY_REVIEW_REQUIRES_MIGRATION: cần xác minh nhãn cũ trước khi chuyển')
            with guard:
                key = str(folder.resolve())
                if key not in cache:
                    if job.get('result', {}).get('schema') == 'roadguard-crack-video-experimental-v1':
                        source = folder/'result.json'
                    else:
                        source = prepare_review(job, folder)
                    cache[key] = ReviewStore(source, folder/'review', context={'job_id': job_id})
                current = cache[key]
                source = current.source
                if source.get('source_analysis_sha256') and sha(folder/'analysis.json') != source['source_analysis_sha256']:
                    raise ValueError('AI rerun đã thay đổi nguồn; giữ revision cũ và tạo job mới')
                current.state()  # Check source binding on every request, including writes/assets.
                return current
        except (ValueError, KeyError, OSError) as exc:
            raise HTTPException(409, detail=str(exc)) from exc

    @router.get('/{job_id}/review-queue/', response_class=HTMLResponse)
    def page(job_id: str):
        service(job_id)
        return (REVIEW_WEB/'video_review_queue.html').read_text(encoding='utf-8').replace('src="/ui.js"', 'src="ui.js"')

    @router.get('/{job_id}/review-queue/ui.js')
    def script(job_id: str):
        service(job_id)
        return FileResponse(REVIEW_WEB/'video_review_queue.js', media_type='text/javascript')

    @router.get('/{job_id}/review-queue/api/state')
    def state(job_id: str):
        from src.api.ckey_routes import vision_state
        current = service(job_id)
        state = current.state()
        vision = vision_state(jobs.directory(runs_root(), job_id), active=True)
        state['vision'] = vision.get('result')
        return state

    @router.get('/{job_id}/review-queue/api/frame/{index}')
    def frame(job_id: str, index: int, mask: bool = False):
        current = service(job_id)
        row = next((f for f in current.source['frames'] if f['frame'] == index), None)
        if row is None:
            raise HTTPException(404, 'Unknown source frame')
        name = row.get('road_overlay') if mask else row['image']
        if not name:
            raise HTTPException(404, 'Road Mask overlay unavailable')
        path = (current.result_path.parent/name).resolve()
        if not path.is_relative_to(current.result_path.parent) or not path.is_file():
            raise HTTPException(404, 'Unknown source frame')
        return FileResponse(path)

    @router.get('/{job_id}/review-queue/api/video')
    def video(job_id: str):
        current = service(job_id)
        path = Path(current.source['video']['path']).resolve()
        if not path.is_relative_to(jobs.directory(runs_root(), job_id).resolve()) or not path.is_file():
            raise HTTPException(404, 'Video is not available in this job')
        return FileResponse(path, media_type='video/mp4')

    @router.get('/{job_id}/review-queue/api/{kind}/{name}')
    def history(job_id: str, kind: str, name: str):
        current = service(job_id)
        if kind not in {'revision', 'report'} or not re.fullmatch(r'[rv]\d{6}\.json', name):
            raise HTTPException(404, 'Unknown revision')
        path = (current.reviews if kind == 'revision' else current.reports)/name
        if not path.is_file() or path.is_symlink():
            raise HTTPException(404, 'Unknown revision')
        return FileResponse(path, media_type='application/json')

    @router.post('/{job_id}/review-queue/api/{action:path}', status_code=201)
    def save(job_id: str, action: str, payload: dict = Body(...)):
        current = service(job_id)
        try:
            return current.write(action, payload)
        except (ValueError, KeyError, TypeError, OSError) as exc:
            raise HTTPException(409, detail=str(exc)) from exc
