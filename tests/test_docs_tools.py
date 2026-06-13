#!/usr/bin/env python3
"""
Tests for the docs retrieval MCP tools (search_docs, get_doc_page).

These tools live-fetch from the documentation site (rascommander.info by default,
overridable via RASCOMMANDER_DOCS_URL). The tests are network-guarded: if the site
is unreachable they SKIP rather than fail, so offline CI stays green.
"""

import os
import sys
from pathlib import Path

import httpx
import pytest

# Add parent directory to path to import server (mirrors test_all_tools.py)
sys.path.insert(0, str(Path(__file__).parent.parent))

from server import (  # noqa: E402
    search_docs,
    get_doc_page,
    DOCS_BASE_URL,
    MCP_SCOPE_TIP,
    _format_tool_response,
    _normalize_doc_path,
    _score_doc,
    _extract_llms_full_section,
)
from fastmcp.exceptions import ToolError  # noqa: E402


def _docs_site_reachable() -> bool:
    """Quick reachability probe for the docs search index. Returns False on any network error."""
    url = f"{DOCS_BASE_URL}/search/search_index.json"
    try:
        resp = httpx.get(url, timeout=10.0, follow_redirects=True)
        return resp.status_code == 200
    except Exception:
        return False


# Evaluate once at import time so the skip reason is clear.
_ONLINE = _docs_site_reachable()
requires_network = pytest.mark.skipif(
    not _ONLINE,
    reason=f"Docs site {DOCS_BASE_URL} unreachable (offline) -- skipping live docs tests.",
)


# ---------------------------------------------------------------------------
# Offline unit tests (no network) -- exercise pure helpers deterministically.
# ---------------------------------------------------------------------------

def test_normalize_doc_path_variants():
    assert _normalize_doc_path("reference/dataframe-reference") == "reference/dataframe-reference"
    assert _normalize_doc_path("/reference/dataframe-reference/") == "reference/dataframe-reference"
    assert _normalize_doc_path("reference/dataframe-reference/index.md") == "reference/dataframe-reference"
    assert _normalize_doc_path("reference/dataframe-reference.md") == "reference/dataframe-reference"
    assert _normalize_doc_path("  /api/remote/  ") == "api/remote"


def test_score_doc_is_deterministic_and_title_weighted():
    terms = ["cross", "section"]
    title_hit = _score_doc(terms, "Cross Section Results", "some body text")
    body_hit = _score_doc(terms, "Unrelated", "cross section appears in the body")
    no_hit = _score_doc(terms, "Unrelated", "nothing relevant here")
    # Title matches outweigh body matches; no match scores zero.
    assert title_hit > body_hit > no_hit == 0
    # Deterministic: identical inputs yield identical scores.
    assert _score_doc(terms, "Cross Section", "x") == _score_doc(terms, "Cross Section", "x")


def test_search_docs_rejects_empty_query():
    from fastmcp.exceptions import ToolError

    with pytest.raises(ToolError):
        search_docs("   ")


def test_get_doc_page_rejects_empty_path():
    with pytest.raises(ToolError):
        get_doc_page("")


@pytest.mark.parametrize(
    "bad",
    [
        "http://evil.com/x",
        "https://evil.com",
        "//evil.com/x",
        "../../etc/passwd",
        "reference/../../secret",
        "reference\\dataframe",
        "reference/dataframe?x=1",
        "reference/dataframe#frag",
        "user@evil.com/x",
        "reference/da\x00ta",
    ],
)
def test_normalize_doc_path_rejects_malicious(bad):
    # Path sanitizer must reject URLs, traversal, query/fragment, userinfo, control chars.
    with pytest.raises(ToolError):
        _normalize_doc_path(bad)


def test_normalize_doc_path_percent_encodes_segments():
    # A stray space in a segment is encoded, not passed through raw.
    assert _normalize_doc_path("user-guide/plan execution") == "user-guide/plan%20execution"


def test_extract_llms_full_exact_match():
    sample = (
        "# Page One\n"
        f"Source: {DOCS_BASE_URL}/reference/dataframe-reference/\n"
        "plan_df columns here.\n"
        "# Page Two\n"
        f"Source: {DOCS_BASE_URL}/user-guide/overview/\n"
        "overview body.\n"
    )
    section = _extract_llms_full_section(sample, "reference/dataframe-reference")
    assert section is not None and "plan_df columns here" in section
    # Must not bleed into the next page.
    assert "overview body" not in section


def test_extract_llms_full_returns_none_on_missing_or_ambiguous():
    # A missing page must return None (caller falls back) -- never a weak-heading guess.
    sample = (
        "# Overview\n"
        f"Source: {DOCS_BASE_URL}/user-guide/overview/\n"
        "overview body.\n"
    )
    # 'missing/overview' shares the last segment 'overview' but is NOT this page.
    assert _extract_llms_full_section(sample, "missing/overview") is None
    assert _extract_llms_full_section(sample, "nope/not-here") is None


def test_format_tool_response_appends_scope_tip_to_substantive_output():
    result = _format_tool_response("Heading\n" + "=" * 80 + "\nSome tabular output")
    assert result.endswith(MCP_SCOPE_TIP)


def test_format_tool_response_skips_tiny_status_and_errors():
    assert MCP_SCOPE_TIP not in _format_tool_response("HEC-RAS Version: 6.6")
    assert MCP_SCOPE_TIP not in _format_tool_response("Error reading compute messages: failed")


def test_format_tool_response_appends_scope_tip_after_truncation():
    result = _format_tool_response(("abcdefghij " * 20).strip(), max_tokens=10)
    assert "[OUTPUT TRUNCATED" in result
    assert result.endswith(MCP_SCOPE_TIP)


# ---------------------------------------------------------------------------
# Live network tests (skip cleanly when offline).
# ---------------------------------------------------------------------------

@requires_network
def test_search_docs_returns_ranked_results():
    result = search_docs("cross section results")
    assert isinstance(result, str)
    assert result.strip()
    # Should not be the "no matches" message for such a common topic.
    assert "No documentation matches found" not in result
    # Results carry the docs base URL and at least one link line.
    assert DOCS_BASE_URL in result
    assert " - http" in result


@requires_network
def test_get_doc_page_returns_markdown_with_known_token():
    result = get_doc_page("reference/dataframe-reference")
    assert isinstance(result, str)
    assert result.strip()
    # The DataFrame reference page documents plan_df regardless of which
    # retrieval strategy (llms-full slice / .md mirror / rendered) succeeds.
    assert "plan_df" in result


@requires_network
def test_get_doc_page_accepts_slashed_path():
    result = get_doc_page("/reference/dataframe-reference/")
    assert "plan_df" in result


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
