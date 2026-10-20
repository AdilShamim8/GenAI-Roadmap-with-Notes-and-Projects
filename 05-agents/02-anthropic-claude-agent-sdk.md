# Anthropic Claude Agent SDK

> **Level:** INT · **Last verified:** 2026-10-20 · **Sources:** [Claude Agent SDK (Python)](https://github.com/anthropics/claude-agent-sdk-python), [Claude Code docs](https://platform.claude.com/docs/en/claude-code/overview)

## Why this matters

Anthropic's Claude Agent SDK (the exposed internals of Claude Code) is purpose-built for long-horizon, file-operating agents. If your agent needs to read/write files, run commands, and persist state across hours of work, this is the strongest choice in 2026. Unlike the OpenAI Agents SDK, it runs the Claude Code engine as a subprocess — the CLI ships bundled with the package.

## Core concepts

### The primitives

- **`query()`** — one-shot async entry point: `async for message in query(prompt=..., options=...)`. Yields a stream of SDK result messages.
- **`ClaudeSDKClient`** — bidirectional, interactive client for multi-turn conversations with streaming input.
- **`ClaudeAgentOptions`** — the configuration object: `model`, `system_prompt`, `cwd` (working directory), `allowed_tools`, `permission_mode`, `mcp_servers`, `hooks`.
- **Sessions** — durable agent state: `resume` a prior session or `fork_session` from it.
- **Permission callbacks** — `can_use_tool` gives you programmatic approval over every tool call; `permission_mode` presets the policy (e.g. `acceptEdits`).

### Built-in tools

The SDK inherits Claude Code's battle-tested toolset: `Bash`, file edit/read/write, `Grep`/`Glob` search, `WebFetch`/`WebSearch`, and the `Task` sub-agent tool. Don't reimplement these — extend via MCP instead.

## Code: minimal agent

```python
import anyio
from claude_agent_sdk import query, ClaudeAgentOptions

async def main():
    async for message in query(
        prompt="Add a docstring to every function in utils.py.",
        options=ClaudeAgentOptions(
            model="claude-sonnet-5-5",
            cwd="/tmp/agent-workspace",
            allowed_tools=["Bash", "Edit", "Read", "Grep"],
            permission_mode="acceptEdits",
        ),
    ):
        print(message)

anyio.run(main)
```

## Code: custom tool via MCP

Custom tools are exposed through an in-process MCP server, not a bare decorator:

```python
from claude_agent_sdk import tool, create_sdk_mcp_server, ClaudeAgentOptions

@tool("query_db", "Run a read-only SQL query", {"sql": str})
async def query_db(args):
    return {"content": [{"type": "text",
                         "text": str(run_sql(args["sql"]))}]}

server = create_sdk_mcp_server("db", [query_db])
# pass server into ClaudeAgentOptions(mcp_servers={"db": server}, ...)
```

## Production concerns

- **Latency:** Long-horizon agents run for minutes to hours. Stream progress; hook `hooks` can emit per-tool events.
- **Cost:** Token usage scales with file sizes the agent reads. Scope `cwd` tightly; the engine compacts context automatically, but raw logs still dominate.
- **Failure modes:** Agents can delete files in their sandbox. Use version control (`cwd` = a git worktree).
- **Security:** Never point `cwd` at `/` or secrets directories; prefer `can_use_tool` approval for destructive tools over blanket allowlists.

## Anti-patterns

- ❌ **Running the agent with no sandbox.** Catastrophic.
- ❌ **Giving the agent write access to your repo without git.** You can't undo.
- ❌ **Ignoring the agent's bash output.** Read every command.
- ❌ **Expecting the OpenAI-style `Agent(...).run()` shape.** This SDK is a streaming subprocess API — `query()` / `ClaudeSDKClient` — not an object graph.

## Decision framework

| Need | Use |
|------|-----|
| Hours-long, file-operating agent | This SDK |
| Quick single-agent loop on any provider | OpenAI Agents SDK (`01-openai-agents-sdk.md`) |
| Durable multi-agent state machines | LangGraph (`03-langgraph-stateful-agents.md`) |
| Comparison table | `../docs/decision-guides/choosing-an-agent-sdk.md` |

## References

- [Claude Agent SDK (Python)](https://github.com/anthropics/claude-agent-sdk-python) — verified 2026-10-20
- [Claude Code docs](https://platform.claude.com/docs/en/claude-code/overview) — verified 2026-10-20
