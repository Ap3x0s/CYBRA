# Project health verification

> Russian version: [docs/ru/VALIDATION.md](ru/VALIDATION.md).

Date: 2026-09-15. Verified locally: Python 3.12.14, Node.js 24.19.0, npm 11.9.0, uv 0.12.11, Linux x86_64. The installed Python dependencies are pinned in `locks/`; the Node dependencies — in `package-lock.json`. The source versions of garak, PyRIT and AgentDojo are installed and imported, and the Promptfoo CLI has been executed.

## Checks performed

1. Nine unittest checks of the transport, reports and scoring: local relay authorization, separate target/judge budgets, the model alias, empty/truncated responses, invalid judge JSON/schema, a missing tool, a model/tool mismatch in the report, HTML escaping and a safe directory name. All passed.
2. All seven real adapters were run sequentially against the list of two API aliases `safe leaky` on the local test server. For each alias, seven COMPLETE statuses and consolidated reports were obtained.
3. An additional run of the standard three garak probes: 513 target requests and 770 detector decisions per alias. Both aliases completed.
4. All 48 author's tests were executed by native Promptfoo for each alias. The `leaky` server returns the secret and the marker: the expected 32 FAILs on marker/canary checks and 16 PASSes from the test judge were obtained. The JSON and JUnit export was read automatically.
5. BIPIA was checked against all 150 supplied contexts, with one of the official attack texts in three positions: 450 target requests, 900 judge requests and 900 normalized security/utility checks per alias. Both aliases completed.

**This is a check of execution and consolidation, not an assessment of the security of real models.** The test server always returns predefined responses; the test judge always answers PASS with an explicit fixture label. In particular, the name `safe` is not an attestation result, and a PASS on harmful/benign/BIPIA in these runs has no substantive value. With AgentDojo, the stub model does not perform real multi-step tasks; goal checks may record a baseline failure, which is expected.

The real LiteLLM/OpenWebUI and your models were not verified: addresses and keys were not provided. The full attack spaces, the real OpenWebUI external tools and all installation platforms were not verified either. The pinned environments were created during development; a clean reinstall from the final ZIP was not performed.

## Reproducing the verification without access to your models

```bash
python3 run.py setup
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 tests/integration.py
```

The integration test brings up the local server itself and calls the real adapters. It does not require target/judge keys. By default it uses a small sample, one garak probe and two model aliases. The dependencies must be installed beforehand.

To repeat the additional run:

```bash
python3 tests/integration.py \
  --tools garak promptfoo bipia --models safe leaky --limit 0 \
  --garak-probes probes.promptinject.HijackHateHumans,probes.dan.Dan_11_0,probes.encoding.InjectBase64 \
  --out validation-final
```

In the integration test, BIPIA is limited to one attack, and AgentDojo to one user task and one injection task. The working budgets and the sample of the main `run.py` are described in the README.
