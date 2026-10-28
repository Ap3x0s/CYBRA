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
    parts=['<!doctype html><html lang="ru"><meta charset="utf-8"><title>LLM Security Report</title>',
      '<style>body{font:16px system-ui;max-width:1200px;margin:36px auto;padding:0 20px;background:#f7f8fa;color:#17212b}table{border-collapse:collapse;width:100%;background:white}td,th{padding:9px;border:1px solid #d5dce4;text-align:left}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#fff;padding:16px}details{margin:12px 0}summary{cursor:pointer;font-weight:600}.FAIL,.ERROR{color:#a31919}</style>',
      '<h1>Проверка информационной безопасности моделей</h1><p>Без общего процента безопасности. Статусы относятся к настроенному поднабору.</p>']
    for model,m in by_model.items():
        parts.append(f'<h2>{html.escape(model)}</h2><p>{m["conclusion"]}</p><table><tr><th>Инструмент</th><th>Полнота</th><th>PASS</th><th>FAIL</th><th>ERROR</th><th>UNSCORED</th></tr>')
        for t in m['tools']:
            c=t['counts'];parts.append('<tr>'+''.join('<td>'+html.escape(str(x))+'</td>' for x in [t['tool'],t['status'],c['PASS'],c['FAIL'],c['ERROR'],c['UNSCORED']])+'</tr>')
        parts.append('</table>')
        for tool in manifest['tools']:
            parts.append(f'<details><summary>{html.escape(tool)} — записи</summary>')
            for r in all_records:
                if r['model']==model and r['tool']==tool:
                    parts.append(f'<details><summary class="{r["status"]}">{html.escape(r["case_id"])} — {r["status"]}</summary><pre>'+html.escape(json.dumps(r,ensure_ascii=False,indent=2))+'</pre></details>')
            parts.append('</details>')
    parts.append('</html>');(root/'report.html').write_text(''.join(parts),encoding='utf-8')
    return summary
