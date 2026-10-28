#!/usr/bin/env python3
"""One entry point: setup, run all adapters against model lists, consolidate."""
import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from security_suite.common import ROOT, TOOLS, read_json, write_json, jsonl, slug, chat, text_content
from security_suite.relay import Relay
from security_suite.setup_tools import setup, python_for
from security_suite.report import consolidate

def positive(value):
    n=int(value)
    if n<=0:raise argparse.ArgumentTypeError('must be positive')
    return n

def nonnegative(value):
    n=int(value)
    if n<0:raise argparse.ArgumentTypeError('must be >=0')
    return n

def endpoint(base,path):
    url=base.rstrip('/')+'/'+path.lstrip('/')
    validate_url(url);return url

def validate_url(url):
    u=urlparse(url)
    if u.scheme not in ('http','https') or not u.netloc or u.username or u.password or u.query or u.fragment:
        raise ValueError('Use an http(s) URL without embedded credentials, query or fragment')

def terminate(p):
    if os.name=='posix':
        try:os.killpg(p.pid,signal.SIGTERM)
        except ProcessLookupError:return
    else:p.terminate()
    try:p.wait(timeout=3)
    except subprocess.TimeoutExpired:
        if os.name=='posix':os.killpg(p.pid,signal.SIGKILL)
        else:p.kill()
        p.wait()

def run(args):
    models=list(dict.fromkeys(m.strip() for group in args.models for m in group.split(',') if m.strip()))
    if not models:raise ValueError('At least one model is required')
    tools=list(dict.fromkeys(args.tools))
    if args.install:setup(tools)
    cfg=vars(args).copy()
    cfg['endpoint']=args.endpoint or endpoint(args.base_url,args.chat_path)
    validate_url(cfg['endpoint'])
    cfg['judge_endpoint']=args.judge_endpoint or (endpoint(args.judge_base_url,args.chat_path) if args.judge_base_url else cfg['endpoint'])
    validate_url(cfg['judge_endpoint'])
    cfg['key']=os.getenv(args.api_key_env,'')
    cfg['judge_key']=os.getenv(args.judge_key_env,'') if args.judge_key_env else cfg['key']
    cfg['temperature']=None if args.temperature=='omit' else float(args.temperature)
    if cfg['temperature'] is not None and not 0<=cfg['temperature']<=2:raise ValueError('Temperature must be 0..2 or omit')
    for field in ('extra_body','judge_extra_body','headers','judge_headers'):
        cfg[field]=read_json(getattr(args,field)) if getattr(args,field) else {}
        if not isinstance(cfg[field],dict):raise ValueError(field+' must be a JSON object')
    for field in ('extra_body','judge_extra_body'):
        if set(cfg[field])&{'model','messages','stream'}:raise ValueError(field+' cannot override model/messages/stream')
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    dest=Path(args.out).resolve()/run_id;dest.mkdir(parents=True,exist_ok=False)
    safe={k:v for k,v in cfg.items() if k not in ('key','judge_key','headers','judge_headers')}
    safe['header_names']=list(cfg['headers']);safe['judge_header_names']=list(cfg['judge_headers'])
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'datasets').rglob('*') if p.is_file()}
    manifest={'run_id':run_id,'models':models,'tools':tools,'config':safe,'model_dirs':{m:slug(m) for m in models},'dataset_sha256':hashes,'sources':read_json(ROOT/'sources.lock.json')}
    write_json(dest/'manifest.json',manifest)
    interrupted=False
    try:
        for model in models:
            for tool in tools:
                out=dest/slug(model)/tool;out.mkdir(parents=True)
                status={'status':'ERROR','error':None}
                print(f'[{model}] {tool}: starting',flush=True)
                with Relay(cfg,model,out) as relay:
                    job={k:cfg[k] for k in ('timeout','max_tokens','seed','limit','variants','garak_probes','bipia_tasks','bipia_attacks','agent_suites','agent_tasks','agent_injections','agent_steps','agent_attack','judge_model')}
                    job.update({'model':model,'tool':tool,'out':str(out),'target_base':relay.base('target'),'judge_base':relay.base('judge')})
                    write_json(out/'job.json',job)
                    env=os.environ.copy();env.update({'SUITE_RELAY_KEY':relay.key,'PYTHONPATH':str(ROOT),
                      'PROMPTFOO_DISABLE_TELEMETRY':'1','PROMPTFOO_DISABLE_REDTEAM_REMOTE_GENERATION':'true',
                      'NO_PROXY':'localhost,127.0.0.1','no_proxy':'localhost,127.0.0.1','TOKENIZERS_PARALLELISM':'false'})
                    for proxy_key in ('http_proxy','https_proxy','all_proxy','HTTP_PROXY','HTTPS_PROXY','ALL_PROXY'):
                        env.pop(proxy_key,None)
                    p=None
                    try:
                        if not Path(python_for(tool)).exists():raise RuntimeError('Dependencies not installed; run setup or add --install')
                        with (out/'worker.log').open('w') as log:
                            p=subprocess.Popen([python_for(tool),'-m','security_suite.worker',str(out/'job.json')],cwd=ROOT,
                              env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=(os.name=='posix'))
                            started=time.monotonic();last=started
                            while p.poll() is None:
                                now=time.monotonic()
                                if now-started>args.tool_timeout:
                                    terminate(p);raise TimeoutError('Tool wall-time budget exhausted')
                                if now-last>15:
                                    print(f'[{model}] {tool}: {int(now-started)}s, requests={relay.counts}',flush=True);last=now
                                time.sleep(.25)
                        ws=read_json(out/'worker_status.json') if (out/'worker_status.json').exists() else {'complete':False,'error':'Worker stopped without status; see worker.log'}
                        rows=jsonl(out/'records.jsonl') if (out/'records.jsonl').exists() else []
                        complete=ws['complete'] and not relay.errors and rows and all(r['status'] in ('PASS','FAIL') for r in rows)
                        status={'status':'COMPLETE' if complete else 'PARTIAL' if rows else 'ERROR','error':ws.get('error'),'exit_code':p.returncode}
                    except KeyboardInterrupt:
                        if p is not None and p.poll() is None:terminate(p)
                        status={'status':'PARTIAL','error':'Interrupted by user'};interrupted=True
                    except Exception as e:
                        if p is not None and p.poll() is None:terminate(p)
                        status={'status':'ERROR','error':str(e)}
                    status.update({'requests':relay.counts,'transport_errors':relay.errors[:20]})
                    write_json(out/'status.json',status)
                consolidate(dest)
                print(f'[{model}] {tool}: {status["status"]}',flush=True)
                if interrupted:raise KeyboardInterrupt
    except KeyboardInterrupt:
        interrupted=True
    summary=consolidate(dest)
    print('REPORT:',dest/'report.html');print('MARKDOWN:',dest/'report.md')
    if interrupted:return 130
    if any(v['conclusion'].endswith('INCOMPLETE') for v in summary['models'].values()):return 2
    if args.fail_on_findings and any(v['conclusion']=='FINDINGS' for v in summary['models'].values()):return 1
    return 0

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    s=sub.add_parser('setup');s.add_argument('--tools',nargs='+',choices=TOOLS,default=list(TOOLS))
    m=sub.add_parser('merge');m.add_argument('run_dir')
    r=sub.add_parser('run');r.add_argument('--models',nargs='+',required=True)
    group=r.add_mutually_exclusive_group(required=True);group.add_argument('--base-url');group.add_argument('--endpoint')
    r.add_argument('--chat-path',default='/chat/completions')
    r.add_argument('--api-key-env',default='TARGET_API_KEY');r.add_argument('--judge-key-env')
    r.add_argument('--judge-model',required=True);jg=r.add_mutually_exclusive_group();jg.add_argument('--judge-base-url');jg.add_argument('--judge-endpoint')
    r.add_argument('--tools',nargs='+',choices=TOOLS,default=list(TOOLS));r.add_argument('--install',action='store_true')
    r.add_argument('--limit',type=nonnegative,default=10,help='per dataset/subset; 0=all; garak uses its own probe selection')
    r.add_argument('--seed',type=int,default=42);r.add_argument('--variants',nargs='+',choices=['direct','roleplay','authority'],default=['direct','roleplay','authority'])
    r.add_argument('--timeout',type=positive,default=120);r.add_argument('--tool-timeout',type=positive,default=3600)
    r.add_argument('--max-requests',type=positive,default=1000,help='per model/tool/route, including native retries')
    r.add_argument('--max-tokens',type=positive,default=2048);r.add_argument('--judge-max-tokens',type=positive,default=4096)
    r.add_argument('--token-parameter',choices=['max_tokens','max_completion_tokens'],default='max_tokens')
    r.add_argument('--temperature',default='0');r.add_argument('--developer-as-system',action='store_true')
    r.add_argument('--drop-params',nargs='*',default=[])
    r.add_argument('--ca-file');r.add_argument(
        "--insecure-skip-tls-verify",
        action="store_true",
        help="Disable TLS certificate verification for target and judge endpoints",
    )
    r.add_argument('--extra-body');r.add_argument('--judge-extra-body');r.add_argument('--headers');r.add_argument('--judge-headers')
    r.add_argument('--garak-probes',default='probes.promptinject.HijackHateHumans,probes.dan.Dan_11_0,probes.encoding.InjectBase64')
    r.add_argument('--bipia-tasks',nargs='+',choices=['email','table'],default=['email','table']);r.add_argument('--bipia-attacks',type=nonnegative,default=4)
    r.add_argument('--agent-suites',nargs='+',choices=['workspace','banking','travel','slack'],default=['workspace'])
    r.add_argument('--agent-tasks',type=nonnegative,default=2);r.add_argument('--agent-injections',type=nonnegative,default=2)
    r.add_argument('--agent-steps',type=positive,default=20);r.add_argument('--agent-attack',choices=['important_instructions','tool_knowledge'],default='important_instructions')
    r.add_argument('--out',default='reports');r.add_argument('--fail-on-findings',action='store_true')
    args=p.parse_args()
    try:
        if args.command=='setup':return 2 if setup(args.tools) else 0
        if args.command=='merge':consolidate(args.run_dir);return 0
        return run(args)
    except (ValueError,OSError) as e:
        print('ERROR:',e,file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())
