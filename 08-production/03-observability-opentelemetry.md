# Observability with OpenTelemetry

> **Level:** INT · **Last verified:** 2026-10-20 · **Sources:** [OpenLLMetry](https://github.com/traceloop/openllmetry), [OpenInference](https://github.com/Arize-ai/openinference)

## Why this matters

LangSmith is great but locks you in. OpenTelemetry (OTel) is the vendor-neutral standard for LLM observability, supported by Arize Phoenix, OpenLLMetry, OpenInference, and most APM vendors. In 2026, OTel is the default for production GenAI. The expert framing: what you're actually buying with OTel is *causality* — the ability to answer "which of the 12 calls in this request went wrong, and what did each see?" That answer requires the trace to be a *complete tree* of the request, not a collection of per-call logs; most teams' LLM observability fails not on tooling but on incomplete trees and unattributed spans.

## Core concepts

### The four signals

| Signal | What | Example |
|--------|------|---------|
| **Traces** | Tree of spans per request | `agent.run -> llm.call -> tool.search_docs` |
| **Metrics** | Aggregated numbers | Request count, p95 latency, cost |
| **Logs** | Discrete events | "Tool call failed: timeout" |
| **Attributes** | Span metadata | model, prompt_template_id, token_count |

### The span hierarchy

A production trace typically looks like:

```text
agent.run (1.2s, $0.03)
├── retriever.search (180ms)
│   ├── embed.query (40ms)
│   └── vector_db.query (140ms)
├── llm.call (900ms, $0.025)
│   ├── system_prompt (cached: yes)
│   └── output_tokens (120)
└── tool.execute (40ms)
```

The three properties that make this tree *diagnosable* (vs. decorative):

1. **Context propagation across async boundaries.** Agent frameworks fan out (parallel tools, background summarizers, sub-agents); each hop must carry the trace context or you get disconnected fragments that look like separate requests. Python's asyncio makes this easy to break — instrument the framework's task-spawn points, not just the calls.
2. **One root per user-facing request** — the trace id *is* the correlation key for "user says it was wrong" debugging. If the gateway, the agent, and the tools each start their own traces, you've rebuilt log-guessing with extra steps.
3. **Every span that spends money carries its cost inputs** — model, input/output/cached token counts. Cost attribution (`01-cost-engineering.md`) and incident forensics both read the same attributes.

### The semantic conventions (portability is the point)

Two ecosystems dominate LLM-instrumentation conventions — OpenLLMetry and OpenInference — with OTel's own GenAI semantic conventions converging the space. Why this matters more than it sounds: span attributes following a convention are *queryable across backends* ("show me all llm.call spans where cached_tokens < 10% of input_tokens" works in Phoenix today, Grafana tomorrow). Ad-hoc attribute names (`tok_count`, `tokensUsed`, `n_tokens` across teams) make every analysis a per-team archaeology project. Pick the convention once, at instrumentation time; retrofitting attribute names across months of stored traces is miserable.

### Sampling: the tail-sampling subtlety

Head sampling (drop X% of traces at creation) is the default and it's wrong for failure analysis: rare failures are exactly what you want 100% of. **Tail sampling** — decide retention *after* the trace completes, keeping all error/slow/high-cost traces and sampling the healthy ones — is the production pattern. Concretely: keep 100% of traces with errors, 100% over a latency threshold, 100% over a cost threshold, 5-10% of the rest. Your dashboards stay cheap; your failure forensics stay complete. (This requires running an OTel Collector between app and backend — the component most teams skip and then regret.)

### What to put on spans (and what never to)

Attributes that earn their storage: model, prompt-template *id* + version (not the full text), token counts (input/output/cached/reasoning), cost, finish/stop reason, tool name + args-hash, latency phases. The temptation to store full prompts/outputs on every span is real (it makes traces self-contained) but wrong by default: prompt content is PII-bearing, storage-heavy, and better kept in a content-addressed side-store keyed by span id, with the span carrying only the reference. You get "click to see the exact prompt" *and* retention policies that don't apply to your observability pipeline.

## Code: instrument with OpenInference

```python
# pip install openinference-instrumentation-openai
from openinference.instrumentation.openai import OpenAIInstrumentor
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

tracer = TracerProvider()
trace.set_tracer_provider(tracer)
tracer.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

OpenAIInstrumentor().instrument()  # auto-instruments openai calls

# Now every OpenAI call emits a span automatically
resp = client.chat.completions.create(model="gpt-6.1-sol", messages=[...])
```

## Code: custom spans

```python
from opentelemetry import trace
tracer = trace.get_tracer(__name__)

def search_docs(query: str) -> list:
    with tracer.start_as_current_span("search_docs") as span:
        span.set_attribute("query_length", len(query))      # metric-ish, safe
        span.set_attribute("query_hash", hash_pii(query))   # reference, not content
        results = vector_db.search(query, k=5)
        span.set_attribute("result_count", len(results))
        return results
```

## Production concerns

- **Latency:** OTel adds <1% overhead. Batch processors keep it there — never export spans synchronously on the request path.
- **Cost:** Trace storage is cheap; sampling for high-volume — with tail-sampling priorities (above), storage tracks *interesting* traces, not raw volume.
- **Failure modes:** (1) sampling too aggressively loses rare failure traces — tail-sample; (2) broken context propagation fragmenting traces — test it: one synthetic request through the full path must appear as *one* trace; (3) attribute drift across teams — lint span attributes in CI like you lint code.
- **Backend breadth:** Phoenix, Langfuse, Grafana LGTM, and Honeycomb all consume OTel natively — the instrumentation layer is the portable part; don't lock into a vendor SDK.
- **Security:** Spans may contain prompts. Redact PII before export — or never put content on spans (reference pattern above); your observability pipeline is almost always your longest-retention, widest-access data store, and treating it as such is a compliance requirement, not paranoia.

## Anti-patterns

- ❌ **Tracing only the LLM call.** Trace the full agent loop — the tree is the product.
- ❌ **No span attributes.** You can't filter later.
- ❌ **100% head sampling in production.** Tail-sample: keep all failures, sample the healthy.
- ❌ **Full prompt text on every span.** PII + storage + retention headaches; store references.
- ❌ **Ad-hoc attribute names.** Follow GenAI semantic conventions; portability is the point.
- ❌ **Unverified context propagation.** A fragmenting trace pipeline fails silently.

## References

- [OpenTelemetry for LLMs (OpenLLMetry)](https://github.com/traceloop/openllmetry) — verified 2026-10-20
- [OpenInference](https://github.com/Arize-ai/openinference) — verified 2026-10-20
- [Arize Phoenix](https://github.com/Arize-ai/phoenix) — verified 2026-10-20
