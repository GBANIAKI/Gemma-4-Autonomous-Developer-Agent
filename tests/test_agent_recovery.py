from types import SimpleNamespace

import pytest

from local_dev import local_agent
from local_dev.execution_budget import ExecutionBudget


class FakeServerError(Exception):
    def __init__(self, message, code):
        super().__init__(message)
        self.code = code


class FakeClientError(Exception):
    def __init__(self, message, code):
        super().__init__(message)
        self.code = code


def install_fake_errors(monkeypatch):
    monkeypatch.setattr(
        local_agent.errors, "ServerError", FakeServerError
    )
    monkeypatch.setattr(
        local_agent.errors, "ClientError", FakeClientError
    )


def test_retry_uses_configured_delays(monkeypatch):
    install_fake_errors(monkeypatch)

    attempts = []
    delays = []

    def fake_generate(**kwargs):
        attempts.append(kwargs)
        if len(attempts) < 3:
            raise FakeServerError("Temporary failure", 503)
        return "success"

    fake_client = SimpleNamespace(
        models=SimpleNamespace(generate_content=fake_generate)
    )

    monkeypatch.setattr(local_agent, "get_client", lambda: fake_client)
    monkeypatch.setattr(local_agent.time, "sleep", delays.append)

    result = local_agent.generate_with_retry(model="test-model")

    assert result == "success"
    assert len(attempts) == 3
    assert delays == [5, 15]


def test_retry_exhaustion_uses_all_delays(monkeypatch):
    install_fake_errors(monkeypatch)

    attempts = []
    delays = []

    def fake_generate(**kwargs):
        attempts.append(kwargs)
        raise FakeServerError("Service unavailable", 503)

    fake_client = SimpleNamespace(
        models=SimpleNamespace(generate_content=fake_generate)
    )

    monkeypatch.setattr(local_agent, "get_client", lambda: fake_client)
    monkeypatch.setattr(local_agent.time, "sleep", delays.append)

    with pytest.raises(FakeServerError):
        local_agent.generate_with_retry(model="test-model")

    assert len(attempts) == 4
    assert delays == [5, 15, 30]


def test_non_retryable_api_error_is_not_retried(monkeypatch):
    install_fake_errors(monkeypatch)

    attempts = []
    delays = []

    def fake_generate(**kwargs):
        attempts.append(kwargs)
        raise FakeClientError("Bad request", 400)

    fake_client = SimpleNamespace(
        models=SimpleNamespace(generate_content=fake_generate)
    )

    monkeypatch.setattr(local_agent, "get_client", lambda: fake_client)
    monkeypatch.setattr(local_agent.time, "sleep", delays.append)

    with pytest.raises(FakeClientError):
        local_agent.generate_with_retry(model="test-model")

    assert len(attempts) == 1
    assert delays == []


def test_run_agent_preserves_evidence_after_api_failure(monkeypatch):
    install_fake_errors(monkeypatch)

    response = SimpleNamespace(
        candidates=[SimpleNamespace(content=None)],
        function_calls=[
            SimpleNamespace(name="get_status", args={})
        ],
        text=None,
    )

    calls = []

    def fake_generate_with_retry(**kwargs):
        calls.append(kwargs)

        if len(calls) == 1:
            return response

        raise FakeServerError("Service unavailable", 503)

    def fake_execute_tool(name, arguments, budget=None):
        if budget is not None:
            reserved = budget.reserve("exploratory")
            assert reserved is True

        return {
            "success": True,
            "status": "clean",
        }

    monkeypatch.setattr(
        local_agent,
        "generate_with_retry",
        fake_generate_with_retry,
    )

    monkeypatch.setattr(
        local_agent,
        "execute_tool",
        fake_execute_tool,
    )

    result = local_agent.run_agent("Inspect repository status")

    assert result["status"] == "incomplete"
    assert result["completion_reason"] == "api_retry_exhausted"
    assert result["investigation_status"] == "incomplete"
    assert result["tool_call_count"] == 1
    assert len(result["evidence_records"]) == 1
    assert result["evidence_records"][0]["evidence_id"] == "M001"
    assert result["api_error"]["status_code"] == 503
    assert "preserved" in result["answer"]

    assert result["budget"]["total_calls"] == 1
    assert result["budget"]["exploratory_calls"] == 1

def test_exploratory_exhaustion_preserves_verification_capacity(monkeypatch):
    budget = ExecutionBudget(
        max_total_calls=2,
        max_exploratory_calls=0,
        max_verification_calls=2,
    )

    monkeypatch.setitem(
        local_agent.FUNCTIONS,
        "get_status",
        lambda: {"success": True},
    )

    exploratory_result = local_agent.execute_tool(
        "get_status",
        {},
        budget=budget,
    )

    assert exploratory_result["status"] == "category_budget_exhausted"
    assert budget.snapshot()["total_calls"] == 0

    monkeypatch.setitem(
        local_agent.FUNCTIONS,
        "verify_patch",
        lambda patch_text, timeout_seconds=30: {
            "success": True,
            "timeout_seconds": timeout_seconds,
        },
    )

    verification_result = local_agent.execute_tool(
        "verify_patch",
        {"patch_text": "test patch"},
        budget=budget,
    )

    assert verification_result["success"] is True
    assert budget.snapshot()["verification_calls"] == 1

@pytest.mark.parametrize("timeout_seconds", [0, 0.5])
def test_invalid_test_timeout_does_not_consume_verification_budget(monkeypatch, timeout_seconds):
    budget = ExecutionBudget(
        max_total_calls=2,
        max_exploratory_calls=0,
        max_verification_calls=2,
    )

    def unexpected_test_execution(**kwargs):
        pytest.fail("Targeted tests should not execute with an invalid timeout.")

    monkeypatch.setitem(
        local_agent.FUNCTIONS,
        "run_targeted_tests",
        unexpected_test_execution,
    )

    result = local_agent.execute_tool(
        "run_targeted_tests",
        {
            "test_paths": ["tests/test_agent_recovery.py"],
            "timeout_seconds": timeout_seconds,
        },
        budget=budget,
    )

    assert result["success"] is False
    assert result["status"] == "error"
    assert "at least one second" in result["error"]
    assert budget.snapshot()["total_calls"] == 0
    assert budget.snapshot()["verification_calls"] == 0


def test_run_agent_can_dispatch_more_than_six_tools(monkeypatch):
    budget = ExecutionBudget(
        max_total_calls=8,
        max_exploratory_calls=8,
        max_verification_calls=0,
    )
    generated_responses = []

    for _ in range(7):
        generated_responses.append(SimpleNamespace(
            candidates=[SimpleNamespace(content=None)],
            function_calls=[SimpleNamespace(name="get_status", args={})],
            text=None,
        ))

    generated_responses.append(SimpleNamespace(
        candidates=[SimpleNamespace(content=None)],
        function_calls=[],
        text="Investigation completed.",
    ))

    def fake_generate_with_retry(**kwargs):
        return generated_responses.pop(0)

    def fake_execute_tool(name, arguments, budget=None):
        assert name == "get_status"
        assert budget.reserve("exploratory") is True
        return {"success": True, "status": "clean"}

    monkeypatch.setattr(
        local_agent, "generate_with_retry", fake_generate_with_retry
    )
    monkeypatch.setattr(
        local_agent, "execute_tool", fake_execute_tool
    )

    result = local_agent.run_agent("Inspect repository status", budget=budget)

    assert result["status"] == "completed"
    assert result["tool_call_count"] == 7
    assert result["budget"]["total_calls"] == 7
    assert len(result["evidence_records"]) == 7
    assert result["answer"] == "Investigation completed."
