# Chunking Strategies

> **Level:** BEG · **Last verified:** 2026-10-20 · **Sources:** [Anthropic: Contextual retrieval](https://www.anthropic.com/news/contextual-retrieval), [Late Chunking](https://arxiv.org/abs/2409.04701)

## Why this matters

Chunking is the highest-leverage RAG decision. Bad chunking = bad retrieval = bad answers, no matter how good your model. The expert framing: a chunk is the *unit of retrieval*, and every property you care about downstream — recall, precision, citation granularity, context completeness for the generator — is constrained by what the chunk boundary cuts. Most RAG problems trace back to chunks that are too big, too small, or split mid-thought.

## Core concepts

### The four strategies

| Strategy | How | Best for | Failure mode |
|----------|-----|----------|--------------|
| **Fixed-size** | Every N chars/tokens with overlap | Quick prototype, uniform docs | Splits sentences/tables mid-way |
| **Recursive character** | Split on `\n\n`, then `\n`, then `.` (LangChain default) | Heterogeneous text | Still structure-blind at boundaries |
| **Document-aware** | Split on Markdown headings, HTML tags, code blocks | Structured docs | Section size varies wildly |
| **Semantic** | Embed sentences, cluster by similarity | Long-form narrative | Clusters don't respect topic shifts the LLM sees |
| **Late chunking** | Embed full doc, then pool per-chunk token embeddings | Preserves cross-chunk context | Requires long-context embedder (8K+) |

### The size tradeoff is actually *two* tradeoffs

Beginner guidance says "512 tokens sweet spot." The expert version: chunk size couples to *both* stages of the pipeline, in opposite directions:

- **Retrieval stage (embedding):** embedding models dilute their representation across a chunk's tokens. Smaller chunks → purer vectors → better top-K recall *for the query that names the topic*.
- **Generation stage (LLM):** a chunk must carry enough surrounding context for the model to *use* it correctly. A 128-token chunk with the right fact but no definition of "it" / "the company" / the table header generates wrong answers despite perfect retrieval.

So: retrieval wants small, generation wants complete. The resolutions, in order of effectiveness:

1. **Decouple the two** — retrieve on small chunks, but *expand to parent* (a.k.a. small-to-big / sentence-window retrieval): embed 1-3 sentences, return the surrounding section. You get recall of small chunks with generation context of big ones. This is the single biggest chunking upgrade most systems can make.
2. **Contextual chunking** (below) — fix the "chunk lost its context" problem at the embedding itself.
3. **Tune only after (1) and (2)** — chunk-size sweeps without the parent-expansion pattern mostly measure noise.

### Why naive chunks fail: the embedding is context-free

When you embed `"...increased 14% year over year, driven by enterprise demand."` the vector has no idea *what* increased. This is the core defect contextual methods attack (Anthropic's contextual retrieval; Jina's late chunking, arXiv 2409.04701, which pools token-level embeddings from a long-context encoder *after* full-document encoding — same intuition, no LLM calls, but requires a long-context embedder).

### Contextual chunking (Anthropic, 2024)

Add a 1-sentence context prefix to each chunk before embedding: "This chunk is from the 'Pricing' section of the Acme API docs, discussing enterprise plan rates." Anthropic reports 49% fewer retrieval failures vs raw chunks alone; 67% combined with BM25 hybrid search. Two implementation details that decide whether you reproduce their numbers:

- Prefix the chunk **before embedding** (the retrieval-time query embeds in the same space), and keep the prefix on the chunk text you *return* to the generator too — it doubles as provenance context.
- The cost is 1 cheap-model LLM call per chunk at **index time only**. On a 100K-chunk corpus at GPT-6 Luna pricing ($0.10/1M in, $0.50/1M out, ~150-token chunks + ~50-token prefix out), that's ~$20 input + ~$7.5 output ≈ **$28 one-time** — trivially amortized over thousands of queries.

### Structure-aware splitting in practice

- **Markdown/code:** split on headings first, then fall back to recursive. Keep fenced code blocks *intact* — a chunk with half a function retrieves fine and generates garbage.
- **Tables:** never split a table across chunks; keep the header row with every chunk if you must split. A row without its header is meaningless to both embedder and generator.
- **Overlap (10–20%):** mitigates boundary facts (a sentence split across chunks), at the price of duplicate storage and double-counted retrieval. With parent-expansion, you can usually drop overlap entirely — the parent provides the continuity.

## Code: recursive splitter with structure-aware separators

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=512,
    chunk_overlap=0,  # parent-expansion handles continuity
    separators=["\n#{1,6} ", "\n```", "\n\n", "\n", ". ", " ", ""],  # headings & code fences first
    is_separator_regex=True,
)
chunks = splitter.split_text(long_text)
```

## Code: contextual chunking with cached prefixes

```python
from openai import OpenAI
client = OpenAI()

def add_context(chunks: list[str], doc_title: str) -> list[str]:
    contextualized = []
    for i, chunk in enumerate(chunks):
        ctx = client.chat.completions.create(
            model="gpt-6-luna",
            messages=[
                {"role": "system", "content": (
                    f"You are indexing a document titled '{doc_title}'. For the chunk "
                    "below, output a 1-sentence context prefix describing where it "
                    "sits in the document. Output ONLY the prefix."
                )},
                {"role": "user", "content": chunk},
            ],
        ).choices[0].message.content
        contextualized.append(f"{ctx}\n\n{chunk}")
    return contextualized
```

## Code: small-to-big (parent expansion)

```python
# At index time: parents = sections; children = sentence windows inside them.
# Embed children only. Store parent_id on each child.
index.add(  # children
    ids=[f"c{i}" for i in range(len(child_chunks))],
    embeddings=embed(child_chunks),
    metadatas=[{"parent_id": p} for p in child_parent],
)

def retrieve_expand(query: str, k: int = 8) -> list[str]:
    hits = index.query(query_embeddings=embed([query]), n_results=k * 3)
    parent_ids = []
    for md in hits["metadatas"][0]:
        if md["parent_id"] not in parent_ids:
            parent_ids.append(md["parent_id"])  # dedupe children → parents
    return [parents[p] for p in parent_ids[:k]]
```

Deduplication matters: three child hits inside one parent should return *one* parent, not three copies — otherwise you burn context on duplicates and starve the generator of distinct evidence.

## Production concerns

- **Latency:** Chunking is index-time; query-time latency is unaffected except via chunk size at generation (more/larger chunks = more prefill).
- **Cost:** Contextual chunking costs ~$0.08–0.30 per 1K chunks with a cheap model (compute for your model and corpus). Re-chunking on embedding-model change is the real cost: budget an index-rebuild pipeline from day one.
- **Failure modes:** (1) structure-blind splitting of code/tables — the #1 quality killer in technical corpora; (2) overlap masking a boundary bug; (3) chunks whose meaning survives retrieval but dies at generation (no context) — invisible to retrieval metrics, visible in answer evals.
- **Security:** Chunk boundaries can split sensitive data across chunks — re-mirror PII detection across boundaries, and remember contextual prefixes *copy document content into a new store* (they inherit its sensitivity and now exist outside your DLP perimeter).
- **Eval discipline:** Always measure end-to-end answer quality, not retrieval top-K alone. A chunking change that improves recall@10 can *lower* answer quality (smaller, decontextualized chunks). Use answer-correctness evals with chunk-id provenance so you can trace failures to boundaries (`../07-evals/04-deepeval-ragas.md`).

## Anti-patterns

- ❌ **Fixed 1000-char chunks with no overlap.** Splits sentences and paragraphs awkwardly.
- ❌ **One chunk per document.** Loses retrieval precision; embedding dilutes across the whole doc.
- ❌ **Splitting tables or code blocks mid-way.** The #1 silent quality killer in technical corpora.
- ❌ **Tuning chunk size before adding parent-expansion.** You're optimizing the wrong variable.
- ❌ **Chunking by tokens without testing recall.** Always measure — corpus-dependence is large.

## References

- [Anthropic: Contextual retrieval](https://www.anthropic.com/news/contextual-retrieval) — verified 2026-10-20
- [Late Chunking: Contextual Chunk Embeddings Using Long-Context Embedding Models](https://arxiv.org/abs/2409.04701) — verified 2026-10-20
- [LangChain text splitters](https://python.langchain.com/docs/how_to/#text-splitters) — verified 2026-10-20
