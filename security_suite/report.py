import html
import json
from collections import defaultdict
from pathlib import Path
from .common import read_json, jsonl, write_json, MODES

def esc(value):
    return html.escape(str(value)).replace('|','&#124;').replace('\n',' ')

def consolidate(run_dir):
    root=Path(run_dir);manifest=read_json(root/'manifest.json')
    by_model={};all_records=[]
    for model,mdir in manifest['model_dirs'].items():
        tools=[];model_rows=[]
        for tool in manifest['tools']:
            d=root/mdir/tool
            status=read_json(d/'status.json') if (d/'status.json').exists() else {'status':'ERROR','error':'Missing adapter status'}
            rows=jsonl(d/'records.jsonl') if (d/'records.jsonl').exists() else []
            counts={'PASS':0,'FAIL':0,'ERROR':0,'UNSCORED':0,'SKIPPED':0}
            groups=defaultdict(lambda:{'PASS':0,'FAIL':0,'ERROR':0,'UNSCORED':0,'SKIPPED':0})
            for r in rows:
                if r['model']!=model or r['tool']!=tool:raise ValueError('Model/tool mismatch in normalized report')
                if r['status'] not in counts:raise ValueError('Unknown verdict '+r['status'])
                if r.get('unit')=='detector_judgement':
                    counts['PASS']+=r['passed'];counts['FAIL']+=r['failed']
                    groups[r['category']]['PASS']+=r['passed'];groups[r['category']]['FAIL']+=r['failed']
                else:
                    counts[r['status']]+=1;groups[r['category']][r['status']]+=1
            n=counts['PASS']+counts['FAIL']
            item={'tool':tool,'mode':MODES[tool],**status,'counts':counts,'failed_check_rate':counts['FAIL']/n if n else None,
                  'unit':'detector_judgement' if tool=='garak' else 'case','categories':dict(groups),
                  'artifact_dir':str(d.relative_to(root))}
            tools.append(item);model_rows.extend(rows)
        findings=any(t['counts']['FAIL'] for t in tools)
        incomplete=any(t['status']!='COMPLETE' for t in tools)
        conclusion=('FINDINGS_AND_INCOMPLETE' if findings and incomplete else 'FINDINGS' if findings else 'INCOMPLETE' if incomplete else 'NO_FINDINGS_ON_TESTED_SET')
        by_model[model]={'conclusion':conclusion,'tools':tools}
        all_records.extend(model_rows)
        write_json(root/mdir/'summary.json',by_model[model])
    summary={'schema_version':1,'run_id':manifest['run_id'],'models':by_model,'methodology':MODES,
      'warning':'No cross-tool aggregate ASR. Adapted evaluations are not official leaderboard scores.'}
    write_json(root/'summary.json',summary)
    (root/'all_records.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in all_records),encoding='utf-8')
    md=['# Итоговая проверка моделей','',f"Run: `{manifest['run_id']}`",'',
        'Оценки относятся к выбранным наборам и профилю запуска. Единый ASR между инструментами не вычисляется.',
        'FAIL — срабатывание проверки; ERROR/UNSCORED/SKIPPED не считаются PASS. Результат судьи требует ручной проверки.','']
    for model,m in by_model.items():
        md += [f'## {esc(model)}','',f"Результат: **{m['conclusion']}**",'',
          '| Инструмент | Полнота | Pass | Fail | Error | Unscored | Skipped | Доля Fail |',
          '|---|---|---:|---:|---:|---:|---:|---:|']
        for t in m['tools']:
            c=t['counts'];pct='N/A' if t['failed_check_rate'] is None else f"{t['failed_check_rate']:.1%}"
            md.append('| '+' | '.join(map(esc,[t['tool'],t['status'],c['PASS'],c['FAIL'],c['ERROR'],c['UNSCORED'],c['SKIPPED'],pct]))+' |')
        md+=['','Полнота COMPLETE относится к настроенному поднабору, а не ко всем возможным атакам.','']
        for t in m['tools']:
            md += [f"### {t['tool']}",'',f"Методика: {t['mode']}. Единица: {t['unit']}.",'',f"Артефакты: `{t['artifact_dir']}`",'']
            if t.get('error'):md+=['Ошибка: '+esc(t['error']),'']
            if t.get('transport_errors'):md+=['Ошибки транспорта: '+esc(t['transport_errors']),'']
            for category,c in t['categories'].items():
                md.append(f"- {esc(category)}: PASS={c['PASS']}, FAIL={c['FAIL']}, ERROR={c['ERROR']}, UNSCORED={c['UNSCORED']}, SKIPPED={c['SKIPPED']}")
            md.append('')
    md+=['## Методические ограничения','',
      '- Garak: счётчики детекторов; один ответ может учитываться несколько раз.',
      '- Promptfoo: корпоративные тесты; отсутствие маркера не исключает другие утечки.',
      '- PyRIT: реальные диалоги из трёх ходов; фиксированные сценарии, без адаптивного атакующего LLM.',
      '- HarmBench: standard/contextual test behaviors и фиксированные обёртки; общий API-судья, не штатный классификатор.',
      '- JailbreakBench: исходные harmful/benign behaviors и API-судья; не официальный прогон JBB.',
      '- BIPIA: штатные builders email/table и исходные атаки; API-судья, а не исходные специализированные evaluators.',
      '- AgentDojo: штатные окружения и goal checks. security=True в upstream означает достижение цели инъекции.',
      '- AgentDojo проверяет модель в тестовом агенте, не ACL и реальные инструменты OpenWebUI.',
      '- Security Regression: синтетические canary-маркеры; '
      'проверяет раскрытие точного значения и распространённых '
      'кодировок, но не заменяет DLP-классификатор.',
      '- Полные запросы, ответы и judge-данные: http.jsonl; ошибки и детали: records.jsonl и нативные отчёты.']
    (root/'report.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
    # Standalone HTML, no untrusted executable markup or remote assets.
    # Стили inline: отчёт должен открываться и печататься без сети, поэтому
    # внешние шрифты и картинки не используются. Палитра — CYBRA, но
    # приглушённая под бумагу: акцент #B07E22 вместо экранного #E5A93C,
    # иначе на белом он нечитаем при печати.
    css = """
@page { size: A4; margin: 16mm 14mm; }
* { box-sizing: border-box; }
body {
  font-family: -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
  font-size: 13px; line-height: 1.6; color: #14141A;
  background: #FBFAF7; margin: 0; padding: 40px 32px;
  -webkit-print-color-adjust: exact; print-color-adjust: exact;
}
.wrap { max-width: 1000px; margin: 0 auto; }
/* Надзаголовок — идентичность документа, поэтому чёрный и заметный.
   Раньше он был мелким серым капсом и читался как служебная сноска. */
.eyebrow {
  font-size: 10.5px; letter-spacing: .14em; text-transform: uppercase;
  color: #14141A; font-weight: 700; margin-bottom: 10px;
}
/* Дата — в правом верхнем углу, в серой плашке. Отделена от потока:
   это метка времени, а не часть заголовка. */
.head-row { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; }
.stamp {
  flex: 0 0 auto;
  background: #EDE8DF; color: #4A453E;
  padding: 5px 11px; border-radius: 3px;
  font-family: ui-monospace, 'SF Mono', Menlo, monospace;
  font-size: 10.5px; white-space: nowrap;
}
/* Название прогона — то, что человек ввёл сам, поэтому крупно и чёрным.
   Надзаголовок остаётся чёрным капсом, но мельче: он объясняет документ,
   а название — это сам запуск. */
h1 { font-size: 27px; line-height: 1.25; margin: 0 0 12px; letter-spacing: -.02em; color: #14141A; font-weight: 600; }
.meta { font-size: 11.5px; color: #6B6660; font-family: ui-monospace, 'SF Mono', Menlo, monospace; }
.rule { height: 2px; background: #14141A; margin: 22px 0 26px; }

/* Карточка-предупреждение: заметна, но не кричит. Левый акцент вместо
   рамки по кругу — так блок читается как ремарка, а не как таблица. */
.note {
  border-left: 3px solid #B07E22; background: #F6F1E6;
  padding: 11px 15px; margin: 12px 0; font-size: 12px; color: #4A453E;
}
.note.critical { border-left-color: #A8321E; background: #FAF0ED; }

/* KPI-строка */
.kpis { display: flex; gap: 10px; margin: 0 0 28px; }
.kpi {
  flex: 1; background: #fff; border: 1px solid #E6E1D8;
  padding: 14px 15px 12px; border-radius: 3px;
}
.kpi-label {
  font-size: 9.5px; letter-spacing: .1em; text-transform: uppercase;
  color: #8A8580; font-weight: 600; margin-bottom: 6px;
}
.kpi-value { font-size: 25px; font-weight: 650; letter-spacing: -.02em; line-height: 1; }
.kpi-sub { font-size: 10.5px; color: #8A8580; margin-top: 5px; }
.kpi-value.bad { color: #A8321E; }

/* Секция модели */
.model {
  background: #fff; border: 1px solid #E6E1D8; border-radius: 3px;
  padding: 22px 24px; margin: 0 0 18px; page-break-inside: avoid;
}
.model-id {
  font-family: ui-monospace, 'SF Mono', Menlo, monospace;
  font-size: 15px; font-weight: 600; margin-bottom: 4px;
}
.verdict { font-size: 12px; color: #4A453E; margin-bottom: 18px; }
.verdict b { color: #14141A; }

h3 {
  font-size: 9.5px; letter-spacing: .12em; text-transform: uppercase;
  color: #8A8580; font-weight: 700; margin: 20px 0 9px;
}

table { width: 100%; border-collapse: collapse; font-size: 12px; margin-bottom: 4px; }
th {
  text-align: left; padding: 7px 9px; font-size: 9px;
  letter-spacing: .1em; text-transform: uppercase; color: #8A8580;
  font-weight: 700; border-bottom: 1.5px solid #14141A; white-space: nowrap;
}
td { padding: 8px 9px; border-bottom: 1px solid #EDE8DF; vertical-align: middle; }
tr:last-child td { border-bottom: none; }
td.num, th.num { text-align: right; font-family: ui-monospace, 'SF Mono', Menlo, monospace; }
td.tool { font-weight: 500; }

/* Статус-чип: цвет + текст, не только цвет — иначе при ч/б печати
   состояния неразличимы. */
.chip {
  display: inline-block; padding: 2px 8px; border-radius: 3px;
  font-size: 9.5px; font-weight: 600; letter-spacing: .04em;
  text-transform: uppercase; white-space: nowrap;
}
.chip.complete { background: #E4F0E9; color: #1F7A4D; }
.chip.partial  { background: #F6F1E6; color: #8A6216; }
.chip.error    { background: #FAF0ED; color: #A8321E; }

/* Полоса доли провалов: значение читается глазом, а не только числом. */
/* Ячейка «полоска + число»: полоска тянется, процент прижат вправо
   и не переносится, чтобы строка таблицы оставалась ровной. */
.bar-cell { display: flex; align-items: center; gap: 8px; min-width: 118px; }
.bar-cell .bar-value {
  font-family: ui-monospace, 'SF Mono', Menlo, monospace;
  font-size: 11px; color: #14141A; white-space: nowrap;
  min-width: 38px; text-align: right;
}
.bar-cell .bar-none { color: #8A8580; font-size: 11px; }
.bar-track { flex: 1; min-width: 60px; height: 6px; background: #EDE8DF; border-radius: 3px; }
.bar-fill { height: 6px; background: #B07E22; border-radius: 3px; }
.bar-fill.high { background: #A8321E; }
.bar-fill.zero { background: #D8D2C8; }

.limits {
  background: #fff; border: 1px solid #E6E1D8; border-radius: 3px;
  padding: 18px 22px; margin-top: 22px; page-break-inside: avoid;
}
.limits ul { margin: 0; padding-left: 18px; font-size: 11.5px; color: #4A453E; }
.limits li { margin-bottom: 5px; }
.foot {
  margin-top: 26px; padding-top: 14px; border-top: 1px solid #E6E1D8;
  font-size: 10px; color: #8A8580;
}

details { margin: 6px 0; }
details.dump { page-break-inside: avoid; }
summary { cursor: pointer; font-size: 11px; color: #6B6660; padding: 4px 0; }
pre {
  white-space: pre-wrap; overflow-wrap: anywhere; background: #FBFAF7;
  border: 1px solid #EDE8DF; border-radius: 3px; padding: 12px;
  font-size: 10.5px; line-height: 1.5; margin: 6px 0 10px;
}
.status-FAIL { color: #A8321E; }
.status-ERROR { color: #A8321E; font-weight: 600; }
.status-PASS { color: #1F7A4D; }

@media print {
  body { background: #fff; padding: 0; font-size: 11.5px; }
  .wrap { max-width: none; }
  .model, .limits, .kpi { border-color: #D8D2C8; }
  .kpis { page-break-inside: avoid; }
  details { display: none; }
}
"""

    # Статусы полноты по-русски. Термины COMPLETE/PARTIAL взяты из нашего
    # словаря метрик, но в отчёте для руководства английские слова читаются
    # как сбой локализации. Исходный термин сохраняем в title: при наведении
    # видно точное значение из контракта, аудитор не теряет однозначность.
    STATUS_RU = {
        'COMPLETE': ('полно', 'complete'),
        'PARTIAL': ('частично', 'partial'),
        'ERROR': ('ошибка', 'error'),
        'CANCELLED': ('отменён', 'error'),
    }

    def chip(status: str) -> str:
        """Статус-чип. Текст дублирует цвет — важно для чёрно-белой печати."""
        key = status.strip().upper()
        label, cls = STATUS_RU.get(key, (status, 'error'))
        return (f'<span class="chip {cls}" title="{html.escape(status)}">'
                f'{html.escape(label)}</span>')

    def bar(share: float, known: bool = True) -> str:
        """Полоса доли провалов с числом справа.

        Полоска показывает пропорцию, но точное значение по ней не прочесть.
        Поэтому процент стоит рядом: глаз сначала видит соотношение, потом
        уточняет цифрой.

        При нуле полоса нулевой ширины не видна вовсе — выглядело как
        отсутствие данных, а не как «ноль провалов». Поэтому для нуля
        рисуем серую точку-минимум.

        known=False означает «оценивать было нечего» (нет ни PASS, ни FAIL):
        тогда вместо 0.0 % ставим прочерк, иначе ноль наблюдений выглядел бы
        как измеренный ноль провалов.
        """
        if not known:
            return '<div class="bar-cell"><span class="bar-none">—</span></div>'
        share = max(0.0, min(1.0, share))
        cls = 'high' if share >= 0.5 else ('zero' if share <= 0 else '')
        width = 6 if share <= 0 else share * 100
        return (
            '<div class="bar-cell">'
            f'<div class="bar-track"><div class="bar-fill {cls}" '
            f'style="width:{width:.1f}%"></div></div>'
            f'<span class="bar-value">{share * 100:.1f}%</span>'
            '</div>'
        )

    # Метаданные собираем фильтром: пустые поля раньше оставляли в строке
    # разделители-сироты вида "id ·  · режим", что читалось как сбой отчёта.
    meta_bits = []
    run_meta = html.escape(str(manifest.get('run_id', '') or ''))
    if run_meta:
        meta_bits.append(run_meta)
    started_raw = str(manifest.get('started_at', '') or '')[:16].replace('T', ' ')
    if started_raw:
        meta_bits.append(html.escape(started_raw))
    # Дата вынесена отдельно: она уходит в плашку справа и не дублируется
    # в строке метаданных.
    stamp = html.escape(started_raw) if started_raw else ''
    if started_raw:
        meta_bits = [b for b in meta_bits if b != html.escape(started_raw)]
    mode = html.escape(str(manifest.get('engine_mode', '') or ''))
    if mode and mode != 'None':
        meta_bits.append(f'режим {mode}')
    meta_line = ' · '.join(meta_bits)

    parts = [
        '<!doctype html><html lang="ru"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<title>CYBRA — отчёт о проверке безопасности LLM</title>',
        f'<style>{css}</style></head><body><div class="wrap">',
        '<div class="head-row">',
        '<div>',
        '<div class="eyebrow">CYBRA · Отчёт о проверке безопасности LLM</div>',
        f'<h1>{html.escape(str(manifest.get("label") or "Проверка моделей"))}</h1>',
        f'<div class="meta">{meta_line}</div>',
        '</div>',
        f'<div class="stamp">{stamp}</div>',
        '</div>',
        '<div class="rule"></div>',
    ]

    if mode == 'mock':
        parts.append(
            '<div class="note critical">Прогон выполнен в демонстрационном режиме '
            '(mock). Вердикты синтетические и не являются оценкой безопасности '
            'какой-либо модели.</div>')

    parts.append(
        '<div class="note">Единый процент безопасности не вычисляется: инструменты '
        'считают разные единицы (у garak — решение детектора, у остальных — '
        'отдельный кейс). Доля провалов относится к конкретному инструменту и '
        'настроенному подмножеству, а не ко всем возможным атакам.</div>')

    # --- KPI-строка по всем моделям -------------------------------------
    total_models = len(by_model)
    total_steps = sum(len(m['tools']) for m in by_model.values())
    total_pass = sum(t['counts']['PASS'] for m in by_model.values() for t in m['tools'])
    total_fail = sum(t['counts']['FAIL'] for m in by_model.values() for t in m['tools'])
    total_scored = total_pass + total_fail
    share = (total_fail / total_scored) if total_scored else 0.0

    parts.append('<div class="kpis">')
    parts.append(f'<div class="kpi"><div class="kpi-label">Моделей</div>'
                 f'<div class="kpi-value">{total_models}</div>'
                 f'<div class="kpi-sub">в прогоне</div></div>')
    parts.append(f'<div class="kpi"><div class="kpi-label">Шагов</div>'
                 f'<div class="kpi-value">{total_steps}</div>'
                 f'<div class="kpi-sub">модель × инструмент</div></div>')
    parts.append(f'<div class="kpi"><div class="kpi-label">Оценено</div>'
                 f'<div class="kpi-value">{total_scored}</div>'
                 f'<div class="kpi-sub">кейсов с вердиктом</div></div>')
    bad_cls = ' bad' if share >= 0.3 else ''
    parts.append(f'<div class="kpi"><div class="kpi-label">Провалов</div>'
                 f'<div class="kpi-value{bad_cls}">{share * 100:.1f}%</div>'
                 f'<div class="kpi-sub">{total_fail} из {total_scored}</div></div>')
    parts.append('</div>')

    # --- Секции по моделям ----------------------------------------------
    for model, m in by_model.items():
        parts.append('<div class="model">')
        parts.append(f'<div class="model-id">{html.escape(model)}</div>')
        parts.append(f'<div class="verdict">{m["conclusion"]}</div>')

        parts.append('<h3>Итоги по инструментам</h3>')
        parts.append('<table><tr><th>Инструмент</th><th>Полнота</th>'
                     '<th class="num">PASS</th><th class="num">FAIL</th>'
                     '<th class="num">Ошибки</th><th class="num">Не оценено</th>'
                     '<th>Доля провалов</th></tr>')
        for t in m['tools']:
            c = t['counts']
            scored = c['PASS'] + c['FAIL']
            rate = (c['FAIL'] / scored) if scored else 0.0
            parts.append(
                f'<tr><td class="tool">{html.escape(str(t["tool"]))}</td>'
                f'<td>{chip(str(t["status"]))}</td>'
                f'<td class="num">{c["PASS"]}</td>'
                f'<td class="num">{c["FAIL"]}</td>'
                f'<td class="num">{c["ERROR"]}</td>'
                f'<td class="num">{c.get("UNSCORED", 0) + c.get("SKIPPED", 0)}</td>'
                f'<td>{bar(rate, known=bool(scored))}</td></tr>')
        parts.append('</table>')

        # Разбивка по категориям. Категории лежат внутри каждого инструмента,
        # а не на уровне модели: у harmbench свои имена, у jailbreakbench —
        # ветки harmful/<тема>, и смешивать их в один список нельзя.
        cat_rows = []
        for t in m['tools']:
            for cat, bucket in (t.get('categories') or {}).items():
                cat_rows.append((t['tool'], cat, bucket))
        if cat_rows:
            parts.append('<h3>Разбивка по категориям</h3>')
            parts.append('<table><tr><th>Инструмент</th><th>Категория</th>'
                         '<th class="num">PASS</th><th class="num">FAIL</th>'
                         '<th class="num">Ошибки</th></tr>')
            for tool_name, cat, bucket in sorted(cat_rows):
                parts.append(
                    f'<tr><td class="tool">{html.escape(str(tool_name))}</td>'
                    f'<td>{html.escape(str(cat))}</td>'
                    f'<td class="num">{bucket.get("PASS", 0)}</td>'
                    f'<td class="num">{bucket.get("FAIL", 0)}</td>'
                    f'<td class="num">{bucket.get("ERROR", 0)}</td></tr>')
            parts.append('</table>')

        # Полный дамп записей — свёрнут, чтобы не рвать печать
        for tool in manifest['tools']:
            rows = [r for r in all_records
                    if r['model'] == model and r['tool'] == tool]
            if not rows:
                continue
            parts.append(f'<details class="dump"><summary>'
                         f'{html.escape(tool)} — записи ({len(rows)})</summary>')
            for r in rows:
                parts.append(
                    f'<details><summary class="status-{html.escape(str(r["status"]))}">'
                    f'{html.escape(str(r["case_id"]))} — '
                    f'{html.escape(str(r["status"]))}</summary>'
                    f'<pre>{html.escape(json.dumps(r, ensure_ascii=False, indent=2))}</pre>'
                    f'</details>')
            parts.append('</details>')

        parts.append('</div>')  # .model

    # --- Ограничения методики -------------------------------------------
    limits = manifest.get('limits') or []
    if not limits:
        limits = [
            'Значения провалов внутри инструмента не сравнимы между инструментами.',
            'COMPLETE относится к выбранному профилю, а не ко всем атакам инструмента.',
            'ERROR, UNSCORED и SKIPPED не считаются PASS.',
            'Результат судьи требует выборочной ручной проверки.',
            'Отчёт не покрывает ACL, RAG, браузер и реальные side effects приложения.',
        ]
    parts.append('<div class="limits"><h3 style="margin-top:0">'
                 'Методические ограничения</h3><ul>')
    for item in limits:
        parts.append(f'<li>{html.escape(str(item))}</li>')
    parts.append('</ul></div>')

    parts.append('<div class="foot">CYBRA · Security Console. Отчёт относится '
                 'к настроенному подмножеству атак и не является сертификатом '
                 'безопасности.</div>')
    parts.append('</div></body></html>')

    (root / 'report.html').write_text(''.join(parts), encoding='utf-8')
    return summary
