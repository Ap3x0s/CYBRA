import json,os,sys,tempfile,threading,unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from security_suite.common import grade,jsonl,slug,write_json,chat,TransportError
from security_suite.relay import Relay
from security_suite.report import consolidate
from mock_server import Handler

class RelayTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.out=Path(self.temp.name)
  self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
  threading.Thread(target=self.server.serve_forever,daemon=True).start()
  self.cfg={'endpoint':f'http://127.0.0.1:{self.server.server_port}/api/chat/completions','judge_endpoint':f'http://127.0.0.1:{self.server.server_port}/v1/chat/completions','key':'secret-target-key','judge_key':'secret-judge-key','judge_model':'judge','max_requests':3,'max_tokens':40,'judge_max_tokens':80,'token_parameter':'max_tokens','temperature':0,'timeout':2}
 def tearDown(self):self.server.shutdown();self.server.server_close();self.temp.cleanup()
 def test_empty_is_error(self):
  with Relay(self.cfg,'empty',self.out) as r:
   status,body=r.forward('target',{'messages':[]});self.assertEqual(status,502);self.assertIn('EMPTY_OUTPUT',body['error']['message']);self.assertTrue(r.errors)
 def test_truncation_is_error(self):
  with Relay(self.cfg,'truncated',self.out) as r:
   status,body=r.forward('target',{'messages':[]});self.assertEqual(status,502);self.assertIn('TRUNCATED',body['error']['message'])
 def test_alias_and_request_budget(self):
  with Relay(self.cfg,'safe',self.out) as r:
   for _ in range(3):self.assertEqual(r.forward('target',{'messages':[]})[0],200)
   self.assertEqual(r.forward('target',{'messages':[]})[0],402)
   self.assertEqual(r.forward('judge',{'messages':[]})[0],200)
  rows=jsonl(self.out/'http.jsonl');self.assertEqual(rows[0]['request']['model'],'safe');self.assertEqual(rows[-1]['request']['model'],'judge');self.assertNotIn('secret-target-key',(self.out/'http.jsonl').read_text())
 def test_actual_url_and_local_auth(self):
  with Relay(self.cfg,'safe',self.out) as r:
   job={'target_base':r.base('target'),'model':'safe','judge_model':'judge','timeout':2}
   with patch.dict(os.environ,{'SUITE_RELAY_KEY':'wrong'}):
    with self.assertRaises(TransportError):chat(job,[])
   with patch.dict(os.environ,{'SUITE_RELAY_KEY':r.key}):self.assertEqual(chat(job,[])['model'],'safe')
 def test_invalid_judge_json_not_pass(self):
  with patch('security_suite.common.chat',return_value={'choices':[{'message':{'content':'not JSON'}}]}):self.assertEqual(grade({},'p','a')['verdict'],'UNSCORED')
 def test_judge_schema_not_pass(self):
  for raw in ('[]','{"verdict":"PASS"}','{"verdict":"unknown","reason":"r"}'):
   with patch('security_suite.common.chat',return_value={'choices':[{'message':{'content':raw}}]}):self.assertEqual(grade({},'p','a')['verdict'],'UNSCORED')
class ReportTests(unittest.TestCase):
 def test_missing_tool_and_html_escape(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);name='<script>alert(1)</script>';m=slug(name)
   write_json(p/'manifest.json',{'run_id':'fixture','model_dirs':{name:m},'tools':['garak','harmbench']})
   d=p/m/'garak';d.mkdir(parents=True);write_json(d/'status.json',{'status':'COMPLETE'})
   row={'model':name,'tool':'garak','case_id':'1','category':'probe','unit':'detector_judgement','status':'FAIL','passed':8,'failed':2,'total':10}
   (d/'records.jsonl').write_text(json.dumps(row)+'\n');model=consolidate(p)['models'][name]
   self.assertEqual(model['conclusion'],'FINDINGS_AND_INCOMPLETE');self.assertEqual(model['tools'][0]['failed_check_rate'],.2)
   self.assertNotIn('<script>alert(1)</script>',(p/'report.html').read_text());self.assertEqual(model['tools'][1]['status'],'ERROR')
 def test_model_mismatch_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);write_json(p/'manifest.json',{'run_id':'fixture','model_dirs':{'a':'a'},'tools':['pyrit']})
   d=p/'a/pyrit';d.mkdir(parents=True);(d/'records.jsonl').write_text(json.dumps({'model':'b','tool':'pyrit','status':'PASS'})+'\n')
   with self.assertRaises(ValueError):consolidate(p)
 def test_model_path_cannot_escape(self):self.assertNotIn('/',slug('../../secret'));self.assertNotEqual(slug('a/b'),slug('a_b'))
if __name__=='__main__':unittest.main()
