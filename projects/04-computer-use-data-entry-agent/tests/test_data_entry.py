import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.main import DataEntryAgent, MockLegacyCRM, Task


class TestMockCRM:
    def test_submit_requires_fields(self):
        crm = MockLegacyCRM()
        assert crm.submit().startswith("error")

    def test_successful_submit_clears_form(self):
        crm = MockLegacyCRM()
        crm.fill("customer_name", "A"); crm.fill("amount", "1")
        assert crm.submit().startswith("confirmation_")
        assert crm.fields == {}

    def test_unknown_field_raises(self):
        import pytest
        with pytest.raises(ValueError):
            MockLegacyCRM().fill("nope", "x")


class TestAgent:
    def test_happy_path_verified(self):
        agent = DataEntryAgent(MockLegacyCRM())
        r = agent.execute(Task("Acme", "10.00"))
        assert r["ok"] and r["detail"].startswith("confirmation_") and r["steps"] <= 3

    def test_duplicate_is_idempotent_noop(self):
        agent = DataEntryAgent(MockLegacyCRM())
        agent.execute(Task("Acme", "10.00"))
        r2 = agent.execute(Task("Acme", "10.00"))
        assert r2["ok"] and r2["detail"].startswith("duplicate")
        assert r2["submitted"] == 1

    def test_missing_fields_recovered_by_loop(self):
        agent = DataEntryAgent(MockLegacyCRM())
        r = agent.execute(Task("Globex", "99.00", notes="x"))
        assert r["ok"]

    def test_max_steps_escalates(self):
        agent = DataEntryAgent(MockLegacyCRM(), max_steps=0)
        r = agent.execute(Task("A", "1"))
        assert not r["ok"] and "escalating" in r["detail"]
