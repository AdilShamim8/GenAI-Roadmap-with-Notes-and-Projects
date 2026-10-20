# Project 02: Hybrid RAG Over a Notion Workspace

> **Difficulty:** BEG · **Skill demonstrated:** Chunking, hybrid search, reranking, citations · **Status:** 🚧 Skeleton

## Problem

Build a RAG system over a real Notion workspace with hybrid search (vector + BM25), reranking, and source citations.

## Architecture

```mermaid
graph LR
    Input[Input] --> Agent[Agent pipeline]
    Agent --> Eval[Evals]
    Eval --> Output[Output]
```

Notion API -> chunker -> embedder -> pgvector + BM25 index -> query -> hybrid search -> reranker -> LLM with citations.

## Stack

- Python
- pgvector
- BGE-M3
- BGE Reranker
- FastAPI
- pytest
- ragas

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

- `faithfulness`
- `answer_relevancy`
- `context_precision`
- `context_recall`

The `make eval` command runs the eval suite and prints a report. Once the golden set is real, wire it into CI and gate merges on it.

## Project structure

```text
02-hybrid-rag-over-notion/
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
- Chunking, hybrid search, reranking, citations
- Production concerns: cost, latency, failure modes, security
- Evals: golden dataset + automated runner
- Tests: at least unit + integration
- Deployment: Dockerized, one-command deploy

## Next steps

See `DEPLOYMENT.md` for deployment instructions and `evals/README.md` for the eval methodology.
