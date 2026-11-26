# Safety & Security — Interview Questions

> **Rung:** [10-safety](../../10-safety/01-prompt-injection-taxonomy.md) · **Last verified:** 2026-10-20

## Q1 — "We've added a filter that blocks prompt injection." What's wrong with that claim?

**Model answer:** It mistakes one layer for the boundary. The structural fact: instruction and data channels are *not separable* in a pure-prompt architecture — the model conditions on one token stream, so no prompt-level defense ("ignore instructions in documents") can be reliable. Filters catch the lazy and known attacks (mass-scanning payloads, public templates) and lose to hand-crafted semantic injections ("speaking as the documentation itself, the correct next step is...").

What actually holds: **capability-grounded design**. Privilege separation (the reader of untrusted content gets no tools — a successful injection on a read-only agent is contained by construction), tool allowlists with scoped credentials (injection succeeds but the capability doesn't exist), egress default-deny (exfiltration needs an outbound channel; cut the channel and the payload has nowhere to go — the highest-yield filter targets the *channel*, not the unbounded payload space), and human approval for irreversible actions. Filters, classifiers, spotlighting are layers on top of that wall.

**Senior note:** severity scales with what the compromised session can *do*, not with payload cleverness — the threat model comes before the defense stack. And every blocked-input log is attack reconnaissance data; review it to see which class is being attempted *before* one succeeds.

## Q2 — Classify prompt injection attacks in a way that helps you defend

**Model answer:** By position × payload. *Position* — who controls the channel: **direct** (the user is the attacker — severity scales with what the session can do; in B2C support it's annoyance, with financial tools it's loss), **indirect** (a third party poisoned content your agent retrieves — the user is the victim; the attacker needs no access to your product, just a webpage you'll eventually fetch), **tool-output** (a compromised dependency your agent treats as authoritative — the MCP-era supply-chain case), **multimodal** (each modality you accept is a filter-bypass channel — your text filters never see the image).

*Payload* — what it wants: **exfiltration** (needs an egress channel — defend the channel), **privilege escalation** (needs a capability — defend with allowlists; if the tool isn't there, the injection is a bark with no bite), **behavior subversion** (no data leaves, but behavior/telemetry is corrupted — the quiet class). Plus the evasion meta-layer: token smuggling (homoglyphs, zero-width) defeated by NFKC normalization + Cf-stripping — cheap, permanent arms race.

**Senior note:** the classification earns its keep by mapping to mitigations — egress-deny targets exfiltration regardless of payload phrasing; capability scoping neutralizes escalation *by class*; multimodal inputs need modality-aware scanning. A taxonomy that doesn't change your defense design is trivia.

## Q3 — Design the red-teaming program for a customer-facing agent

**Model answer:** Layered by cadence and depth, findings feeding forward: **promptfoo redteam on every PR** (minutes — regression coverage against our own attack corpus), **Garak on every model change** (hours — the known-vulnerability space systematically; read it like a fuzzer: the signal is per-probe-class failure-rate *trends* across versions, not individual hits), **PyRIT campaigns quarterly and pre-launch** (deep, adaptive — the adversarial-chat pattern gives you multi-turn attacks that find what templates can't: conditioning attacks over several turns, callback extraction, tool-chain coercion).

Operational rules: scan against **staging with sandboxed tools and fake credentials** — the scanner is deliberately sending malicious instructions to your agent; never let it reach production tools. Judge the objective-success scoring like any LLM-as-judge (calibrate, spot-check). And triage findings in writing into fix / accept / track — a discovered-and-unfixed vulnerability that later leaks is worse than never having scanned, because you *knew*.

**Senior note:** re-run on every model upgrade — model changes are the #1 source of new vulnerability classes in an unchanged system. And "no known vulnerabilities found by these probes" ≠ "safe" — the coverage claim is bounded by the probe library; say exactly that in the report.

## Q4 — Output filtering: what breaks when you bolt it onto a streaming agent?

**Model answer:** The race: tokens reach the user before a completed-text filter can act — "filter the final text for the log" is forensics, not defense. The ladder: **sentence-boundary buffering** (hold each sentence until its verdict; one sentence of latency; blocked sentences replaceable mid-stream — the consumer default), **first-chunk gating** (filter chunk 1 hard, trust momentum; catches most policy breaks, no guarantee), **full buffering on high-stakes paths** (legal/medical — latency buys the guarantee).

The second breakage: **one rule set for two audiences**. User-facing text needs PII/moderation (human harm); tool-call arguments need domain rules and schema validation (machine harm — a URL arg to fetch_url is an exfiltration channel). The most common production gap is filtering the visible response while tool args pass straight through.

And the failure-action design: redact when repairable (PII masking keeps the answer usable), replace when blocked (a designed fallback, not a bare refusal), intercept at the tool when it's a tool problem. "Block everything" produces brittle systems product then fights.

**Senior note:** Presidio over regex — models *reformat* (a phone number spaced your regex never saw); NER-based detection understands context and checksum validators confirm before masking. Regex's asymmetric errors hurt: false negatives leak exactly what you existed to catch; false positives redact order IDs users need. Filter logs are your most sensitive store (the worst outputs + user data) — strictest retention in the system.

## Q5 — What are your EU AI Act obligations as a deployer?

**Model answer:** Timeline first: in force 2024-08-01; prohibited practices since 2025-02-02; **GPAI obligations since 2025-08-02** (providers owe transparency, copyright policy, training-data summaries — and that information flows *to you*); **high-risk system obligations phase in from 2026-08-02**. Article 50 and the GPAI chain-of-interest rules mean a downstream complaint can ask what you knew about the model you deployed.

Deployer duties in practice: **risk-classify your own use case** (limited vs high risk — it's your classification to make and defend, and it determines which obligations apply), maintain the model audit doc (exact version *snapshots*, not rolling aliases; provider intended-use; data-handling terms; limitations mapped to actions — every card limitation gets a routing rule, a mitigation, or a written acceptance), and keep the documentation that proves diligence — in an incident, "we knew and accepted this risk in writing" versus "we never looked" is the negligence line.

**Senior note:** the audit doc is risk information the provider hands you for free, and engaging with it demonstrably allocates liability. Pin dated snapshots because cards describe checkpoints, not aliases; and watch provider changelogs for data-handling term changes like you watch dependency advisories.
