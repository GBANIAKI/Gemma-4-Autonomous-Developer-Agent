import subprocess

from local_dev import local_tools


def test_targeted_tests_success(monkeypatch):
    def fake_run(command, **kwargs):
        assert command[0]
        assert command[1:4] == [
            "-m", "pytest", "-q"
        ]
        assert kwargs["shell"] is False
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="3 passed in 0.10s\n",
            stderr="",
        )

    monkeypatch.setattr(local_tools.subprocess, "run", fake_run)

    result = local_tools.run_targeted_tests(
        ["tests/test_repository_graph.py"]
    )

    assert result["success"] is True
    assert result["status"] == "passed"
    assert result["exit_code"] == 0
    assert result["counts"]["passed"] == 3


def test_reject_path_outside_tests():
    result = local_tools.run_targeted_tests(
        ["local_dev/local_agent.py"]
    )

    assert result["success"] is False
    assert result["status"] == "error"


def test_reject_nonexistent_test_file():
    result = local_tools.run_targeted_tests(
        ["tests/test_missing.py"]
    )

    assert result["success"] is False
    assert result["status"] == "error"


def test_reject_excessive_timeout():
    result = local_tools.run_targeted_tests(
        ["tests/test_repository_graph.py"],
        timeout_seconds=500,
    )

    assert result["success"] is False
    assert "between 1 and 300" in result["error"]


def test_timeout_returns_structured_failure(monkeypatch):
    def fake_run(command, **kwargs):
        raise subprocess.TimeoutExpired(
            command,
            timeout=1,
            output="partial output",
            stderr="",
        )

    monkeypatch.setattr(local_tools.subprocess, "run", fake_run)

    result = local_tools.run_targeted_tests(
        ["tests/test_repository_graph.py"],
        timeout_seconds=1,
    )

    assert result["success"] is False
    assert result["status"] == "timeout"
    assert result["exit_code"] is None
    assert result["stdout"] == "partial output"
