# Data provenance and licenses

> Russian version: [docs/ru/DATA_SOURCES.md](ru/DATA_SOURCES.md).

All official files are included in the archive; no dataset downloads are required at run time. Tool dependencies are installed separately. The checksums of the archive files are in `CHECKSUMS.sha256`, and those of the data used are also in the manifest of each run.

| Dataset | Files | Volume and usage |
|---|---|---|
| Author's corporate | `datasets/corporate.jsonl` | 48: direct injection 12, indirect injection 12, secret leak 8, harmful 8, benign 8; 24 RU and 24 EN |
| Author's multi-turn | `datasets/multiturn.jsonl` | 8 dialogues of 3 turns each |
| HarmBench test | `datasets/harmbench.csv` | 320 lines in the source file; 159 standard + 81 contextual are used, 80 copyright ones excluded |
| JBB Behaviors | `datasets/jbb-harmful-behaviors.csv`, `jbb-benign-behaviors.csv` | 100 harmful + 100 benign |
| BIPIA | `datasets/bipia/email/test.jsonl`, `table/test.jsonl`, `text_attack_test.json` | 50 email, 100 table, 75 attack texts in 15 groups |

## Pinned sources

- [bipia](https://github.com/microsoft/BIPIA): `a004b69ec0dd446e0afd461d98cb5e96e120a5d0`.
- [harmbench](https://github.com/centerforaisafety/HarmBench): `8e1604d1171fe8a48d8febecd22f600e462bdcdd`.
- [agentdojo](https://github.com/ethz-spylab/agentdojo): `089ed468cf3ed0322acc66b0211f26d9d90dbf60`.
- [pyrit](https://github.com/microsoft/PyRIT): `c0bcdcadba340ecd9e4ce05047874de80fd480d6`.
- [jailbreakbench](https://github.com/JailbreakBench/jailbreakbench): `23dbdf6b19650521604456229bc1d9c4156c85c1`.
- [jbb_dataset](https://huggingface.co/datasets/JailbreakBench/JBB-Behaviors): `886acc352a31533ffbcf4ef22c744658688086fc`.
- [garak](https://github.com/NVIDIA/garak): `93aa9cdec309ec4170559676f1826ea2a679920c`.
- [promptfoo](https://github.com/promptfoo/promptfoo): `0.123.0`.

The source HarmBench CSV: `data/behavior_datasets/harmbench_behaviors_text_test.csv` in the pinned repository. BIPIA: `benchmark/<task>/test.jsonl` and `benchmark/text_attack_test.json`; the original Python builders are included unchanged in `vendor/bipia/`. The JBB CSVs are derived from the JBB-Behaviors dataset of the specified revision.

`licenses/` contains upstream license texts. Garak is Apache-2.0; the listed source repositories of the other tools ship MIT texts. The licenses of dependencies and source materials inside the datasets may have separate terms; the orchestrator's license does not replace them. The JBB dataset license is preserved separately.

The author's data and code are described in `NOTICE.md`. The created RU/EN scenarios are not passed off as built-in Promptfoo/PyRIT datasets: these frameworks have their own suites and examples, but in this configuration our fixed regression scenarios are wired in.
