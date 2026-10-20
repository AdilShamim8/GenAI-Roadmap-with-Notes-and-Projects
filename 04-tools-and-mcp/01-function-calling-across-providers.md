# Function Calling Across Providers

> **Level:** BEG → INT · **Last verified:** 2026-10-20

## Why this matters

Function calling is what turns an LLM from a text generator into an agent that can act. Every major provider supports it, but the syntax, semantics, and reliability differ. Knowing the differences matters when you're picking a stack or porting between providers.

## Core concepts

### The shape, abstracted

All providers implement the same idea:
1. You declare tools (name, description, JSON-schema params).
2. The model decides to call a tool, emitting structured arguments.
3. You execute the tool and return the result.
4. The model uses the result to continue.

### Provider comparison

| Provider | Tool declaration | Tool call returns | Streaming | Parallel calls |
|----------|------------------|-------------------|-----------|----------------|
| OpenAI | `tools` array in request | `tool_calls` in message | Yes (content-block) | Yes |
| Anthropic | `tools` array in request | `tool_use` content block | Yes | Yes |
| Gemini | `tools` / `function_declarations` | `function_call` part | Yes | Yes |
| Mistral | `tools` array | `tool_calls` (OpenAI-style) | Yes | Yes |

### The reliability problem

On OpenAI, prefer the **Responses API** for new builds — tools are first-class there; `chat.completions` tool calling still works and remains the cross-provider convention.

Even in 2026, models:
- Hallucinate tool names that don't exist.
- Emit JSON that doesn't match the schema.
- Call tools in the wrong order.
- Refuse to call tools when they should.

Mitigations:
- Use schema-constrained decoding (native JSON schema, not just "respond in JSON").
- Validate every tool call's args before executing.
- Include a `error` tool result type so the model can recover.
- Cap tool-call iterations (5–10 max).

## Code: OpenAI function calling

```python
from openai import OpenAI
client = OpenAI()

tools = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the current weather in a city.",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    },
}]

resp = client.chat.completions.create(
    model="gpt-6.1-sol",
    messages=[{"role": "user", "content": "What's the weather in Tokyo?"}],
    tools=tools,
)

tool_call = resp.choices[0].message.tool_calls[0]
import json
args = json.loads(tool_call.function.arguments)
# Execute: weather = get_weather(args["city"])
# Then send back as a "tool" role message.
```

## Code: Anthropic tool use

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
        print(block.name, block.input)  # 'get_weather' {'city': 'Tokyo'}
```

## Production concerns

- **Latency:** Tool calls add a round-trip. Stream tool args to start executing early.
- **Cost:** Tool definitions count toward input tokens. Cache them.
- **Failure modes:** Models loop calling the same tool. Cap iterations and detect loops.
- **Security:** Validate tool args. Never let the model pick arbitrary endpoints or SQL.

## Anti-patterns

- ❌ **Declaring 20 tools at once.** Models degrade past ~10–15 tools. Use sub-agents for more.
- ❌ **Trusting tool args blindly.** Always validate against the schema.
- ❌ **Returning raw tool output.** Summarize large outputs before sending back.

## References

- [OpenAI function calling (Responses API)](https://developers.openai.com/api/docs/guides/function-calling) — verified 2026-10-20
- [Anthropic tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview) — verified 2026-10-20
- [Gemini function calling](https://ai.google.dev/gemini-api/docs/function-calling) — verified 2026-10-20
