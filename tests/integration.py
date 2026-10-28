"""Real adapters against a local fixture API. No security conclusions about real models."""
import argparse
import json
import subprocess
import sys
import threading
from pathlib import Path
from http.server import ThreadingHTTPServer
from mock_server import Handler
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--tools',nargs='+',default=['garak','promptfoo','pyrit','harmbench','jailbreakbench','bipia','agentdojo', 'security-regression',]);p.add_argument('--models',nargs='+',default=['safe','leaky']);p.add_argument('--out',default='test-runs');p.add_argument('--limit',default='2');p.add_argument('--garak-probes',default='probes.dan.Dan_11_0');a=p.parse_args()
server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
cmd=[sys.executable,str(ROOT/'run.py'),'run','--endpoint',f'http://127.0.0.1:{server.server_port}/v1/chat/completions','--models',*a.models,'--judge-model','judge','--tools',*a.tools,'--limit',a.limit,'--bipia-attacks','1','--agent-tasks','1','--agent-injections','1','--garak-probes',a.garak_probes,'--tool-timeout','180','--timeout','10','--out',a.out]
try:
 code=subprocess.call(cmd,cwd=ROOT)
 run_dir=sorted((ROOT/a.out).iterdir())[-1]
 data=json.loads((run_dir/'summary.json').read_text())
 errors=[]
 for model,result in data['models'].items():
  for tool in result['tools']:
   if tool['status']!='COMPLETE':errors.append((model,tool['tool'],tool))
 if 'promptfoo' in a.tools and 'leaky' in a.models:
  pf=next(t for t in data['models']['leaky']['tools'] if t['tool']=='promptfoo')
  if not pf['counts']['FAIL']:errors.append(('leaky','promptfoo','Expected marker/canary failures'))
 if errors:
  print(json.dumps(errors,indent=2));raise SystemExit(1)
 print('INTEGRATION PASSED: all requested real adapters completed against fixture. No real-model assessment.')
finally:server.shutdown();server.server_close()
