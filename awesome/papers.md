# Papers

> Verified 2026-10-20.

## Foundational

- [Attention Is All You Need](https://arxiv.org/abs/1706.03762) — The transformer paper. Read once; you'll cite it forever.
- [Language Models are Few-Shot Learners (GPT-3)](https://arxiv.org/abs/2005.14165) — Established in-context learning.
- [Training Language Models to Follow Instructions (InstructGPT)](https://arxiv.org/abs/2203.02155) — The RLHF paper that became ChatGPT.
- [Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks](https://arxiv.org/abs/2005.11401) — The original RAG paper.
- [Direct Preference Optimization](https://arxiv.org/abs/2305.18290) — DPO; alignment without a reward model.
- [DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via Reinforcement Learning](https://arxiv.org/abs/2501.12948) — The paper that made RL-trained reasoning models an open commodity; also the pure-RL training recipe.
- [Kimi K2: Open Agentic Intelligence](https://arxiv.org/abs/2507.20534) — A 1T-parameter open-weight MoE built for tool use and agentic workflows.

## Reasoning & test-time compute

- [Scaling LLM Test-Time Compute Optimally Can be More Effective than Scaling Model Parameters](https://arxiv.org/abs/2408.03314) — The case for spending compute at inference time; the shift behind o-series and thinking models.
- [s1: Simple Test-time Scaling](https://arxiv.org/abs/2501.19393) — Budget forcing: 1K samples, 16x compute, near-frontier math reasoning.

## Evals

- [Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena](https://arxiv.org/abs/2306.05685) — The LLM-as-judge paper and its biases.
- [Lost in the Middle](https://arxiv.org/abs/2307.03172) — Long-context recall degrades in the middle.

## RAG

- [Corrective Retrieval Augmented Generation (CRAG)](https://arxiv.org/abs/2401.15884) — Self-correcting retrieval.
- [GraphRAG](https://arxiv.org/abs/2404.16130) — Microsoft's graph-based RAG.
- [Contextual Retrieval (Anthropic)](https://www.anthropic.com/news/contextual-retrieval) — Context-prefix chunking.

## Agents

- [ReAct: Synergizing Reasoning and Acting](https://arxiv.org/abs/2210.03629) — The original agent loop paper.
- [Reflexion](https://arxiv.org/abs/2303.11366) — Self-reflection for agents.
- [Building Effective Agents (Anthropic)](https://www.anthropic.com/research/building-effective-agents) — Not a paper, but the field's most-cited engineering essay on workflows vs agents and when not to build one.
- [Model Context Protocol specification](https://modelcontextprotocol.io/) — The vendor-neutral tool-interop standard; read alongside the spec changelog.
- [A2A (Agent2Agent) Protocol](https://a2a-protocol.org/) — Linux Foundation-governed agent-to-agent interop protocol; the complement to MCP for cross-vendor agents.

## Safety

- [Not what you've signed up for (indirect prompt injection)](https://arxiv.org/abs/2302.12173) — The indirect injection paper.
- [Universal and Transferable Adversarial Attacks](https://arxiv.org/abs/2307.15043) — Universal jailbreaks.

## Inference

- [Efficient Memory Management for LLMs (PagedAttention)](https://arxiv.org/abs/2309.06180) — The vLLM paper.
- [FlashAttention-2](https://arxiv.org/abs/2307.08691) — Faster attention.

## Fine-tuning

- [LoRA](https://arxiv.org/abs/2106.09685) — Low-rank adaptation.
- [QLoRA](https://arxiv.org/abs/2305.14314) — 4-bit quantized LoRA.
- [Mixtral of Experts](https://arxiv.org/abs/2401.04088) — MoE in practice.
