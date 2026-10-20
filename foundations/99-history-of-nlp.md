# History of NLP (Context Only)

> **Level:** BEG · **Last verified:** 2026-10-20 · **Sources:** [Attention Is All You Need](https://arxiv.org/abs/1706.03762), [InstructGPT](https://arxiv.org/abs/2203.02155)

## Why this is here, briefly

You will hear "RNN", "LSTM", "Word2Vec", and "BERT" in interviews and papers. You don't need to implement any of them in 2026, but you should know what they solved and why transformers replaced them.

## The 60-second timeline

| Era | Dominant technique | Why it died |
|------|-------------------|-------------|
| ~2010 | n-grams, TF-IDF | No semantics; sparse; O(V) features |
| ~2013 | Word2Vec, GloVe, FastText | Static embeddings; same word, same vector regardless of context |
| ~2014 | RNN, LSTM, GRU | Sequential → can't parallelize; vanishing gradients at long ranges |
| ~2017 | Transformer | Parallel; long-range attention; scales |
| ~2018 | BERT, GPT | Pretrain + fine-tune; transfer learning works |
| ~2020 | GPT-3 | Scale + in-context learning; few-shot works |
| ~2022 | ChatGPT / InstructGPT | RLHF makes models usable in conversation |
| ~2024 | Multimodal frontier models; open-weight surge (Mixtral, Llama 3, Qwen) | N/A — current |
| ~2025 | Reasoning as a product: o-series, DeepSeek-R1, thinking models; agents + MCP (Nov 2024) standardize tool interop | N/A — current |
| ~2026 | Agentic default: GPT-6 family, Claude 5.5, Gemini 3.x, DeepSeek V4; A2A for agent interop; context engineering as a discipline | N/A — current |

## What to actually remember

- **Attention** replaced recurrence. That's the only architectural shift that matters for your day-to-day.
- **Word2Vec** is the ancestor of embeddings. You'll still see "embeddings" everywhere; just don't use Word2Vec.
- **BERT** is bidirectional encoder; GPT is autoregressive decoder. Modern chat models are GPT-style.
- **RLHF** turned text generators into assistants; RL post-training (R1-style) then made reasoning a trainable skill.
- **The retrieval lineage** — TF-IDF/BM25 → dense embeddings → hybrid — is the direct ancestor of modern RAG; the old sparse tricks never died, they got recombined.
- **Protocols recur**: MCP (2024) did for tools what HTTP did for documents; A2A (2025) is trying to do it for agents. When a layer standardizes, build on it.

## What you can safely skip

- Implementing an LSTM from scratch.
- The BERT vs GPT benchmarking era.
- Any paper on attention variants before 2020 unless you do research.

## References

- [The Illustrated Word2Vec — Jay Alammar](https://jalammar.github.io/illustrated-word2vec/) — verified 2026-10-20
- [Attention Is All You Need](https://arxiv.org/abs/1706.03762) — verified 2026-10-20
- [Illustrated BERT](https://jalammar.github.io/illustrated-bert/) — verified 2026-10-20
