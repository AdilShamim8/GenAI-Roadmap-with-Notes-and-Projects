import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.main import build_graph_from_source, CodeGraph


SRC = """
def auth_middleware(request):
    return check_token(request)

def check_token(tok):
    return decode_jwt(tok)

def decode_jwt(jwt):
    return parse_claims(jwt)

def parse_claims(c):
    return c

def unrelated():
    return 1
"""


def test_graph_extracts_symbols_and_calls():
    g = build_graph_from_source(SRC)
    assert "auth_middleware" in g.symbols and "decode_jwt" in g.symbols
    assert ("auth_middleware", "check_token") in g.edges


def test_callers_of_multi_hop():
    g = build_graph_from_source(SRC)
    assert set(g.callers_of("decode_jwt")) == {"check_token"}


def test_traverse_assembles_chain():
    g = build_graph_from_source(SRC)
    ctx = g.traverse("auth_middleware", depth=2)
    assert "check_token" in ctx and "decode_jwt" in ctx


def test_answer_context_combines_match_and_graph():
    g = build_graph_from_source(SRC)
    ctx = g.answer_context("auth middleware token", depth=1)
    assert any("auth" in c for c in ctx)
    assert "unrelated" not in ctx
