import copy
import json
import unittest
from unittest.mock import patch
from src.inference.ckey import settings, VERIFIED_VISION, parse_json
from types import SimpleNamespace as NS
from src.inference.ckey import Client, validate_vision, preview

CONFIG={'vision_model':'gemini-3.8-flash','report_model':'dungcsnd113/qwen3.8-omni-flash','max_images':2,'max_tokens':1024,'contract_verified':False,'minimum_interval_s':0}
def response(value):return NS(choices=[NS(message=NS(content=json.dumps(value)),finish_reason='stop')],usage=NS(prompt_tokens=10,completion_tokens=20))
def row(i):return {'image_id':str(i),'frame_id':str(i),'image_bytes':b'fixture'}
def output(i):return {'image_id':str(i),'frame_id':str(i),'status':'uncertain','detections':[{'class':'pothole','bbox_xyxy_norm':None,'confidence':None,'evidence':'cần kiểm tra','needs_review':True}],'ft95_disagreements':['possible false positive'],'limitations':[]}
class CKEYTests(unittest.TestCase):
 def test_provider_json_fence(self):
  self.assertEqual(parse_json('```json\n{"images": []}\n```'),{'images':[]})
  with self.assertRaises(ValueError):parse_json('Explanation\n```json\n{}\n```')
 def test_verified_vision_does_not_enable_report(self):
  with patch.dict('os.environ',{'KDV_API_KEY':'fixture','KDV_BASE_URL':'https://api.xah.io/v1','VISION_MODEL':VERIFIED_VISION,'CKEY_REPORT_CONTRACT_VERIFIED':'0'}):
   cfg=settings();self.assertTrue(cfg['vision_contract_verified']);self.assertFalse(cfg['report_contract_verified'])
 def test_batch_mapping_and_proposals(self):
  calls=[]
  def transport(**kw):
   calls.append(kw);meta=[json.loads(x['text']) for x in kw['messages'][1]['content'] if x['type']=='text'];return response({'images':[output(x['image_id']) for x in meta]})
  result=Client(transport,CONFIG,sleep=lambda _:None).vision([row(i) for i in range(5)])
  self.assertEqual(len(calls),3);self.assertEqual(len(result['images']),5);self.assertEqual(result['review_status'],'ai_proposal')
  self.assertEqual(calls[0]['messages'][1]['content'][1]['type'],'image_url')
 def test_invalid_class_mapping_confidence(self):
  for key,value in [('class','unknown'),('confidence',.9),('needs_review',False),('review_status','approved')]:
   r=output(1);r['detections'][0][key]=value
   with self.assertRaises(ValueError):validate_vision({'images':[r]},[row(1)])
  with self.assertRaises(ValueError):validate_vision({'images':[output(2)]},[row(1)])
 def test_timeout_retry_bounded(self):
  calls=[]
  def fail(**kw):calls.append(kw);raise TimeoutError()
  with self.assertRaises(ValueError):Client(fail,CONFIG,sleep=lambda _:None).vision([row(1)])
  self.assertEqual(len(calls),3)
 def test_probe_timeout_without_retries(self):
  calls=[]
  def fail(**kw):
   calls.append(kw)
   raise TimeoutError('provider details must stay private')
  config={**CONFIG,'retries':0}
  with self.assertRaisesRegex(ValueError,'^CKEY_TIMEOUT$'):
   Client(fail,config,sleep=lambda _:None).vision([row(1)])
  self.assertEqual(len(calls),1)
  self.assertEqual(preview(5,config)['max_requests_with_retries'],3)
 def test_invalid_json_retry(self):
  bad=NS(choices=[NS(message=NS(content='not JSON'),finish_reason='stop')],usage=None)
  with self.assertRaises(ValueError):Client(lambda **kw:bad,CONFIG,sleep=lambda _:None).vision([row(1)])
 def test_split_on_provider_limit(self):
  def transport(**kw):
   meta=[json.loads(x['text']) for x in kw['messages'][1]['content'] if x['type']=='text']
   if len(meta)>1:
    e=RuntimeError('too many images');e.status_code=413;raise e
   return response({'images':[output(meta[0]['image_id'])]})
  self.assertEqual(len(Client(transport,CONFIG,sleep=lambda _:None).vision([row(1),row(2)])['images']),2)
 def test_report_cannot_invent_metrics(self):
  facts={k:{} for k in ['executive_summary','inspection_scope','physical_defect_summary','review_status','coverage_and_limitations','technical_appendix']};facts.update(recommended_followup=[],allowed_followups=[])
  valid={k:v for k,v in facts.items() if k!='allowed_followups'}
  self.assertEqual(Client(lambda **kw:response(valid),CONFIG,sleep=lambda _:None).report(facts),valid)
  invalid=copy.deepcopy(valid);invalid['executive_summary']={'recall':1.0}
  with self.assertRaises(ValueError):Client(lambda **kw:response(invalid),CONFIG,sleep=lambda _:None).report(facts)
 def test_contract_gate_and_cost_unknown(self):
  with self.assertRaisesRegex(ValueError,'UNVERIFIED'):Client(config=CONFIG)
  self.assertIsNone(preview(50,CONFIG)['estimated_cost'])
if __name__=='__main__':unittest.main()
