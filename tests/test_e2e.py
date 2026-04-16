"""End-to-end MCP protocol test over HTTP.

Requires the server running: PROFGRAPH_TRANSPORT=streamable-http PROFGRAPH_PORT=8765 python -m profgraph
"""

import json
import sys

import httpx

BASE = "http://localhost:8765/mcp"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


def _call(client: httpx.Client, method: str, params: dict = None, req_id: int = 1) -> dict:
    """Send an MCP JSON-RPC call and parse the SSE response."""
    body: dict = {"jsonrpc": "2.0", "id": req_id, "method": method}
    if params:
        body["params"] = params

    headers = dict(HEADERS)
    if hasattr(client, "_session_id") and client._session_id:
        headers["mcp-session-id"] = client._session_id

    r = client.post(BASE, json=body, headers=headers, timeout=30.0)

    # Capture session ID from response
    sid = r.headers.get("mcp-session-id")
    if sid:
        client._session_id = sid

    # Parse SSE response
    for line in r.text.split("\n"):
        if line.startswith("data: "):
            return json.loads(line[6:])
    raise RuntimeError(f"No data in response: {r.text[:200]}")


def _notify(client: httpx.Client, method: str) -> None:
    """Send an MCP notification (no response expected)."""
    headers = dict(HEADERS)
    if hasattr(client, "_session_id") and client._session_id:
        headers["mcp-session-id"] = client._session_id
    client.post(BASE, json={"jsonrpc": "2.0", "method": method}, headers=headers)


def _tool_call(client: httpx.Client, tool: str, args: dict, req_id: int = 1) -> str:
    """Call an MCP tool and return the text content."""
    resp = _call(client, "tools/call", {"name": tool, "arguments": args}, req_id)
    if "error" in resp:
        raise RuntimeError(f"Tool error: {resp['error']}")
    content = resp.get("result", {}).get("content", [])
    texts = [c["text"] for c in content if c.get("type") == "text"]
    return "\n".join(texts)


def main():
    passed = 0
    failed = 0
    results = {}

    with httpx.Client() as client:
        client._session_id = None

        # Initialize
        print("[....] MCP Initialize")
        init = _call(client, "initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "e2e-test", "version": "1.0"},
        })
        assert init["result"]["serverInfo"]["name"] == "profgraph_mcp"
        _notify(client, "notifications/initialized")
        print("[PASS] MCP Initialize")
        passed += 1

        # List tools
        print("[....] Tools List")
        tools_resp = _call(client, "tools/list", req_id=2)
        tools = tools_resp["result"]["tools"]
        tool_names = [t["name"] for t in tools]
        assert len(tools) == 10, f"Expected 10 tools, got {len(tools)}"
        print(f"[PASS] Tools List ({len(tools)} tools)")
        passed += 1

        # Test each tool
        tests = [
            ("list_universities", {}, lambda r: "UTD" in r.upper() or "utd" in r),
            ("search_professors", {"university": "utd", "query": "Jason Smith"},
             lambda r: "Jason" in r and "Smith" in r),
            ("search_professors (TAMU)", {"university": "tamu", "query": "Ritchey"},
             lambda r: "Ritchey" in r),
            ("get_professor_profile", {"university": "utd", "professor": "Jason Smith"},
             lambda r: "Teaching Style" in r and "Tags" in r),
            ("get_grade_distribution", {"university": "utd", "course": "CS 3341"},
             lambda r: "Grade Distribution" in r and "GPA" in r),
            ("compare_professors", {"university": "utd", "professors": ["Jason Smith", "Beiyu Lin"]},
             lambda r: "Comparison" in r),
            ("predict_grade", {"university": "utd", "course": "CS 3341", "professor": "smith", "student_gpa": 3.5},
             lambda r: "Prediction" in r and "%" in r),
            ("recommend_professor", {"university": "utd", "course": "CS 3341", "professors": ["Jason Smith", "Beiyu Lin"]},
             lambda r: "Recommendation" in r),
            ("get_prerequisites", {"university": "utd", "course": "CS 4349"},
             lambda r: "Prerequisite" in r),
            ("submit_intel", {"university": "utd", "course": "CS 3341", "professor": "Jason Smith",
                              "semester": "26S", "exam_weight": 85, "curve": "likely",
                              "notes": "E2E test entry"},
             lambda r: "submitted" in r.lower()),
            ("get_intel", {"university": "utd", "course": "CS 3341"},
             lambda r: "Community Intel" in r or "E2E test" in r),
        ]

        for i, (name, args, check) in enumerate(tests, start=3):
            tool_name = name.split(" (")[0]  # strip label suffix
            try:
                print(f"[....] {name}")
                result = _tool_call(client, tool_name, args, req_id=i)
                assert check(result), f"Check failed. Output: {result[:200]}"
                print(f"[PASS] {name}")
                passed += 1
            except Exception as e:
                print(f"[FAIL] {name}: {e}")
                failed += 1

    print(f"\n{passed} passed, {failed} failed out of {passed + failed}")
    return failed == 0


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
