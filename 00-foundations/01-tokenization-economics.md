# Tokenization Economics

> **Level:** BEG · **Last verified:** 2026-10-20 · **Sources:** [tiktoken](https://github.com/openai/tiktoken), [BPE (Sennrich et al. 2016)](https://arxiv.org/abs/1508.07909), [SentencePiece](https://arxiv.org/abs/1808.06226)

## Why this matters

You are billed per token. You are rate-limited per token. Your context window is measured in tokens. Yet most engineers treat tokens as a black box. Understanding tokenization is the single fastest way to cut your API bill by 30-50% — and the fastest way to understand why the same prompt "costs more" on one provider than another, why your search-over-text code misses matches, and why reasoning models bill you for output you never see.

## Core concepts

### What is a token?

A token is a sub-word unit. "tokenization" is one word in English but ~3 tokens: `token` + `ization`. The rules are learned by a tokenizer and differ per model family. Token counts for the same text can differ 10-20% across families — and a tokenizer change silently reprices your workload (Claude Haiku 5.5's less-generous tokenizer effectively raised per-word cost ~1.25× vs Haiku 4.5).

### How BPE actually works (5-minute version)

Modern tokenizers are byte-level BPE (byte-pair encoding), trained before the model ever sees data:

1. Start from **bytes, not characters**. Byte-level BPE ([introduced with GPT-2](https://cdn.openai.com/better-language-models/language_models_are_unsupervised_multitask_learners.pdf)) means every possible input — any Unicode string, any binary-ish blob — is encodable. The `UNK` token is extinct in frontier tokenizers; you cannot produce an out-of-vocabulary input, only an expensive one.
2. **Learn merges greedily.** Count adjacent byte-pair frequencies across a huge corpus, merge the most frequent pair into a new token, repeat ~100-200K times. That merge table *is* the tokenizer: a flat, deterministic list of substitutions applied longest-match-first.
3. **Vocabularies are big and model-specific.** Roughly: OpenAI `cl100k` ~100K tokens (GPT-3.5/4 era), `o200k` ~200K (GPT-4o and later, still the family for GPT-5.x/6), Llama 3 128K, Gemma 256K. Bigger vocab = shorter sequences for common text (especially non-English) but a bigger embedding table — see the self-hosting math below.

Anthropic and Google use SentencePiece-family tokenizers ([Kudo & Richardson 2018](https://arxiv.org/abs/1808.06226)) — same subword idea, trained on raw text with a lossless reversible normalization, and the byte-fallback variant has the same no-UNK property. What differs in practice is *what the merges learned on*, which is why per-family counts differ by 10-20% on identical text.

### Token counts are not character counts

| Text | Characters | GPT-style tokens | Claude-style tokens |
|------|------------|------------------|---------------------|
| `Hello, world!` | 13 | 4 | 4 |
| `オープンソース` (5 chars) | 5 | ~7 | ~6 |
| `def fibonacci(n):` | 16 | 6 | 6 |
| A 1000-word English essay | ~6000 | ~1300 | ~1300 |

The rules of thumb that survive contact with production:

- **English prose:** ~4 characters/token, ~75 words per 100 tokens. The only case where `len(text)/4` works.
- **Code:** 2.5-3.5 chars/token. Indentation whitespace, `{`, `:`, `,` each cost real tokens — pretty-printed JSON is the classic silent bloat (minifying JSON before sending can cut 20-40%).
- **CJK scripts:** often ~1 token per character or worse — Japanese/Chinese can run 2-4× the per-word cost of English on GPT-style BPE (it's English-leaning); Gemini and Claude handle CJK noticeably better.
- **Structured chat overhead:** every message carries ~3-4 structural tokens; system prompts and tool schemas are billed on every request that isn't cache-hit (see `01-llm-calling/06-prompt-caching.md`).

### The economics

If a model costs $5/1M input tokens:
- 1M English tokens ≈ 750K words ≈ a 3000-page book.
- 1K requests/day averaging 4K input tokens = $20/day = $600/month.
- Cut input by 30% via better chunking = $180/month saved.

The line item most teams discover late: **reasoning/thinking tokens are billed as output tokens** — and output runs 3-5× the input rate. A reasoning model that "thinks" for 3,000 tokens before a 200-token answer bills like a 3,200-token completion, not a 200-token one. Budget evals and production traffic accordingly (thinking budgets/`effort` controls exist precisely to cap this — see `02-context-engineering/05-extended-thinking-models.md`).

## Code: count tokens correctly

```python
import tiktoken

enc = tiktoken.encoding_for_model("gpt-4o")  # o200k_base; GPT-5.x/6 use the same family
enc = tiktoken.encoding_for_model("gpt-5")     # or name the model directly
text = "Tokenization matters more than you think."
print(len(enc.encode(text)))  # ~7

# Per-message overhead in chat APIs
def chat_tokens(messages):
    base = 3  # every message has ~3 tokens of structural overhead
    return sum(base + len(enc.encode(m["content"])) for m in messages)

# Inspect what the tokenizer actually did — the debugging step everyone skips
for tok in enc.encode("Mississippiless"):
    print(repr(enc.decode([tok])))
```

For Anthropic there is no public local tokenizer — use the `count_tokens` API (free, exact) rather than estimating. For Gemini, `model.count_tokens(...)` in the SDK does the same.

## Production concerns

- **Latency:** More tokens = slower prefill = slower first-token latency. Prefill is parallel but still ~2·N FLOPs per token (see `00-transformers-deep-dive.md`); a 200K-token system prompt is seconds of prefill on the provider side — which is what prompt caching exists to skip.
- **Cost:** Tokens you can prune are tokens you don't pay for — on both sides of the request.
- **Search/matching breaks on token boundaries.** "Mississippi" may be 2-3 tokens; substring search, redaction filters, and regex guards over *text* can miss payloads that span merges. Token-level redaction (find the token ids, redact those) is the robust pattern.
- **Failure modes:** Whitespace, code indentation, and non-ASCII bloat token counts invisibly.
- **Security:** Prompt-injection payloads exploit tokenization quirks — homoglyphs (Cyrillic 'а' vs Latin 'a'), zero-width chars, and token-boundary smuggling that defeats naive string blocklists. Normalize and re-encode before filtering (see `02-context-engineering/04-prompt-injection-defense.md`).
- **Self-hosting vocabulary math:** the embedding table costs `vocab × hidden_dim × 2` bytes in bf16 — Llama-3-8B: 128,256 × 4096 × 2 ≈ 1.05 GB of weights before you reach a single attention layer, and every generated token pays a full `hidden × vocab` softmax at the LM head. Vocab size is a real serving cost, not a free lunch.

## Anti-patterns

- ❌ **Estimating tokens as `len(text) / 4`** — works on English prose, breaks on code, JSON, or non-Latin scripts. Use the real tokenizer: it's a local, offline, deterministic operation.
- ❌ **Caching by string instead of by token-hash** — same text, different tokenizers, false cache hits.
- ❌ **Truncating by characters** — slices tokens mid-way, producing garbage. Truncate on token ids, or on document/paragraph boundaries.
- ❌ **Ignoring reasoning tokens in cost models** — they're billed as output; a "cheap" reasoning model can out-cost a pricier non-reasoning one on your workload.
- ❌ **Hardcoding one provider's token counts in multi-provider routers** — counts differ 10-20%; count per-provider or your routing thresholds drift.

## Decision framework

| Need | Use |
|------|-----|
| Count tokens before sending (OpenAI) | `tiktoken` locally, exact via the tokenizer API |
| Count tokens before sending (Anthropic) | `client.messages.count_tokens(...)` — no local tokenizer exists |
| Count tokens before sending (Gemini) | `model.count_tokens(...)` — per-model, exact |
| Minimize tokens in stored prompts | Compress, dedupe, summarize; minify JSON payloads |
| Tokenize non-English well | Prefer Gemini or Claude tokenizers; GPT's BPE is English-leaning |
| Tokenize code | Use a model with a code-aware tokenizer (most modern ones) |
| Redact/filter content | Do it on token ids or normalized text, not raw substring matches |

## References

- [tiktoken](https://github.com/openai/tiktoken) — verified 2026-10-20
- [Neural Machine Translation of Rare Words with Subword Units (BPE)](https://arxiv.org/abs/1508.07909) — verified 2026-10-20
- [SentencePiece](https://arxiv.org/abs/1808.06226) — verified 2026-10-20
- [OpenAI Tokenizer](https://developers.openai.com/tokenizer) — verified 2026-10-20
- [Anthropic: Counting tokens](https://platform.claude.com/docs/en/api/messages-count-tokens) — verified 2026-10-20
