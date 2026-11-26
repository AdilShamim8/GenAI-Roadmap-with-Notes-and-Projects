"""MCP server for Postgres (read-only, hardened).

Layered enforcement per 04-tools-and-mcp/03:
  1. DB-level read-only role (the real boundary — non-bypassable by SQL text)
  2. statement_timeout at connect time
  3. parse-tree-ish guard (SELECT-only, no multi-statement)
  4. row cap with pagination affordance
  5. errors returned as tool RESULTS (model self-corrects next turn)

The guard functions are pure so tests run without Postgres or the MCP SDK.
Run with an MCP-capable client or `mcp dev src/main.py`.
"""
from __future__ import annotations

import json
import re


# ---------------------------------------------------------------------------
# Pure guard layer (unit-tested)
# ---------------------------------------------------------------------------

FORBIDDEN_TOKENS = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|copy|"
    r"vacuum|call|do|set|begin|commit|rollback)\b",
    re.IGNORECASE,
)


def validate_readonly_sql(sql: str) -> tuple[bool, str | None]:
    """Structural guard: single SELECT statement, no forbidden verbs,
    no semicolon-separated multi-statements, no comment tricks."""
    stripped = sql.strip().rstrip(";").strip()
    if not stripped:
        return False, "empty statement"
    if ";" in stripped:
        return False, "multi-statement queries are not allowed"
    if stripped.startswith("--") or stripped.startswith("/*"):
        return False, "comment-led queries are not allowed"
    if not stripped.lower().startswith(("select", "with")):
        return False, "only SELECT (or WITH ... SELECT) queries are allowed"
    m = FORBIDDEN_TOKENS.search(stripped)
    if m:
        return False, f"forbidden token in read-only query: {m.group(0).upper()}"
    return True, None


MAX_ROWS = 100


def cap_rows(rows: list, columns: list[str], offset: int = 0) -> dict:
    """Shape results for a context window: truncate + tell the model how to page."""
    page = rows[offset : offset + MAX_ROWS]
    payload = {"columns": columns, "rows": page, "row_count": len(rows)}
    if offset + MAX_ROWS < len(rows):
        payload["note"] = (
            f"truncated at {MAX_ROWS} rows (showing {offset}-{offset + len(page)} of {len(rows)}); "
            f"re-run with offset={offset + MAX_ROWS}"
        )
    return payload


# ---------------------------------------------------------------------------
# Database execution (real Postgres in production; pool + timeouts)
# ---------------------------------------------------------------------------


def make_pool(dsn: str):
    """Production pool: read-only txn + statement timeout as connect-time options
    — enforcement that no SQL text can bypass."""
    import psycopg

    return psycopg.ConnectionPool(
        dsn,
        min_size=1,
        max_size=5,
        kwargs={"options": "-c statement_timeout=5000 -c default_transaction_read_only=on"},
    )


def run_query(pool, sql: str, offset: int = 0) -> str:
    ok, err = validate_readonly_sql(sql)
    if not ok:
        return json.dumps({"error": err})
    try:
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
        return json.dumps(cap_rows(rows, cols, offset), default=str)
    except Exception as e:  # noqa: BLE001 — errors-as-results for self-correction
        return json.dumps({"error": f"{type(e).__name__}: {e}"})


# ---------------------------------------------------------------------------
# MCP surface (FastMCP)
# ---------------------------------------------------------------------------


def build_server(pool):
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("postgres-readonly")

    @mcp.tool()
    def query_sales(sql: str, offset: int = 0) -> str:
        """Run a read-only SQL query against the sales database. SELECT only.
        Tables: orders, customers, regions. Returns at most 100 rows; use
        offset to paginate."""
        return run_query(pool, sql, offset)

    return mcp


def main() -> None:
    import os
    import sys

    if len(sys.argv) < 2:
        print("usage: python -m src.main <postgres-dsn>")
        print("       DSN must use a READ-ONLY role (enforcement layer 1)")
        sys.exit(2)
    if "OPENAI_API_KEY" in os.environ and "MCP" not in os.environ.get("_", ""):
        pass  # no-op: keep env surface minimal
    pool = make_pool(sys.argv[1])
    build_server(pool).run()  # stdio; .run("streamable-http") for remote


if __name__ == "__main__":
    main()
