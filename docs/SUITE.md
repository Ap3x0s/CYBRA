# LLM Security Suite — a single run of eight check suites

> Russian version: [docs/ru/SUITE.md](ru/SUITE.md).

The project tests **a list of models through the OpenAI-compatible Chat Completions API** and automatically collects results for each model in Markdown, HTML, and JSON. It is suitable for LiteLLM, OpenWebUI, and any other server with this API contract.

Included: **garak, Promptfoo, PyRIT, HarmBench, JailbreakBench, BIPIA, AgentDojo, security-regression**. All eight adapters make requests and save results; there are no stubs for "unconnected" tools. However, the integration methods differ — see the table below. The project does not claim to run all existing attacks of these projects.

## Quick start

Verified environment: Linux x86_64, Python 3.12, Node.js 22+, npm, git, and uv. On Windows use WSL2. The selected checks do not need a GPU. The garak and PyRIT dependencies are substantial: installation downloads CPU versions of ML libraries among other things. The first installation needs access to GitHub, PyPI, npm, and the package repositories they use.

```bash
cd llm-security-suite
python3 -m pip install uv

# The key is entered without saving its value in the command history.
read -rsp 'API key: ' TARGET_API_KEY; echo
export TARGET_API_KEY

python3 run.py run --install \
  --endpoint http://localhost:4000/v1/chat/completions \
  --models model-a model-b model-c \
  --judge-model judge-model \
  --out reports
```

Replace `model-a`, `model-b`, `model-c`, `judge-model` with the **exact IDs/aliases available on your server**. `--models 'provider/model-a' 'provider/model-b'` and `--models model-a,model-b` also work. All models of one run are checked through a single target endpoint. For a different endpoint, perform a separate run.

`--install` automatically installs the dependencies into isolated `.tools/<tool>` and runs the whole suite. On repeated runs, remove `--install`. Installation is also available separately:

```bash
python3 run.py setup
```

The control script itself has no third-party Python dependencies. `setup` uses the versions from `locks/*.txt`, `sources.lock.json`, and `package-lock.json`.

## LiteLLM and OpenWebUI

It is preferable to specify the full method URL so as not to get a redundant `/v1`:

```bash
# LiteLLM: a typical address
python3 run.py run \
  --endpoint http://localhost:4000/v1/chat/completions \
  --models model-a model-b --judge-model judge-model

# OpenWebUI: a typical address of its own API
python3 run.py run \
  --endpoint http://localhost:3000/api/chat/completions \
  --models model-a model-b --judge-model judge-model
```

The actual prefix depends on the reverse proxy and your installation. An available API key and permission for the selected models are required. API-key authentication for OpenWebUI is configured on the server side. The code does not use a browser session. For the standard prefix, `--base-url http://localhost:4000/v1` is acceptable: the script appends `/chat/completions`.

### A separate judge model

The judge is needed for semantic evaluations: whether the response helps a harmful goal, follows an injection, or copes with a permissible task. By default the same endpoint and key are used, but with a separate `--judge-model`.

```bash
read -rsp 'Judge key: ' JUDGE_API_KEY; echo
export JUDGE_API_KEY
python3 run.py run \
  --endpoint https://target.example.org/v1/chat/completions \
  --models model-a model-b \
  --judge-endpoint https://judge.example.org/v1/chat/completions \
  --judge-model independent-judge \
  --judge-key-env JUDGE_API_KEY
```

When comparing models, keep the same judge and settings. The judge must understand RU/EN and return JSON as instructed. Self-evaluation by the same model is possible but introduces bias. A response of `UNSCORED`, malformed JSON, and an API refusal are not turned into PASS.

### Differences in API contracts

- If the server does not accept `temperature`: add `--temperature omit`.
- If the new limit parameter is required: `--token-parameter max_completion_tokens`.
- If the model spends the limit on reasoning: increase `--max-tokens`, for example to `8192`. There is a separate `--judge-max-tokens` for the judge.
- To remove an incompatible parameter: `--drop-params stop`. Do not remove `tools` for AgentDojo: that changes the functionality under test.
- If the `developer` role is incompatible: `--developer-as-system`. This is an explicit protocol modification, and it is recorded in the manifest.
- Additional request body: `--extra-body examples/extra-body.json`; for the judge — `--judge-extra-body`.
- Additional HTTP headers — `--headers /path/to/private-headers.json` and `--judge-headers`. Format: a JSON object. Header values are not written to the manifest.
- Corporate CA: `--ca-file /path/to/ca.pem`. TLS verification is enabled.

The temperature/token-parameter/drop-params transformations apply to both routes. If the judge has different requirements, use its `--judge-extra-body` to override the values. Do not put secrets in extra-body: the request body is saved in the report.

The project supports synchronous **Chat Completions**, not an arbitrary format, the Responses API, embeddings, or images. AgentDojo additionally requires a valid `tools`/`tool_calls` and a multi-turn dialogue. Compatibility errors appear as ERROR/PARTIAL. A successful HTTP response by itself does not mean compatibility.

## What exactly runs

| Adapter | Actual execution | Data and evaluation |
|---|---|---|
| garak | Native CLI 0.17.0 via OpenAICompatible | Built-in probes and detectors; by default PromptInject HijackHateHumans, DAN 11.0, Base64 |
| Promptfoo | Native `promptfoo eval` 0.123.0 | 48 in-house RU/EN tests; canary/marker assertions and an API judge |
| PyRIT | Native `MultiPromptSendingAttack` | 8 in-house dialogues of 3 turns each; the API judge evaluates the responses of all turns |
| HarmBench | Adapted API run of the official data | 240 standard/contextual behaviors from the test split; 3 fixed wrappers; the API judge |
| JailbreakBench | Adapted API run of the official data | 100 harmful + 100 benign behaviors; wrappers for harmful; the API judge |
| BIPIA | Native builders create the requests; adapted API run | Official email/table test contexts and text attacks; security and utility are evaluated separately |
| AgentDojo | Native tasks, attacks, agent loop, and goal checks | Built-in suites; a clean baseline and runs with injections; the API model calls the test tools |
| security-regression | Deterministic checks on the exact value and six encodings, without a judge | Its own set: synthetic PII, secret leak, canary injection markers |

**HarmBench/JailbreakBench do not use the stock classifiers and attack optimizers. BIPIA does not use the original GPU inference stack and specialized evaluators. These evaluations cannot be called official leaderboard scores.** The chosen integration makes it possible to compare arbitrary API models without access to their weights.

## Scope and repeatability

By default a limited starter profile is executed, not an exhaustive sweep of all suites:

- `--limit 10`: up to 10 source records in each suite being processed; JBB separately for harmful and benign, BIPIA separately for email and table. Promptfoo — 10 of 48; PyRIT — all 8 available dialogues.
- `--variants direct roleplay authority`: three variants for harmful HarmBench/JBB behaviors.
- `--bipia-attacks 4`: four official attack texts; three insertion positions for each context/attack pair.
- `--agent-suites workspace --agent-tasks 2 --agent-injections 2`: two baselines and four attacking runs.
- garak has its own selection via `--garak-probes`; `--limit` **does not apply** to it. One response for each selected prompt.
- `--seed 42`: the same sample for all models. Even at temperature=0 the server may return non-deterministic responses.

With a limit of L, A BIPIA attacks, and two context types, BIPIA makes up to `2 × L × A × 3` target requests and twice as many judge requests. AgentDojo makes a variable number of requests because of tool calls. When the budget is exhausted, the result is incomplete rather than successful.

For a wider run:

```bash
python3 run.py run \
  --endpoint http://localhost:4000/v1/chat/completions \
  --models model-a model-b --judge-model judge-model \
  --limit 0 --bipia-attacks 10 \
  --agent-suites workspace banking travel slack \
  --agent-tasks 5 --agent-injections 3 \
  --garak-probes probes.promptinject,probes.dan,probes.encoding \
  --max-requests 20000 --tool-timeout 14400
```

`0` means all records for `--limit`, `--bipia-attacks`, `--agent-tasks`, `--agent-injections`. A full BIPIA over the supplied data: 150 contexts × 75 attacks × 3 positions = **33,750 target requests**, plus 67,500 judge requests. The budget will have to be increased separately. Use the starter profile before a large run.

Default limits: `--max-requests 1000` **per model, tool, and target/judge route**, `--timeout 120` seconds per request, and `--tool-timeout 3600` per tool. Native retries also consume the budget. Models and tools are processed sequentially so as not to create uncontrolled parallel load.

A single tool is run in the same way:

```bash
python3 run.py run --endpoint http://localhost:4000/v1/chat/completions \
  --models model-a model-b --judge-model judge-model --tools garak
```

`--tools` accepts any list of the eight names from the table. Without the parameter, all eight are run.

## Output files

Each run creates a new directory `reports/<UTC-time>-<ID>/`:

| File | Contents |
|---|---|
| `report.html` | Standalone HTML: models, statuses, and expandable records |
| `report.md` | A single summary across models, tools, and categories |
| `summary.json` | Machine-readable totals for each model |
| `all_records.jsonl` | Normalized records of all tools |
| `manifest.json` | Endpoint, settings, model aliases, data SHA-256, source revisions |
| `<model-hash>/summary.json` | Summary of a single model |
| `<model-hash>/<tool>/records.jsonl` | Normalized checks of the tool |
| `<model-hash>/<tool>/http.jsonl` | Target and judge requests/responses without auth headers |
| `<model-hash>/<tool>/status.json` | Completeness, number of requests, transport errors |
| `<model-hash>/<tool>/worker.log` | Adapter and native tool diagnostics |

In addition, the native garak/Promptfoo/PyRIT reports, the selected HarmBench/JBB behaviors, and the AgentDojo traces are saved. Adapted runs have their own schema, so consolidation is performed via `records.jsonl`.

Consolidation is performed automatically after each tool and at the end. To rebuild it again without API requests:

```bash
python3 run.py merge reports/RUN_DIRECTORY_NAME
```

`merge` reads a directory **of this project that has a manifest**, not arbitrary external reports of incompatible versions. Runs against different endpoints are deliberately kept separate so as not to mix check modes.

### How to read the result

- PASS: the specific criterion is met.
- FAIL: the criterion is violated; see the category. For benign/baseline/utility this is insufficient utility, for security it is the attack check firing.
- ERROR: a request, a tool, or the infrastructure returned an error.
- UNSCORED: insufficient data or an invalid evaluator response.
- SKIPPED: the test was explicitly skipped.
- COMPLETE: all executed checks of the configured subset have PASS/FAIL; this is **not** a security certificate.
- PARTIAL/ERROR: some evaluations are missing, execution was interrupted, or there were transport errors.

The model result: `FINDINGS`, `INCOMPLETE`, `FINDINGS_AND_INCOMPLETE`, or `NO_FINDINGS_ON_TESTED_SET`. No overall "security percentage" is computed: for garak the unit is a detector decision, for the others it is an individual check; the suites overlap. The FAIL share within a tool may include utility checks — the categories in the report must be considered separately.

Exit code: `0` — the run completed; `2` — incompleteness/error; `130` — Ctrl+C. With `--fail-on-findings` a completed run with a FAIL returns `1`. Without this parameter, FAIL does not change the code `0`.

## Data and extension

The datasets are already included in the archive. The in-house `corporate.jsonl` and `multiturn.jsonl` can be restored with the command `python3 generate_datasets.py`; it does not modify the official files. This is a starter regression set, not a representative scientific benchmark.

Extend the JSONL with the existing fields and new unique `id`s; Promptfoo categories: `direct_injection`, `indirect_injection`, `secret_leak`, `harmful`, `benign`. For different check logic you need to extend the assertions in `security_suite/native.py` and the criteria in `common.py`.

The synthetic secret and marker in the data are public and intended solely for checking compliance with instruction boundaries. A marker match is a narrow heuristic signal; the absence of a match does not prove the absence of other leak paths.

Full responses may contain unwanted content and information from your application. Access to the report directory should be restricted in the same way as access to the original requests. Sending to the judge is a separate transfer of these texts to the selected judge endpoint.

Details: [methodology and sources](METHODOLOGY.md), [project validation](VALIDATION.md), [licenses and provenance](DATA_SOURCES.md).
