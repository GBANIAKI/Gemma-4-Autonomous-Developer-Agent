from types import SimpleNamespace

import pytest

from local_dev import local_agent


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

    monkeypatch.setattr(
        local_agent,
        "generate_with_retry",
        fake_generate_with_retry,
    )
    monkeypatch.setattr(
        local_agent,
        "execute_tool",
        lambda name, arguments: {
            "success": True,
            "status": "clean",
        },
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
