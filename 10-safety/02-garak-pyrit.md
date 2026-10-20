# Garak & PyRIT — Red-Teaming Tools

> **Level:** ADV · **Last verified:** 2026-10-20 · **Sources:** [Garak (NVIDIA)](https://github.com/NVIDIA/garak), [PyRIT](https://github.com/Azure/PyRIT) · **Sources:** [Garak](https://github.com/leondz/garak), [PyRIT](https://github.com/Azure/PyRIT)

## Why this matters

Manual red-teaming finds maybe 10% of vulnerabilities. Automated scanners like Garak and PyRIT cover the known space of LLM vulnerabilities systematically. If you're shipping a production agent, you need both.

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

## Which scanner when

**Garak** is the fast, probe-library scanner — run it in CI on every model change. **PyRIT** is the framework for custom multi-turn attack orchestrators — use it when you need to simulate a specific adversary. **promptfoo redteam** (see `../07-evals/03-promptfoo.md`) is the lightest option and lives in your existing eval config.

## Production concerns

- **Latency:** Red-teaming is offline.
- **Cost:** 1000s of LLM calls per scan. Budget $5–$50 per scan.
- **Failure modes:** Scanners produce false positives; review manually.
- **Security:** Run in isolated environments; some attacks can affect infrastructure.

## Anti-patterns

- ❌ **Shipping without red-teaming.** Garak takes 30 minutes; ship-blockers are common.
- ❌ **Running red-team once.** Re-run on every model upgrade.
- ❌ **Treating scanner pass as "safe."** It means "no known vulns found."

## References

- [Garak (NVIDIA org)](https://github.com/NVIDIA/garak) — verified 2026-10-20
- [PyRIT](https://github.com/Azure/PyRIT) — verified 2026-10-20
- [OWASP LLM Top 10](https://genai.owasp.org/) — verified 2026-10-20
