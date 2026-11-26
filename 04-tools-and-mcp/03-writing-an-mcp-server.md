# Writing an MCP Server

> **Level:** INT · **Last verified:** 2026-10-20 · **Sources:** [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk), [MCP spec 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/basic/)

## Why this matters

Off-the-shelf MCP servers cover common cases (filesystem, Postgres, GitHub). But the moment you have an internal API, a custom database, or a domain-specific tool, you need to write your own. It's a 50-line exercise in Python. The expert part isn't the protocol plumbing — the SDK handles that — it's the interface design: what you expose as a *tool* (model-controlled, schema-validated) vs a *resource* (host-controlled, read-only) vs not at all, and how much rope each tool hands the model.

## Core concepts

### The MCP Python SDK

```bash
pip install mcp
```

The SDK exposes two layers: the low-level `Server` class (manual handler registration) and **FastMCP** (`from mcp.server.fastmcp import FastMCP`) — the high-level, decorator-based standard used in virtually all current examples. Use FastMCP unless you need raw protocol control. Test any server with `mcp dev server.py` (MCP Inspector).

### The lifecycle

1. Server starts, registers handlers.
2. Client connects; capability negotiation.
3. Client calls `tools/list` → server returns tool schemas.
4. Client (on behalf of LLM) calls `tools/call` with a tool name + args.
5. Server executes, returns result.
6. Repeat.

Note where *your* code runs: only steps 3-5's handlers. The SDK owns framing, negotiation, and dispatch. Your exposure is the handler bodies — everything about them (validation, error shape, timeouts, privileges) is your security and reliability surface.

### Tool design: the API you're really writing

An MCP server's tools are a *model-facing API*, and normal API-design instincts need translation:

- **Fewer, coarser tools beat many thin ones.** Every tool's schema loads into context on every request, and selection accuracy drops as tool count grows (`01-function-calling-across-providers.md`). `query_sales(sql)` is one tool; `get_customer`, `get_orders`, `get_regions` as three thin wrappers are context bloat *unless* the model can't write SQL safely — in which case the wrappers are the safety boundary. Design rule: expose the *verb the model would naturally say*, not your internal function decomposition.
- **Return errors as results, not exceptions.** A tool result of `"Error: only SELECT allowed; got UPDATE"` lets the model self-correct next turn. An unhandled exception kills the handler (and depending on the host, the session) and teaches the model nothing.
- **Shape output for a context window, not a screen.** The result goes back into the prompt. A 10K-row dump is ~2.5M tokens of poison. Paginate, truncate with an explicit marker ("rows 1-50 of 8,212; pass offset=50"), and summarize where counts suffice. This single design decision does more for agent reliability than any prompt engineering downstream.
- **Make parameters self-describing and enum-constrained.** `"table": {"type": "string", "enum": [...]}` beats free-text table names — it's both a guardrail and a hint about what exists.

### The read-only Postgres pattern (done right)

The classic MCP footgun is `query_sales(sql: str)`. Even with a `startswith("select")` check, the model can still write `SELECT pg_sleep(30)` (DoS), `SELECT * FROM pg_catalog.pg_shadow` (credential hashes), or build a cross-join that eats the DB. The check parses nothing — it pattern-matches. Layered fixes, in order of strength:

1. **Read-only DB user** — `CREATE ROLE ... READ ONLY` at the database level. Non-bypassable by any SQL text.
2. **Statement timeout** — `options='-c statement_timeout=5000'` in the connection string caps runaway queries server-side.
3. **Row/byte limits** — `LIMIT` injection or result truncation in the handler.
4. **Query allowlisting / parse-tree validation** — if you must accept SQL from the model, parse it (e.g. `sqlglot`) and reject anything but a single SELECT — not `startswith`, an actual parse.

### Handling concurrency and state

stdio servers are per-host-connection singletons: one host, one process, potentially concurrent tool calls (hosts may pipeline). FastMCP handlers can run concurrently depending on the runner — which makes a module-level `psycopg2.connect(...)` a shared-mutable-state bug (psycopg2 connections aren't safe across threads). Use a connection pool or connection-per-call; the same discipline as any threaded Python server. For Streamable HTTP deployments, you're a stateless-ish web service: no in-process session state, everything durable goes to the database.

## Code: a Postgres-querying MCP server (FastMCP, hardened)

```python
# server.py  —  pip install "mcp[cli]" "psycopg[pool]"
from mcp.server.fastmcp import FastMCP
import psycopg
import json

mcp = FastMCP("postgres-readonly")

# Pool: handlers may run concurrently; psycopg2/psycopg connections are not thread-safe.
# Read-only role + statement timeout at connect time = non-bypassable guardrails.
POOL = psycopg.ConnectionPool(
    "dbname=sales user=readonly host=localhost",
    min_size=1, max_size=5,
    kwargs={"options": "-c statement_timeout=5000 -c default_transaction_read_only=on"},
)

MAX_ROWS = 100

@mcp.tool()
def query_sales(sql: str, offset: int = 0) -> str:
    """Run a read-only SQL query against the sales database. SELECT only.
    Returns at most 100 rows; pass offset to paginate. Tables: orders, customers, regions."""
    if not sql.strip().lower().startswith("select"):
        return "Error: only SELECT queries allowed."
    try:
        with POOL.connection() as conn, conn.cursor() as cur:
            cur.execute(sql)  # statement_timeout + read-only txn enforce the contract
            rows = cur.fetchmany(MAX_ROWS)
            cols = [d[0] for d in cur.description]
            truncated = cur.fetchone() is not None  # anything left = truncated
    except Exception as e:
        return f"Error: {type(e).__name__}: {e}"  # error-as-result, model self-corrects
    payload = {"columns": cols, "rows": rows}
    if truncated:
        payload["note"] = f"truncated at {MAX_ROWS} rows; re-run with offset={offset + MAX_ROWS}"
    return json.dumps(payload, default=str)

if __name__ == "__main__":
    mcp.run()  # stdio transport; mcp.run("streamable-http") for remote
```

Compare with the naive version: pool instead of shared connection, DB-enforced read-only instead of string check, statement timeout, row cap with pagination affordance, errors as results. ~15 extra lines, categorically different production posture.

Run with an MCP-aware client (Claude Desktop, Cursor, your own agent), or debug interactively with `mcp dev server.py`.

## Production concerns

- **Latency:** Each tool call is a request/response. Use connection pooling for DB-backed servers (above); keep result payloads small (latency *and* downstream token cost — the result lands in the model's context).
- **Cost:** Self-hosted; the cost is your infra. The hidden cost is *token* cost: verbose tool results inflate every conversation that touches them.
- **Failure modes:** (1) unhandled exceptions crash the handler or session — wrap everything, return errors as results; (2) slow handlers (no statement timeout) hang the host's agent loop — enforce timeouts *inside* the tool; (3) schema drift — your DB changes, the tool description lies, the model calls columns that don't exist; generate descriptions from the schema or test them in CI.
- **Security:** Enforce least privilege at the server level (read-only DB user, filesystem-scoped roots) — never at the prompt level. Add `readOnlyHint`/`destructiveHint` annotations for hosts that use them, but treat annotations as UX, not enforcement (`02-mcp-architecture.md`). Secrets via env vars, never in tool results or logs.
- **Testing:** The Inspector (`mcp dev`) is for interactive checks; real tests belong in CI — call `tools/list` (schema contract) and `tools/call` with known inputs (behavior contract). A server without tests is a runtime dependency you can't refactor.

## Anti-patterns

- ❌ **Exposing mutating SQL (INSERT/UPDATE/DELETE).** Use read-only DB users — and `default_transaction_read_only=on` for belt-and-suspenders.
- ❌ **`startswith("select")` as your only SQL guard.** Parse or drop to DB-enforced read-only.
- ❌ **Hand-rolling the low-level Server when FastMCP suffices.** Half the code, fewer protocol bugs.
- ❌ **stdio transport for a remote server.** Remote deployments use Streamable HTTP with OAuth 2.1.
- ❌ **Returning huge result sets.** Paginate or summarize — results go into the model's context.
- ❌ **Hardcoding credentials.** Use env vars.
- ❌ **Module-level shared DB connections.** Pools or per-call connections; handlers can run concurrently.

## References

- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) — verified 2026-10-20
- [MCP TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk) — verified 2026-10-20
- [MCP spec 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/basic/) — verified 2026-10-20
