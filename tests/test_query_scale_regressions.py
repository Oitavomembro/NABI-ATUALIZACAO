from __future__ import annotations

from benchmark_tests.benchmark_query_scale import run


def test_five_thousand_rows_keep_searches_bounded_and_totals_complete() -> None:
    result = run(5_000)
    assert result["customer_suggestion"]["ids"][0] == 5_000
    assert len(result["customer_suggestion"]["ids"]) <= 30
    assert result["customer_page"]["materialized"] == 50
    assert result["customer_page"]["total"] == 5_000
    assert result["product_search"]["materialized"] == 30
    assert result["product_search"]["peak_bytes"] < 2_000_000
