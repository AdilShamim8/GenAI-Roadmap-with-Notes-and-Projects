# Responsible AI Patterns

> **Level:** INT · **Last verified:** 2026-10-20 · **Sources:** [EU AI Act](https://artificialintelligenceact.eu/), [NIST AI RMF](https://www.nist.gov/itl/ai-risk-management-framework)

## Why this matters

Responsible AI is no longer optional. EU AI Act enforcement started in 2026; sectoral regulations (HIPAA, GDPR, FCRA) apply to AI outputs; customer contracts increasingly require AI governance. The good news: the same patterns that satisfy regulators also produce better, safer products. The expert framing: Responsible-AI patterns are *engineering controls for agent misbehavior* — the same class as timeouts and retries, but for semantic failures. Nobody calls a retry policy "overhead"; the discipline here is treating human-oversight and audit controls as *operational infrastructure* with the same design rigor, not as compliance garnish.

## Core concepts

### The seven patterns

| Pattern | What | Why | Failure it's controlling |
|---------|------|-----|--------------------------|
| **Human-in-the-loop** | Human approves high-stakes actions | Catches agent errors | Confident wrong actions |
| **Audit logging** | Every input, output, decision logged | Forensics; compliance | Unexplainable incidents |
| **Explainability** | Cite sources; show reasoning trace | User trust; debugging | Unverifiable answers |
| **Feedback channel** | User can flag bad output | Continuous improvement | Silent quality failures |
| **Opt-out / override** | User can disable AI features | Consent; trust | Unwanted automation |
| **Bias testing** | Eval across subgroups | Fairness; compliance | Skewed performance |
| **Explainability of decisions** | Which model/prompt/tool produced this | Accountability | Opaque causality |

Two of these deserve their engineering depth:

**Human-in-the-loop as queue design.** "Human approves" sounds like a checkbox; in production it's a *queue with SLAs*, and its failure mode is queue collapse: too many approvals → approvers rubber-stamp → the control becomes theater. Design rules: approval *volume* is a metric (if >N/hour, your agent policy is too aggressive — fix the policy, not the queue); each approval request must carry *decision-relevant context* (what's about to happen, why the agent thinks it's right, risk class) not a wall of JSON; and *timeouts on approval requests* route to safe-default (deny + notify), never auto-approve.

**Audit logging as reconstruction, not recording.** A log that records everything but can't *reconstruct the decision* — which prompt version, which retrieved chunks, which tool results fed this answer — answers "what did the user see" but not "why did the system do that." The forensically complete record is the *full decision input set*, referenced by id: prompt-template id+version, context chunks, tool args/results, model snapshot. This is the same artifact design as observability spans (`08-production/03-observability-opentelemetry.md`) — one pipeline serves debugging and compliance.

### The audit log

Every production agent should log:

```json
{
  "timestamp": "2026-10-20T12:34:56Z",
  "user_id": "u_abc",
  "session_id": "s_xyz",
  "model": "gpt-5-2026-04-15",
  "prompt_template_id": "billing_agent_v3",
  "input_tokens": 1240,
  "output_tokens": 80,
  "tool_calls": [{"name": "issue_refund", "args": {"order_id": "123"}, "result": "success"}],
  "output": "I've issued refund r_456 for order 123.",
  "feedback": null,
  "eval_scores": {"faithfulness": 0.95, "helpfulness": 4}
}
```

This is your forensic record. If a user complains, you can reconstruct exactly what happened.

### Bias testing as subgroup eval, concretely

"Bias testing" decomposes into: define subgroups relevant to your users (language, dialect, name-ethnicity proxies in PII, region), run the golden set *per subgroup*, and compare metrics. A system at 92% overall that's 96% on one subgroup and 78% on another has a fairness bug that no aggregate metric will ever show. The eval tooling is the same (`07-evals/`); the discipline is the *slicing*. NIST AI RMF frames this under its Measure function — the operational version is: subgroup slices are first-class eval dimensions, with their own thresholds and alerts, not an annual report.

## Code: structured audit logging

```python
import json, time, logging
logger = logging.getLogger("agent_audit")

def audit_log(user_id: str, session_id: str, model: str, prompt_id: str,
              input_text: str, output_text: str, tool_calls: list, tokens: dict):
    record = {
        "timestamp": time.time(),
        "user_id": user_id,
        "session_id": session_id,
        "model": model,
        "prompt_template_id": prompt_id,
        "input_tokens": tokens.get("input"),
        "output_tokens": tokens.get("output"),
        "tool_calls": tool_calls,
        "output": output_text,
        # Don't log full input_text — PII. Log hash instead.
        "input_hash": hashlib.sha256(input_text.encode()).hexdigest(),  # Python hash() is salted per process - not forensic
    }
    logger.info(json.dumps(record))
```

## Code: feedback capture

```python
def response_endpoint(response_id: str, response_text: str):
    return {
        "response_id": response_id,
        "response_text": response_text,
        "feedback_html": f'''
        <div class="feedback">
          <button onclick="submitFeedback('{response_id}', 'good')">+1</button>
          <button onclick="submitFeedback('{response_id}', 'bad')">-1</button>
          <textarea id="feedback_text" placeholder="What went wrong?"></textarea>
        </div>
        ''',
    }
```

The feedback channel closes the loop only if flagged outputs *become eval cases* (`07-evals/05-online-vs-offline.md`'s conversion discipline): flagged → triaged weekly → added to golden set with a label → regression-gated forever. A feedback button whose outputs go nowhere is a trust signal, not a control.

## Production concerns

- **Latency:** Audit logging adds <1ms.
- **Cost:** Log storage is cheap. Don't skimp — but note retention has a *compliance* dimension in both directions: too short and you can't answer a subject-access or incident question from 6 months ago; too long and you're retaining PII beyond your stated policy. Set retention per record class (audit vs feedback vs blocked-content) deliberately.
- **Failure modes:** (1) logs without `prompt_template_id` are useless for forensics — make the field mandatory at the schema level; (2) human-approval queue collapse (above); (3) opt-out that's buried — a dark-pattern opt-out satisfies no regulator and no user.
- **Security:** Logs contain user data. Encrypt at rest; restrict access; and remember audit logs are themselves attack-relevant artifacts (they contain your outputs and user inputs — an attacker with log access has your corpus).

## Anti-patterns

- ❌ **No audit logging.** You can't investigate incidents — or prove diligence.
- ❌ **Logging PII in plaintext.** Encrypt or hash.
- ❌ **No feedback channel.** You're blind to user-reported issues.
- ❌ **Human-in-the-loop without queue design.** Volume metrics, decision context, safe-default timeouts — or it's rubber-stamp theater.
- ❌ **Aggregate-only metrics.** Subgroup slices are where fairness failures live.
- ❌ **Feedback that goes nowhere.** Flagged outputs must become eval cases.

## References

- [EU AI Act](https://artificialintelligenceact.eu/) — verified 2026-10-20
- [NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework) — verified 2026-10-20
- [Anthropic: Responsible AI](https://www.anthropic.com/news) — verified 2026-10-20
