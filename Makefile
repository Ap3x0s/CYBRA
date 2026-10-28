
SHELL := /bin/bash

# without dojo
.PNONY: all
all:
	@set -a; \
	source .env; \
	set +a; \
	PROMPTFOO_DISABLE_REDTEAM_REMOTE_GENERATION=true \
	python run.py run \
		--base-url "$$TARGET_BASE_URL" \
		--models $(models) \
		--judge-model "$$JUDGE_MODEL" \
		--tools harmbench jailbreakbench pyrit bipia promptfoo security-regression \
		--limit 20 \
		--variants direct \
		--bipia-tasks email \
		--bipia-attacks 1 \
		--max-requests 400 \
		--max-tokens 2048 \
		--judge-max-tokens 1024 \
		--timeout 300 \
		--tool-timeout 14400 \
		--insecure-skip-tls-verify \
		--out reports/reports-all-no-dojo

garak-all:
	@set -a; \
	source .env; \
	set +a; \
	PROMPTFOO_DISABLE_REDTEAM_REMOTE_GENERATION=true \
	python run.py run \
		--base-url "$$TARGET_BASE_URL" \
		--models $(models) \
		--judge-model "$$JUDGE_MODEL" \
		--tools garak \
		--garak-probes 'probes.dan.Dan_11_0,probes.promptinject.HijackHateHumans,probes.promptinject.HijackKillHumans,probes.encoding.InjectBase64,probes.encoding.InjectHex,probes.encoding.InjectROT13' \
		--max-tokens 2048 \
		--judge-max-tokens 1024 \
		--token-parameter max_completion_tokens \
		--max-requests 20 \
		--timeout 300 \
		--tool-timeout 14400 \
		--insecure-skip-tls-verify \
		--out reports/reports-garak-all

garak:
	python run.py run \
		--endpoint $(API_ENDPOINT) \
		--models $(models) \
		--judge-model $(JUDGE_MODEL) \
		--tools garak \
		--garak-probes probes.dan.Dan_11_0 \
		--max-tokens 2048 \
		--judge-max-tokens 1024 \
		--token-parameter max_completion_tokens \
		--max-requests 100 \
		--timeout 300 \
		--tool-timeout 14400 \
		--insecure-skip-tls-verify \
		--out reports/reports-garak

promptfoo:
	python run.py run \
		--endpoint $(API_ENDPOINT) \
		--models $(models) \
		--judge-model $(JUDGE_MODEL) \
		--tools promptfoo \
		--limit 1 \
		--max-requests 20 \
		--max-tokens 2048 \
		--judge-max-tokens 1024 \
		--token-parameter max_completion_tokens \
		--timeout 300 \
		--tool-timeout 14400 \
		--insecure-skip-tls-verify \
		--out reports/reports-promptfoo

# good
harmbench:
	python run.py run \
		--endpoint $(API_ENDPOINT) \
		--models $(models) \
		--judge-model $(JUDGE_MODEL) \
		--tools harmbench \
		--limit 10 \
		--variants direct roleplay authority\
		--max-requests 100 \
		--max-tokens 2048 \
		--judge-max-tokens 1024 \
		--timeout 1000 \
		--tool-timeout 14400 \
		--insecure-skip-tls-verify \
		--out reports/reports-harmbench-smoke

harmbench-test:
	@set -a; \
	source .env; \
	set +a; \
	PROMPTFOO_DISABLE_REDTEAM_REMOTE_GENERATION=true \
	python run.py run \
		--base-url "$$TARGET_BASE_URL" \
		--models $(models) \
		--judge-model "$$JUDGE_MODEL" \
		--tools harmbench \
		--limit 1 \
		--variants direct \
		--max-requests 20 \
		--max-tokens 2048 \
		--judge-max-tokens 1024 \
		--timeout 1000 \
		--tool-timeout 14400 \
		--insecure-skip-tls-verify \
		--out reports/reports-harmbench-smoke

#good
jailbreakbench:
	python run.py run \
		--endpoint $(API_ENDPOINT) \
		--models $(models) \
		--judge-model $(JUDGE_MODEL) \
		--tools jailbreakbench \
		--limit 20 \
		--variants direct \
		--max-tokens 2048 \
		--judge-max-tokens 1024 \
		--max-requests 100 \
		--timeout 300 \
		--tool-timeout 14400 \
		--insecure-skip-tls-verify \
		--out reports/reports-jbb-limit1

#good
pyrit:
	python run.py run \
		--endpoint $(API_ENDPOINT) \
		--models $(models) \
		--judge-model $(JUDGE_MODEL) \
		--tools pyrit \
		--limit 20 \
		--max-tokens 2048 \
		--judge-max-tokens 1024 \
		--token-parameter max_completion_tokens \
		--max-requests 100 \
		--timeout 300 \
		--tool-timeout 14400 \
		--insecure-skip-tls-verify \
		--out reports/reports-pyrit-limit1

#good
bipia:
	python run.py run \
		--endpoint $(API_ENDPOINT) \
		--models $(models) \
		--judge-model $(JUDGE_MODEL) \
		--tools bipia \
		--limit 1 \
		--bipia-tasks email \
		--bipia-attacks 1 \
		--max-tokens 2048 \
		--judge-max-tokens 1024 \
		--token-parameter max_completion_tokens \
		--max-requests 200 \
		--timeout 300 \
		--tool-timeout 43200 \
		--insecure-skip-tls-verify \
		--out reports/reports-bipia-limit1

#good
dojo:
	python run.py run \
		--endpoint $(API_ENDPOINT) \
		--models $(models) \
		--judge-model $(JUDGE_MODEL) \
		--tools agentdojo \
		--agent-suites workspace \
		--agent-tasks 5 \
		--agent-injections 3 \
		--agent-steps 20 \
		--agent-attack important_instructions \
		--max-tokens 2048 \
		--token-parameter max_completion_tokens \
		--max-requests 1000 \
		--timeout 300 \
		--tool-timeout 43200 \
		--insecure-skip-tls-verify \
		--out reports/reports-agentdojo-limit1

security:
	@set -a; \
	source .env; \
	set +a; \
	PROMPTFOO_DISABLE_REDTEAM_REMOTE_GENERATION=true \
	python run.py run \
		--base-url "$$TARGET_BASE_URL" \
		--models $(models) \
		--judge-model "$$JUDGE_MODEL" \
		--tools security-regression \
		--max-tokens 2048 \
		--token-parameter max_completion_tokens \
		--max-requests 1000 \
		--timeout 300 \
		--limit 1 \
		--tool-timeout 43200 \
		--insecure-skip-tls-verify \
		--out reports/reports-security