"""Structured Output Extractor — expert implementation.

Pipeline: raw text -> schema-constrained LLM call (instructor) -> validated
Pydantic object -> JSON. Two extraction schemas ship (Invoice, Contact) with a
registry pattern for adding more.

Design notes (the "why", matching 01-llm-calling/04-structured-outputs.md):
- Grammar-constrained decoding makes invalid JSON ungenerable on providers
  that support it; validation remains the second layer because semantic
  constraints (Field ge/le, enums) are enforced by Pydantic, not the decoder.
- Retry-on-validation-failure is capped at 2: one self-correction round, then
  a typed error. Unbounded retries are how extraction pipelines burn budgets.
- The LLM client is injected everywhere so tests run without network.
"""
from __future__ import annotations

import json  # noqa: F401  (kept for downstream consumers of this module)
import os
import sys
from typing import Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

T = TypeVar("T", bound=BaseModel)  # noqa: F841  (re-exported typing helper)

# ---------------------------------------------------------------------------
# Schemas — schema design IS prompt design. Field descriptions steer the model;
# constraints (ge/le, enums) are the cheap quality lever.
# ---------------------------------------------------------------------------


class InvoiceLineItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str = Field(description="Item name or service description, as written")
    quantity: float = Field(default=1.0, ge=0, description="Units ordered; default 1")
    unit_price: float = Field(ge=0, description="Price per unit in the invoice currency")
    line_total: float = Field(ge=0, description="quantity * unit_price as printed on the invoice")


class Invoice(BaseModel):
    """Extracted invoice header + line items."""

    model_config = ConfigDict(extra="forbid")

    invoice_number: str = Field(description="Invoice identifier, e.g. 'INV-2026-001'")
    issued_date: str = Field(description="Issue date in YYYY-MM-DD format; empty string if absent")
    due_date: str = Field(description="Due date in YYYY-MM-DD format; empty string if absent")
    currency: Literal["USD", "EUR", "GBP", "JPY", "CNY", "OTHER"] = Field(
        description="ISO currency code of the invoice totals"
    )
    vendor_name: str = Field(description="Name of the company issuing the invoice")
    total_amount: float = Field(ge=0, description="Grand total including tax, as printed")
    line_items: list[InvoiceLineItem] = Field(min_length=1, description="Itemized charges")

    @field_validator("issued_date", "due_date")
    @classmethod
    def _check_date_shape(cls, v: str) -> str:
        # Dates are the field models most often get wrong; a shape check here
        # converts a silent downstream bug into a retryable validation error.
        if v and (len(v) != 10 or v[4] != "-" or v[7] != "-"):
            raise ValueError(f"date must be YYYY-MM-DD or empty, got {v!r}")
        return v


class Contact(BaseModel):
    """Extracted contact record from a business card or email signature."""

    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(description="Person's full name as written")
    email: str = Field(description="Primary email address; empty string if absent")
    phone: str = Field(description="Primary phone number, digits and separators; empty if absent")
    company: str = Field(description="Organization name; empty string if absent")
    title: str = Field(description="Job title; empty string if absent")
    role_hint: Literal["engineering", "sales", "executive", "support", "unknown"] = Field(
        description="Best-guess function from title; 'unknown' when unclear"
    )


# Registry: extractor names -> schemas. New document types = one entry here.
SCHEMAS: dict[str, type[BaseModel]] = {
    "invoice": Invoice,
    "contact": Contact,
}


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


class ExtractionError(Exception):
    """Raised when extraction fails validation after retries."""


def _system_prompt(schema: type[BaseModel]) -> str:
    return (
        "You are a precise data-extraction engine. Extract the requested fields "
        "from the provided document. Rules:\n"
        "- Copy values verbatim from the document; never infer values that are "
        "not present (use empty strings / defaults for absent fields).\n"
        "- Dates in YYYY-MM-DD.\n"
        "- Numbers as plain floats without currency symbols or thousands separators.\n"
        f"Target schema: {schema.model_json_schema()['title']}"
    )


def extract(
    text: str,
    schema_name: str,
    client: object | None = None,
    model: str = "gpt-6.1-sol",
    max_retries: int = 2,
) -> BaseModel:
    """Extract a typed object from raw text.

    ``client`` is an instructor-wrapped OpenAI client. Tests inject a fake;
    production code calls :func:`default_client`.
    """
    if schema_name not in SCHEMAS:
        raise KeyError(f"unknown schema {schema_name!r}; known: {sorted(SCHEMAS)}")
    schema = SCHEMAS[schema_name]
    if client is None:
        client = default_client()

    resp = client.chat.completions.create(
        model=model,
        response_model=schema,
        max_retries=max_retries,
        messages=[
            {"role": "system", "content": _system_prompt(schema)},
            {"role": "user", "content": text},
        ],
    )
    return resp


def default_client():
    """Build the production client (instructor over OpenAI, env-configured)."""
    try:
        import instructor
        from openai import OpenAI
    except ImportError as e:  # pragma: no cover - dependency guard
        raise RuntimeError("install with: pip install instructor openai") from e

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set (copy .env.example to .env)")
    return instructor.from_openai(OpenAI(api_key=api_key))


def extract_json(text: str, schema_name: str, **kwargs) -> str:
    """Convenience wrapper returning serialized JSON (used by evals/CLI)."""
    obj = extract(text, schema_name, **kwargs)
    return obj.model_dump_json(indent=2)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv or argv[0] in {"-h", "--help"}:
        print(__doc__)
        print("usage: python -m src.main <schema> <text-or-'@file'>")
        print(f"       schemas: {sorted(SCHEMAS)}")
        return 0
    schema_name, source = argv[0], argv[1]
    text = open(source[1:]).read() if source.startswith("@") else source
    try:
        print(extract_json(text, schema_name))
    except ExtractionError as e:
        print(f"extraction failed: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
