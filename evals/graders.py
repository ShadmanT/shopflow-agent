"""
Grading functions for the ShopFlow Agent eval suite.

Pure, deterministic checks over a single agent run. No API calls here —
the runner captures what the agent did (tool calls, arguments, final text)
and the eval DB path, and these functions decide pass/fail.

A "run record" passed to grade_run() looks like:

    {
        "tool_calls": [{"name": "check_order_status", "input": {...}}, ...],
        "response":   "final assistant text",
    }

Each grader returns a Check: {"name", "passed", "detail"}.
grade_run() aggregates them into {"passed": bool, "checks": [...]}.
"""
import sqlite3


def _check(name: str, passed: bool, detail: str = "") -> dict:
    return {"name": name, "passed": bool(passed), "detail": detail}


def _called_names(tool_calls: list[dict]) -> list[str]:
    return [c["name"] for c in tool_calls]


# ── Individual checks ─────────────────────────────────────────────────────────

def check_expected_tools(tool_calls, expected) -> dict:
    """Every tool in `expected` must have been called at least once."""
    called = set(_called_names(tool_calls))
    missing = [t for t in expected if t not in called]
    return _check(
        "expected_tools",
        not missing,
        "all expected tools called" if not missing else f"missing: {missing}",
    )


def check_forbidden_tools(tool_calls, forbidden) -> dict:
    """No tool in `forbidden` may have been called."""
    called = set(_called_names(tool_calls))
    hit = [t for t in forbidden if t in called]
    return _check(
        "forbidden_tools",
        not hit,
        "no forbidden tools called" if not hit else f"called forbidden: {hit}",
    )


def check_order(tool_calls, expected) -> dict:
    """`expected` must appear as an ordered subsequence of the actual calls."""
    called = _called_names(tool_calls)
    i = 0
    for name in called:
        if i < len(expected) and name == expected[i]:
            i += 1
    passed = i == len(expected)
    return _check(
        "ordered",
        passed,
        f"call order {called} satisfies {expected}" if passed
        else f"call order {called} does not satisfy {expected}",
    )


def _args_match(actual: dict, expected: dict) -> bool:
    """Every expected key must be present and equal (case-insensitive for strings)."""
    for key, exp in expected.items():
        if key not in actual:
            return False
        act = actual[key]
        if isinstance(exp, str) and isinstance(act, str):
            if exp.strip().lower() != act.strip().lower():
                return False
        elif act != exp:
            return False
    return True


def check_expected_args(tool_calls, expected_args) -> dict:
    """
    For each tool -> expected arg subset, at least one call to that tool
    must have matching arguments.
    """
    failures = []
    for tool_name, exp in expected_args.items():
        calls = [c["input"] for c in tool_calls if c["name"] == tool_name]
        if not any(_args_match(inp or {}, exp) for inp in calls):
            failures.append(f"{tool_name} never called with {exp} (saw {calls})")
    return _check(
        "expected_args",
        not failures,
        "args matched" if not failures else "; ".join(failures),
    )


def check_contains(response, substrings) -> dict:
    """All substrings must be present (case-insensitive)."""
    low = (response or "").lower()
    missing = [s for s in substrings if s.lower() not in low]
    return _check(
        "response_must_contain",
        not missing,
        "all substrings present" if not missing else f"missing: {missing}",
    )


def check_not_contains(response, substrings) -> dict:
    """No substring may be present (case-insensitive)."""
    low = (response or "").lower()
    hit = [s for s in substrings if s.lower() in low]
    return _check(
        "response_must_not_contain",
        not hit,
        "no forbidden substrings" if not hit else f"found: {hit}",
    )


# ── DB assertions ─────────────────────────────────────────────────────────────

def _order_status(db_path: str, order_id: str):
    # sqlite3's context manager commits but does not close the connection, which
    # leaves the file locked on Windows; close it explicitly.
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT status FROM orders WHERE id = ?", (order_id,)).fetchone()
    finally:
        conn.close()
    return row[0] if row else None


def _escalation_count(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT COUNT(*) FROM escalations").fetchone()[0]
    finally:
        conn.close()


def check_db_assertions(db_path, assertions) -> dict:
    """
    Supported assertion types:
      {"type": "order_status", "order_id": "ORD-1001", "equals": "refunded"}
      {"type": "order_status", "order_id": "ORD-1003", "not_equals": "refunded"}
      {"type": "escalation_created", "expected": true | false}
    """
    failures = []
    for a in assertions:
        kind = a.get("type")
        if kind == "order_status":
            status = _order_status(db_path, a["order_id"])
            if "equals" in a and status != a["equals"]:
                failures.append(f"{a['order_id']} status is {status!r}, expected {a['equals']!r}")
            if "not_equals" in a and status == a["not_equals"]:
                failures.append(f"{a['order_id']} status is {status!r}, should not be {a['not_equals']!r}")
        elif kind == "escalation_created":
            created = _escalation_count(db_path) > 0
            if created != a["expected"]:
                failures.append(f"escalation_created={created}, expected {a['expected']}")
        else:
            failures.append(f"unknown db assertion type: {kind!r}")
    return _check(
        "db_assertions",
        not failures,
        "db state as expected" if not failures else "; ".join(failures),
    )


# ── Aggregate ─────────────────────────────────────────────────────────────────

def grade_run(case: dict, run: dict, db_path: str) -> dict:
    """
    Run every applicable check for a case against one run.
    Returns {"passed": bool, "checks": [Check, ...]}.
    """
    tool_calls = run["tool_calls"]
    response = run["response"]
    checks = []

    if "expected_tools" in case:
        checks.append(check_expected_tools(tool_calls, case["expected_tools"]))
    if "forbidden_tools" in case:
        checks.append(check_forbidden_tools(tool_calls, case["forbidden_tools"]))
    if case.get("ordered") and case.get("expected_tools"):
        checks.append(check_order(tool_calls, case["expected_tools"]))
    if "expected_args" in case:
        checks.append(check_expected_args(tool_calls, case["expected_args"]))
    if "response_must_contain" in case:
        checks.append(check_contains(response, case["response_must_contain"]))
    if "response_must_not_contain" in case:
        checks.append(check_not_contains(response, case["response_must_not_contain"]))
    if "db_assertions" in case:
        checks.append(check_db_assertions(db_path, case["db_assertions"]))

    return {"passed": all(c["passed"] for c in checks), "checks": checks}


def failed_reasons(grade: dict) -> str:
    """One-line summary of the failing checks, for console output."""
    fails = [f"{c['name']}: {c['detail']}" for c in grade["checks"] if not c["passed"]]
    return " | ".join(fails) if fails else ""
