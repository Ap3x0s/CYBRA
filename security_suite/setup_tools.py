import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from .common import ROOT, read_json, write_json

def python_for(tool):
    # Инструменты без собственного окружения работают в основном venv.
    # BIPIA здесь не случайно: это vendored-библиотека (vendor/bipia) плюс
    # четыре пакета, поставленных в основной venv. Отдельного .tools/bipia
    # не существует, поэтому прежняя проверка его наличия в run.py давала
    # «Dependencies not installed» ещё до запуска адаптера.
    if tool in (
        'promptfoo',
        'harmbench',
        'jailbreakbench',
        'security-regression',
        'bipia',
    ):
        return sys.executable

    env = ROOT / '.tools' / tool
    return str(
        env / (
            'Scripts/python.exe'
            if os.name == 'nt'
            else 'bin/python'
        )
    )

def setup(tools):
    uv = shutil.which('uv')
    lock = read_json(ROOT / 'sources.lock.json')

    specs = {
        'garak': [
            'git+https://github.com/NVIDIA/garak.git@'
            + lock['garak']['revision']
        ],
        'pyrit': [
            'git+https://github.com/microsoft/PyRIT.git@'
            + lock['pyrit']['revision']
        ],
        'agentdojo': [
            'git+https://github.com/ethz-spylab/agentdojo.git@'
            + lock['agentdojo']['revision']
        ],
        'bipia': [
            'pandas>=2.2,<4',
            'jsonlines>=4,<5',
            'nltk>=3.9,<4',
            'transformers>=4.34,<5',
        ],
    }

    if any(tool in specs for tool in tools) and not uv:
        raise RuntimeError(
            'Install uv first: python -m pip install uv'
        )
    errors={}
    # Офлайн-режим: на серверах заказчика нет интернета. Если задан
    # CYBRA_OFFLINE_DIR, пакеты берутся из привезённого каталога, а не из
    # сети. Без этой ветки `uv pip install` бесконечно ждёт PyPI и падает
    # по таймауту — сообщение при этом невнятное («connection reset»).
    offline = os.environ.get('CYBRA_OFFLINE_DIR')
    offline_path = Path(offline) if offline else None
    if offline_path and not offline_path.exists():
        raise RuntimeError(f'CYBRA_OFFLINE_DIR указан, но каталога нет: {offline_path}')
    for tool in tools:
        try:
            if tool=='promptfoo':
                npm=shutil.which('npm')
                if not npm:raise RuntimeError('Node.js 22+ and npm are required')
                dest=ROOT/'.tools/promptfoo';dest.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(ROOT/'package.json',dest/'package.json')
                if (ROOT/'package-lock.json').exists():shutil.copyfile(ROOT/'package-lock.json',dest/'package-lock.json')
                npm_args=[npm,'ci' if (dest/'package-lock.json').exists() else 'install','--no-audit','--no-fund']
                if offline_path:
                    # --offline запрещает обращения к registry: если пакета
                    # нет в кеше, установка падает честно, а не висит.
                    npm_args += ['--offline', f'--cache={offline_path / "npm"}']
                subprocess.run(npm_args,cwd=dest,check=True)
            elif tool in specs:
                dest=ROOT/'.tools'/tool
                if not Path(python_for(tool)).exists():subprocess.run([uv,'venv','--python','3.12',str(dest)],check=True)
                frozen=ROOT/'locks'/f'{tool}.txt'
                args=['-r',str(frozen)] if frozen.exists() else specs[tool]
                install_args=[uv,'pip','install','--python',python_for(tool)]
                if offline_path:
                    # --no-index: не смотреть в PyPI вообще. --find-links:
                    # брать только из привезённых колёс.
                    install_args += ['--no-index', f'--find-links={offline_path / "wheels"}']
                else:
                    install_args += ['--torch-backend','cpu']
                subprocess.run([*install_args,*args],check=True)
                out=subprocess.check_output([uv,'pip','freeze','--python',python_for(tool)],text=True)
                (dest/'installed.txt').write_text(out)
            print('READY:',tool,flush=True)
        except Exception as e:
            errors[tool]=str(e);print('SETUP ERROR:',tool,e,file=sys.stderr,flush=True)
    write_json(ROOT/'.tools/setup_status.json',errors)
    return errors
