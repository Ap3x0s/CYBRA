# Происхождение данных и лицензии

Все официальные файлы включены в архив; скачивание датасетов при запуске не требуется. Зависимости инструментов устанавливаются отдельно. Контрольные суммы файлов архива находятся в `CHECKSUMS.sha256`, использованных данных — также в manifest каждого запуска.

| Набор | Файлы | Объём и использование |
|---|---|---|
| Авторский корпоративный | `datasets/corporate.jsonl` | 48: direct injection 12, indirect injection 12, secret leak 8, harmful 8, benign 8; 24 RU и 24 EN |
| Авторский multi-turn | `datasets/multiturn.jsonl` | 8 диалогов по 3 хода |
| HarmBench test | `datasets/harmbench.csv` | 320 строк в исходном файле; используются 159 standard + 81 contextual, исключены 80 copyright |
| JBB Behaviors | `datasets/jbb-harmful-behaviors.csv`, `jbb-benign-behaviors.csv` | 100 harmful + 100 benign |
| BIPIA | `datasets/bipia/email/test.jsonl`, `table/test.jsonl`, `text_attack_test.json` | 50 email, 100 table, 75 текстов атак в 15 группах |

## Закреплённые источники

- [bipia](https://github.com/microsoft/BIPIA): `a004b69ec0dd446e0afd461d98cb5e96e120a5d0`.
- [harmbench](https://github.com/centerforaisafety/HarmBench): `8e1604d1171fe8a48d8febecd22f600e462bdcdd`.
- [agentdojo](https://github.com/ethz-spylab/agentdojo): `089ed468cf3ed0322acc66b0211f26d9d90dbf60`.
- [pyrit](https://github.com/microsoft/PyRIT): `c0bcdcadba340ecd9e4ce05047874de80fd480d6`.
- [jailbreakbench](https://github.com/JailbreakBench/jailbreakbench): `23dbdf6b19650521604456229bc1d9c4156c85c1`.
- [jbb_dataset](https://huggingface.co/datasets/JailbreakBench/JBB-Behaviors): `886acc352a31533ffbcf4ef22c744658688086fc`.
- [garak](https://github.com/NVIDIA/garak): `93aa9cdec309ec4170559676f1826ea2a679920c`.
- [promptfoo](https://github.com/promptfoo/promptfoo): `0.123.0`.

Исходный HarmBench CSV: `data/behavior_datasets/harmbench_behaviors_text_test.csv` в закреплённом репозитории. BIPIA: `benchmark/<task>/test.jsonl` и `benchmark/text_attack_test.json`; оригинальные Python builders включены без изменения в `vendor/bipia/`. JBB CSV получены из набора JBB-Behaviors указанной ревизии.

`licenses/` содержит upstream license texts. Garak — Apache-2.0; перечисленные исходные репозитории остальных инструментов поставляют MIT-тексты. Лицензии зависимостей и исходных материалов внутри датасетов могут иметь отдельные условия; лицензия оркестратора их не заменяет. JBB dataset license сохранена отдельно.

Авторские данные и код описаны в `NOTICE.md`. Созданные RU/EN сценарии не выдаются за встроенные датасеты Promptfoo/PyRIT: эти фреймворки имеют собственные наборы и примеры, но в данной конфигурации подключены наши фиксированные регрессионные сценарии.
