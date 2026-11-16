# CYBRA Metrics: What to Measure So an MLSec Specialist Gets an Answer

> Russian version: [docs/ru/metrics-research.md](ru/metrics-research.md).

This document answers the lead's question: which metrics to add and how to
consolidate the existing ones. Nothing in the code changes — this is a theoretical study.

Date: 13.11.2026. Based on the MLCommons AILuminate, HarmBench,
JailbreakBench, AgentDojo, XSTest standards and on agentic evaluation practice.

---

## 1. The Main Finding of the Study

One fact outweighs everything else:

> "0% ASR in a model that fails XSTest is not a safe model,
> it is a broken model."

**Refusing everything** yields ideal safety figures and zero
utility. Formally "safe", in practice unusable. So any
claim of safety must be accompanied by the number of over-refusals
on a control set of benign requests.

This is not an opinion but the industry's position: the same logic is in MLCommons, XSTest, OR-Bench.

**What this means for us.** CYBRA currently shows 8 metrics, of which
`refusal_rate` and `benign_utility_rate` are the only pair that hints at
this balance. But they live apart, in one table row, and do not add up
to an answer to "is the model safe or does it just reject everything".

Hence the main proposal — **to consolidate them into a single entity**.

---

## 2. What Checked Out in the Current Catalog

Before adding anything, a note: some of our decisions matched the industry.

| Our decision | Standard | Match |
|---|---|---|
| `coverage` — share of records with a verdict | MLCommons requires recording the completeness of the run | ✅ |
| `unscored_rate` separate from `failed_check_rate` | ERROR/UNSCORED are not counted as PASS | ✅ |
| Refusing a single safety percentage | AILuminate does not collapse different taxonomies into a scalar | ✅ |
| `attack_success_rate` over harmful behaviours only | HarmBench counts success over harmful behaviours | ✅ |
| garak's unit is the detector decision, not the case | garak's unit is different by nature | ✅ |

**Conclusion:** the foundation is right. The problem is not that we measure the wrong thing,
but that we measure **in parts** and do not assemble it into a decision.

---

## 3. What to Measure According to the Standards

### 3.1 Resilience Gap (MLCommons) — metric #1

The industry's key metric, which we do not have.

**Formula:**
```
Resilience Gap = Safety(baseline) − Safety(under attack)
```

where Safety is the share of non-violating responses to the same set of harmful
requests presented twice: as is and in an attacking wrapper.

Example from the MLCommons documentation: a model gives 80% safe responses to
direct requests and 60% under jailbreak. The gap = 20 percentage points.

**Published v0.5 results** (39 text models, 1200 prompts,
12 hazard categories): 35 of 39 models scored worse under
attack. The average drop is **19.81 p.p.** for text models and
**25.27 p.p.** for multimodal ones. The drop is smeared across all categories,
and different attack tactics yield very different effectiveness.

In other words: in a typical model under attack roughly one fifth of the
protection falls apart. This is the baseline against which our own results are worth comparing.

**Why this is better than our `attack_success_rate`.** Our ASR shows "how many
attacks succeeded" but does not answer the question "how much worse the model is under attack
than without one". The difference is fundamental:

- a model with 60% ASR on direct requests and 60% under attack is **resilient**:
  the attack broke nothing, the weakness is innate;
- a model with 5% on direct and 55% under attack is **fragile**: the protection falls apart from
  the wrapper.

A single ASR does not distinguish these two cases. Resilience Gap does.

**What is needed for implementation.** A paired run: the same harmful set in two
variants — native and attacking. We already have `variants: ['direct']` in
the run spec, so the groundwork is there, but the second variant is not used.

**Cost:** ×2 requests per harmful set. For us this is tangible, but it is precisely
this metric that turns "ASR 32.4%" into a meaningful judgement.

---

### 3.1.1 ISO/IEC 42001 Alignment — an Unexpected Finding

The official MLCommons FAQ states outright: the benchmark is designed for
integration with AI management systems under **ISO/IEC 42001** and provides four
artefacts for audit:

- datasets — data sets;
- configurations — run configurations;
- run logs — execution logs;
- metrics for risk assessment — metrics for risk assessment.

**Our file contract already contains all four.**

| ISO requirement | What we have | File |
|---|---|---|
| datasets | dataset versions with revisions | `sources.lock.json`, `datasets/` |
| configurations | run profile, models, limits | `manifest.json` |
| run logs | all requests and responses with timings | `http.jsonl`, `records.jsonl` |
| metrics | aggregates and verdicts | `summary.json` |

This is no accident: the "supervisor reads the file
contract" architecture yields exactly the traceability the standard requires.

**Practical meaning:** a CYBRA run can be presented as audit
evidence, not merely as an internal report. For an MLSec specialist this is
the answer to the question "what do I show compliance".

**What is missing for full alignment:** an explicit record of the version
of the standard and the threat model in the report itself. Right now it has run_id and mode but
no line saying "assessed under methodology X, version Y".

### 3.2 Over-refusal Rate (XSTest, OR-Bench) — metric #2

**Formula:**
```
Over-refusal = refusals on benign requests / all benign requests
```

We cover this partly with `refusal_rate`, but there is a gap in the set itself.

XSTest is built on **traps**: requests with dangerous words in a benign
context — "how to kill a process", "where to buy a cooking knife", "how to crack
nuts". A well-calibrated model answers. An over-cautious one refuses.

**What we do not have.** Our benign sets (JBB benign, BIPIA utility) are
ordinary questions. They do not test **calibration on trigger words**.
A model can pass them and still fail on "how to kill a process".

**Proposal:** a separate class of cases `benign_trigger` — benign requests
with dangerous vocabulary. The metric is the same, only the set changes.

---

### 3.3 Utility under Attack — metric #3

**Formula:**
```
Utility drop = Utility(without attack) − Utility(under injection)
```

It answers: "how much does the protection get in the way of the work?"

BIPIA has a `utility` category, and we do count it (`benign_utility_rate`
gives 45.5% on the last run). But the metric mixes two different questions:
"is it useful at all" and "how much the injection gets in the way". The second is an engineering
indicator of protection quality, and it matters more for acceptance.

**Separation:** `benign_utility_rate` — baseline utility,
`utility_under_attack` — utility under an active injection. The difference between them
is the price of protection.

---

### 3.4 Agentic Metrics (AgentDojo) — metric #4

For agents the classic ASR is incomplete. The industry counts three numbers:

| Metric | What it measures | Ours |
|---|---|---|
| **Targeted ASR** | whether the attacker reached their goal | `workspace/attack` → FAIL |
| **Benign utility** | whether the agent performs legitimate tasks | `workspace/baseline` |
| **False positive rate** | whether the protection blocks legitimate actions | we do not count it |

The third is our gap. An agent with an external filter can repel all attacks and
break normal operation along the way. We will only see "attacks repelled" and conclude
that all is well.

The data exists: `workspace/baseline` is exactly the control set of legitimate
tasks. Only the metric `agent_false_block_rate` is needed.

---

### 3.5 Judge Agreement — metric #5

MLCommons honestly publishes the quality of its judge: **17.1% false safe rate,
29.7% false unsafe rate**. That is, even the reference evaluator errs in roughly
a third of cases.

We judge with an LLM judge and **do not measure how far it can be trusted**. At the same time
our numbers go into reports as facts.

**Proposal:** `judge_agreement` — the share of cases where the judge agreed with
human labelling on a control sample. It requires manual labelling of
~50 cases, then it is reused. Without this number the ASR is the judge's
result, not the model's, and the report should say so explicitly.

---

## 4. How to Consolidate the Existing Ones: the "Profile" Idea

Right now the 8 metrics are a flat list. An MLSec specialist looks at them and does not
get an answer to the question for which the run was launched.

**Proposal:** group them into three dimensions, the way mature
platforms do.

### Security
```
Resilience Gap          ← the main one, replaces the single ASR
Attack Success Rate     ← keep as a raw indicator
Injection Follow Rate
Leak Rate
```

### Availability / Utility
```
Benign Utility Rate
Over-refusal Rate
Utility under Attack
Agent False Block Rate
```

### Trust in the Numbers
```
Coverage
Unscored Rate
Judge Agreement
```

The point of the grouping: **security and availability trade off against each other**, and
looking at them separately means not seeing the trade-off. The third group answers
the question "can the first two be trusted".

### Visualisation — a Plane, not a Chart

The key idea: ASR and over-refusal should be shown **as a point on the plane
(ASR, FRR)**, not as two separate numbers.

```
        high FRR
             │
   broken    │
   (rejects  │
   everything│
   ──────────┼──────────
             │  good zone
             │
             └──────────── high ASR
```

A model in the upper left corner is useless. In the lower right it is dangerous. The goal is the
lower left corner. One movement of the point across the plane tells more than
a table of eight rows.

This is what is missing right now and what will give a "professional view" of the run.

---

## 5. What NOT to Do

The research also suggests the opposite — what to avoid.

**Do not collapse everything into a single safety percentage.** MLCommons, despite having a
standard, does not publish a "score of 87 out of 100". The reason: different taxonomies
are incomparable, and a single number creates false confidence. Our decision not to
compute a single percentage is **correct and matches the industry**.

**Do not compare tools against each other.** With garak the unit is the
detector decision, with the others it is the case. We have already stipulated this, and it is right.

**Do not build a ranking "model X is safer than model Y".** Without a fixed
attack profile and data set it is meaningless.

**Do not confuse "no findings" with "safe".** `NO_FINDINGS_ON_TESTED_SET` is the
correct wording. We already have it.

---

## 6. Priorities

If done one at a time, this is the order.

| # | Metric | Value | Cost |
|---|---|---|---|
| 1 | **Resilience Gap** | The industry's main metric; answers "is the protection fragile" | ×2 harmful runs |
| 2 | **The ASR/FRR plane** | One movement instead of a table | Frontend only |
| 3 | **Over-refusal on trigger words** | Catches the over-caution we do not see | A new case set |
| 4 | **Utility under Attack** | The price of protection in utility | Already counted, a formula is needed |
| 5 | **Agent False Block Rate** | A gap in agentic evaluation | The data exists |
| 6 | **Judge Agreement** | The honesty of the numbers themselves | ~50 manual labels |

The first two give the most with the least work: Resilience Gap is essentially
a second run of the same set, and the plane is pure visualisation of the numbers
we already have.

---

## 7. Honest Caveats

**The judge errs.** 17.1% false safe rate and 29.7% false unsafe rate are the
published figures of the MLCommons reference evaluator. Our numbers must be read
as "the result of an LLM judge", not as measured truth.

Moreover MLCommons itself honestly notes: in v0.5 "evaluator errors are not fit
for decisions with a high cost of error". We work with a judge of the same class.
Until `judge_agreement` is measured, this is an unknown quantity — and in the report
it is more honest to write "by the judge's assessment" than "ASR = 32%".

**A separate asymmetry worth knowing:** false unsafe (29.7%) is twice
as high as false safe (17.1%). That is, the judge more often mistakenly recognises a response
as DANGEROUS than as safe. So our ASR figures are more likely overstated than
understated — this matters more for interpretation than it seems.

**Resilience Gap requires paired runs.** Without a baseline run on the same
set it is not computed. We have `variants: ['direct']`, there is no second variant.

**The sample is small.** At limit=8 the statistical error is huge. The metrics
are fit for comparing configurations but not for conclusions that "the model is safe".

**One model ≠ a system.** We test the model through an API. Prompt injections in a
real application depend on orchestration, RAG and access rights — none of which we
see.

---

## In a Single Sentence

The foundation is right, but the metrics are counted in parts and are not assembled into a decision.
The main thing missing is **Resilience Gap** (how much an attack breaks the protection)
and **a joint view of security together with availability** (the ASR/FRR plane),
because "0% attacks" without a measurement of over-refusals means not a safe
model but a broken one.
