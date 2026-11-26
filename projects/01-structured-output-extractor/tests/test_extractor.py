"""Tests for the extractor — all offline (fake injected client, no network).

The fake client mimics instructor's create(response_model=...) contract:
given a dict payload, it validates through the Pydantic model and returns it.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.main import Contact, Invoice, SCHEMAS, ExtractionError, extract, extract_json


class FakeClient:
    """Duck-typed instructor client returning a scripted payload."""

    def __init__(self, payload: dict):
        self.payload = payload
        self.calls: list[dict] = []

        class _Completions:
            def create(inner_self, *, model, response_model, messages, **kwargs):
                self.calls.append({"model": model, "messages": messages})
                return response_model.model_validate(self.payload)

        class _Chat:
            completions = _Completions()

        self.chat = _Chat()


INVOICE_TEXT = """
INVOICE INV-2026-0417
Issued: March 3, 2026      Due: April 2, 2026
From: Globex Analytics LLC

  Consulting services (40 hrs @ $150)      $6,000.00
  Data pipeline setup                      $1,200.00

TOTAL DUE: $7,200.00 USD
"""

VALID_INVOICE = {
    "invoice_number": "INV-2026-0417",
    "issued_date": "2026-03-03",
    "due_date": "2026-04-02",
    "currency": "USD",
    "vendor_name": "Globex Analytics LLC",
    "total_amount": 7200.00,
    "line_items": [
        {"description": "Consulting services", "quantity": 40, "unit_price": 150.0, "line_total": 6000.0},
        {"description": "Data pipeline setup", "quantity": 1, "unit_price": 1200.0, "line_total": 1200.0},
    ],
}


class TestSchemas:
    def test_registry_contains_both_schemas(self):
        assert set(SCHEMAS) == {"invoice", "contact"}

    def test_invoice_rejects_bad_date_shape(self):
        with pytest.raises(ValidationError):
            Invoice.model_validate({**VALID_INVOICE, "issued_date": "03/03/2026"})

    def test_invoice_rejects_negative_total(self):
        with pytest.raises(ValidationError):
            Invoice.model_validate({**VALID_INVOICE, "total_amount": -1})

    def test_invoice_requires_line_items(self):
        with pytest.raises(ValidationError):
            Invoice.model_validate({**VALID_INVOICE, "line_items": []})

    def test_invoice_rejects_extra_fields(self):
        with pytest.raises(ValidationError):
            Invoice.model_validate({**VALID_INVOICE, "unexpected": "field"})

    def test_contact_role_hint_enum(self):
        ok = Contact.model_validate(
            {"full_name": "Ada", "email": "a@x.io", "phone": "", "company": "", "title": "CTO", "role_hint": "executive"}
        )
        assert ok.role_hint == "executive"
        with pytest.raises(ValidationError):
            Contact.model_validate(
                {"full_name": "Ada", "email": "a@x.io", "phone": "", "company": "", "title": "CTO", "role_hint": "chef"}
            )


class TestExtract:
    def test_extract_returns_typed_invoice(self):
        client = FakeClient(VALID_INVOICE)
        result = extract(INVOICE_TEXT, "invoice", client=client)
        assert isinstance(result, Invoice)
        assert result.total_amount == 7200.0
        assert len(result.line_items) == 2

    def test_extract_passes_system_prompt_and_text(self):
        client = FakeClient(VALID_INVOICE)
        extract(INVOICE_TEXT, "invoice", client=client)
        call = client.calls[0]
        roles = [m["role"] for m in call["messages"]]
        assert roles == ["system", "user"]
        assert "data-extraction engine" in call["messages"][0]["content"]
        assert "INV-2026-0417" in call["messages"][1]["content"]

    def test_extract_unknown_schema_raises(self):
        with pytest.raises(KeyError, match="unknown schema"):
            extract("text", "receipt")

    def test_extract_json_serializes(self):
        client = FakeClient(VALID_INVOICE)
        out = extract_json(INVOICE_TEXT, "invoice", client=client)
        assert '"invoice_number": "INV-2026-0417"' in out

    def test_validation_error_propagates(self):
        class BadClient(FakeClient):
            def __init__(self):
                super().__init__({})

        # payload missing required fields -> Pydantic raises through the fake
        with pytest.raises(ValidationError):
            extract(INVOICE_TEXT, "invoice", client=BadClient())


class TestCLI:
    def test_help_exits_zero(self, capsys):
        from src.main import main

        assert main(["--help"]) == 0
        assert "usage" in capsys.readouterr().out

    def test_unknown_schema_reports_error(self, capsys):
        from src.main import main

        with pytest.raises(KeyError):
            main(["receipt", "whatever"])


def test_extraction_error_is_importable_and_documented():
    """The typed error is part of the module's public surface."""
    assert ExtractionError.__doc__ is not None
