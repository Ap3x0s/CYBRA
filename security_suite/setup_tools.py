import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from .common import ROOT, read_json, write_json

def _local_source_archives(offline: Path) -> dict:
    """Найти в bundle архивы инструментов, которые обычно ставятся с git.

    Сборщик bundle (scripts/build_offline_bundle.py) кладёт их в
    <bundle>/sources как <tool>-<revision[:12]>.tar.gz. Здесь строим карту
    «имя инструмента -> путь к архиву», чтобы подменить git-ссылку в
    lock-файле на локальный файл.

    Возвращает пустой словарь, если каталога нет: вызывающая сторона должна
    предупредить, а не молча уйти в сеть.
    """
    sources = offline / 'sources'
    if not sources.is_dir():
        return {}
    found = {}
    for archive in sorted(sources.glob('*.tar.gz')):
        # Имя файла: <tool>-<sha12>.tar.gz. Инструмент может содержать дефис
        # (security-regression), поэтому отрезаем по последнему дефису.
        stem = archive.name[:-len('.tar.gz')]
        tool = stem.rsplit('-', 1)[0]
        # Оставляем первый найденный: в bundle он один на инструмент.
        found.setdefault(tool, archive)
    return found


def _rewrite_git_args(args: list, frozen: Path, local_sources: dict) -> list:
    """Подменить в аргументах установки git-ссылки на локальные архивы.

    `args` — либо ['-r', '<lock>'], либо список спецификаций для инструментов
    без lock. В lock-файле git-ссылка выглядит строкой (см. locks/garak.txt):

        garak @ git+https://github.com/NVIDIA/garak.git@<sha>

    Готовим ВРЕМЕННЫЙ lock-файл, где такие строки заменены на полные пути к
    архивам из bundle. Проверено: без этой подмены установка уходит в сеть
    на этапе клонирования, хотя архив уже лежит рядом.

    Если архива нет — оставляем строку как есть. Тогда установка честно
    упадёт на сетевой ошибке, и это правильнее, чем молча пропустить
    инструмент: частичная установка выглядит успешной, но не работает.
    """
    if not frozen.exists():
        return args

    lines = []
    changed = 0
    for line in frozen.read_text(encoding='utf-8').splitlines():
        stripped = line.strip()
        if 'git+' in stripped and ' @ ' in stripped:
            name = stripped.split(' @ ', 1)[0].strip()
            archive = local_sources.get(name)
            if archive is not None:
                lines.append(str(archive))
                changed += 1
                continue
            print(f'  {name}: архива нет в bundle, установка потребует сети',
                  file=sys.stderr, flush=True)
        lines.append(line)

    if not changed:
        return args

    # Временный файл рядом с исходным lock: путь относительный, чтобы
    # подстановка не зависела от текущего каталога.
    tmp = frozen.with_name(frozen.stem + '.offline.txt')
    tmp.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    result = [str(tmp) if item == str(frozen) else item for item in args]
    print(f'  git-ссылок заменено на локальные архивы: {changed}', flush=True)
    return result


def _remove_then_retry(path: Path, attempts: int = 5) -> None:
    """Убрать каталог прошлой попытки, не падая на занятых файлах.

    На Windows каталог виртуального окружения часто нельзя удалить: .pyd и
    .dll держит антивирус (Defender сканирует каждую новую библиотеку),
    индексатор поиска или только что завершившийся процесс pip. Ошибка —
    os error 5 «Отказано в доступе»; повтор обычно не помогает, потому что
    файл занят на секунды или минуты.

    Поэтому два шага:

    1. Обычное удаление с несколькими попытками — покрывает случай, когда
       файл освобождается быстро.
    2. Если не вышло — ПЕРЕИМЕНОВАНИЕ каталога в сторону. Переименование
       проходит, даже когда отдельные файлы внутри заняты: меняется только
       запись в родительском каталоге. Дальше venv создаётся с нуля, а
       старое содержимое удалится само, когда его отпустят.

    Так `cybra setup` не блокируется из-за антивируса, и повторный запуск
    после прерванной установки работает. Без этого он падал намертво:
    uv отказывается работать с существующим каталогом, а удалить не выходит.
    """
    for attempt in range(attempts):
        try:
            shutil.rmtree(path)
            return
        except FileNotFoundError:
            return
        except OSError:
            time.sleep(0.2 * (attempt + 1))

    if not path.exists():
        return

    stale = path.with_name(f'{path.name}.stale-{int(time.time())}')
    try:
        path.rename(stale)
    except OSError as error:
        raise RuntimeError(
            f'не удалось ни удалить, ни отложить {path} '
            f'(файлы заняты антивирусом?): {error}') from error

    print(f'  старое окружение отложено: {stale.name}', flush=True)
    shutil.rmtree(stale, ignore_errors=True)


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

# Инструменты, которые умеет ставить `cybra setup`. Список нужен, чтобы
# CLI мог отличить опечатку («garakk») от имени и вернуть понятную ошибку,
# а не отрапортовать успех, ничего не поставив.
KNOWN_TOOLS = frozenset(
    {'garak', 'pyrit', 'agentdojo', 'promptfoo', 'bipia'}
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

    # Сообщаем режим до начала работы: это первое, что должен увидеть
    # администратор. Иначе в офлайне он ждёт сетевых таймаутов и получает
    # «connection reset» без подсказки, что нужен bundle.
    if offline_path:
        wheels = len(list((offline_path / 'wheels').glob('*.whl'))) \
            if (offline_path / 'wheels').is_dir() else 0
        archives = len(list((offline_path / 'sources').glob('*.tar.gz'))) \
            if (offline_path / 'sources').is_dir() else 0
        npm_cache = (offline_path / 'npm' / '_cacache').is_dir()
        print(f'Режим: офлайн', flush=True)
        print(f'  bundle : {offline_path}', flush=True)
        print(f'  колёс  : {wheels}', flush=True)
        print(f'  архивов: {archives}', flush=True)
        print(f'  npm    : {"есть" if npm_cache else "нет"}', flush=True)
        print('  сеть не используется', flush=True)
    else:
        print('Режим: онлайн (PyPI + npm)', flush=True)
        print('Для установки без интернета задайте CYBRA_OFFLINE_DIR',
              flush=True)
    print(flush=True)


    # Git-ссылки в офлайне надо подменить на локальные архивы из bundle.
    #
    # Зачем это отдельный шаг: lock-файл содержит строку вида
    #   garak @ git+https://github.com/NVIDIA/garak.git@<sha>
    # Это НЕ колесо: pip при установке пойдёт клонировать репозиторий, то
    # есть в сеть. --no-index на git-ссылки не действует — он ограничивает
    # только поиск пакетов на индексе. На сервере без интернета установка
    # падала бы именно здесь, хотя архив garak-<sha>.tar.gz уже лежит в
    # bundle/sources.
    local_sources = _local_source_archives(offline_path) if offline_path else {}
    if offline_path and not local_sources:
        print(
            'ВНИМАНИЕ: в bundle нет каталога sources — инструменты из git '
            '(garak, pyrit, agentdojo) не установятся без сети',
            file=sys.stderr, flush=True)
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
                venv_python=Path(python_for(tool))
                # Проверяем ИМЕННО интерпретатор, а не каталог. Каталог
                # может остаться от прерванной установки: uv создал его, но
                # venv не достроил. Тогда `uv venv` падает с «A directory
                # already exists» — проверка по каталогу это пропускала.
                if not venv_python.exists():
                    # Окружение создаём через uv, но сначала убираем остатки
                    # прошлой попытки.
                    #
                    # Почему не `uv venv --clear --force`: на Windows он
                    # падает с «Отказано в доступе» при удалении, если файлы
                    # заняты — антивирусом, индексатором или самим процессом.
                    # uv сдаётся сразу, а удаление с повторами обычно
                    # проходит: файл освобождается через доли секунды.
                    if dest.exists():
                        _remove_then_retry(dest)
                    subprocess.run([uv,'venv','--python','3.12',str(dest)],check=True)
                frozen=ROOT/'locks'/f'{tool}.txt'
                args=['-r',str(frozen)] if frozen.exists() else specs[tool]
                if offline_path:
                    # Подменяем git-строки на локальные архивы. Без этого
                    # pip пойдёт клонировать репозиторий: --no-index
                    # ограничивает только поиск на индексе, а git-ссылка
                    # обрабатывается отдельным механизмом и требует сети.
                    args=_rewrite_git_args(args, frozen, local_sources)
                install_args=[uv,'pip','install','--python',python_for(tool)]
                if offline_path:
                    # --no-index: не смотреть в PyPI вообще. --find-links:
                    # брать только из привезённых колёс.
                    install_args += ['--no-index', f'--find-links={offline_path / "wheels"}']
                else:
                    install_args += ['--torch-backend','cpu']
                try:
                    subprocess.run([*install_args,*args],check=True)
                finally:
                    # Временный lock с путями к архивам больше не нужен.
                    # Убираем и при успехе, и при ошибке: файл содержит
                    # абсолютные пути конкретной машины.
                    for item in args:
                        candidate = Path(str(item))
                        if (candidate.suffix == '.txt'
                                and candidate.stem.endswith('.offline')):
                            candidate.unlink(missing_ok=True)
                out=subprocess.check_output([uv,'pip','freeze','--python',python_for(tool)],text=True)
                (dest/'installed.txt').write_text(out)
            print('READY:',tool,flush=True)
        except Exception as e:
            errors[tool]=str(e);print('SETUP ERROR:',tool,e,file=sys.stderr,flush=True)
    write_json(ROOT/'.tools/setup_status.json',errors)
    return errors
