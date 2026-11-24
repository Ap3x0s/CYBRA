# CYBRA documentation

> Russian version: [docs/ru/README.md](ru/README.md).

Primary documentation. Russian copies live in [docs/ru/](ru/README.md) and are
maintained in parallel.

| File | Contents |
|---|---|
| [METHODOLOGY.md](METHODOLOGY.md) | Full methodology: properties, benchmarks, 11 metrics, verdicts, limits |
| [SUITE.md](SUITE.md) | Running the suite without the console: CLI, profiles, artifacts |
| [metrics.md](metrics.md) | Metric dictionary with formulas |
| [metrics-research.md](metrics-research.md) | Research behind the safety and availability metrics |
| [DATA_SOURCES.md](DATA_SOURCES.md) | Data sources and their licences |
| [VALIDATION-CYBRA.md](VALIDATION-CYBRA.md) | What is verified and what is not |
| [VALIDATION.md](VALIDATION.md) | Validation against real models |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Delivery and deployment: CI/CD, image, environment, state |
| [OFFLINE.md](OFFLINE.md) | Installing the heavy benchmarks on a machine with no internet: bundle, transfer, verification |

Project README: [README.md](../README.md) · Russian: [README.ru.md](../README.ru.md).

## Screenshots

Images in `media/` are captured with the English interface. Russian versions are
in [docs/ru/media/](ru/media/).

## Benchmarks vs metrics

A common point of confusion: **8 benchmarks** are the tools that generate test
cases and verdicts (`security_suite/common.py`, constant `TOOLS`); **11 metrics**
are the formulas computed over those verdicts (`backend/cybra/metrics.py`,
constant `CATALOG`). Both counts are correct and mean different things.
