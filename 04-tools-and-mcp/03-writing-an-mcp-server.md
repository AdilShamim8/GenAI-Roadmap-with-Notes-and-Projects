# Writing an MCP Server

> **Level:** INT · **Last verified:** 2026-10-20 · **Sources:** [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk), [MCP spec 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/basic/)

## Why this matters

Off-the-shelf MCP servers cover common cases (filesystem, Postgres, GitHub). But the moment you have an internal API, a custom database, or a domain-specific tool, you need to write your own. It's a 50-line exercise in Python.

## Core concepts

### The MCP Python SDK

```bash
pip install mcp
```

The SDK exposes two layers: the low-level `Server` class (manual handler registration) and **FastMCP** (`from mcp.server.fastmcp import FastMCP`) — the high-level, decorator-based standard used in virtually all current examples. Use FastMCP unless you need raw protocol control. Test any server with `mcp dev server.py` (MCP Inspector).

### The lifecycle

1. Server starts, registers handlers.
2. Client connects, requests capability negotiation.
3. Client calls `tools/list` → server returns tool schemas.
4. Client (on behalf of LLM) calls `tools/call` with a tool name + args.
5. Server executes, returns result.
6. Repeat.

## Code: a Postgres-querying MCP server (FastMCP)

```python
# server.py  —  pip install "mcp[cli]" psycopg2-binary
from mcp.server.fastmcp import FastMCP
import psycopg2, json

mcp = FastMCP("postgres-readonly")
conn = psycopg2.connect("dbname=sales user=readonly host=localhost")

@mcp.tool()
def query_sales(sql: str) -> str:
    """Run a read-only SQL query against the sales database. SELECT only."""
    if not sql.strip().lower().startswith("select"):
        return "Error: only SELECT queries allowed."
    with conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
    return json.dumps({"columns": cols, "rows": rows}, default=str)

if __name__ == "__main__":
    mcp.run()  # stdio transport; mcp.run("streamable-http") for remote

```

Run with an MCP-aware client (Claude Desktop, Cursor, your own agent), or debug interactively with `mcp dev server.py`.

## Production concerns

- **Latency:** Each tool call is a request/response. Use connection pooling for DB-backed servers.
- **Cost:** Self-hosted; the cost is your infra.
- **Failure modes:** Unhandled exceptions in a tool handler crash the server. Wrap everything in try/except.
- **Security:** Enforce least privilege at the server level (read-only DB user) and add `readOnlyHint`-style annotations. Don't trust the LLM to police itself.

## Anti-patterns

- ❌ **Exposing mutating SQL (INSERT/UPDATE/DELETE).** Use read-only DB users.
- ❌ **Hand-rolling the low-level Server when FastMCP suffices.** Half the code, fewer protocol bugs.
- ❌ **stdio transport for a remote server.** Remote deployments use Streamable HTTP with OAuth 2.1.
- ❌ **Returning huge result sets.** Paginate or summarize.
- ❌ **Hardcoding credentials.** Use env vars.

## References

- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) — verified 2026-10-20
- [MCP TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk) — verified 2026-10-20
