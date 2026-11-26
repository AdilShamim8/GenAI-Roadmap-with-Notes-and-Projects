"""Offline tests for the SQL guard layer and row capping — no Postgres needed."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.main import MAX_ROWS, cap_rows, validate_readonly_sql  # noqa: E402


class TestReadOnlyGuard:
    def test_plain_select_ok(self):
        ok, err = validate_readonly_sql("SELECT * FROM orders LIMIT 10")
        assert ok, err

    def test_with_cte_ok(self):
        ok, err = validate_readonly_sql("WITH t AS (SELECT 1) SELECT * FROM t")
        assert ok, err

    def test_update_rejected(self):
        ok, err = validate_readonly_sql("UPDATE orders SET total = 0")
        assert not ok and "forbidden" in err.lower()

    def test_drop_rejected(self):
        ok, err = validate_readonly_sql("DROP TABLE orders")
        assert not ok

    def test_multi_statement_rejected(self):
        ok, err = validate_readonly_sql("SELECT 1; DROP TABLE orders")
        assert not ok and "multi-statement" in err

    def test_comment_trick_rejected(self):
        ok, err = validate_readonly_sql("-- innocuous\nSELECT secret FROM pg_shadow")
        assert not ok

    def test_insert_rejected(self):
        ok, err = validate_readonly_sql("INSERT INTO orders VALUES (1)")
        assert not ok

    def test_pg_sleep_via_select_rejected_token(self):
        # SELECT ...; CALL and SET are blocked; pg_sleep inside SELECT is a
        # statement_timeout concern (layer 2), noted in the docstring
        ok, _ = validate_readonly_sql("SELECT pg_sleep(30)")
        assert ok  # structurally a SELECT; the timeout layer owns this


class TestRowCapping:
    def test_caps_at_max_rows_with_note(self):
        rows = [(i,) for i in range(250)]
        out = cap_rows(rows, ["n"])
        assert len(out["rows"]) == MAX_ROWS
        assert "offset=100" in out["note"]

    def test_offset_pages(self):
        rows = [(i,) for i in range(250)]
        out = cap_rows(rows, ["n"], offset=100)
        assert out["rows"][0][0] == 100

    def test_no_note_when_fits(self):
        out = cap_rows([(1,), (2,)], ["n"])
        assert "note" not in out
        assert out["row_count"] == 2
