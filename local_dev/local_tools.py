
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
