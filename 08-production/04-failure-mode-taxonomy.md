# Failure-Mode Taxonomy

> **Level:** ADV · **Last verified:** 2026-10-20

## Why this matters

Most production GenAI incidents fall into ~8 categories — plus a 2026-era set you must now also watch: **MCP tool poisoning** (a malicious/compromised server returns instructions that hijack the agent), **rogue MCP server** (supply-chain risk in third-party servers), and **inter-agent confused deputy** (in multi-agent or A2A systems, a mis-scoped agent acts with another's privileges). Knowing the taxonomy lets you build detection, mitigation, and runbooks for each — instead of treating every incident as a surprise. The expert framing: this is SRE's "error budget" thinking adapted to a system whose failures are *semantic* (wrong-but-plausible) as often as *mechanical* (crashed, timed out). Mechanical failures alert on their own; semantic failures need evals to notice. Half the taxonomy is invisible without measurement.

## The taxonomy

| # | Failure mode | Symptom | Detection | Failure class |
|---|--------------|---------|-----------|---------------|
| 1 | **Hallucination** | Confident wrong answer | Faithfulness eval; cross-check | Semantic |
| 2 | **Context overflow** | Truncated input, missed context | Token counter pre-call | Mechanical |
| 3 | **Tool-call loop** | Agent calls same tool repeatedly | Iteration counter | Mechanical |
| 4 | **Prompt injection** | Agent follows injected instructions | Input + output filters | Semantic |
| 5 | **Rate limit / overload** | 429s from provider | Retry with backoff + fallback | Mechanical |
| 6 | **Latency spike** | p99 > 10s | OTel + alerting | Mechanical |
| 7 | **Cost runaway** | Daily cost 10× baseline | Cost dashboard + alerts | Mechanical |
| 8 | **Drift** | Quality degrades over weeks | Online evals vs baseline | Semantic |
| 9 | **MCP tool poisoning** | Agent executes instructions from tool output | Output diffing vs declared schema; tool-output injection scan | Semantic |
| 10 | **Rogue MCP server** | Supply-chain behavior change in a dependency | Version pinning + tool-schema drift alerts | Semantic |
| 11 | **Inter-agent confused deputy** | Agent acts with another's privileges | Per-agent authz audit on every tool call | Semantic |

The semantic/mechanical split is the operational insight: mechanical failures (#2,3,5,6,7) are detectable with counters and thresholds — they *announce themselves*; semantic failures (#1,4,8–11) produce valid-looking traffic that only evals, injection scanners, or authz audits catch. A monitoring stack that would pass a traditional SRE review catches the left half of the table and is blind to the right half — which is where the worst incidents live (an agent confidently exfiltrating data via a poisoned tool "works" flawlessly at every mechanical layer).

## Per-mode mitigations

### Hallucination

- RAG with citations.
- Faithfulness eval in pipeline.
- "I don't know" allowed in system prompt.

### Context overflow

- Pre-count tokens; trim history.
- Summarize old turns.

### Tool-call loop

- Cap iterations (5–10).
- Detect repeated tool calls with same args.

### Prompt injection

- Input filters (deterministic).
- Constitutional pattern (second model checks).
- Privilege separation.

### Rate limit / overload

- Exponential backoff with jitter.
- Multi-vendor fallback chain.

### Latency spike

- Timeouts per call.
- Stream to mask latency.
- Cache common queries.

### Cost runaway

- Per-request budget.
- Per-user daily cap.
- Alert on >2× baseline.

### Drift

- Online evals (sample 1–5%).
- Weekly comparison vs baseline.
- Periodic prompt refresh.

### MCP tool poisoning / rogue servers

- Pin MCP server versions; alert on tool-schema changes at `tools/list` (a server that silently adds a tool is a supply-chain event).
- Scan tool outputs for instruction-like content before they enter context (`02-context-engineering/04-prompt-injection-defense.md`).
- Least-privilege credentials per server so a poisoned server's blast radius is its own tools only.

### Inter-agent confused deputy

- Per-agent identity + scoped credentials — the *agent*, not the user request, is the authz principal.
- Audit every tool call with (caller-agent, target-agent, tool, decision) so cross-privilege actions are reconstructible.
- In A2A, verify the calling agent's declared identity and scope on every hop (`06-multi-agent/02-handoff-protocols.md`).

## Code: iteration counter

```python
class AgentLoop:
    def __init__(self, max_iterations=10):
        self.max_iterations = max_iterations
        self.history = []

    def run(self, query: str):
        for i in range(self.max_iterations):
            resp = call_model(query, history=self.history)
            if not resp.tool_calls:
                return resp.content
            for tc in resp.tool_calls:
                key = (tc.name, json.dumps(tc.args, sort_keys=True))
                if self.history.count(key) >= 2:
                    raise RuntimeError(f"Loop detected: {tc.name} called 3x with same args")
                self.history.append(key)
                result = execute_tool(tc.name, tc.args)
                self.history.append({"tool_result": result})
        raise RuntimeError(f"Max iterations ({self.max_iterations}) exceeded")
```

## Production concerns

- **Latency:** Detection adds <1ms.
- **Cost:** Negligible.
- **Failure modes:** Detection itself can fail. Test it — inject each failure mode in staging (a looping tool, a poisoned payload, a 429 storm) and verify the detector fires. An untested detector is a runbook line, not a control.
- **Security:** Detection logs may contain PII. Treat as sensitive.
- **Runbooks:** The taxonomy earns its keep when each row has a *runbook* — for mode N: symptom, first three debugging steps, containment action, escalation path. Incidents under time pressure should be executed from the runbook, not improvised from the table.

## Anti-patterns

- ❌ **No detection for tool loops.** Catastrophic cost.
- ❌ **No cost alerts.** One bug = $1000s.
- ❌ **Treating each incident as novel.** Categorize; build runbooks.
- ❌ **Mechanical-only monitoring.** Semantic failures pass every infra check; evals and authz audits are the only nets that catch them.
- ❌ **Untested detectors.** Inject failures in staging; verify alerts fire.
- ❌ **No runbook per mode.** The table is the index; the runbooks are the value.

## References

- [OpenAI: Error codes](https://platform.openai.com/docs/guides/error-codes) — verified 2026-10-20
- [OWASP LLM Top 10](https://genai.owasp.org/) — verified 2026-10-20
- [MCP security considerations](https://modelcontextprotocol.io/specification/2026-07-28/basic/security-best-practices) — verified 2026-10-20
