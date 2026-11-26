# Code Execution Sandboxes

> **Level:** INT · **Last verified:** 2026-10-20 · **Sources:** [E2B](https://e2b.dev/), [Modal](https://modal.com/)

## Why this matters

Agents that can run code are dramatically more capable (data analysis, math, file transforms, scraping). Agents that can run code on *your* infrastructure are a security nightmare. Sandboxes give you the capability without the risk. The expert framing: a sandbox is a *capability boundary expressed as infrastructure* — and the boundary is only as good as its weakest dimension. Isolation without egress control is exfiltration-as-a-service; egress control without resource limits is a DoS waiting for a `while True`; all three without observability is an incident you can't investigate.

## Core concepts

### The options

| Option | Latency | Cost | Isolation | Best for |
|--------|---------|------|-----------|----------|
| OpenAI Code Interpreter | 5–30s | $0.05/run | OpenAI-managed | Quick analysis, charts |
| Anthropic code execution | 5–20s | metered | Anthropic-managed | Claude-integrated workflows |
| E2B | 1–5s | $0.05/min | MicroVM | Production agents needing fast cold-start |
| Modal | 1–3s | pay-per-invocation | Container | Python functions at scale |
| Daytona | 1–5s | per-seat | Devcontainer | Long-lived dev envs |
| Self-hosted gVisor / Firecracker | 50–500ms | infra | VM | Full control, max complexity |

The managed-vs-self-hosted split is the first decision: provider-managed interpreters (OpenAI/Anthropic) give you *zero* isolation configuration — you inherit their boundaries, including their egress policies, and your data transits their infra (a compliance question, not just a technical one). Self-managed sandboxes (E2B, Modal, Firecracker) put the boundary *under your control* — you decide egress, snapshots, retention — at the price of operating them.

### What a sandbox gives you — as a checklist to verify, not a promise to assume

- **Isolation** — the agent's code can't reach your network or filesystem. *Verify:* what's the isolation primitive (microVM > container > process), and can guest code see host metadata endpoints?
- **Ephemerality** — every run starts from a clean snapshot. *Verify:* is filesystem state truly per-session, or do warm sandboxes share state across runs? Warm-start optimization can quietly break ephemerality.
- **Resource limits** — CPU, memory, network egress caps. *Verify:* are limits enforced per-sandbox, and what happens on breach (kill? throttle? bill you?)
- **Auditability** — full input/output logs. *Verify:* where do logs live, who can read them, do they capture network flows or just stdout?

The checklist matters because "sandboxed" spans a quality range: a Firecracker microVM and a Docker container with `--network=host` are both "sandboxes" in marketing copy.

### The egress question (where most deployments fail)

The dominant real-world risk isn't the code escaping the sandbox — it's the code *using the sandbox's network* to phone home. An agent that reads your CRM (via a tool), then runs "analysis code" that POSTs the data to an attacker domain has exfiltrated through a fully-isolated sandbox, exactly as designed. The prompt-injection chain that enables this is `02-context-engineering/04-prompt-injection-defense.md`; the sandbox-side defense is egress policy:

- **Default-deny egress.** No network unless allowlisted. Analysis of local data (files, DataFrames) needs zero egress in the common case.
- **Allowlist by domain, not by "suspicious-looking."** If datasets must be fetched, allowlist the specific hosts (your CDN, specific data sources).
- **Log every blocked attempt.** Blocked-egress alerts are your highest-signal injection-detection telemetry — a "benign" analysis script trying to reach a webhook URL is an attack signature.

### State, files, and the data-in / data-out boundary

Code-execution sessions are stateful within a session (variables, files persist across `run` calls) and ephemeral across sessions. Design the data boundary explicitly:

- **Data in:** upload files/variables as *inputs*; don't give the sandbox credentials to fetch from your systems (an agent code session with your DB password is not a sandbox, it's a pivot point). If the sandbox must fetch, give it scoped, short-lived, read-only tokens.
- **Data out:** pull results explicitly (return values, artifacts). Treat outputs as untrusted content *and* untrusted files — generated charts and CSVs go to object storage with scanning, not straight into user browsers.

### Cold-start economics

Cold-start is the hidden latency term: the first run in a session pays sandbox boot (50ms-5s depending on platform), and short-lived analysis sessions pay it *every task*. E2B/Modal's sub-second starts exist precisely because agent loops are bursty-short. Self-hosted Firecracker gives 50-125ms boots but you own the fleet management (pool warm sandboxes, snapshot-restore patterns). Match the platform to your task shape: long sessions amortize cold-start anywhere; 30-second analysis tasks are dominated by it.

## Code: E2B sandbox

```python
from e2b_code_interpreter import Sandbox

sbx = Sandbox()  # consider Sandbox(timeout=120) to bound runaway sessions
result = sbx.run_code('''
import pandas as pd
df = pd.read_csv("https://raw.githubusercontent.com/mwaskom/seaborn-data/master/iris.csv")
df.groupby("species").sepal_length.mean().to_dict()
''')
print(result.text)  # last expression's value
sbx.close()
```

Note the example's implicit egress: fetching from GitHub works because E2B's default sandbox has open egress — fine for public data, wrong for a default-deny production posture. Configure egress per deployment rather than inheriting it.

## Code: OpenAI Code Interpreter (Responses API)

```python
from openai import OpenAI
client = OpenAI()

resp = client.responses.create(
    model="gpt-6.1-sol",
    tools=[{"type": "code_interpreter", "container": {"type": "auto"}}],
    input="Analyze sales.csv and return the top 5 products by revenue.",
)
# The model calls code interpreter autonomously in the container.
```

## Production concerns

- **Latency:** Cold-start matters for UX. E2B and Modal are sub-second. Pool warm sandboxes if self-hosting.
- **Cost:** Sandboxes are cheap ($0.05/min) until they're not (10K runs/day = $720/day — do the multiplication for *your* traffic before launching). Per-run pricing (OpenAI ~$0.05/run) vs per-minute (E2B) flips the economics depending on session length: 10-minute analysis sessions are $0.50 on per-minute, the same price as 10 trivial 1-second runs on per-run.
- **Failure modes:** (1) runaway compute — `while True` loops; enforce CPU-time and wall-clock limits *inside* the platform config, not just your harness; (2) OOM kills mid-analysis — set memory limits and return a graceful error result so the agent can retry with a smaller sample; (3) zombie sessions — unclosed sandboxes bill forever; always close in `finally:` and set platform-level max session TTL.
- **Security:** Egress default-deny (above). Treat sandbox output as untrusted — don't pipe it directly into your DB or render raw HTML/PDFs from it without sanitization. Sandbox images are a supply-chain surface: pin and build your own base images; don't let a third-party template update underneath you.
- **Compliance:** Provider-managed interpreters mean code and data execute on their infrastructure and their region. For regulated data, that's often disqualifying regardless of technical isolation quality — self-hosted sandboxes in your VPC are the answer there.

## Anti-patterns

- ❌ **Running agent code on your application server.** Always isolate.
- ❌ **Open egress "because the model needs to install packages."** Pre-bake dependencies into the image; allowlist package mirrors if truly dynamic.
- ❌ **Giving the sandbox your DB credentials.** Upload data as inputs; use scoped read-only tokens when fetching is unavoidable.
- ❌ **No resource limits.** A `while True` will cost you.
- ❌ **Treating sandbox outputs as trusted.** They're model-generated artifacts — scan, sanitize, store separately.
- ❌ **Ignoring session close.** Unclosed sandboxes are your cloud bill's silent line item.

## References

- [E2B](https://e2b.dev/) — verified 2026-10-20
- [Modal](https://modal.com/) — verified 2026-10-20
- [OpenAI Code Interpreter](https://platform.openai.com/docs/assistants/tools/code-interpreter) — verified 2026-10-20
