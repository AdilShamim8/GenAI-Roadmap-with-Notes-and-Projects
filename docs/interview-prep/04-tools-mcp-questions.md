# Tools & MCP — Interview Questions

> **Rung:** [04-tools-and-mcp](../../04-tools-and-mcp/01-function-calling-across-providers.md) · **Last verified:** 2026-10-20

## Q1 — "The model keeps calling tools wrong." Decompose the problem before fixing it

**Model answer:** "Calling tools wrong" is three different problems. **Selection** (wrong tool or hallucinated tool names): usually too many similar tools or descriptions that don't discriminate — fix with fewer tools, sharper descriptions naming when-to-use *and* when-not, enum-constrained params. **Formulation** (schema-violating args): no decoding constraint or ambiguous schema — `strict: true` on OpenAI constrains the decoder (invalid JSON becomes ungenerable); elsewhere, validate server-side and *return the validation error as a tool result* so the model self-corrects in one turn. **Orchestration** (wrong order, loops, refusal to call): the model can't see your state machine — make state explicit in-conversation ("already called X, it failed with Y"), cap iterations, hash (name, args) to detect duplicate calls.

The recovery pattern everyone under-uses: errors-as-results. `{"error": "city not found; known cities: [...]"}` teaches the model in one round-trip; raising in your harness teaches it nothing.

**Senior note:** the loop is *yours* on every provider — the model only emits requests; your harness executes and feeds back. Loop-level failure modes (caps, dedup, validation) are harness responsibilities that don't port between frameworks; own them once, centrally.

## Q2 — What does MCP actually standardize, and when would you skip it?

**Model answer:** MCP standardizes the app↔tool integration layer: one protocol (JSON-RPC) exposing tools, resources, and prompts from servers to any MCP-capable host, with capability negotiation, OAuth 2.1 for remote servers, and (2025+) sampling and elicitation for server→client LLM use and human input. The value is the N×M collapse: N apps and M tools need N+M adapters instead of N×M bespoke integrations — the same network effect as LSP, which is its design ancestor.

Skip it when: one application you own consumes one tool you own — plain function calling is simpler (no JSON-RPC, no negotiation). Earn it when a second consumer appears, or when tool logic must run near the data.

The security model is where expertise shows: **the host is the boundary, not the protocol.** MCP authenticates connections, not intent. Tool annotations (`readOnlyHint`) are unverified claims. stdio servers run with your user's privileges (a malicious one reads SSH keys). Sampling inverts control — a server can ask *your* LLM to complete its prompt (confused-deputy risk; approve explicitly). Treat MCP servers as executed dependencies: vet, pin, sandbox.

**Senior note:** transports and versions — stdio for local, Streamable HTTP (HTTP+SSE is *removed* from the spec; tutorials showing it are stale) for remote, Registry for discovery; and gate features on the *negotiated* protocol version, not on "MCP supports X."

## Q3 — Design an MCP server that exposes a sales database. What are the failure modes of the naive version?

**Model answer:** The naive version is `query(sql: str)` with a `startswith("select")` check. Its failure modes, in escalating severity: pattern-match bypass (the check parses nothing), `pg_sleep`/catalog queries (DoS, credential-hashing reads), cross-join table scans (DB meltdown), 10K-row dumps as tool results (~2.5M tokens poisoning the conversation), a module-level DB connection shared across concurrent handlers (psycopg2 connections aren't thread-safe), and unhandled exceptions crashing the session.

The hardened version layers enforcement: **read-only DB role** + `default_transaction_read_only=on` (non-bypassable by any SQL text) > statement timeout at connect (`options='-c statement_timeout=5000'`) > parse-tree validation if accepting SQL at all (sqlglot, not string checks) > row cap with an explicit `offset` affordance for pagination > **connection pool** > errors returned as tool *results* > tool description that documents tables so the model doesn't guess.

**Senior note:** the design rule — expose the *verb the model would naturally say*, not your internal function decomposition; coarse `query_sales(sql)` beats three thin wrappers *unless* the wrappers are the safety boundary for a model that can't write SQL safely. And results are shaped for a context window: truncate with markers, paginate with affordances — that one decision does more for agent reliability than any downstream prompt work.

## Q4 — Computer use: when is it justified, and how do you make it not terrible?

**Model answer:** Justified only when no API exists and no DOM is accessible (legacy internal tools, desktop apps, RDP). The reliability ladder: API > DOM-level agents (Browser-Use/Stagehand — machine-readable page state) > Playwright MCP for browser driving > pixel-level computer use (vision reconstructs what the DOM would have given you).

Making it not terrible: **act-then-verify loops** — every task ends with a programmatic assertion (file exists, row count changed, confirmation text visible), because silent failures (click registered, nothing happened) accumulate into corrupted flows; idempotent task decomposition so retries don't double-submit; bounded retries *with variation* (identical retries fail identically — re-read the page, try a different selector); and human-handoff points for CAPTCHA/2FA/payment instead of improvising.

**Senior note:** the action-space decomposition — *where* (localization under resolution/theme changes; fixed 1280×800 viewport, wait for network idle), *when* (can't distinguish loading from done; wait states + post-action screenshot diffs), *what happened* (silent failures; end-state assertions). Latency and cost are structural: 3-10s/step, screenshot tokens on every step, $1-5/task — batch workflows, not live UX. And the injection surface: pages the agent reads are untrusted content that can *instruct* it.

## Q5 — An agent needs to run model-generated code. What's your architecture?

**Model answer:** Sandbox as capability boundary expressed as infrastructure, with four verifiable dimensions: **isolation** (microVM > container > process — check what guest code can reach), **egress** (default-deny network; the dominant real risk isn't escape, it's the code *using the sandbox's network* to phone home — analysis of local data needs zero egress), **resource limits** (CPU/wall-clock/memory enforced platform-side, because `while True` is coming), **auditability** (inputs, outputs, and every *blocked egress attempt* — blocked-egress alerts are your highest-signal injection telemetry).

Data boundary: data goes *in* as inputs (never DB credentials into the sandbox — that's a pivot point, not a sandbox); outputs come out as untrusted artifacts (scan, store separately, don't pipe into your DB). Managed interpreters (OpenAI/Anthropic) mean your data executes on their infra — a compliance question before a technical one; self-managed (E2B/Modal/Firecracker) put the boundary under your control.

**Senior note:** cold-start economics — the first run pays sandbox boot (50ms-5s by platform); short-lived analysis sessions pay it every task, which is why sub-second-start platforms exist. Match platform to task shape; pin sandbox base images (supply chain); close sessions in `finally:` (zombie sandboxes are a silent bill).

## Q6 — Provider-specific tool-calling: what breaks when you port from OpenAI to Anthropic?

**Model answer:** Four things: **pairing discipline** — Anthropic requires every `tool_use` block answered by a `tool_result` in the very next message (even for failures); get it wrong and you get a 400 naming tool_use ids. **Argument types** — OpenAI chat emits stringified JSON you parse; Anthropic hands you a parsed object in `input`. **Escape hatches** — `tool_choice: {"type": "any"}` *forces* a tool call on Anthropic (a footgun when the task sometimes needs no tools); on OpenAI "auto" plus a plain reply is the norm. **Strictness** — OpenAI's `strict: true` enables constrained decoding for arguments (the biggest single reliability lever, and it does nothing on providers that ignore unknown fields).

**Senior note:** the harness-level invariants that *don't* port automatically — iteration caps, duplicate-call detection, arg validation — reimplement or port them deliberately; frameworks differ in which they own. And tool definitions count toward input tokens on every call: 15 tools ≈ 2K+ tokens/call — prune per route and cache the prefix, or you're paying a tool-token tax at scale.
