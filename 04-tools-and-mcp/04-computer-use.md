# Computer Use & Browser Automation

> **Level:** ADV · **Last verified:** 2026-10-20 · **Sources:** [Anthropic computer use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool), [Browser-Use](https://github.com/browser-use/browser-use)

## Why this matters

Some tasks have no API. Legacy internal tools, desktop apps, gated websites — sometimes the only path is driving a browser or desktop GUI. Computer-use agents unlock these workflows, but they're slow, brittle, and risky. Use sparingly. The expert framing: computer use trades the *contract* of an API (typed, stable, testable) for the *pixels* of a UI (ambiguous, shifting, unversioned) — every reliability technique in this note is about re-introducing contract-like structure where none exists.

## Core concepts

### Three approaches

| Approach | Examples | Best for | Failure surface |
|----------|----------|----------|-----------------|
| **Browser automation libs** | Playwright, Selenium, Puppeteer | Scripted, deterministic flows | Code rot when selectors change |
| **LLM + browser automation** | Browser-Use, Stagehand, LaVague | Adaptive flows with LLM deciding next action | Model misreads page; DOM drift |
| **Native computer use** | Anthropic computer use, OpenAI CUA | Full desktop control, not just browser | Everything above + pixel ambiguity |

### The capability ladder (spend reliability where you can get it)

The ordering that matters, from most to least reliable:

1. **API exists** → use it. No exceptions worth discussing.
2. **DOM is accessible** → DOM-level agents (Browser-Use, Stagehand): the model reads structured accessibility-tree/DOM state, not pixels. Selectors and text survive CSS redesigns; labels survive layout shifts.
3. **Only pixels exist** (desktop apps, RDP, canvas-heavy web apps, games) → native computer use. Screenshot-in, action-out.

The reliability gap between rungs is not incremental. DOM-level agents get *machine-readable* page state; pixel-level agents reconstruct it from vision — every step is an interpretation that can be wrong. The 2026 practical split: for web-only workflows, **Playwright MCP** (drive a real browser through the MCP protocol) and DOM-level agents are cheaper and more reliable than pixel-level computer use — reach for pixels only when there is no DOM.

### The action-space problem

A GUI exposes a huge action space (click any pixel, type anything, any key combo). Models narrow it with vision + conventions, but the residual ambiguity is the root cause of brittleness:

- **The "where" problem.** "Click the Submit button" requires localizing a visual pattern; resolution changes, themes, and lazy-loading move targets. Mitigations: constrain viewport (fixed 1280×800 screenshots — the tool config exists for this reason), wait for network idle before acting, retry-on-miss.
- **The "when" problem.** The model can't distinguish "loading" from "done" from "error" without explicit signals. Mitigations: add wait states to your harness, verify post-action state (screenshot diff: did the page actually change?).
- **The "what happened" problem.** Silent failures (click registered, nothing happened) accumulate into corrupted flows. Mitigations: validate end-state assertions — a computer-use task isn't done when the model stops; it's done when a *checkable* outcome holds (file exists, confirmation text visible, row count changed).

That last point is the single biggest upgrade from naive to production computer-use: **turn every task into act-then-verify loops** with programmatic verification wherever the end state is observable (filesystem, DB, follow-up API call).

### The latency reality

Computer use is slow:

- Screenshot → model → action → screenshot → ...: 3–10s per step.
- A 20-step flow takes 1–3 minutes.
- Cost: 20 steps × ~$0.05/step = $1+/task (screenshot tokens + thinking + actions; screenshots are *input tokens* on every step — a fresh 1280×800 frame each time, which is why per-step cost stays flat-to-rising while the conversation grows).

Reserve for low-frequency, high-value tasks. A nightly 20-step reconciliation over a legacy tool at $1.50/run is fine; the same technique in a live chat UX is a non-starter.

### Recovery and idempotency

UI flows fail mid-sequence (auth timeout, modal popup, A/B layout change). Production harnesses need:

- **Idempotent task decomposition** — each step either hasn't run or completed; retries don't double-submit orders. Where the UI can't guarantee this, checkpoint (screenshot + state) before committing actions.
- **Bounded retries with variation** — retrying the identical action that failed usually fails identically; retry with a re-read of the page (fresh screenshot, possibly scrolled) or escalate to a different selector/path.
- **Human handoff points** — define the states where the flow parks for a human (CAPTCHA, 2FA, payment confirmation) instead of improvising.

## Code: Browser-Use (LLM + Playwright)

```python
from browser_use import Agent
from langchain_openai import ChatOpenAI

agent = Agent(
    task="Go to amazon.com, search for 'wireless mouse', sort by price low-to-high, return the top 3 product names and prices.",
    llm=ChatOpenAI(model="gpt-6.1-sol"),
)
result = await agent.run()
print(result.final_output)
```

## Code: Anthropic computer use

```python
import anthropic
client = anthropic.Anthropic()

resp = client.beta.messages.create(
    model="claude-sonnet-5-5",
    max_tokens=4096,
    tools=[{"type": "computer_20250919", "name": "computer", "display_width_px": 1280, "display_height_px": 800, "display_number": 0}],
    messages=[{"role": "user", "content": "Open Firefox and navigate to example.com."}],
    betas=["computer-use-2025-09-19"],
)
# Then implement: screenshot, send to model, execute returned action (click, type, key), repeat.
```

## Production concerns

- **Latency:** 3–10s per step. Use for batch, not real-time UX. Parallelize *tasks* (multiple browser sessions), never steps within a task.
- **Cost:** $1–5 per task is typical. Screenshot tokens dominate: every step re-sends a fresh frame as input. Fixed viewport sizes keep per-step cost predictable; trimmed screenshots (crop to the relevant region when your harness can infer it) cut it.
- **Failure modes:** (1) UI changes break flows — detect (post-action verification), retry with variation, alert on pattern-of-failure (3 failures at the same step = the page changed, not bad luck); (2) model hallucinates a button that doesn't exist — the act-then-verify loop catches it, a fire-and-forget harness doesn't; (3) flaky selectors — prefer DOM-level access where possible for exactly this reason.
- **Security:** Computer-use agents can do anything a human can — sandbox them (VM, restricted user, no admin, network allowlist). Credential handling is the sharp edge: the agent must authenticate *somewhere*; prefer scoped session credentials injected per-task and revoked after, over long-lived passwords in the environment. And remember the injection surface: the pages the agent reads are untrusted content that can *instruct* it (`02-context-engineering/04-prompt-injection-defense.md`) — a crafted webpage saying "click here to continue" is an attack on the agent.
- **Observability:** Keep the screenshot sequence for every run (before/after each action). When it fails — and it will — the sequence is the only debuggable artifact. This is also your audit trail for compliance-sensitive flows.

## Anti-patterns

- ❌ **Using computer use for tasks that have an API.** Always prefer APIs.
- ❌ **Fire-and-forget task definitions.** Every task needs a programmatic end-state assertion.
- ❌ **Running computer-use agents with admin privileges** or on hosts with reachable secrets.
- ❌ **No screenshot logging.** When it fails, you can't debug without the screenshot sequence.
- ❌ **Pixel-level automation when the DOM is accessible.** Climb *down* the reliability ladder only when forced.

## References

- [Anthropic computer use tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool) — verified 2026-10-20
- [Browser-Use](https://github.com/browser-use) — verified 2026-10-20
- [Stagehand](https://github.com/browserbase/stagehand) — verified 2026-10-20
