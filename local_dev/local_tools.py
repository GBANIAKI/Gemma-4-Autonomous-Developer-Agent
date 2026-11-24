
from pathlib import Path
import subprocess

# Project root: parent directory of local_dev/
PROJECT_ROOT = Path(__file__).resolve().parent.parent

IGNORED_DIRECTORIES = {
    ".git",
    ".venv",
    "__pycache__",
    "wheelhouse",
    "_snapshot_git_check",
}

SEARCHABLE_EXTENSIONS = {
    ".py", ".md", ".yaml", ".yml",
    ".json", ".toml", ".txt"
}


def _safe_path(target: str) -> Path:
    """Resolve a path and prevent access outside the project."""
    candidate = Path(target)

    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate

    resolved = candidate.resolve()

    if not resolved.is_relative_to(PROJECT_ROOT):
        raise PermissionError("Access outside the project directory is denied.")

    return resolved


def get_status() -> dict:
    """Return the current Git working-tree status."""
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

        if result.returncode != 0:
            return {
                "success": False,
                "error": result.stderr.strip(),
            }

        return {
            "success": True,
            "project_root": str(PROJECT_ROOT),
            "git_status": result.stdout.strip() or "Working tree clean",
        }

    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"success": False, "error": str(exc)}


def read_file(target: str) -> dict:
    """Read a project file with line and character limits."""
    try:
        path = _safe_path(target)

        if not path.is_file():
            return {
                "success": False,
                "error": "File does not exist.",
            }

        if path.stat().st_size > 1_000_000:
            return {
                "success": False,
                "error": "File exceeds the 1 MB read limit.",
            }

        content = path.read_text(
            encoding="utf-8",
            errors="replace"
        )

        lines = content.splitlines()
        selected = lines[:150]
        output = "\n".join(selected)[:10000]

        return {
            "success": True,
            "file": str(path.relative_to(PROJECT_ROOT)),
            "content": output,
            "total_lines": len(lines),
            "truncated": (
                len(lines) > 150 or len("\n".join(selected)) > 10000
            ),
        }

    except (OSError, PermissionError, ValueError) as exc:
        return {"success": False, "error": str(exc)}


def search_similar_code(
    query: str,
    max_results: int = 10
) -> dict:
    """
    Search project text files for case-insensitive literal matches.

    This is lexical search, not embedding-based semantic search.
    """
    if not query or not query.strip():
        return {"success": False, "error": "Search query is empty."}

    max_results = max(1, min(int(max_results), 20))
    needle = query.casefold()
    results = []

    try:
        for path in PROJECT_ROOT.rglob("*"):
            if not path.is_file():
                continue

            relative = path.relative_to(PROJECT_ROOT)

            if any(part in IGNORED_DIRECTORIES for part in relative.parts):
                continue

            if path.suffix.lower() not in SEARCHABLE_EXTENSIONS:
                continue

            try:
                if path.stat().st_size > 1_000_000:
                    continue

                lines = path.read_text(
                    encoding="utf-8",
                    errors="replace"
                ).splitlines()

            except (OSError, UnicodeError):
                continue

            for line_number, line in enumerate(lines, start=1):
                if needle in line.casefold():
                    results.append({
                        "file": str(relative),
                        "line": line_number,
                        "text": line.strip()[:500],
                    })

                    if len(results) >= max_results:
                        return {
                            "success": True,
                            "query": query,
                            "results": results,
                            "result_limit_reached": True,
                        }

        return {
            "success": True,
            "query": query,
            "results": results,
            "result_limit_reached": False,
        }

    except (OSError, ValueError) as exc:
        return {"success": False, "error": str(exc)}
