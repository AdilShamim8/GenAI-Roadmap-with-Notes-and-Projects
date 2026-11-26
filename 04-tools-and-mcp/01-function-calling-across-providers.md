# Function Calling Across Providers

> **Level:** BEG → INT · **Last verified:** 2026-10-20 · **Sources:** [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling), [Anthropic tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview)

## Why this matters

Function calling is what turns an LLM from a text generator into an agent that can act. Every major provider supports it, but the syntax, semantics, and reliability differ. Knowing the differences matters when you're picking a stack or porting between providers. The expert layer on top: function calling is not one capability but three — *selection* (which tool), *formulation* (what arguments), and *orchestration* (what order, when to stop) — and providers differ in all three, which is why "the model can't call tools reliably" is usually a solvable design problem, not a model limitation.

## Core concepts

### The shape, abstracted

All providers implement the same loop:

1. You declare tools (name, description, JSON-schema params).
2. The model decides to call a tool, emitting structured arguments.
3. You execute the tool and return the result.
4. The model uses the result to continue — repeat until it answers with plain text.

The loop is *yours* to manage on every provider. None of them execute anything — the model only ever emits a request; your harness executes and feeds back. This means loop-level failure modes (iteration caps, duplicate-call detection, argument validation) are harness responsibilities that don't port between frameworks automatically.

### Provider comparison

| Provider | Tool declaration | Tool call returns | Streaming | Parallel calls |
|----------|------------------|-------------------|-----------|----------------|
| OpenAI | `tools` array in request | `tool_calls` in message (chat) / function items (Responses) | Yes (content-block) | Yes |
| Anthropic | `tools` array in request | `tool_use` content block, paired `tool_result` required | Yes | Yes |
| Gemini | `tools` / `functionDeclarations` | `functionCall` part | Yes | Yes |
| Mistral | `tools` array | `tool_calls` (OpenAI-style) | Yes | Yes |

The semantic differences that bite during ports:

- **Pairing discipline.** Anthropic requires every `tool_use` block to be answered by a `tool_result` in the very next message — even for failures. OpenAI's chat API also expects a `tool` role reply per `tool_call_id`, but is more lenient in practice. Get this wrong and you get a 400 that names tool_use ids.
- **Argument type strictness.** OpenAI historically emits stringified JSON in `arguments` (parse it yourself); Anthropic gives you a parsed object in `input`. Gemini matches parameter types to your schema *only if the schema declares them* — loose schemas produce loose types.
- **"No tool" escape.** Every provider needs a way for the model to answer without tools. OpenAI: `tool_choice: "auto"` + the model just replies. Anthropic: same, but with `tool_choice: {"type": "any"}` the model *must* call a tool — a footgun when the task sometimes needs no tools.
- **Strict mode.** OpenAI's `strict: true` enables constrained decoding for tool arguments (the same guarantee as structured outputs — invalid JSON is ungenerable, `01-llm-calling/04-structured-outputs.md`). Anthropic and Gemini validate-but-don't-constrain by default. This is the single biggest reliability lever on OpenAI; on the others, your validation layer does that work.

### The reliability problem, decomposed

On OpenAI, prefer the **Responses API** for new builds — tools are first-class there; `chat.completions` tool calling still works and remains the cross-provider convention.

Even in 2026, the three failure classes differ in cause and fix:

| Failure | What's happening | Fix |
|---------|------------------|-----|
| Hallucinated tool names | Selection confusion — usually too many similar tools, or descriptions that don't discriminate | Fewer tools, sharper descriptions, disambiguate with `when to use` / `when NOT to use` lines |
| Schema-violating JSON | Formulation — no decoding constraint, or schema is ambiguous (missing `required`, unspecified formats) | `strict: true` where available; always validate server-side; reject-and-return-error lets the model self-correct in one turn |
| Wrong order / refusal / loops | Orchestration — the model can't see your state machine | Make state explicit in the conversation ("already called X, it failed with Y"), cap iterations, detect duplicate calls |

The recovery pattern most teams under-use: **return errors as tool results, not exceptions.** A tool result of `{"error": "city not found; known cities: [...]"}` teaches the model in one round-trip; raising in your harness and crashing the loop teaches it nothing. Budget one self-correction cycle in your iteration cap.

### The tool-description contract

The description is a prompt. The model reads it every call, and it competes with your system prompt and the user request. Three rules that measurably move selection accuracy:

1. **Lead with what it does, then when to use it.** "Get the current weather in a city" beats "Weather tool."
2. **Make mutually-exclusive tools say so.** If `search_docs` and `search_kb` coexist, each description should name the boundary ("search_docs: engineering documentation only — for customer-facing help articles use search_kb").
3. **Enum-constrain parameters instead of free-text.** `"unit": {"type": "string", "enum": ["c", "f"]}` eliminates a whole error class.

Tool definitions count toward input tokens on every call — with 10+ tools this is thousands of tokens, which is both a cost line and a prompt-caching consideration (`01-llm-calling/06-prompt-caching.md`: keep tool definitions serialized in a stable order at the prefix).

## Code: OpenAI function calling

```python
from openai import OpenAI
import json
client = OpenAI()

tools = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the current weather in a city. Use for any question about present conditions; NOT for forecasts (use get_forecast).",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name, e.g. 'Tokyo'"},
                "unit": {"type": "string", "enum": ["c", "f"], "description": "Temperature unit"},
            },
            "required": ["city"],
            "additionalProperties": False,
        },
        "strict": True,  # constrained decoding for arguments
    },
}]

resp = client.chat.completions.create(
    model="gpt-6.1-sol",
    messages=[{"role": "user", "content": "What's the weather in Tokyo?"}],
    tools=tools,
)
tool_call = resp.choices[0].message.tool_calls[0]
args = json.loads(tool_call.function.arguments)
# Execute, then reply as a "tool" role message with tool_call_id — one per call.
```

## Code: Anthropic tool use (with the pairing discipline)

```python
import anthropic
client = anthropic.Anthropic()

tools = [{
    "name": "get_weather",
    "description": "Get the current weather in a city.",
    "input_schema": {
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"],
    },
}]

resp = client.messages.create(
    model="claude-sonnet-5-5",
    max_tokens=1024,
    tools=tools,
    messages=[{"role": "user", "content": "What's the weather in Tokyo?"}],
)

for block in resp.content:
    if block.type == "tool_use":
        # execute...
        # then the NEXT message MUST contain a tool_result for this block id:
        # {"role": "user", "content": [{"type": "tool_result",
        #   "tool_use_id": block.id, "content": "22C, clear"}]}
        print(block.name, block.input)
```

## Production concerns

- **Latency:** Tool calls add a round-trip. Stream tool args to start executing early (assemble from index-keyed deltas, `01-llm-calling/05-streaming.md`).
- **Cost:** Tool definitions count toward input tokens *every call*. 15 tools × ~150 tokens = ~2.2K tokens/call — at $2/1M that's ~$0.005/call before any content, on a million calls a day, $4.4K/day. Cache the prefix; and prune the tool list per route (a support agent rarely needs all 15 tools in every turn).
- **Failure modes:** Loops (same tool, same args, repeatedly — detect by hashing (name, args) and refusing exact duplicates); over-calling (calling tools when it already has the answer — instruct "answer from context when sufficient"); under-calling (answering without tools because the tool description undersold it).
- **Security:** Validate tool args against the schema *and* against authorization (the model may legitimately formulate a request the user isn't allowed to make — the tool layer enforces permissions, not the model). Never let the model pick arbitrary endpoints or SQL.

## Anti-patterns

- ❌ **Declaring 20 tools at once.** Models degrade past ~10–15 tools. Route to sub-agent toolsets (`../06-multi-agent/05-sub-agent-design.md`).
- ❌ **Trusting tool args blindly.** Always validate against schema + authz.
- ❌ **Returning raw tool output.** Summarize large outputs before sending back (`02-context-engineering/03-context-distillation.md`).
- ❌ **Raising exceptions on tool failure instead of returning error results.** You lose the model's one-turn self-correction.
- ❌ **Unvalidated strictness assumptions.** `strict: true` constrains OpenAI's decoder; it does nothing on providers that ignore unknown fields — your validation layer is the real contract.

## References

- [OpenAI function calling (Responses API)](https://developers.openai.com/api/docs/guides/function-calling) — verified 2026-10-20
- [Anthropic tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview) — verified 2026-10-20
- [Gemini function calling](https://ai.google.dev/gemini-api/docs/function-calling) — verified 2026-10-20
