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
    _normalize_doc_path,
    _score_doc,
)


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
    from fastmcp.exceptions import ToolError

    with pytest.raises(ToolError):
        get_doc_page("")


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
