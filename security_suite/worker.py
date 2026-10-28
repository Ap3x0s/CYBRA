import sys
import traceback
from pathlib import Path
from .common import read_json, write_json, jsonl

def main():
    job=read_json(sys.argv[1])
    try:
        if job['tool'] == 'security-regression':
            from .security_regression import run
            run(job)

        elif job['tool'] in ('garak', 'promptfoo', 'pyrit', 'agentdojo'):
            from . import native
            getattr(native, job['tool'])(job)

        else:
            from . import adapted
            runner = (
                adapted.bipia
                if job['tool'] == 'bipia'
                else adapted.text_benchmark
            )
            runner(job)
        path=Path(job['out'])/'records.jsonl'
        if not path.exists() or not jsonl(path):raise RuntimeError('Adapter produced zero records')
        write_json(Path(job['out'])/'worker_status.json',{'complete':True})
    except Exception as e:
        traceback.print_exc()
        write_json(Path(job['out'])/'worker_status.json',{'complete':False,'error':str(e)})
        raise SystemExit(2)
if __name__=='__main__':main()
