# Project 08: Cost-Optimized Routing Proxy

> **Difficulty:** INT · **Skill demonstrated:** Agent economics, prompt caching, cascade · **Status:** 🚧 Skeleton

## Problem

Build an OpenAI-compatible proxy that routes queries by complexity to minimize cost while preserving quality.

## Architecture

```mermaid
graph LR
    Input[Input] --> Agent[Agent pipeline]
    Agent --> Eval[Evals]
    Eval --> Output[Output]
```

Incoming request -> classifier (small model) -> route to GPT-6 Luna / GPT-6.1 Sol / thinking tier -> response + cost telemetry.

## Stack

- Python
- FastAPI
- openai
- anthropic
- redis
- prometheus

## Getting started

```bash
# Install
make install

# Run
make run

# Run tests
make test

# Run evals
make eval
```

## Evals

This project ships with an eval harness (runner + a golden-dataset placeholder to fill with real cases). Eval metrics:

- `cost_per_1k_requests`
- `quality_score`
- `routing_accuracy`

The `make eval` command runs the eval suite and prints a report. Once the golden set is real, wire it into CI and gate merges on it.

## Project structure

```text
08-cost-optimized-routing-proxy/
├── README.md              # this file
├── pyproject.toml         # dependencies
├── Makefile               # install/run/test/eval targets
├── DEPLOYMENT.md          # how to deploy
├── src/
│   └── __init__.py
├── tests/
│   └── test_smoke.py
├── evals/
│   ├── golden.jsonl       # golden dataset
│   ├── eval_runner.py     # eval runner
│   └── README.md
└── .gitignore
```

## What this project demonstrates

This is a portfolio project. When complete, it should clearly demonstrate:
- Agent economics, prompt caching, cascade
- Production concerns: cost, latency, failure modes, security
- Evals: golden dataset + automated runner
- Tests: at least unit + integration
- Deployment: Dockerized, one-command deploy

## Next steps

See `DEPLOYMENT.md` for deployment instructions and `evals/README.md` for the eval methodology.
