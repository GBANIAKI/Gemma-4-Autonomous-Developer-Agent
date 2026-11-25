import subprocess

from local_dev import local_tools


VALID_PATCH = """\
diff --git a/example.py b/example.py
index 1111111..2222222 100644
--- a/example.py
+++ b/example.py
@@ -1 +1 @@
-print("old")
+print("new")
"""


def test_verify_patch_applicable(monkeypatch):
    def fake_run(command, **kwargs):
        assert command == [
            "git", "apply", "--check", "--verbose"
        ]
        assert kwargs["input"] == VALID_PATCH
        assert kwargs["shell"] is False
        assert kwargs["check"] is False
        return subprocess.CompletedProcess(
            command, 0, stdout="",
            stderr="Checking patch example.py...\n",
        )

    monkeypatch.setattr(local_tools.subprocess, "run", fake_run)

    result = local_tools.verify_patch(VALID_PATCH)

    assert result["success"] is True
    assert result["status"] == "applicable"
    assert result["exit_code"] == 0
    assert result["read_only"] is True


def test_verify_patch_rejected(monkeypatch):
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(
            command, 1, stdout="",
            stderr="error: patch failed\n",
        )

    monkeypatch.setattr(local_tools.subprocess, "run", fake_run)

    result = local_tools.verify_patch(VALID_PATCH)

    assert result["success"] is True
    assert result["status"] == "rejected"
    assert result["exit_code"] == 1


def test_reject_empty_patch():
    result = local_tools.verify_patch("")

    assert result["success"] is False
    assert result["status"] == "error"


def test_reject_patch_without_diff_header():
    result = local_tools.verify_patch(
        "--- a/example.py\n+++ b/example.py\n"
    )

    assert result["success"] is False
    assert result["status"] == "error"


def test_reject_path_traversal():
    patch = VALID_PATCH.replace(
        "a/example.py b/example.py",
        "a/../outside.py b/../outside.py",
    )

    result = local_tools.verify_patch(patch)

    assert result["success"] is False
    assert result["status"] == "error"


def test_reject_git_metadata_path():
    patch = VALID_PATCH.replace(
        "a/example.py b/example.py",
        "a/.git/config b/.git/config",
    )

    result = local_tools.verify_patch(patch)

    assert result["success"] is False
    assert result["status"] == "error"


def test_reject_oversized_patch():
    patch = VALID_PATCH + (" " * 256_001)

    result = local_tools.verify_patch(patch)

    assert result["success"] is False
    assert result["status"] == "error"
    assert "limit" in result["error"]


def test_timeout_returns_structured_failure(monkeypatch):
    def fake_run(command, **kwargs):
        raise subprocess.TimeoutExpired(
            command,
            timeout=30,
            output="partial output",
            stderr="",
        )

    monkeypatch.setattr(local_tools.subprocess, "run", fake_run)

    result = local_tools.verify_patch(VALID_PATCH)

    assert result["success"] is False
    assert result["status"] == "timeout"
    assert result["exit_code"] is None
    assert result["stdout"] == "partial output"


def test_os_error_returns_structured_failure(monkeypatch):
    def fake_run(command, **kwargs):
        raise OSError("git executable unavailable")

    monkeypatch.setattr(local_tools.subprocess, "run", fake_run)

    result = local_tools.verify_patch(VALID_PATCH)

    assert result["success"] is False
    assert result["status"] == "error"
    assert "git executable unavailable" in result["error"]
