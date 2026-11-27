
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




def get_code_neighbors(target: str, max_results: int = 20):
    """
    Find Python files that directly import the target file, or are
    directly imported by it.

    This is a local AST-based approximation of the competition's
    code-neighbor tool. It does not perform semantic or call-graph analysis.
    """
    import ast

    try:
        target_path = _safe_path(target)
    except Exception as exc:
        return {"error": str(exc)}

    if not target_path.exists():
        return {"error": f"File not found: {target}"}

    if not target_path.is_file() or target_path.suffix.lower() != ".py":
        return {"error": "target must be an existing Python file."}

    excluded_dirs = {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        "wheelhouse",
        "_snapshot_git_check",
        "node_modules",
    }

    python_files = []
    module_to_path = {}

    for path in PROJECT_ROOT.rglob("*.py"):
        relative_parts = path.relative_to(PROJECT_ROOT).parts

        if any(part in excluded_dirs for part in relative_parts):
            continue

        try:
            if path.stat().st_size > 1_000_000:
                continue
        except OSError:
            continue

        python_files.append(path)

        parts = list(relative_parts)

        if parts[-1] == "__init__.py":
            module_parts = parts[:-1]
        else:
            module_parts = parts[:-1] + [path.stem]

        module_name = ".".join(module_parts)

        if module_name:
            module_to_path[module_name] = path

        # Also support direct imports when a script is run from its
        # own directory, such as: from local_tools import read_file
        module_to_path.setdefault(path.stem, path)

    if target_path not in python_files:
        return {"error": "Target is excluded or could not be indexed."}

    def resolve_module(module_name):
        """Resolve a module name to the longest matching project file."""
        if not module_name:
            return None

        parts = module_name.split(".")

        for index in range(len(parts), 0, -1):
            candidate = ".".join(parts[:index])
            resolved = module_to_path.get(candidate)

            if resolved is not None:
                return resolved

        return None

    imports_by_file = {path: set() for path in python_files}
    parse_errors = []

    for path in python_files:
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except (OSError, UnicodeError, SyntaxError) as exc:
            parse_errors.append({
                "path": str(path.relative_to(PROJECT_ROOT)),
                "error": str(exc),
            })
            continue

        relative_parts = path.relative_to(PROJECT_ROOT).parts

        if relative_parts[-1] == "__init__.py":
            current_module = ".".join(relative_parts[:-1])
        else:
            current_module = ".".join(
                relative_parts[:-1] + (path.stem,)
            )

        current_package = (
            current_module
            if relative_parts[-1] == "__init__.py"
            else current_module.rpartition(".")[0]
        )

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    dependency = resolve_module(alias.name)

                    if dependency is not None and dependency != path:
                        imports_by_file[path].add(dependency)

            elif isinstance(node, ast.ImportFrom):
                base_module = node.module or ""

                if node.level > 0:
                    package_parts = (
                        current_package.split(".")
                        if current_package
                        else []
                    )

                    trim_count = node.level - 1

                    if trim_count:
                        package_parts = package_parts[:-trim_count]

                    if base_module:
                        package_parts.extend(base_module.split("."))

                    base_module = ".".join(package_parts)

                if base_module:
                    dependency = resolve_module(base_module)

                    if dependency is not None and dependency != path:
                        imports_by_file[path].add(dependency)

                for alias in node.names:
                    if alias.name == "*":
                        continue

                    candidate = (
                        f"{base_module}.{alias.name}"
                        if base_module
                        else alias.name
                    )

                    dependency = resolve_module(candidate)

                    if dependency is not None and dependency != path:
                        imports_by_file[path].add(dependency)

    imported_by = {path: set() for path in python_files}

    for source_file, dependencies in imports_by_file.items():
        for dependency in dependencies:
            imported_by[dependency].add(source_file)

    target_imports = sorted(
        str(path.relative_to(PROJECT_ROOT))
        for path in imports_by_file[target_path]
    )

    target_imported_by = sorted(
        str(path.relative_to(PROJECT_ROOT))
        for path in imported_by[target_path]
    )

    try:
        limit = max(1, min(int(max_results), 100))
    except (TypeError, ValueError):
        limit = 20

    return {
        "target": str(target_path.relative_to(PROJECT_ROOT)),
        "imports": target_imports[:limit],
        "imported_by": target_imported_by[:limit],
        "import_count": len(target_imports),
        "imported_by_count": len(target_imported_by),
        "truncated": (
            len(target_imports) > limit
            or len(target_imported_by) > limit
        ),
        "parse_errors": parse_errors[:10],
        "note": (
            "Direct Python import relationships only. "
            "This does not identify every function call, runtime dependency, "
            "or semantic relationship."
        ),
    }


def get_code_subgraph(
    target: str,
    max_depth: int = 2,
    max_nodes: int = 50,
) -> dict:
    """
    Build a directed Python import subgraph starting from a target file.

    Each edge represents an import relationship:
        source -> target

    Traversal follows imports made by each discovered file.
    This is an AST-based approximation, not a complete semantic graph.
    """
    from collections import deque
    from pathlib import Path

    try:
        max_depth = int(max_depth)
        max_nodes = int(max_nodes)
    except (TypeError, ValueError):
        return {
            "success": False,
            "error": "max_depth and max_nodes must be integers.",
        }

    if not 0 <= max_depth <= 5:
        return {
            "success": False,
            "error": "max_depth must be between 0 and 5.",
        }

    if not 1 <= max_nodes <= 100:
        return {
            "success": False,
            "error": "max_nodes must be between 1 and 100.",
        }

    # Validate and resolve the starting file using the existing tool.
    initial_result = get_code_neighbors(target, max_results=100)

    if "error" in initial_result:
        return {
            "success": False,
            "error": initial_result["error"],
        }

    root = str(Path(initial_result["target"]))

    # Each queue entry contains a project-relative file path and its depth.
    queue = deque([(root, 0)])

    nodes = {root}
    edges = set()
    visited = set()
    analysis_errors = []
    truncated = False

    while queue:
        current_file, current_depth = queue.popleft()

        if current_file in visited:
            continue

        visited.add(current_file)

        if current_depth >= max_depth:
            continue

        result = get_code_neighbors(
            current_file,
            max_results=100,
        )

        if "error" in result:
            analysis_errors.append({
                "file": current_file,
                "error": result["error"],
            })
            continue

        # Preserve parsing errors reported by the neighbor analyzer.
        for parse_error in result.get("parse_errors", []):
            analysis_errors.append(parse_error)

        # Follow outgoing imports only.
        for imported_file in result.get("imports", []):
            dependency = str(Path(imported_file))

            edge = (current_file, dependency)

            # Do not duplicate graph edges.
            if edge in edges:
                continue

            if dependency not in nodes:
                if len(nodes) >= max_nodes:
                    truncated = True
                    continue

                nodes.add(dependency)

                queue.append((
                    dependency,
                    current_depth + 1,
                ))

            edges.add(edge)

    return {
        "success": True,
        "root": root,
        "nodes": sorted(nodes),
        "edges": [
            {
                "source": source,
                "target": destination,
                "relationship": "imports",
            }
            for source, destination in sorted(edges)
        ],
        "node_count": len(nodes),
        "edge_count": len(edges),
        "max_depth": max_depth,
        "max_nodes": max_nodes,
        "truncated": truncated,
        "analysis_errors": analysis_errors[:20],
        "note": (
            "Directed Python import subgraph generated using AST-based "
            "analysis. Traversal follows outgoing imports only. It does "
            "not identify all function calls, runtime dependencies, "
            "dynamic imports, or semantic relationships."
        ),
    }

def run_targeted_tests(
    test_paths: list[str],
    timeout_seconds: int = 120,
) -> dict:
    """
    Run explicitly selected pytest files inside the repository tests directory.

    This tool does not execute arbitrary shell commands or modify source files.
    """
    import re
    import subprocess
    import sys
    import time

    MAX_TIMEOUT = 120
    MAX_TEST_FILES = 10
    OUTPUT_LIMIT = 12000

    if not isinstance(test_paths, list) or not test_paths:
        return {
            "success": False,
            "status": "error",
            "error": "Provide a non-empty list of test file paths.",
        }

    if len(test_paths) > MAX_TEST_FILES:
        return {
            "success": False,
            "status": "error",
            "error": f"At most {MAX_TEST_FILES} test files may be selected.",
        }

    try:
        timeout_seconds = int(timeout_seconds)
    except (TypeError, ValueError):
        return {
            "success": False,
            "status": "error",
            "error": "timeout_seconds must be an integer.",
        }

    if not 1 <= timeout_seconds <= MAX_TIMEOUT:
        return {
            "success": False,
            "status": "error",
            "error": f"timeout_seconds must be between 1 and {MAX_TIMEOUT}.",
        }

    tests_root = (PROJECT_ROOT / "tests").resolve()
    validated_paths = []

    for target in test_paths:
        if not isinstance(target, str) or not target.strip():
            return {
                "success": False,
                "status": "error",
                "error": "Every test path must be a non-empty string.",
            }

        try:
            path = _safe_path(target)
            path.relative_to(tests_root)
        except (OSError, ValueError, PermissionError):
            return {
                "success": False,
                "status": "error",
                "error": f"Test path must be inside tests/: {target}",
            }

        if not path.is_file() or path.suffix.lower() != ".py":
            return {
                "success": False,
                "status": "error",
                "error": f"Test path must be an existing Python file: {target}",
            }

        validated_paths.append(
            path.relative_to(PROJECT_ROOT).as_posix()
        )

    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "--disable-warnings",
        "--no-header",
        *validated_paths,
    ]

    started = time.monotonic()

    try:
        result = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout_seconds,
            check=False,
            shell=False,
        )

        duration = round(time.monotonic() - started, 3)
        stdout = result.stdout or ""
        stderr = result.stderr or ""

        combined_output = stdout + "\n" + stderr

        counts = {
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "skipped": 0,
            "xfailed": 0,
            "xpassed": 0,
            "deselected": 0,
        }

        for match in re.finditer(
            r"(\d+)\s+(passed|failed|errors?|skipped|xfailed|xpassed|deselected)",
            combined_output,
            flags=re.IGNORECASE,
        ):
            count = int(match.group(1))
            label = match.group(2).lower()

            if label in ("error", "errors"):
                label = "errors"

            if label in counts:
                counts[label] += count

        if result.returncode == 0:
            status = "passed"
        else:
            status = "failed"

        stdout_truncated = len(stdout) > OUTPUT_LIMIT
        stderr_truncated = len(stderr) > OUTPUT_LIMIT

        return {
            "success": True,
            "status": status,
            "exit_code": result.returncode,
            "test_paths": validated_paths,
            "duration_seconds": duration,
            "timeout_seconds": timeout_seconds,
            "counts": counts,
            "stdout": stdout[:OUTPUT_LIMIT],
            "stderr": stderr[:OUTPUT_LIMIT],
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
            "command": command,
        }

    except subprocess.TimeoutExpired as exc:
        duration = round(time.monotonic() - started, 3)

        def decode_output(value):
            if isinstance(value, bytes):
                return value.decode("utf-8", errors="replace")
            return value or ""

        stdout = decode_output(exc.stdout)
        stderr = decode_output(exc.stderr)

        return {
            "success": False,
            "status": "timeout",
            "exit_code": None,
            "test_paths": validated_paths,
            "duration_seconds": duration,
            "timeout_seconds": timeout_seconds,
            "stdout": stdout[:OUTPUT_LIMIT],
            "stderr": stderr[:OUTPUT_LIMIT],
            "stdout_truncated": len(stdout) > OUTPUT_LIMIT,
            "stderr_truncated": len(stderr) > OUTPUT_LIMIT,
            "error": "Test execution exceeded the configured timeout.",
        }

    except OSError as exc:
        return {
            "success": False,
            "status": "error",
            "test_paths": validated_paths,
            "error": str(exc),
        }


def verify_patch(patch_text: str, timeout_seconds: float = 30) -> dict:
    """
    Check whether a unified Git diff can be applied.

    This function is strictly read-only: it runs git apply --check
    and never applies, stages, or commits the patch.
    """
    import re
    import time

    MAX_PATCH_SIZE = 256_000
    OUTPUT_LIMIT = 12_000
    MAX_TIMEOUT_SECONDS = 30

    try:
        timeout_seconds = float(timeout_seconds)
    except (TypeError, ValueError):
        return {
            "success": False,
            "status": "error",
            "error": "timeout_seconds must be a number between 0 and 30.",
        }

    if not 0 < timeout_seconds <= MAX_TIMEOUT_SECONDS:
        return {
            "success": False,
            "status": "error",
            "error": "timeout_seconds must be greater than 0 and at most 30.",
        }

    if not isinstance(patch_text, str) or not patch_text.strip():
        return {
            "success": False,
            "status": "error",
            "error": "patch_text must be a non-empty string.",
        }

    if len(patch_text.encode("utf-8")) > MAX_PATCH_SIZE:
        return {
            "success": False,
            "status": "error",
            "error": f"Patch exceeds the {MAX_PATCH_SIZE}-byte limit.",
        }

    if "GIT binary patch" in patch_text or "Binary files " in patch_text:
        return {
            "success": False,
            "status": "error",
            "error": "Binary patches are not supported.",
        }

    def validate_path(raw_path: str) -> None:
        """Accept only safe, repository-relative Git paths."""
        from pathlib import PurePosixPath

        if (
            not raw_path
            or raw_path.startswith("/")
            or "\\" in raw_path
            or ":" in raw_path
            or '"' in raw_path
        ):
            raise ValueError(f"Unsupported or unsafe patch path: {raw_path}")

        parts = raw_path.split("/")

        if any(part in ("", ".", "..") for part in parts):
            raise ValueError(f"Unsafe patch path: {raw_path}")

        if any(part.lower() == ".git" for part in parts):
            raise ValueError("Patches targeting the .git directory are denied.")

        normalized = str(PurePosixPath(raw_path))
        _safe_path(normalized)

    diff_headers = 0

    try:
        for line in patch_text.splitlines():
            if line.startswith("diff --git "):
                match = re.fullmatch(
                    r"diff --git a/([^ \t]+) b/([^ \t]+)",
                    line,
                )

                if not match:
                    raise ValueError(
                        "Unsupported diff header. Paths must be "
                        "unquoted and contain no whitespace."
                    )

                validate_path(match.group(1))
                validate_path(match.group(2))
                diff_headers += 1

            elif line.startswith("--- ") or line.startswith("+++ "):
                raw_path = line[4:].split("\t", 1)[0]

                if raw_path == "/dev/null":
                    continue

                if raw_path.startswith(("a/", "b/")):
                    validate_path(raw_path[2:])
                else:
                    raise ValueError(
                        f"Unsupported unified-diff file header: {line}"
                    )

            elif line.startswith(("rename from ", "rename to ",
                                  "copy from ", "copy to ")):
                raw_path = line.split(" ", 2)[2]
                validate_path(raw_path)

        if diff_headers == 0:
            raise ValueError(
                "No supported 'diff --git' header was found."
            )

    except (ValueError, PermissionError, OSError) as exc:
        return {
            "success": False,
            "status": "error",
            "error": str(exc),
        }

    command = ["git", "apply", "--check", "--verbose"]
    started = time.monotonic()

    try:
        result = subprocess.run(
            command,
            input=patch_text,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout_seconds,
            check=False,
            shell=False,
        )

        stdout = result.stdout or ""
        stderr = result.stderr or ""

        return {
            "success": True,
            "status": (
                "applicable" if result.returncode == 0 else "rejected"
            ),
            "exit_code": result.returncode,
            "duration_seconds": round(time.monotonic() - started, 3),
            "timeout_seconds": timeout_seconds,
            "stdout": stdout[:OUTPUT_LIMIT],
            "stderr": stderr[:OUTPUT_LIMIT],
            "stdout_truncated": len(stdout) > OUTPUT_LIMIT,
            "stderr_truncated": len(stderr) > OUTPUT_LIMIT,
            "command": command,
            "read_only": True,
        }

    except subprocess.TimeoutExpired as exc:
        def decode_output(value):
            if isinstance(value, bytes):
                return value.decode("utf-8", errors="replace")
            return value or ""

        stdout = decode_output(exc.stdout)
        stderr = decode_output(exc.stderr)

        return {
            "success": False,
            "status": "timeout",
            "exit_code": None,
            "duration_seconds": round(time.monotonic() - started, 3),
            "timeout_seconds": timeout_seconds,
            "stdout": stdout[:OUTPUT_LIMIT],
            "stderr": stderr[:OUTPUT_LIMIT],
            "error": "Patch verification exceeded the configured timeout.",
        }

    except OSError as exc:
        return {
            "success": False,
            "status": "error",
            "error": str(exc),
        }
