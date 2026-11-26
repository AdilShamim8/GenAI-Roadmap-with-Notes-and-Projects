# Production Engineering — Interview Questions

> **Rung:** [08-production](../../08-production/01-cost-engineering.md) · **Last verified:** 2026-10-20

## Q1 — Your LLM bill tripled last month. Walk me through the investigation

**Model answer:** First question: is it *price × volume* (more traffic), *volume × tokens* (longer conversations), or *tokens × rate* (mix shift to expensive models)? Attribution answers it — per-span cost telemetry (model, input/output/cached/reasoning tokens per request, rolled up by route/user/workflow) is the difference between targeted fixes and global cost-cutting.

The usual culprits, in observed-frequency order: (1) **context creep** — conversation histories grew (a new feature keeps more turns; a tool started returning bigger payloads); (2) **cache collapse** — someone added a timestamp or reordered tool definitions in the prefix; cached-token rate fell from 80% to 20%, and at ~10x price spread that triples input cost alone; (3) **reasoning-token drift** — a model upgrade flipped a default effort level, and thinking tokens bill as output; (4) **mix shift** — a routing change sent simple traffic to the balanced tier; (5) genuine traffic growth.

Then the levers, composed: prompt caching (prefix-exact discipline), task-type routing from the call site (zero-latency, zero-misroute — "is this hard?" classifiers misroute exactly where it matters), output caps (output tokens are the 5x-expensive class everyone forgets), batch for the async portion.

**Senior note:** the metric that prevents recurrence is *cost per successful outcome*, not cost per request — a "cheap" 70%-success agent costs more per success than an "expensive" 95% one once retries and handoffs count. And alert on creeping baselines (baseline + 2σ), not just spikes; the quiet creep is the budget killer.

## Q2 — Design the SLO for a chat feature with streaming. What are the failure modes?

**Model answer:** Streaming changes the contract, not the physics: total time is unchanged; *perceived* latency becomes TTFT. So the SLOs split: TTFT p95 < 500ms (prefill — the caching lever), inter-token latency p95 < 100ms (a mid-stream stall is *worse* than a clean wait — it looks broken), and end-to-end p95 as the budget sum. Decode time is output-tokens ÷ TPS — serial, unbypassable; the only levers are fewer output tokens or a faster tier, and "tuning" cannot fix physics.

The budget view makes it manageable: 4s p95 = 4000ms allocated (retrieval 200, TTFT 500, decode 3000, overhead 300); when one component wants more, another must shrink or the SLO moves explicitly. Two dependencies people forget: the *provider's* p95 is a monitored dependency (their congestion lands in your tail; budget for it, alert on their drift, respond with fallback — not by paging your on-call to fix latency they can't affect), and the *retry budget must fit inside* the SLO (3 retries × backoff schedule can exceed a 3s p95 before the user sees anything).

**Senior note:** thinking models blow up tails specifically — reasoning length is stochastic, so "medium effort" spans 2s-40s; per-route budgets are the TTFT control. And measure TTFT/ITL/decode separately: one "request latency" histogram cannot distinguish a prefill problem from a decode problem from provider congestion.

## Q3 — What's different about incident response for agents vs. classic services?

**Model answer:** Classic IR assumes containment = stop the bleeding and rollback restores good state. Agents break both: **long-horizon runs keep running** after you flip the kill switch (async work in flight with hours of autonomy left), and **the damage is delivered content** (wrong answers shown, emails sent, files written) that rollback doesn't un-show. So agent IR adds two verbs: *quarantine* (kill switch stops new requests; then enumerate in-flight runs from the run registry and revoke their tool credentials — the run that can't call tools can't do harm even if the loop lives) and *recall* (a logged artifact index of every user-visible action, so "how many users saw the wrong price?" is a query, not archaeology; external effects need their pre-documented undo story — a payment API with no void operation discovered at 2am is its own incident).

Also: the "fix" during an incident is often a prompt edit — the most seductive dangerous move (feels safe, no rollback discipline). The rule: incident prompt changes go through the same eval gate, compressed — golden-set run in minutes, then ship. The eval-less emergency edit is how a P1 becomes two P1s.

**Senior note:** mechanical monitoring catches half the failure taxonomy — semantic failures (hallucination at scale, injection, drift) pass every infra check and need evals/authz-audit nets. And game-day the flow quarterly; a runbook that has never been run won't run.

## Q4 — A model you depend on is being deprecated in 6 weeks. What's the plan?

**Model answer:** If we've been rehearsing, this is a config flip: the quarterly "next-gen candidate" eval runs mean the migration was validated before the deadline arrived. If not, compressed version of the same playbook: (1) offline evals old vs new on the golden set — new models are *differently* good; budget prompt-adaptation time (untouched prompts on a new model is the naive swap); (2) check the *non-quality* diffs: latency profile (different TTFT/TPS tiers — does it meet the SLO?), price tier (unit economics: 2x price for 5% quality needs the cost-per-success check), tokenizer drift (token counts shift → context guards trip at different string lengths, cache breakpoints move, cost-per-request shifts — migrations that "pass evals" and page finance a week later); (3) canary 5% behind a feature flag with the *old model pinned as a dated snapshot*, not a rolling alias; (4) compare online metrics during canary; ramp or rollback; (5) decommission.

The bundling discipline: model + prompts + eval thresholds ship as one *behavioral version* — a model change and a prompt change deployed separately is the classic silent-regression setup nobody can attribute two weeks later.

**Senior note:** alias-vs-snapshot policy — snapshot where you measure (judges, eval baselines: your ruler must not move), alias where you serve (inherit fixes, but canary metrics are what notice the silent updates). And review the DPA on any *new vendor*: a migration is a data-flow change.

## Q5 — "Just add observability later." Why is that the wrong order for agents?

**Model answer:** Because agents fail *semantically* — confidently wrong outputs that no uptime dashboard registers — and the debugging question is always causality: "which of the 12 calls in this request went wrong, and what did each see?" That answer requires a complete trace tree built at request time: one root per user-facing request (the trace id *is* the correlation key for user complaints), context propagated across every async hop (framework task-spawns are where traces fragment), and cost inputs on every span that spends money (model, input/output/cached/reasoning tokens) — the same attributes power cost attribution and incident forensics.

The "later" trap specifically: OpenTelemetry conventions and span attributes are decided at instrumentation time; retrofitting attribute names across months of stored traces is miserable, and un-instrumented months are dark for every drift comparison you'll later want. Tail sampling from day one — keep 100% of error/slow/high-cost traces, 5-10% of the healthy — keeps it cheap without losing failure forensics.

**Senior note:** prompts don't go on spans (PII, retention, widest-access data store) — content-addressed references do; "click to see the exact prompt" without the compliance headache. And verify propagation with a synthetic request that must appear as *one* trace — fragmenting pipelines fail silently.
