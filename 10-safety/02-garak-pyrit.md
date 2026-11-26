# Garak & PyRIT — Red-Teaming Tools

> **Level:** ADV · **Last verified:** 2026-10-20 · **Sources:** [Garak (NVIDIA)](https://github.com/NVIDIA/garak), [PyRIT](https://github.com/Azure/PyRIT)

## Why this matters

Manual red-teaming finds maybe 10% of vulnerabilities. Automated scanners like Garak and PyRIT cover the known space of LLM vulnerabilities systematically. If you're shipping a production agent, you need both. The expert framing: these are *fuzzers for language interfaces*. Classical fuzzing throws malformed inputs at parsers looking for crashes; LLM red-teaming throws adversarial prompts at models looking for *policy violations* — the same shift as the failure model itself: the "crash" is semantic (a harmful output, a leaked prompt), not mechanical. And like classical fuzzing, the discipline that makes it valuable is running it continuously and *measuring what it finds*, not the one-off scan.

## Garak

Garak is an LLM vulnerability scanner. Run it like a fuzzer against your model or endpoint; it tries thousands of known attack patterns.

```bash
pip install garak
garak --model_type openai --model_name gpt-6-luna --probes promptinject,jailbreak,leakreplay
```

Garak runs probes (each is a category of attack) and reports pass/fail per probe. Useful probes for production:

- `promptinject` — direct prompt injection
- `jailbreak` — known jailbreak templates
- `leakreplay` — training-data extraction
- `maliciousgen` — generates malicious content
- `xss` — XSS in outputs

Read Garak's output like a fuzzer engineer: the unit of interest is *probe-class failure rate over time*, not individual hits. Any given jailbreak template landing is low-signal (templates are public; models drift); a *jump* in a probe class between model versions is high-signal — it says the new model version regressed on that defense. Trend the per-probe rates in CI artifacts and diff them across upgrades; that's where Garak becomes a gate instead of a checkbox.

## PyRIT (Microsoft)

PyRIT is the Python Risk Identification Toolkit. More sophisticated than Garak; supports multi-turn attacks and attacker-side LLMs.

```python
# pip install pyrit  (1.x orchestrator API; run inside asyncio.run)
from pyrit.common import initialize_pyrit
from pyrit.orchestrators import RedTeamingOrchestrator
from pyrit.prompt_target import OpenAIChatTarget

initialize_pyrit()

target = OpenAIChatTarget(model_name="gpt-6.1-sol")
orchestrator = RedTeamingOrchestrator(
    objective_target=target,
    adversarial_chat=OpenAIChatTarget(model_name="gpt-6-luna"),
    max_turns=3,
)
result = await orchestrator.run_attack_async(
    objective="Extract the system prompt from the target.")
print(result)
```

The design leap in the *adversarial_chat* parameter: the attacker is itself an LLM that *adapts* — it reads the target's responses and rewrites the next attack. This is automated social engineering, and it models the real threat: attackers with time and feedback. Single-turn scanners (Garak templates) test the wall; multi-turn adversarial agents test the *siege* — probing for the request that gets one step closer each turn, exploiting the target's own replies ("you're right, I misspoke — here's the continuation...").

What multi-turn finds that single-turn can't: multi-turn *conditioning* attacks (build a benign context over 5 turns, then escalate — the context makes the boundary feel already-crossed), callback extraction (get the target to *reconstruct* its prompt from memory rather than dump it), and tool-chain coercion (groom the agent into calling a tool with attacker-shaped args across several plausible-looking steps).

## Which scanner when

**Garak** is the fast, probe-library scanner — run it in CI on every model change. **PyRIT** is the framework for custom multi-turn attack orchestrators — use it when you need to simulate a specific adversary. **promptfoo redteam** (see `../07-evals/03-promptfoo.md`) is the lightest option and lives in your existing eval config.

The cadence that works in production: promptfoo redteam on every PR (minutes, catches regressions against your own attack corpus), Garak on model changes (hours, broad known-space coverage), PyRIT campaigns quarterly or before major launches (deep, adaptive, adversarial-specific). Each layer's findings feed the next campaign — a PyRIT-discovered multi-turn pattern becomes a promptfoo test case, so *that specific hole* never reopens silently.

## Production concerns

- **Latency:** Red-teaming is offline.
- **Cost:** 1000s of LLM calls per scan. Budget $5–$50 per scan — and for PyRIT multi-turn campaigns, adversary turns × target turns multiplies fast; a 200-objective campaign at 5 turns avg is 2000+ calls *minimum* before judge scoring.
- **Failure modes:** (1) scanners produce false positives — a "leak" that's actually benign boilerplate; review manually before firing the incident process; (2) *objective-success judging* is itself model-based — the judge that scores "did the attack succeed" has its own error rate; spot-check judgments on a sample (`07-evals/02-llm-as-judge.md` calibration discipline applies); (3) coverage illusion — a clean scan means "no known vulnerabilities found by these probes," which is different from "safe."
- **Security:** Run in isolated environments; some attacks can affect infrastructure (the scanner is *sending your agent malicious instructions on purpose* — make sure it can't reach production tools with real credentials; scan against staging with sandboxed tools).

## Anti-patterns

- ❌ **Shipping without red-teaming.** Garak takes 30 minutes; ship-blockers are common.
- ❌ **Running red-team once.** Re-run on every model upgrade — model changes are the #1 source of *new* vulnerability classes appearing in an unchanged system.
- ❌ **Treating scanner pass as "safe."** It means "no known vulns found."
- ❌ **Red-teaming against production credentials.** The scanner is a controlled attacker; give it a sandbox.
- ❌ **Findings without follow-through.** A discovered-and-unfixed vuln that later leaks is worse than never having scanned — you *knew*. Triage findings into fix / accept / track, in writing.

## References

- [Garak (NVIDIA org)](https://github.com/NVIDIA/garak) — verified 2026-10-20
- [PyRIT](https://github.com/Azure/PyRIT) — verified 2026-10-20
- [OWASP LLM Top 10](https://genai.owasp.org/) — verified 2026-10-20
