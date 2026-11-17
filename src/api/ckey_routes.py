"""Explicit paid experiments attached to an immutable source job."""
import json
import uuid
from pathlib import Path
from fastapi import Body, HTTPException
from src.inference.ckey import Client, settings, preview
from tools.video_review_queue import sha


def install(router, get_job, runs_root, guard):
    @router.get('/ckey/models')
    def models():
        cfg=settings()
        return {**cfg,'capability_status':'operator_verified' if cfg['contract_verified'] else 'unverified',
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
        return preview(len(job['result']['frames']))

    @router.post('/{job_id}/ckey/{kind}',status_code=201)
    def run(job_id: str,kind: str,body: dict=Body(...)):
        if kind not in {'vision','report'}:raise HTTPException(404,'Unknown CKEY operation')
        if body.get('confirm_paid') is not True:raise HTTPException(409,'Cần thao tác xác nhận chạy API trả phí')
        job,folder=source(job_id)
        cfg=settings()
        if not cfg['vision_contract_verified' if kind=='vision' else 'report_contract_verified']:
            raise HTTPException(409,'CKEY_CONTRACT_UNVERIFIED: model của tác vụ này chưa được xác minh')
        if not guard.acquire(blocking=False):raise HTTPException(409,'Một yêu cầu CKEY đang chạy')
        try:
            client=Client();run_id=uuid.uuid4().hex;output=folder/'ckey_runs'/run_id;output.mkdir(parents=True)
            manifest={'run_id':run_id,'job_id':job_id,'source_analysis_sha256':sha(folder/'analysis.json'),'kind':kind,'status':'running','provider':'CKEY'}
            (output/'request.json').write_text(json.dumps(manifest),encoding='utf-8')
            if kind=='vision':
                mode=body.get('mode','FT95 + Vision')
                if mode not in {'Vision','FT95 + Vision'}:raise ValueError('CKEY_MODE_INVALID')
                rows=[]
                for frame in job['result']['frames']:
                    path=(folder/(frame.get('original') or frame['image'])).resolve()
                    if not path.is_relative_to(folder.resolve()):raise ValueError('INVALID_IMAGE_PATH')
                    rows.append({'image_id':f"{job_id}:{frame['frame']}",'frame_id':str(frame['frame']),
                        'timestamp':frame['timestamp_s'],'image_sha256':sha(path),'image_bytes':path.read_bytes(),
                        'ft95_detections':[d for d in job['result']['detections'] if d['frame']==frame['frame']] if mode=='FT95 + Vision' else []})
                result=client.vision(rows)
                result['source_images']=[{k:v for k,v in row.items() if k!='image_bytes'} for row in rows]
                result['mode']=mode
            else:
                from src.api.video_review import prepare_review
                from tools.video_review_queue import ReviewStore,report_snapshot
                service=ReviewStore(prepare_review(job,folder),folder/'review',context={'job_id':job_id})
                state=service.state()['state'];snapshot=report_snapshot(service.source,state,0,body.get('reviewer','CKEY draft request'))
                facts={'executive_summary':snapshot['overview'],'inspection_scope':snapshot['video'],
                    'physical_defect_summary':snapshot['cracks'],'review_status':{'status':'draft','review_revision':state['revision']},
                    'coverage_and_limitations':{'coverage':snapshot['technical_appendix']['coverage'],'limitations':snapshot['observation_limits'],'unverified_frames':snapshot['overview']['unverified_frames']},
                    'recommended_followup':[],'technical_appendix':snapshot['technical_appendix'],'allowed_followups':['Kiểm tra bổ sung các vùng chưa xác minh']}
                result={'report':client.report(facts),'model':client.config['report_model'],'provider':'CKEY','usage':client.usage,'status':'draft','review_revision':state['revision']}
            result.update(run_id=run_id,job_id=job_id,source_analysis_sha256=manifest['source_analysis_sha256'])
            (output/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            return result
        except (ValueError,OSError):raise HTTPException(502,'CKEY_RUN_FAILED: output/schema/provider unavailable; no GT changed') from None
        finally:guard.release()
