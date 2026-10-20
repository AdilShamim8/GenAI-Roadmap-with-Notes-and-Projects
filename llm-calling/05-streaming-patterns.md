# Streaming Patterns

> **Level:** INT · **Last verified:** 2026-10-20 · **Sources:** [OpenAI streaming](https://developers.openai.com/api/docs/), [Anthropic streaming](https://platform.claude.com/docs/en/api/messages-streaming)

## Why this matters

Users abandon an LLM UI that takes 5 seconds to show a token. Streaming cuts perceived latency by 5–10x. But streaming is harder than blocking: you need to handle partial JSON, tool-call deltas, and client disconnects.

## Core concepts

### Two stream granularities

1. **Token streaming** — yield each token as it's generated. Standard since 2023.
2. **Content-block / event streaming (Anthropic, OpenAI Responses API)** — yield structured, typed events: `text_start` / `text_delta` / `text_stop`, `tool_use_start` / `tool_input_delta` / `tool_use_stop` on Anthropic; `response.output_text.delta` and friends on OpenAI. More complex but more parseable.

### Server-Sent Events (SSE) — and why the wire format differs per vendor

Most providers stream over SSE: each event is `data: {...}\n\n`. But the terminator is **not** standardized: OpenAI ends with `data: [DONE]`; Anthropic instead emits typed `event:` lines ending in `message_stop`. Never assume one vendor's SSE grammar works against another's.

## Code: SSE in FastAPI (async, with disconnect handling)

```python
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI

app = FastAPI()
client = AsyncOpenAI()

@app.get("/chat")
async def chat(q: str, request: Request):
    async def gen():
        stream = await client.chat.completions.create(
            model="gpt-6.1-sol",
            messages=[{"role": "user", "content": q}],
            stream=True,
        )
        async for chunk in stream:
            if await request.is_disconnected():
                await stream.close()  # stop paying for orphaned tokens
                break
            if chunk.choices and chunk.choices[0].delta.content:
                yield f"data: {chunk.choices[0].delta.content}\n\n"
        yield "data: [DONE]\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream")
```

## Streaming structured outputs

```python
from partial_json_parser import loads  # pip install partial-json-parser

buffer = ""
async for chunk in await client.chat.completions.create(
    model="gpt-6.1-sol",
    messages=[{"role": "user", "content": "..."}],
    response_format={"type": "json_object"},
    stream=True,
):
    delta = chunk.choices[0].delta.content or ""
    buffer += delta
    try:
        partial = loads(buffer)  # best-effort partial parse
        print(partial)
    except Exception:
        pass  # wait for more tokens
```

## Production concerns

- **Latency:** Aim for <500ms time-to-first-token. Anything above feels broken.
- **Cost:** Streaming doesn't save tokens; it saves perceived latency. Capture final usage with `stream_options={"include_usage": True}` (OpenAI) or the `message_delta` usage event (Anthropic).
- **Failure modes:** Client disconnects mid-stream — your server must detect and cancel the upstream request or you'll pay for orphaned generations. Guard `chunk.choices` (usage-only final chunks have an empty list).
- **Security:** Don't stream PII to logs.

## Anti-patterns

- ❌ **Buffering the entire response before sending.** Defeats the point.
- ❌ **Ignoring client disconnects.** Costs money and ties up provider rate limits.
- ❌ **Using WebSockets when SSE suffices.** SSE is simpler and has better proxy support. (Exception: bidirectional audio — see `realtime-voice/`.)
- ❌ **Assuming `data: [DONE]` terminates every provider's stream.** It's OpenAI-specific; Anthropic closes with `message_stop`.

## Decision framework

| Need | Use |
|------|-----|
| Browser/HTTP text streaming | SSE (this pattern) |
| Python backend, many concurrent streams | `AsyncOpenAI` + `async for` |
| Streaming JSON to a UI | Partial-JSON parsing with a terminal-object strategy |
| Bidirectional audio/video | WebSockets or WebRTC (Realtime API — see `realtime-voice/01-openai-realtime-api.md`) |

## References

- [OpenAI streaming](https://developers.openai.com/api/docs/guides/streaming) — verified 2026-10-20
- [Anthropic streaming](https://platform.claude.com/docs/en/api/messages-streaming) — verified 2026-10-20
- [FastAPI StreamingResponse](https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse) — verified 2026-10-20
