import os

import httpx
import pytest
from fastmcp.exceptions import ToolError

import server


def _response(url, status_code=200, text="", json_data=None):
    request = httpx.Request("GET", url)
    return httpx.Response(status_code, request=request, text=text, json=json_data)


def test_normalize_doc_path_variants():
    assert server._normalize_doc_path("reference/dataframe-reference") == "reference/dataframe-reference"
    assert server._normalize_doc_path("/reference/dataframe-reference/") == "reference/dataframe-reference"
    assert server._normalize_doc_path("reference/dataframe-reference/index.md") == "reference/dataframe-reference"
    assert server._normalize_doc_path("reference/dataframe-reference.md") == "reference/dataframe-reference"
    assert server._normalize_doc_path("  /api/remote/  ") == "api/remote"


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
    with pytest.raises(ToolError):
        server._normalize_doc_path(bad)


def test_normalize_doc_path_percent_encodes_segments():
    assert server._normalize_doc_path("user-guide/plan execution") == "user-guide/plan%20execution"


def test_score_doc_is_deterministic_and_title_weighted():
    terms = ["cross", "section"]
    title_hit = server._score_doc(terms, "Cross Section Results", "some body text")
    body_hit = server._score_doc(terms, "Unrelated", "cross section appears in the body")
    no_hit = server._score_doc(terms, "Unrelated", "nothing relevant here")

    assert title_hit > body_hit > no_hit == 0
    assert server._score_doc(terms, "Cross Section", "x") == server._score_doc(
        terms, "Cross Section", "x"
    )


def test_extract_llms_full_exact_match():
    sample = (
        "# Page One\n"
        f"Source: {server.DOCS_BASE_URL}/reference/dataframe-reference/\n"
        "plan_df columns here.\n"
        "# Page Two\n"
        f"Source: {server.DOCS_BASE_URL}/user-guide/overview/\n"
        "overview body.\n"
    )

    section = server._extract_llms_full_section(sample, "reference/dataframe-reference")

    assert section is not None
    assert "plan_df columns here" in section
    assert "overview body" not in section


def test_extract_llms_full_returns_none_on_missing_or_ambiguous():
    sample = (
        "# Overview\n"
        f"Source: {server.DOCS_BASE_URL}/user-guide/overview/\n"
        "overview body.\n"
    )

    assert server._extract_llms_full_section(sample, "missing/overview") is None
    assert server._extract_llms_full_section(sample, "nope/not-here") is None


def test_search_docs_returns_ranked_results_without_network(monkeypatch):
    docs = [
        {
            "location": "reference/dataframe-reference/",
            "title": "DataFrame Reference",
            "text": "<p>plan_df and geom_df reference columns for HEC-RAS projects.</p>",
        },
        {
            "location": "user-guide/overview/",
            "title": "Overview",
            "text": "general project orientation",
        },
    ]
    monkeypatch.setattr(server, "_get_search_index", lambda: docs)

    result = server.search_docs("plan dataframe")

    assert "Documentation search results for: 'plan dataframe'" in result
    assert "DataFrame Reference" in result
    assert f"{server.DOCS_BASE_URL}/reference/dataframe-reference/" in result
    assert "Overview" not in result


def test_search_docs_reports_no_matches_without_network(monkeypatch):
    monkeypatch.setattr(
        server,
        "_get_search_index",
        lambda: [{"location": "overview/", "title": "Overview", "text": "general orientation"}],
    )

    result = server.search_docs("velocity")

    assert "No documentation matches found for query: 'velocity'" in result


def test_search_docs_rejects_empty_query():
    with pytest.raises(ToolError, match="Query must be a non-empty string"):
        server.search_docs("   ")


def test_search_docs_fetch_failure_surfaces_tool_error(monkeypatch):
    def raise_fetch_error():
        raise ToolError("Failed to fetch docs search index")

    monkeypatch.setattr(server, "_get_search_index", raise_fetch_error)

    with pytest.raises(ToolError, match="Failed to fetch docs search index"):
        server.search_docs("plan")


def test_get_doc_page_returns_llms_full_section_without_network(monkeypatch):
    sample = (
        "# DataFrame Reference\n"
        f"Source: {server.DOCS_BASE_URL}/reference/dataframe-reference/\n"
        "plan_df columns here.\n"
        "# Overview\n"
        f"Source: {server.DOCS_BASE_URL}/user-guide/overview/\n"
        "overview body.\n"
    )
    monkeypatch.setattr(server, "_get_llms_full", lambda: sample)

    result = server.get_doc_page("reference/dataframe-reference")

    assert result.startswith(f"# Source: {server.DOCS_BASE_URL}/reference/dataframe-reference/")
    assert "plan_df columns here" in result
    assert "overview body" not in result


def test_get_doc_page_uses_markdown_mirror_fallback(monkeypatch):
    calls = []
    monkeypatch.setattr(server, "_get_llms_full", lambda: None)

    def fake_get(url, timeout, follow_redirects):
        calls.append((url, timeout, follow_redirects))
        return _response(url, text="# DataFrame Reference\n\nplan_df markdown body")

    monkeypatch.setattr(server.httpx, "get", fake_get)

    result = server.get_doc_page("reference/dataframe-reference")

    assert calls == [
        (
            f"{server.DOCS_BASE_URL}/reference/dataframe-reference/index.md",
            server.DOCS_HTTP_TIMEOUT,
            True,
        )
    ]
    assert result.startswith(f"# Source: {server.DOCS_BASE_URL}/reference/dataframe-reference/index.md")
    assert "plan_df markdown body" in result


def test_get_doc_page_uses_rendered_page_fallback(monkeypatch):
    monkeypatch.setattr(server, "_get_llms_full", lambda: None)

    def fake_get(url, timeout, follow_redirects):
        if url.endswith("/index.md"):
            return _response(url, status_code=404)
        return _response(url, text="<html><body><main>plan_df rendered body</main></body></html>")

    monkeypatch.setattr(server.httpx, "get", fake_get)

    result = server.get_doc_page("reference/dataframe-reference")

    assert result.startswith(
        f"# Source: {server.DOCS_BASE_URL}/reference/dataframe-reference/ (rendered page text)"
    )
    assert "plan_df rendered body" in result


def test_get_doc_page_rejects_empty_path():
    with pytest.raises(ToolError, match="Path must be a non-empty string"):
        server.get_doc_page("")


def test_get_doc_page_rejects_off_origin_redirect(monkeypatch):
    monkeypatch.setattr(server, "_get_llms_full", lambda: None)
    monkeypatch.setattr(
        server.httpx,
        "get",
        lambda url, timeout, follow_redirects: _response("https://evil.example/index.md", text="bad"),
    )

    with pytest.raises(ToolError, match="Refusing docs response from off-origin URL"):
        server.get_doc_page("reference/dataframe-reference")


def test_get_doc_page_network_failure_raises_tool_error(monkeypatch):
    monkeypatch.setattr(server, "_get_llms_full", lambda: None)

    def raise_connect_error(url, timeout, follow_redirects):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(server.httpx, "get", raise_connect_error)

    with pytest.raises(ToolError, match="Failed to fetch docs page"):
        server.get_doc_page("reference/dataframe-reference")


live_docs = pytest.mark.skipif(
    os.environ.get("RASCOMMANDER_DOCS_LIVE_TESTS") != "1",
    reason="Set RASCOMMANDER_DOCS_LIVE_TESTS=1 to run live docs checks.",
)


def test_format_tool_response_appends_scope_tip_to_substantive_output():
    result = server._format_tool_response("Heading\n" + "=" * 80 + "\nSome tabular output")
    assert result.endswith(server.MCP_SCOPE_TIP)


def test_format_tool_response_skips_tiny_status_and_errors():
    assert server.MCP_SCOPE_TIP not in server._format_tool_response("HEC-RAS Version: 6.6")
    assert server.MCP_SCOPE_TIP not in server._format_tool_response("Error reading compute messages: failed")


def test_format_tool_response_appends_scope_tip_after_truncation():
    result = server._format_tool_response(("abcdefghij " * 20).strip(), max_tokens=10)
    assert "[OUTPUT TRUNCATED" in result
    assert result.endswith(server.MCP_SCOPE_TIP)


# ---------------------------------------------------------------------------
# Live network tests (skip cleanly when offline).
# ---------------------------------------------------------------------------


@live_docs
def test_search_docs_live_returns_ranked_results():
    result = server.search_docs("cross section results")

    assert "No documentation matches found" not in result
    assert server.DOCS_BASE_URL in result
    assert " - http" in result


@live_docs
def test_get_doc_page_live_returns_known_token():
    result = server.get_doc_page("reference/dataframe-reference")

    assert "plan_df" in result
