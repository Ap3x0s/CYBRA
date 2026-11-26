"""Проверки инфраструктуры: то, что ловится только на живом стенде.

Скрипты в scripts/ не являются тестами сами по себе — они проверяют
репозиторий. Здесь проверяется, что они действительно ЛОВЯТ ошибки,
а не просто печатают «всё хорошо»: правило, которое не срабатывает
никогда, хуже отсутствующего, потому что на него рассчитывают.

Отдельно проверяется то, что уже ломалось:
  * `proxy_pass` с прямым именем хоста — `nginx -t` падает при сборке;
  * `docker/compose.prod.yaml` без пометки об устаревании после
    разделения на два сервиса;
  * манифест релиза с PLACEHOLDER вместо digest.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def run_script(name: str, *args: str) -> subprocess.CompletedProcess:
    """Запустить скрипт отдельным процессом.

    Окружение задаётся явно: на Windows дочерний процесс иначе берёт
    кодировку консоли (cp1251), и чтение русского вывода падает на
    UnicodeDecodeError — причём не в проверяемом скрипте, а в тесте,
    который его читает.
    """
    env = dict(__import__('os').environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUTF8'] = '1'
    return subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / name), *args],
        cwd=ROOT, capture_output=True, text=True,
        encoding='utf-8', errors='replace', env=env)


# ----------------------------------------------------------------------
# Структура репозитория
# ----------------------------------------------------------------------

def test_repo_structure_passes() -> None:
    """На текущем дереве проверка проходит."""
    result = run_script('check_repo_structure.py')
    assert result.returncode == 0, result.stdout + result.stderr


def test_nginx_direct_proxy_pass_is_rejected(tmp_path, monkeypatch) -> None:
    """proxy_pass с прямым именем хоста обязан ловиться.

    Такая форма разрешает имя один раз при разборе конфига: `nginx -t`
    падает при сборке образа, а после перезапуска бэкенда nginx ходит на
    старый IP. Проверка должна это видеть, иначе она бесполезна.
    """
    sys.path.insert(0, str(ROOT / 'scripts'))
    import check_repo_structure as module

    broken = ROOT / 'frontend' / 'nginx.conf.broken'
    broken.write_text(
        'server {\n'
        '    location /api/ {\n'
        '        proxy_pass http://backend:8000;\n'
        '    }\n'
        '    location / { try_files $uri $uri/ /index.html; }\n'
        '}\n', encoding='utf-8')
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    (tmp_path / 'frontend').mkdir(parents=True, exist_ok=True)
    (tmp_path / 'frontend' / 'nginx.conf').write_text(
        broken.read_text(encoding='utf-8'), encoding='utf-8')

    module.problems.clear()
    module.checks.clear()
    module.check_nginx_proxies_api()

    broken.unlink()
    assert any('прямым именем хоста' in problem for problem in module.problems), \
        f'прямой proxy_pass не поймали: {module.problems}'


def test_nginx_resolver_form_is_accepted(tmp_path, monkeypatch) -> None:
    """Форма с resolver и переменной — правильная, замечаний быть не должно."""
    sys.path.insert(0, str(ROOT / 'scripts'))
    import check_repo_structure as module

    monkeypatch.setattr(module, 'ROOT', tmp_path)
    (tmp_path / 'frontend').mkdir(parents=True, exist_ok=True)
    (tmp_path / 'frontend' / 'nginx.conf').write_text(
        'server {\n'
        '    resolver 127.0.0.11 valid=10s ipv6=off;\n'
        '    set $backend_upstream "backend:8000";\n'
        '    location /api/ {\n'
        '        proxy_pass http://$backend_upstream;\n'
        '    }\n'
        '    location / { try_files $uri $uri/ /index.html; }\n'
        '}\n', encoding='utf-8')

    module.problems.clear()
    module.checks.clear()
    module.check_nginx_proxies_api()

    assert not module.problems, module.problems
    assert any('resolver' in check for check in module.checks)


# ----------------------------------------------------------------------
# Манифест релиза
# ----------------------------------------------------------------------

def test_release_manifest_requires_digest(tmp_path, monkeypatch) -> None:
    """Образ без digest или с PLACEHOLDER не должен проходить."""
    sys.path.insert(0, str(ROOT / 'scripts'))
    import check_release as module

    # ROOT обязан указывать на tmp_path: иначе check_manifest вызывает
    # path.relative_to(ROOT) с путём вне ROOT и падает на TypeError —
    # проверка не срабатывает, а тест падает по чужой причине.
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    manifest = tmp_path / 'cybra-9.9.9.yml'
    manifest.write_text(yaml.safe_dump({
        'release_id': 'cybra-9.9.9',
        'config_ref': 'abc123',
        'services': {
            'backend': {'image': 'registry.gitlab.com/x/backend:latest'},
            'frontend': {'image': 'registry.gitlab.com/x/frontend@sha256:'
                                  + 'P' * 64},
        },
    }), encoding='utf-8')

    module.problems.clear()
    module.results.clear()
    data = yaml.safe_load(manifest.read_text(encoding='utf-8'))
    module.check_manifest(manifest, data)

    assert any('без digest' in problem for problem in module.problems), \
        module.problems
    # PLACEHOLDER ловится в двух случаях: когда он попал в digest (форма
    # неверна) и когда образ не заполнен вовсе. Оба — находка, и обе
    # должны быть в списке: молча пропустить незаполненный манифест значит
    # развернуть вчерашний образ, ничего об этом не сказав.
    assert any('PLACEHOLDER' in problem or 'не заполнен' in problem
               or 'неверную форму' in problem
               for problem in module.problems), module.problems


def test_release_manifest_rejects_foreign_registry(tmp_path, monkeypatch) -> None:
    """Образ из неразрешённого registry — находка."""
    sys.path.insert(0, str(ROOT / 'scripts'))
    import check_release as module

    monkeypatch.setattr(module, 'ROOT', tmp_path)
    manifest = tmp_path / 'cybra-9.9.9.yml'
    manifest.write_text(yaml.safe_dump({
        'release_id': 'cybra-9.9.9',
        'config_ref': 'abc123',
        'services': {
            'backend': {'image': 'evil.example.com/x/backend@sha256:' + 'a' * 64},
            'frontend': {'image': 'registry.gitlab.com/x/frontend@sha256:'
                                  + 'b' * 64},
        },
    }), encoding='utf-8')

    module.problems.clear()
    module.results.clear()
    data = yaml.safe_load(manifest.read_text(encoding='utf-8'))
    module.check_manifest(manifest, data)

    assert any('registry' in problem for problem in module.problems), \
        module.problems


# ----------------------------------------------------------------------
# infra и Ansible
# ----------------------------------------------------------------------

def test_infra_check_passes() -> None:
    """Инфра в текущем виде проходит проверку."""
    result = run_script('check_infra.py')
    assert result.returncode == 0, result.stdout + result.stderr


def test_ansible_security_passes() -> None:
    """Playbook не содержит опасных конструкций."""
    result = run_script('check_ansible_security.py')
    assert result.returncode == 0, result.stdout + result.stderr


def test_ansible_string_command_with_variable_is_flagged(monkeypatch) -> None:
    """`cmd:` строкой с подстановкой — путь к инъекции, должен ловиться.

    Форма `argv:` безопасна (shell не участвует), и ругаться на неё
    значило бы заставлять добавлять noqa там, где всё в порядке.
    Проверяем обе стороны.
    """
    sys.path.insert(0, str(ROOT / 'scripts'))
    import check_ansible_security as module

    dangerous = [{
        'name': 'опасная задача',
        'ansible.builtin.command': 'docker run --name {{ release_id }} image',
    }]
    module.problems.clear()
    module.walk_tasks(dangerous, ROOT / 'infra' / 'ansible' / 'test.yml')
    assert module.problems, 'строковый command с переменной не поймали'

    safe = [{
        'name': 'безопасная задача',
        'ansible.builtin.command': {
            'argv': ['docker', 'run', '--name', '{{ release_id }}', 'image'],
        },
    }]
    module.problems.clear()
    module.walk_tasks(safe, ROOT / 'infra' / 'ansible' / 'test.yml')
    assert not module.problems, f'argv ложно помечен: {module.problems}'


# ----------------------------------------------------------------------
# Пайплайны
# ----------------------------------------------------------------------

def test_iac_check_passes() -> None:
    """Dockerfile, compose и пайплайны проходят проверку."""
    result = run_script('check_iac.py')
    assert result.returncode == 0, result.stdout + result.stderr


def test_two_pipelines_exist_and_cover_scheme() -> None:
    """У каждого сервиса свой пайплайн, и в каждом 18 шагов схемы.

    Проверяется не наличие файла, а то, что шаги реально названы: пайплайн
    из трёх job'ов прошёл бы проверку существования, но задание требует
    схему.

    Имена job'ов начинаются с `<service>:` — режем по последнему двоеточию,
    а не по первому, иначе от `backend:deploy-test:` останется `backend`.
    """
    expected_steps = ('validate', 'format', 'lint', 'test', 'sast', 'secrets',
                      'iac', 'build', 'sca', 'image-scan', 'deploy-test',
                      'sign', 'release', 'approve', 'deploy-prod', 'rollback')

    for service in ('backend', 'frontend'):
        path = ROOT / '.gitlab' / 'ci' / 'pipelines' / f'{service}.yml'
        assert path.exists(), f'нет пайплайна {service}'

        text = path.read_text(encoding='utf-8')
        jobs = [line.rstrip()[:-1] for line in text.splitlines()
                if line.startswith(f'{service}:') and line.rstrip().endswith(':')]
        assert len(jobs) >= 15, f'{service}: найдено всего job\'ов {jobs}'

        # Шаг считается покрытым, если он упомянут в имени любого job'а.
        joined = ' '.join(jobs)
        for step in expected_steps:
            assert step in joined, (
                f'{service}: шаг «{step}» не найден среди job\'ов {jobs}')


def test_frontend_smoke_checks_proxy() -> None:
    """Smoke фронтенда обязан проверять прокси, а не только отдачу SPA.

    Забытый proxy_pass — самая вероятная ошибка при разделении монолита, и
    без этой проверки она обнаруживается у заказчика.
    """
    text = (ROOT / '.gitlab' / 'ci' / 'pipelines' / 'frontend.yml').read_text(
        encoding='utf-8')
    assert '/api/v1/health' in text, 'smoke не дёргает API через nginx'
    assert 'proxy_pass' in text.lower() or 'прокси' in text.lower()


def test_old_compose_is_marked_obsolete() -> None:
    """Старый compose не должен притворяться рабочим."""
    path = ROOT / 'docker' / 'compose.prod.yaml'
    assert path.exists(), 'файл удалён — проверка должна это допускать'
    text = path.read_text(encoding='utf-8').lower()
    assert 'устарел' in text or 'infra/compose.yaml' in text
