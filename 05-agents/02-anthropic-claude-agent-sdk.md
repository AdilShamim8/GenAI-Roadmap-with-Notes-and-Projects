# Anthropic Claude Agent SDK

> **Level:** INT · **Last verified:** 2026-10-20 · **Sources:** [Claude Agent SDK (Python)](https://github.com/anthropics/claude-agent-sdk-python), [Claude Code docs](https://platform.claude.com/docs/en/claude-code/overview)

## Why this matters

Anthropic's Claude Agent SDK (the exposed internals of Claude Code) is purpose-built for long-horizon, file-operating agents. If your agent needs to read/write files, run commands, and persist state across hours of work, this is the strongest choice in 2026. Unlike the OpenAI Agents SDK, it runs the Claude Code engine as a subprocess — the CLI ships bundled with the package. The expert framing: you're not getting a *library*, you're getting an *operator* — a subprocess with its own context management (compaction), its own permission model, and its own tool implementations that have been hardened in one of the most-deployed agent runtimes on earth. You supervise it; you don't reimplement it.

## Core concepts

### The primitives

- **`query()`** — one-shot async entry point: `async for message in query(prompt=..., options=...)`. Yields a stream of SDK result messages.
- **`ClaudeSDKClient`** — bidirectional, interactive client for multi-turn conversations with streaming input.
- **`ClaudeAgentOptions`** — the configuration object: `model`, `system_prompt`, `cwd` (working directory), `allowed_tools`, `permission_mode`, `mcp_servers`, `hooks`.
- **Sessions** — durable agent state: `resume` a prior session or `fork_session` from it.
- **Permission callbacks** — `can_use_tool` gives you programmatic approval over every tool call; `permission_mode` presets the policy (e.g. `acceptEdits`).

### The subprocess architecture (and why it changes your ops)

The engine runs as a child process speaking JSON over stdio. Implications that surprise people coming from in-process SDKs:

- **The engine owns context management.** Automatic compaction (Claude Code's signature long-run capability) happens inside the subprocess — your orchestrator doesn't watch the token count. This is the killer feature for hours-long runs: the agent stays coherent across contexts that would overflow a naive loop.
- **The boundary is process-level.** Tools execute in the subprocess's privileges within `cwd`. Your sandbox *is* the process boundary plus filesystem scoping — not a language-level isolation. This is why `cwd` discipline and permission callbacks matter more than any in-code check.
- **Lifecycle is yours to manage.** Subprocesses die, hang, and leak. Wrap queries with timeouts, handle restart-on-crash, and kill process trees on teardown (orphaned engines keep running — and keep billing).
- **Latency profile differs.** Every turn crosses a stdio boundary and the engine's own startup (~seconds for a fresh session). You don't use this SDK for snappy request/response — you use it because the task takes an hour.

### Built-in tools

The SDK inherits Claude Code's battle-tested toolset: `Bash`, file edit/read/write, `Grep`/`Glob` search, `WebFetch`/`WebSearch`, and the `Task` sub-agent tool. Don't reimplement these — extend via MCP instead. Two expert notes on them:

- **These tools are *good* in ways homegrown ones aren't.** The `Edit` tool's old-string/new-string matching, `Grep`'s ripgrep-backed search, and `Task`'s isolated sub-agent contexts encode thousands of hours of agentic-failure tuning. Rebuilding them is the most common way teams lose the SDK's value.
- **`allowed_tools` is the blast-radius dial.** `["Read", "Grep", "Glob"]` is a read-only researcher; adding `Bash` is a step change in capability and risk. Scope it per task-type, not per deployment.

### The permission model — three tiers, use all of them

1. **`permission_mode` presets** — coarse policy (`acceptEdits` auto-approves edits but not arbitrary Bash).
2. **`allowed_tools` / deny rules** — the capability allowlist; what *can* be called.
3. **`can_use_tool` callback** — per-call programmatic approval: your code inspects every (tool, args) pair and decides. This is where real policy lives: "Bash allowed only for `git`/`pytest` command prefixes; Write allowed only under `/workspace/src`."

The production pattern: allowlist defines the menu, `permission_mode` sets defaults, and `can_use_tool` encodes the actual rules — logged, versioned, tested. Destructive actions additionally route to a human through your orchestrator (the SDK emits the request; you surface it).

### Sessions and forking — long-horizon state

`resume(session_id)` continues a prior session (history intact); `fork_session` branches from it — the agent-memory equivalent of `git branch`. Patterns this enables: retry a failed long task *from the fork* with different instructions (the agent doesn't re-read all the files it already read — session history carries the context); run "what-if" branches from a checkpoint; or hand a session to a reviewer agent. Sessions are the state layer — combine with git in `cwd` for the filesystem layer, and your long-horizon agent gets both rewindable.

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

## Code: permission-gated agent (production shape)

```python
from claude_agent_sdk import query, ClaudeAgentOptions

async def can_use_tool(tool_name: str, tool_input: dict) -> bool:
    if tool_name == "Bash":
        cmd = tool_input.get("command", "")
        return cmd.split()[0] in {"git", "pytest", "ruff"}  # prefix allowlist
    if tool_name == "Write":
        return tool_input.get("file_path", "").startswith("/workspace/src")
    return tool_name in {"Read", "Grep", "Glob"}

options = ClaudeAgentOptions(
    model="claude-sonnet-5-5",
    cwd="/workspace",                      # the filesystem boundary
    allowed_tools=["Bash", "Edit", "Read", "Write", "Grep", "Glob"],
    permission_mode="default",             # everything asks
    can_use_tool=can_use_tool,             # your programmatic policy
)
# for tool_name, args, result in await query_with_permissions(...): ...
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

- **Latency:** Long-horizon agents run for minutes to hours. Stream progress; `hooks` can emit per-tool events — surface them (a progress UI is the difference between "trusted tool" and "black box we tolerate").
- **Cost:** Token usage scales with file sizes the agent reads — the engine reads whole files and greps across trees. Scope `cwd` tightly (a monorepo root costs orders of magnitude more than a service subdirectory). Compaction keeps the *context* bounded but your bill still reflects everything read.
- **Failure modes:** (1) agents delete or mangle files in their sandbox — run `cwd` as a git worktree and diff the result; (2) subprocess hangs — external watchdog timeouts (the engine won't police itself); (3) session corruption on abrupt kill — resume fails; fork early on long tasks.
- **Security:** Never point `cwd` at `/` or secrets directories. Prefer `can_use_tool` approval for destructive tools over blanket allowlists. Treat the agent's *file reads* as data egress — a workspace containing secrets plus a WebFetch-enabled agent is an exfiltration chain (`02-context-engineering/04-prompt-injection-defense.md`).
- **Observability:** `hooks` give you tool-level events; persist them with the session id. When an hours-long task goes wrong, the event stream plus git history is your incident report.

## Anti-patterns

- ❌ **Running the agent with no sandbox.** Catastrophic.
- ❌ **Giving the agent write access to your repo without git.** You can't undo.
- ❌ **Blanket `allowed_tools` including Bash with no `can_use_tool` policy.** The allowlist is the menu, not the policy.
- ❌ **Ignoring the agent's bash output.** Read every command.
- ❌ **Expecting the OpenAI-style `Agent(...).run()` shape.** This SDK is a streaming subprocess API — `query()` / `ClaudeSDKClient` — not an object graph.
- ❌ **Reimplementing file/search tools the SDK already ships.** You lose hardened behavior and gain bugs.

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
