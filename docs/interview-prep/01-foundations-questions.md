# Foundations — Interview Questions

> **Rung:** [00-foundations](../../00-foundations/00-transformers-deep-dive.md) · **Last verified:** 2026-10-20

Answer out loud before reading the model answer. The "senior note" is what separates a pass from a strong hire.

## Q1 — Walk me through what happens on a single forward pass of a transformer during text generation.

**Model answer:** Every generated token requires a full pass over the context so far. Each position's query attends over all previous keys/values (causal masking), producing contextual representations; the last position's representation predicts the next token's distribution; we sample; append; repeat. The defining property is that generation is *autoregressive* — tokens are produced one at a time, and every token's computation attends to everything before it.

The critical asymmetry for serving: at prefill (processing your prompt), all positions compute *in parallel* — it's compute-bound and fast per token. At decode (generating), each token requires a fresh sequential pass — it's *memory-bandwidth-bound* because the weights and KV cache must be re-read from HBM for every single token. That's why decode dominates latency and why tokens/sec is bounded by memory bandwidth divided by model+cache bytes, not by FLOPS.

**Senior note:** derive the decode ceiling from bandwidth: an 8B model in bf16 is ~16GB of weights; an H100 has ~3.35TB/s of bandwidth; that's ~200 tokens/sec *per sequence* ceiling before batching — and why batching many sequences amortizes the weight-read cost (continuous batching). Candidates who can do this arithmetic on a whiteboard are rare.

## Q2 — What is the KV cache and why does it exist?

**Model answer:** Attention requires each new token to query the keys and values of *every* previous token. Recomputing those for all previous positions at every step would be quadratic work over generation. The KV cache stores each position's computed K and V vectors so subsequent steps only compute the *new* token's contribution.

Its size grows linearly with context: roughly `2 × layers × kv_heads × head_dim × bytes × tokens`. For Llama-3.1-8B (GQA, 8 KV heads of 128 dims, 32 layers, fp16): ~128KB per token — 16.8GB for a 128K-token context, *per sequence*. That's why context length is a memory problem before it's a model problem, and why GQA/MLA (reducing KV heads or compressing KV representations) exists: DeepSeek-V2's MLA cut cache size ~93% with a large throughput win.

**Senior note:** connect it to serving economics — PagedAttention (vLLM) fixes the *fragmentation* of pre-allocated caches by paging them like OS virtual memory, which is what lets a GPU run 2-3x more concurrent requests; prefix caching/RadixAttention deduplicates *shared* prefixes across requests. If asked "why is my self-hosted throughput bad," cache management is the first place to look.

## Q3 — Explain MoE to a product manager, then to an engineer.

**Model answer (PM):** A model with a built-in committee. For each piece of text, a router picks a few specialists out of many to handle it. You get a much bigger brain for the same thinking cost — that's why top open models serve hundreds of billions of parameters cheaply.

**Model answer (engineer):** Replace each FFN block with N expert FFNs plus a router that picks top-k experts per token. Only k experts compute per token — FLOPs stay small while total parameters (knowledge capacity) scale. Mixtral made this mainstream; DeepSeek-V3 runs 256 fine-grained experts with top-8 routing plus shared experts, using aux-loss-free balancing (bias-adjusted routing) to keep expert utilization even — because the classic auxiliary-loss balancing fights the language-model loss, and load imbalance wastes capacity (GShard's capacity factor drops overflow tokens).

The serving catch: total parameters must sit in memory even though few are active per token — DeepSeek-V3 at FP8 is ~671GB of VRAM despite cheap per-token compute. MoE trades memory footprint for per-token FLOPs.

**Senior note:** know the failure modes — expert collapse (router sends everything to few experts; the aux-loss-free paper's motivation), token dropping at capacity (quality loss under load), and batch-size-dependent economics (small batches waste the memory advantage; large batches amortize it).

## Q4 — Why does tokenization matter beyond "it's how text becomes numbers"?

**Model answer:** Tokenization determines the interface between your text and the model — and it leaks into product behavior:

- **Cost and latency:** you're billed per token; per-domain ratios differ hugely (code ~2.5-3.5 chars/token, CJK up to 2-4x worse than English) — a naive chars/4 estimate can be 50% off in either direction, which breaks budget projections and cache-breakpoint planning.
- **Failure modes:** token-boundary effects — a search/redaction system that matches on strings can miss a secret split across tokens; models struggle with character-level tasks (counting letters) because they see tokens, not characters.
- **Context math:** every context-budget and cache calculation downstream is in tokens, so tokenizer ignorance compounds.

Modern tokenizers are byte-level BPE (no UNK token — any byte sequence is representable), with vocab sizes 100K-250K by family; the vocab's embedding table is itself serving cost (a 128K vocab × 4096-dim model carries ~1GB of embeddings).

**Senior note:** the practical flex is knowing *which* tokenizer each provider uses and its quirks — e.g., reasoning models bill thinking tokens as output (the expensive class), so a tokenizer-aware cost model is a production skill, not trivia.

## Q5 — "Bigger context windows make RAG obsolete." Argue both sides, then pick one.

**Model answer:** *Against RAG:* 1M-token windows handle single-doc tasks (summarize this PDF) with zero indexing infrastructure; prompt caching can hold a stable corpus prefix at ~10x discount; citations can cite the stuffed document.

*For RAG:* (1) **effective context ≠ advertised context** — RULER showed aggregation and multi-hop tasks degrade far inside the window; NoLiMa showed associative-reasoning degradation by 32K tokens; (2) **cost and latency scale with corpus** — 1M fresh input tokens at $2/1M is $2/request vs ~$0.01 for 5K retrieved tokens, and 1M-token prefill is tens of seconds; (3) **freshness and access control** — an index updates incrementally and enforces per-tenant permissions at retrieval; a stuffed context must be filtered pre-assembly; (4) **citations are native** to retrieval.

*Verdict:* hybrid — retrieve top-K, then let a long-context model reason across the retrieved set. The window is reasoning room for selected evidence, not storage for the corpus. The decision is empirical per workload: corpus size, traffic, cache-friendliness, and multi-tenancy decide it (`../../03-rag/08-long-context-vs-rag.md` has the arithmetic).

**Senior note:** the answer interviewers want is the four-axis reasoning (capability/cost/latency/governance) plus the admission that "window" and "index" solve different problems — selection vs. volume. Anyone who answers with only "RAG is cheaper" or "context is better now" is reciting, not reasoning.

## Q6 — What does "attention is all you need" actually change, and what replaced/kept its pieces by 2026?

**Model answer:** The original transformer replaced recurrence (RNNs) with attention — every position directly attends to every other, enabling parallel prefill and long-range dependencies. What survived: the overall block structure (attention + FFN + residuals + normalization). What evolved: pre-norm replaced post-norm (training stability); RMSNorm replaced LayerNorm (cheaper); RoPE replaced absolute positional encodings (relative positions, length extrapolation with YaRN-style scaling); SwiGLU replaced plain FFN activations; GQA/MLA replaced vanilla multi-head attention (KV-cache size); FlashAttention made exact attention memory-efficient (IO-aware tiling — no approximation, same math).

**Senior note:** the pattern to articulate is *evolutionary efficiency* — the architecture's function stayed, every component got cheaper/faster/stabler. And decode remains the bottleneck it always was: all this progress barely touched the autoregressive memory-bandwidth wall, which is why speculative decoding and disaggregated serving exist at the systems layer.
