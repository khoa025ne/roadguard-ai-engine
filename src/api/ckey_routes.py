"""Explicit paid experiments attached to an immutable source job."""
import hashlib
import json
import uuid
import cv2
import numpy as np
from fastapi import Body, HTTPException
from fastapi.responses import JSONResponse
from src.inference.ckey import Client, settings, preview
from tools.video_review_queue import sha
from src.api.local_video_report import ai_facts, snapshot


def vision_state(folder, active=False, kind='vision', successful_only=False):
    """Read only results for the current immutable analysis."""
    analysis = folder / 'analysis.json'
    if not analysis.is_file():
        return {'status': 'pending'}
    source_hash = sha(analysis)
    requests = sorted((folder / 'ckey_runs').glob('*/request.json'),
                      key=lambda path: path.stat().st_mtime_ns, reverse=True)
    for path in requests:
        try:
            receipt = json.loads(path.read_text(encoding='utf-8'))
            if receipt['kind'] != kind or receipt['source_analysis_sha256'] != source_hash:
                continue
            result = path.with_name('result.json')
            if result.is_file():
                return {**receipt, 'status': 'completed', 'result': json.loads(result.read_text(encoding='utf-8'))}
            if successful_only:
                continue
            if receipt['status'] == 'running' and not active:
                receipt['status'] = 'interrupted'
            return receipt
        except (KeyError, OSError, ValueError):
            continue
    return {'status': 'pending'}


def vision_config():
    cfg = settings()
    cfg['max_images'] = min(5, cfg['max_images'])
    return cfg


def input_revision(facts, model):
    encoded = json.dumps([model, facts], ensure_ascii=False, sort_keys=True).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def compare_frame(proposals, detections, width, height):
    """Count one-to-one overlaps of the same class. Agreement is not GT."""
    candidates = []
    for i, proposal in enumerate(proposals):
        box = proposal['bbox_xyxy_norm']
        if box is None:
            continue
        x1, y1, x2, y2 = box
        for j, detection in enumerate(detections):
            if proposal['class'] != detection['class_name']:
                continue
            dx1, dy1, dx2, dy2 = detection['bbox']
            a, b, c, d = dx1/width, dy1/height, dx2/width, dy2/height
            common = max(0, min(x2,c)-max(x1,a)) * max(0, min(y2,d)-max(y1,b))
            union = (x2-x1)*(y2-y1) + (c-a)*(d-b) - common
            if union > 0 and common / union >= .5:
                candidates.append((common / union, i, j))
    vision, local = set(), set()
    for _, i, j in sorted(candidates, reverse=True):
        if i not in vision and j not in local:
            vision.add(i)
            local.add(j)
    return {'matched': len(vision), 'ft95_unmatched': len(detections)-len(local),
            'gemini_unmatched': len(proposals)-len(vision)}


def install(router, get_job, runs_root, guard):
    @router.get('/ckey/models')
    def models():
        cfg=settings()
        public = {key: value for key, value in cfg.items() if key != 'base_url'}
        return {**public,'capability_status':'operator_verified' if cfg['contract_verified'] else 'unverified',
                'modes':['FT95','Vision','FT95 + Vision'],'automatic_execution':False}

    def source(job_id):
        from src.api.video_job_store import directory
        job=get_job(job_id)
        if job['status']!='COMPLETED':raise HTTPException(409,'Job chưa hoàn tất')
        folder=directory(runs_root(),job_id)
        return job,folder

    @router.get('/{job_id}/ckey/preview')
    def estimate(job_id: str):
        job,_=source(job_id)
        return preview(len(job['result']['frames']), vision_config())

    @router.get('/{job_id}/ckey/vision')
    def vision_result(job_id: str):
        _,folder=source(job_id)
        return vision_state(folder, guard.locked())

    @router.get('/{job_id}/ckey/report/preview')
    def report_preview(job_id: str):
        job, folder = source(job_id)
        cfg = settings()
        facts = ai_facts(snapshot(job, folder))
        return {'requests': 1, 'estimated_cost': None, 'images': 0,
                'model': cfg['report_model'], 'contract_verified': cfg['report_contract_verified'],
                'input_revision': input_revision(facts, cfg['report_model']), 'input': facts}

    @router.get('/{job_id}/ckey/report')
    def report_result(job_id: str, download: bool = False):
        _, folder = source(job_id)
        draft = vision_state(folder, kind='report', successful_only=True).get('result')
        if download:
            if not draft:
                raise HTTPException(404, 'Chưa có bản nháp AI để tải')
            return JSONResponse(draft, headers={'Content-Disposition':
                f'attachment; filename="roadguard-ai-draft-{draft["run_id"]}.json"'})
        current = vision_state(folder, guard.locked(), kind='report')
        return {**current, 'result': draft}

    @router.post('/{job_id}/ckey/{kind}',status_code=201)
    def run(job_id: str,kind: str,body: dict=Body(...)):
        if kind not in {'vision','report'}:raise HTTPException(404,'Unknown CKEY operation')
        if body.get('confirm_paid') is not True:raise HTTPException(409,'Cần thao tác xác nhận chạy API trả phí')
        job,folder=source(job_id)
        cfg=vision_config() if kind == 'vision' else settings()
        if kind == 'report':
            cfg = {**cfg, 'retries': 0}
        mode = job.get('detection_mode') or body.get('mode', 'FT95 + Vision')
        if kind == 'vision' and mode not in {'Vision', 'FT95 + Vision'}:
            raise HTTPException(409, 'Job này sử dụng chế độ FT95 Local')
        if not cfg['credential_available']:
            raise HTTPException(409, 'Thiếu KDV_API_KEY trong cấu hình máy chủ')
        if not cfg['vision_contract_verified' if kind=='vision' else 'report_contract_verified']:
            raise HTTPException(409,'CKEY_CONTRACT_UNVERIFIED: model của tác vụ này chưa được xác minh')
        facts = None
        if kind == 'report':
            facts = ai_facts(snapshot(job, folder))
            if body.get('input_revision') != input_revision(facts, cfg['report_model']):
                raise HTTPException(409, 'Dữ liệu đã đổi hoặc chưa xem trước. Mở lại nội dung gửi và xác nhận.')
        if not guard.acquire(blocking=False):raise HTTPException(409,'Một yêu cầu CKEY đang chạy')
        manifest = None
        try:
            client=Client(config=cfg);run_id=uuid.uuid4().hex;output=folder/'ckey_runs'/run_id;output.mkdir(parents=True)
            manifest={'run_id':run_id,'job_id':job_id,'source_analysis_sha256':sha(folder/'analysis.json'),'kind':kind,'status':'running','provider':'CKEY'}
            (output/'request.json').write_text(json.dumps(manifest),encoding='utf-8')
            if kind=='vision':
                result={'images': [], 'source_images': [], 'mode': mode, 'model': cfg['vision_model'],
                        'provider': 'CKEY', 'review_status': 'ai_proposal', 'usage': client.usage}
                frames = job['result']['frames']
                detections = {}
                if mode == 'FT95 + Vision':
                    for detection in job['result']['detections']:
                        detections.setdefault(detection['frame'], []).append(detection)
                for offset in range(0, len(frames), cfg['max_images']):
                    rows=[]
                    sizes={}
                    for frame in frames[offset:offset + cfg['max_images']]:
                        path=(folder/(frame.get('original') or frame['image'])).resolve()
                        if not path.is_relative_to(folder.resolve()):raise ValueError('INVALID_IMAGE_PATH')
                        image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
                        if image is None:
                            raise ValueError('INVALID_IMAGE')
                        sizes[str(frame['frame'])] = (image.shape[1],image.shape[0])
                        scale = min(1, 768/image.shape[1], 432/image.shape[0])
                        if scale < 1:
                            image = cv2.resize(image, (max(1,round(image.shape[1]*scale)),
                                max(1,round(image.shape[0]*scale))), interpolation=cv2.INTER_AREA)
                        ok, png = cv2.imencode('.png', image)
                        if not ok:
                            raise ValueError('INVALID_IMAGE')
                        rows.append({'image_id':f"{job_id}:{frame['frame']}",'frame_id':str(frame['frame']),
                            'timestamp':frame['timestamp_s'],'image_sha256':sha(path),'image_bytes':png.tobytes(),
                            'ft95_detections':detections.get(frame['frame'], [])})
                    predictions = client.vision(rows)['images']
                    if mode == 'FT95 + Vision':
                        for prediction in predictions:
                            frame_id = prediction['frame_id']
                            prediction['comparison'] = compare_frame(prediction['detections'],
                                detections.get(int(frame_id), []), *sizes[frame_id])
                    result['images'].extend(predictions)
                    result['source_images'].extend({k:v for k,v in row.items() if k!='image_bytes'} for row in rows)
            else:
                (output/'input.json').write_text(json.dumps(facts, ensure_ascii=False), encoding='utf-8')
                result={'report':client.report(facts),'model':cfg['report_model'],'provider':'CKEY',
                        'usage':client.usage,'status':'draft','review_revision':facts['review_status']['review_revision']}
            result.update(run_id=run_id,job_id=job_id,source_analysis_sha256=manifest['source_analysis_sha256'])
            pending = output/'result.tmp'
            pending.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            pending.replace(output/'result.json')
            return result
        except (ValueError,OSError,cv2.error) as exc:
            if manifest:
                manifest.update(status='failed', error='timeout' if str(exc)=='CKEY_TIMEOUT' else 'provider_or_input_error')
                pending = output/'request.tmp'
                pending.write_text(json.dumps(manifest),encoding='utf-8')
                pending.replace(output/'request.json')
            message = ('API báo cáo quá thời gian chờ. Báo cáo local vẫn sẵn sàng.'
                       if str(exc) == 'CKEY_TIMEOUT' else
                       'API báo cáo lỗi hoặc trả dữ liệu sai schema. Không có bản nháp mới.')
            raise HTTPException(502,message if kind == 'report' else
                                'CKEY_RUN_FAILED: kiểm tra provider hoặc thử lại với batch nhỏ hơn') from None
        finally:guard.release()
